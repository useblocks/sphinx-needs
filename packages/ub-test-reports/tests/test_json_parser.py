"""The JSON parser, called directly: parse, the mapping, result normalisation, errors.

There is no standard JSON test report, so the parser reads whatever ``tr_json_mapping``
(or the converter's equivalent) declares: each output key maps to a path into the report
and a default. These tests drive it over the three JSON fixtures -- flat, nested paths, and
custom fields -- without Sphinx; the extension's own suite covers the same reports through a
build.
"""

import builtins
import json
from pathlib import Path

import pytest

from ub_test_reports.jsonparser import JsonFileMissing, JsonParser, dict_get

FIXTURES = Path(__file__).parent / "fixtures"

#: A case's fields as the flat fixture spells them, each read from the key of its name.
CASE_KEYS = [
    "name",
    "classname",
    "file",
    "line",
    "time",
    "result",
    "type",
    "text",
    "message",
    "system-out",
]


def _mapping(suite_name=("name",), testcases=("testcase",), extra=None):
    """A ``tr_json_mapping`` entry: ``key -> (path into the report, default)``."""
    testcase = {key: ([key], "unknown") for key in CASE_KEYS}
    testcase.update(extra or {})
    return {
        "testsuite": {
            "name": (list(suite_name), "unknown"),
            "tests": (["tests"], "unknown"),
            "errors": (["errors"], "unknown"),
            "failures": (["failures"], "unknown"),
            "skips": (["skips"], "unknown"),
            "passed": (["passed"], "unknown"),
            "time": (["time"], "unknown"),
            "testcases": (list(testcases), "unknown"),
        },
        "testcase": testcase,
    }


def _parse(name, mapping):
    parser = JsonParser(FIXTURES / name, json_mapping=mapping)
    assert parser.validate() is True
    return parser.parse()


class TestParse:
    def test_a_flat_report_gives_one_suite_with_its_cases(self):
        (suite,) = _parse("json_data.json", _mapping())
        assert suite["name"] == "test suite 1"
        assert (suite["tests"], suite["failures"], suite["skips"]) == (3, 1, 1)
        assert suite["testsuite_nested"] == []
        assert [case["name"] for case in suite["testcases"]] == [
            "test case 1",
            "test case 2",
            "test case 3",
        ]
        first = suite["testcases"][0]
        assert first["classname"] == "class name 1"
        assert first["line"] == 123
        assert first["message"] == "all went wrong :( (message)"

    def test_nested_paths_reach_into_the_report(self):
        (suite,) = _parse(
            "json_complex_data.json",
            _mapping(
                suite_name=("internals", "name"), testcases=("testcase", "nested")
            ),
        )
        assert suite["name"] == "test suite 1"
        assert [case["classname"] for case in suite["testcases"]] == [
            "class name 1",
            "class name 2",
            "class name 3",
        ]

    def test_custom_fields_take_their_default_where_a_case_lacks_them(self):
        extra = {
            "id": (["id"], None),
            "status": (["status"], "unknown"),
            "tags": (["tags"], "unknown"),
        }
        (suite,) = _parse("json_custom_data.json", _mapping(extra=extra))
        cases = suite["testcases"]
        assert [case["id"] for case in cases] == [
            "TEST_CASE_1",
            "TEST_CASE_2",
            "TEST_CASE_3",
            None,
        ]
        assert cases[0]["tags"] == "a,b,c"
        # present but empty is the report's value, not the default
        assert cases[2]["status"] == ""
        assert cases[3]["status"] == "unknown"

    def test_report_is_read_as_utf8_when_locale_default_is_not(
        self, tmp_path, monkeypatch
    ):
        report = tmp_path / "report.json"
        report.write_text(
            json.dumps(
                [
                    {
                        "name": "utf8 suite",
                        "tests": 1,
                        "errors": 0,
                        "failures": 0,
                        "skips": 0,
                        "passed": 1,
                        "time": 0.01,
                        "testcase": [
                            {
                                "name": "emoji ✅",
                                "classname": "UnicodeTests",
                                "file": "test_unicode.py",
                                "line": 1,
                                "time": 0.01,
                                "result": "passed",
                            }
                        ],
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        real_open = builtins.open

        def locale_defaulting_open(file, mode="r", *args, **kwargs):
            if Path(file) == report and "b" not in mode and "encoding" not in kwargs:
                kwargs["encoding"] = "cp1252"
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", locale_defaulting_open)

        (suite,) = _parse(report, _mapping())

        assert suite["testcases"][0]["name"] == "emoji ✅"


class TestResultNormalisation:
    """The JSON parser's ``result`` is the JUnit parser's vocabulary."""

    def test_each_case_result_is_normalised(self):
        (suite,) = _parse("json_data.json", _mapping())
        # the report spells the first `failure`, after the JUnit element name
        assert [case["result"] for case in suite["testcases"]] == [
            "failed",
            "passed",
            "skipped",
        ]

    def test_a_missing_result_keeps_its_default(self):
        mapping = _mapping(extra={"result": (["no_such_key"], None)})
        (suite,) = _parse("json_data.json", mapping)
        assert [case["result"] for case in suite["testcases"]] == [None, None, None]


class TestErrors:
    def test_a_missing_file_is_named(self, tmp_path):
        missing = tmp_path / "missing.json"
        with pytest.raises(JsonFileMissing, match=r"missing\.json"):
            JsonParser(missing, json_mapping=_mapping())

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b'[{"name": ', " (line 1, column 11): Expecting value"),
            (
                b'[{"name": "caf\xe9"}]',
                " is not valid UTF-8 (invalid continuation byte at byte 14)",
            ),
        ],
        ids=["not-json", "not-utf8"],
    )
    def test_an_unreadable_file_is_a_report_read_error(self, tmp_path, data, expected):
        """#2052: these escaped as ``json.JSONDecodeError`` / ``UnicodeDecodeError`` and
        ended a Sphinx build reading the report through ``test-file``."""
        from ub_test_reports.errors import ReportReadError

        path = tmp_path / "report.json"
        path.write_bytes(data)
        with pytest.raises(ReportReadError) as caught:
            JsonParser(str(path), json_mapping=_mapping())
        assert str(caught.value) == f"{path}{expected}"

    @pytest.mark.parametrize(
        ("data", "kind"), [(b'{"not": "a list"}', "an object"), (b"3", "a number")]
    )
    def test_a_report_that_is_not_a_list_is_a_report_read_error(
        self, tmp_path, data, kind
    ):
        """A top level that is not a list of suites was walked anyway, and every field
        fell back to its default (``int('unknown')`` downstream)."""
        from ub_test_reports.errors import ReportReadError

        path = tmp_path / "report.json"
        path.write_bytes(data)
        with pytest.raises(ReportReadError) as caught:
            JsonParser(str(path), json_mapping=_mapping()).parse()
        assert str(caught.value) == (
            f"{path}: the JSON report is not a list of test suites (got {kind})"
        )

    @pytest.mark.parametrize(
        ("data", "kind"),
        [(b'[1, "x"]', "a number"), (b"[[]]", "an array")],
        ids=["number", "array"],
    )
    def test_a_suite_that_is_not_an_object_is_a_report_read_error(
        self, tmp_path, data, kind
    ):
        """A list whose items are not suites was walked anyway (``int('unknown')``
        downstream) -- fix round 2. An array item is refused too (the loop-ender). An
        EMPTY object item, ``[{}]``, is an object and is read as a suite of defaults --
        it fails downstream, on master too; not this round's (follow-up V2-F4c)."""
        from ub_test_reports.errors import ReportReadError

        path = tmp_path / "report.json"
        path.write_bytes(data)
        with pytest.raises(ReportReadError) as caught:
            JsonParser(str(path), json_mapping=_mapping()).parse()
        assert (
            str(caught.value) == f"{path}: test suite 0 is not an object (got {kind})"
        )

    def test_a_byte_order_mark_is_read_past(self, tmp_path):
        """UTF-8 with or without a BOM, as ``test-env`` reads it (#2141's rule) -- fix
        round 2. Before: ``Unexpected UTF-8 BOM (decode using utf-8-sig)``."""
        plain = FIXTURES / "json_data.json"
        bom = tmp_path / "bom.json"
        bom.write_bytes(b"\xef\xbb\xbf" + plain.read_bytes())

        assert _parse_path(bom) == _parse_path(plain)

    def test_a_missing_file_is_an_ordinary_exception(self, tmp_path):
        """``JsonFileMissing`` derives from ``Exception`` (it was a ``BaseException``,
        which a caller's ``except Exception`` does not catch) (#2052)."""
        assert issubclass(JsonFileMissing, Exception)
        with pytest.raises(Exception, match=r"missing\.json"):
            JsonParser(tmp_path / "missing.json", json_mapping=_mapping())

    @pytest.mark.parametrize(
        ("items", "expected"),
        [
            (["nested", "a_list", 0, "finally"], "target_data"),
            (["nested", "no_such_key"], "default"),  # KeyError
            (["nested", "a_list", 5], "default"),  # IndexError
            (["nested", "a_list", "finally"], "default"),  # TypeError: list["finally"]
        ],
    )
    def test_dict_get_falls_back_to_the_default(self, items, expected):
        data = {"nested": {"a_list": [{"finally": "target_data"}]}}
        assert dict_get(data, items, "default") == expected


def _parse_path(path):
    return JsonParser(str(path), json_mapping=_mapping()).parse()
