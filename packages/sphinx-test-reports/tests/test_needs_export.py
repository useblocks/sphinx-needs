"""Unit tests for the needs.json writer and the URL helpers behind it.

The CLI tests cover the end-to-end shape; these pin down the pieces whose
failure would be silent in that shape -- evidence text mangled but present,
cases lost but the file valid, a URL that looks right and 404s.
"""

import pytest

from sphinxcontrib.test_reports.needs_export import (
    build_content,
    build_need,
    build_needs_file,
)
from sphinxcontrib.test_reports.remote import (
    check_url_pattern,
    normalise_remote_url,
    source_url,
)


def _case(name="test_x", **extra):
    return {"classname": "Suite", "name": name, "file": "t.py", "line": 3, **extra}


class TestEvidenceText:
    def test_relative_indentation_survives(self):
        # A traceback is only readable with its indentation; only the common
        # indentation XML pretty-printing adds may go.
        text = (
            "\n"
            "      Traceback (most recent call last):\n"
            '        File "t.py", line 3, in test_x\n'
            "          assert a == b\n"
            "                 ^^^^^^\n"
            "      AssertionError\n"
            "    "
        )
        content = build_content({"parts": [{"kind": "failure", "text": text}]})
        assert '   Traceback (most recent call last):\n     File "t.py"' in content
        assert "            ^^^^^^\n   AssertionError" in content

    def test_blank_lines_carry_no_trailing_whitespace(self):
        content = build_content({"parts": [{"kind": "failure", "text": "a\n\nb"}]})
        assert "\n   a\n\n   b\n" in content


class TestDuplicateCases:
    def test_a_case_reported_twice_is_refused(self):
        # Its ID is derived from where the test is, so a repeat is the same
        # case twice; collapsing them would silently lose evidence.
        reports = [
            ("a.xml", [{"name": "s", "testcases": [_case(), _case("test_y")]}]),
            ("b.xml", [{"name": "s", "testcases": [_case()]}]),
        ]
        with pytest.raises(ValueError, match="1 test case.*testcase__Suite__test_x"):
            build_needs_file(reports)

    def test_distinct_cases_are_all_kept(self):
        reports = [("a.xml", [{"name": "s", "testcases": [_case(), _case("test_y")]}])]
        payload = build_needs_file(reports)
        assert payload["versions"]["1.0"]["needs_amount"] == 2


class TestPropertyCollisions:
    def test_a_property_named_like_a_builtin_field_is_dropped_and_collected(self):
        collisions = set()
        need = build_need(
            "r.xml",
            "s",
            _case(properties={"result": "tampered", "owner": "me"}),
            extra_options=("result", "owner"),
            collisions=collisions,
        )
        assert need["result"] != "tampered"
        assert need["owner"] == "me"
        assert collisions == {"result"}

    def test_a_listed_name_no_case_carries_is_not_a_collision(self):
        collisions = set()
        build_need(
            "r.xml", "s", _case(), extra_options=("result",), collisions=collisions
        )
        assert collisions == set()

    def test_collisions_are_reported_once_per_run(self):
        # Every other diagnostic fires once per run; so does this one, however
        # many cases carry the property.
        reported = []
        reports = [
            (
                "a.xml",
                [
                    {
                        "name": "s",
                        "testcases": [
                            _case("t1", properties={"result": "x"}),
                            _case("t2", properties={"result": "y", "time": "z"}),
                        ],
                    }
                ],
            ),
        ]
        build_needs_file(
            reports, extra_options=("result", "time"), warn=reported.append
        )
        assert len(reported) == 1
        assert "result" in reported[0] and "time" in reported[0]
        assert "taken by built-in or link fields" in reported[0]

    def test_without_a_collector_the_property_is_still_dropped(self):
        # `file` is the report-path field by default, so a property of that
        # name collides with it and the report path wins.
        need = build_need(
            "r.xml",
            "s",
            _case(properties={"file": "elsewhere.py"}),
            extra_options=("file",),
        )
        assert need["file"] == "r.xml"


class TestNeedShape:
    def test_matches_the_build_s_test_case_need(self):
        need = build_need("reports/r.xml", "suite-1", _case("test_x[a-b]"))
        assert need["suite"] == "suite-1"
        assert need["case"] == "test_x[a-b]"
        assert need["case_name"] == "test_x"
        assert need["case_parameter"] == "a-b"
        assert need["classname"] == "Suite"
        assert need["file"] == "reports/r.xml"
        assert need["case_file"] == "t.py"
        assert need["case_line"] == "3"

    def test_field_names_follow_the_section(self):
        # The names the build's file_option / source_*_option select.
        fields = {
            "file_option": "report_file",
            "source_file_option": "file",
            "source_line_option": "line",
        }
        need = build_need("r.xml", "s", _case(), fields=fields)
        assert need["report_file"] == "r.xml"
        assert need["file"] == "t.py"
        assert need["line"] == "3"
        assert "case_file" not in need


class TestPropertyGate:
    def test_only_named_properties_are_exported(self):
        case = _case(properties={"TestType": "unit", "Owner": "me"})
        need = build_need("r.xml", "s", case, extra_options=("TestType",))
        assert need["TestType"] == "unit"
        assert "Owner" not in need

    @staticmethod
    def _two_cases_with_properties():
        return [
            (
                "a.xml",
                [
                    {
                        "name": "s",
                        "testcases": [
                            _case("t1", properties={"Owner": "me", "Kind": "x"}),
                            _case("t2", properties={"Owner": "you"}),
                        ],
                    }
                ],
            ),
        ]

    def test_left_out_properties_are_reported_once_for_all_names(self):
        # One report naming both -- not one per name, not one per case.
        reported = []
        build_needs_file(self._two_cases_with_properties(), warn=reported.append)
        assert len(reported) == 1
        assert "Owner" in reported[0] and "Kind" in reported[0]
        assert "extra_options" in reported[0]

    def test_exported_properties_are_not_reported(self):
        reported = []
        build_needs_file(
            self._two_cases_with_properties(),
            extra_options=("Kind",),
            warn=reported.append,
        )
        assert len(reported) == 1
        assert "Owner" in reported[0] and "Kind" not in reported[0]

    def test_an_exported_property_absent_from_a_case_is_null(self):
        # The field is always there, so a schema can require it; null is what
        # the build leaves in a registered field a directive did not set.
        need = build_need("r.xml", "s", _case(), extra_options=("TestType",))
        assert "TestType" in need
        assert need["TestType"] is None


class TestRemoteUrls:
    @pytest.mark.parametrize(
        ("remote", "base"),
        [
            (
                "ssh://git@gitlab.example.com:2222/org/repo.git",
                "https://gitlab.example.com/org/repo",
            ),
            ("ssh://git@github.com/org/repo.git", "https://github.com/org/repo"),
            ("git@github.com:org/repo.git", "https://github.com/org/repo"),
            ("https://github.com/org/repo.git/", "https://github.com/org/repo"),
            ("gitlab.example.com/org/repo", "https://gitlab.example.com/org/repo"),
            ("git://github.com/org/repo.git", "https://github.com/org/repo"),
            ("file:///srv/git/repo.git", "file:///srv/git/repo.git"),  # passed through
            # GitLab's CI_REPOSITORY_URL: the job token must not reach the file.
            (
                "https://gitlab-ci-token:glcbt-xyz@gitlab.example.com/org/repo.git",
                "https://gitlab.example.com/org/repo",
            ),
            ("https://user:pass@github.com/org/repo/", "https://github.com/org/repo"),
            ("token@github.com:org/repo.git", "https://github.com/org/repo"),
            # Local paths are passed through -- a drive letter is not a host.
            ("C:\\repos\\repo", "C:\\repos\\repo"),
            ("C:/repos/repo", "C:/repos/repo"),
            ("/srv/git/repo", "/srv/git/repo"),
        ],
    )
    def test_remotes_normalise_to_a_browsable_base(self, remote, base):
        # An ssh port belongs to the ssh endpoint, not the web UI -- and must
        # not be mistaken for the first path segment.
        assert normalise_remote_url(remote) == base

    def test_without_a_line_the_anchor_is_dropped(self):
        assert (
            source_url("https://h/r", "abc", "f.py", "") == "https://h/r/blob/abc/f.py"
        )

    def test_without_a_line_a_fragment_without_the_line_is_kept(self):
        url = source_url(
            "https://h/r", "abc", "f.py", "", "{base}/{file}?ref={commit}#src"
        )
        assert url == "https://h/r/f.py?ref=abc#src"

    def test_without_a_line_a_query_pattern_keeps_its_shape(self):
        url = source_url(
            "https://h/r", "abc", "f.py", "", "{base}/{file}?ref={commit}&line={line}"
        )
        assert url == "https://h/r/f.py?ref=abc&line="


class TestUrlPatternCheck:
    def test_the_default_and_a_custom_pattern_pass(self):
        assert check_url_pattern("{base}/blob/{commit}/{file}#L{line}") is None
        assert check_url_pattern("{base}/-/blob/{commit}/{file}#L{line}") is None

    def test_an_unknown_placeholder_is_named(self):
        problem = check_url_pattern("{base}/blob/{ref}/{file}#L{line}")
        assert problem is not None
        assert "{ref}" in problem
        assert "{commit}" in problem  # the allowed names are listed

    @pytest.mark.parametrize(
        "pattern",
        [
            "{base/blob/{commit}/{file}",
            "{}/{file}",
            "{0}/{file}",
            "{base}}",
            "{line:zz}",
        ],
    )
    def test_a_malformed_template_is_rejected(self, pattern):
        problem = check_url_pattern(pattern)
        assert problem is not None
        assert "malformed" in problem

    @pytest.mark.parametrize(
        "pattern", ["{base.__class__}/{file}", "{base[0]}/{file}", "{base.anything}"]
    )
    def test_an_attribute_or_index_lookup_is_an_unknown_placeholder(self, pattern):
        # str.format would resolve these on the substituted value -- and fail
        # with an AttributeError, not a KeyError, on the first case.
        problem = check_url_pattern(pattern)
        assert problem is not None
        assert "unknown placeholder {base" in problem
        assert "{commit}" in problem


class TestDeclaredSchema:
    """Every field the file uses is declared in the file.

    sphinx-needs writes a ``needs_schema`` into the ``needs.json`` it produces
    and the converter has to do the same, or the type of a field is knowable
    only by loading this extension into a Sphinx build -- which a consumer of
    the artifact (a schema check, S-CORE's tooling, a plain jsonschema
    validator) does not do.
    """

    @staticmethod
    def _declared(**kwargs):
        """The schema block and the needs of a one-case report."""
        reports = [("a.xml", [{"name": "s", "testcases": [_case()]}])]
        payload = build_needs_file(reports, **kwargs)
        version = payload["versions"][payload["current_version"]]
        return version["needs_schema"], version["needs"]

    def test_the_block_is_a_json_schema(self):
        schema, _ = self._declared()
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert schema["type"] == "object"

    def test_no_field_of_a_need_is_undeclared(self):
        schema, needs = self._declared(
            link_properties={"Verifies": "verifies"},
            extra_options=("TestType",),
        )
        written = {key for need in needs.values() for key in need}
        assert written - set(schema["properties"]) == set()

    def test_the_core_fields_are_declared_as_core(self):
        schema, _ = self._declared()
        properties = schema["properties"]
        assert properties["id"]["field_type"] == "core"
        assert properties["tags"]["type"] == "array"
        assert properties["content"]["type"] == "string"

    def test_time_is_declared_as_the_string_it_is(self):
        # Pins today's type. It is the field's declared type in the build too,
        # so the two change together or not at all.
        schema, _ = self._declared()
        assert schema["properties"]["time"]["type"] == ["string", "null"]

    def test_every_declaration_carries_a_description(self):
        # A type alone does not say what a field holds; `case_line` and
        # `result_text` are not self-explanatory.
        schema, _ = self._declared(
            link_properties={"Verifies": "verifies"}, extra_options=("TestType",)
        )
        undescribed = [
            name
            for name, declaration in schema["properties"].items()
            if not declaration.get("description")
        ]
        assert undescribed == []

    def test_renamed_fields_are_declared_under_their_names(self):
        schema, _ = self._declared(
            fields={
                "file_option": "report_file",
                "source_file_option": "file",
                "source_line_option": "line",
            }
        )
        properties = schema["properties"]
        assert properties["report_file"]["description"] == "Test file name"
        assert "line" in properties
        assert "case_file" not in properties
        assert "case_line" not in properties

    def test_a_mapped_link_field_is_declared_as_a_list_of_ids(self):
        schema, _ = self._declared(link_properties={"Verifies": "verifies"})
        assert schema["properties"]["verifies"] == {
            "type": "array",
            "items": {"type": "string"},
            "description": "Link field",
            "field_type": "links",
            "default": [],
        }

    def test_an_extra_option_is_declared_even_when_no_case_carries_it(self):
        # The option is what the build registers, so the file says the field
        # exists; a case without the property carries it as null -- the type
        # the declaration allows for exactly that.
        schema, needs = self._declared(extra_options=("TestType",))
        assert next(iter(needs.values()))["TestType"] is None
        assert schema["properties"]["TestType"]["type"] == ["string", "null"]

    def test_the_counts_of_file_and_suite_needs_are_not_declared(self):
        # The converter writes test-case needs only; declaring `passed` and
        # friends would promise fields the file never carries.
        schema, _ = self._declared()
        assert "passed" not in schema["properties"]
        assert "suites" not in schema["properties"]
