"""The pytest plugin produces the XML shape this extension reads.

Run through ``pytester``: a small test file is executed with the plugin enabled
and the resulting JUnit XML inspected. The property model comes from the
``test_reports_properties`` ini option; S-CORE's is the profile most tests use.
"""

import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from sphinxcontrib.test_reports import pytest_plugin
from sphinxcontrib.test_reports.pytest_plugin import (
    Property,
    apply_test_metadata,
    clean_source_path,
    parse_properties,
    properties_mapping,
)

PLUGIN = "sphinxcontrib.test_reports.pytest_plugin"

#: S-CORE's model, as the docs show it: the profile most of these tests run with.
SCORE_PROFILE = """\
test_reports_properties =
    partially_verifies = PartiallyVerifies, list
    fully_verifies = FullyVerifies, list
    test_type = TestType
    derivation_technique = DerivationTechnique
"""

DECORATED = """
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties

@add_test_properties(
    partially_verifies=["REQ_1", "REQ_2"],
    test_type="requirements-based",
    derivation_technique="requirements-analysis",
    Owner="team-a",
)
def test_addition():
    assert 1 + 1 == 2


def test_plain():
    assert True
"""

RUNTIME = """
import pytest
from sphinxcontrib.test_reports.pytest_plugin import apply_test_metadata

@pytest.mark.parametrize("spec", ["a.rst", "b.rst"])
def test_driven_by_a_file(spec, record_property):
    apply_test_metadata(
        record_property=record_property,
        metadata={"fully_verifies": ["REQ_9"], "test_type": "interface-test"},
        file=f"../_main/specs/{spec}",
        line=7,
    )
    assert spec.endswith(".rst")
"""

RUNTIME_COMPAT = """
from sphinxcontrib.test_reports.pytest_plugin import apply_test_metadata

def test_score_style(record_property, record_xml_attribute):
    apply_test_metadata(
        record_property=record_property,
        metadata={"fully_verifies": ["REQ_9"]},
        record_xml_attribute=record_xml_attribute,
        file="specs/a.rst",
        line=7,
    )
"""

SKIPPED = """
import pytest
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties


@pytest.fixture(scope="module")
def broken():
    raise RuntimeError("no database")


@pytest.mark.skip(reason="not today")
@add_test_properties(partially_verifies=["REQ_1"])
def test_skipped():
    assert False


@pytest.mark.xfail(run=False, reason="never run")
def test_not_run():
    assert False


@add_test_properties(fully_verifies=["REQ_2"])
def test_setup_error(broken):
    assert True


def test_runs():
    assert True
"""

NESTED = """
import pytest
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties


@add_test_properties(partially_verifies=["REQ_1"])
def test_before():
    assert True


def test_inner_session(tmp_path):
    # A project testing its own pytest setup runs an inner session in process.
    inner = tmp_path / "test_inner.py"
    inner.write_text("def test_inner():\\n    assert True\\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\\n")
    assert pytest.main(["-q", "-p", "no:cacheprovider", "-p", "PLUGIN", str(inner)]) == 0


@add_test_properties(partially_verifies=["REQ_2"])
def test_after():
    assert True
""".replace("PLUGIN", PLUGIN)

PLAIN = """
def test_plain():
    assert True
"""

MARKED_STRICT = """
import pytest


@pytest.mark.filterwarnings("error")
def test_strict():
    assert True
"""

STACKED = """
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties


@add_test_properties(test_type="requirements-based", Owner="team-a")
class TestThing:
    @add_test_properties(partially_verifies=["REQ_1"])
    def test_one(self):
        assert True

    @add_test_properties(partially_verifies=["REQ_2"], Owner="team-b")
    def test_two(self):
        assert True


@add_test_properties(fully_verifies=["REQ_3"])
@add_test_properties(test_type="interface-test")
def test_stacked():
    assert True
"""

CUSTOM = """
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties

@add_test_properties(satisfies=["REQ_1", "REQ_2"], reviewers=["ann", "bob"], Owner="x")
def test_custom():
    assert True
"""


def _line_of(source, needle):
    """1-based line of *needle* in the file pytester writes (it strips the
    leading blank line)."""
    return next(
        index
        for index, line in enumerate(source.strip().splitlines(), start=1)
        if line.startswith(needle)
    )


# pytest points a decorated function at its first decorator line.
ADDITION_LINE = _line_of(DECORATED, "@add_test_properties(")
PLAIN_LINE = _line_of(DECORATED, "def test_plain")
SKIPPED_LINES = {
    "test_skipped": _line_of(SKIPPED, "@pytest.mark.skip"),
    "test_not_run": _line_of(SKIPPED, "@pytest.mark.xfail"),
    "test_setup_error": _line_of(SKIPPED, "@add_test_properties(fully_verifies"),
    "test_runs": _line_of(SKIPPED, "def test_runs"),
}


def _run(pytester, source, *extra, family="xunit1", profile=SCORE_PROFILE, ini=""):
    """Run *source* with the plugin in a fresh pytest process and parse the XML.

    *profile* is the ``test_reports_properties`` block of the ini file, *ini*
    any further ini lines. A subprocess, not in-process: this module has the
    plugin imported already, and pytest warns about a ``-p`` module it cannot
    assert-rewrite any more -- noise in the warning counts, an error under a
    strict warning policy.
    """
    pytester.makeini("[pytest]\n" + profile + ini)
    pytester.makepyfile(source)
    report = pytester.path / "report.xml"
    result = pytester.runpytest_subprocess(
        "-p", PLUGIN, "--junitxml", str(report), "-o", f"junit_family={family}", *extra
    )
    return result, (ET.parse(report).getroot() if report.exists() else None)


def _cases(root):
    return {case.get("name"): case for case in root.iter("testcase")}


def _properties(case):
    return {p.get("name"): p.get("value") for p in case.iter("property")}


@pytest.fixture
def score_model(monkeypatch):
    """The S-CORE profile installed as the plugin's model, for direct calls."""
    lines = [line.strip() for line in SCORE_PROFILE.splitlines()[1:]]
    monkeypatch.setattr(pytest_plugin, "PROPERTIES", parse_properties(lines))


class TestXmlShape:
    def test_every_case_carries_its_source_location(self, pytester):
        result, root = _run(pytester, DECORATED)
        result.assert_outcomes(passed=2)
        cases = _cases(root)
        for case in cases.values():
            assert case.get("file") == "test_every_case_carries_its_source_location.py"
        # pytest counts lines from 0; the attribute counts from 1 like editors.
        # A decorated function is located at its first decorator.
        assert cases["test_addition"].get("line") == str(ADDITION_LINE)
        assert cases["test_plain"].get("line") == str(PLAIN_LINE)

    def test_the_decorator_writes_properties(self, pytester):
        _, root = _run(pytester, DECORATED)
        assert _properties(_cases(root)["test_addition"]) == {
            "PartiallyVerifies": "REQ_1, REQ_2",
            "TestType": "requirements-based",
            "DerivationTechnique": "requirements-analysis",
            "Owner": "team-a",
        }
        assert _properties(_cases(root)["test_plain"]) == {}

    def test_runtime_metadata_and_location_override(self, pytester):
        result, root = _run(pytester, RUNTIME)
        result.assert_outcomes(passed=2)
        case = _cases(root)["test_driven_by_a_file[a.rst]"]
        assert _properties(case) == {
            "FullyVerifies": "REQ_9",
            "TestType": "interface-test",
        }
        assert case.get("file") == "specs/a.rst"
        assert case.get("line") == "7"

    def test_record_xml_attribute_is_still_accepted(self, pytester):
        # score_pytest call sites pass it; it is not needed any more. Requesting
        # pytest's fixture is what draws its experimental-feature notice.
        result, root = _run(pytester, RUNTIME_COMPAT)
        result.assert_outcomes(passed=1, warnings=1)
        case = _cases(root)["test_score_style"]
        assert (case.get("file"), case.get("line")) == ("specs/a.rst", "7")

    def test_the_fixture_request_is_the_callers_under_a_strict_policy(self, pytester):
        # The plugin neither requests that fixture nor silences its notice any
        # more, so under -W error the request in the test's own signature is
        # the error -- the docs say to drop it from the signature.
        result, _ = _run(pytester, RUNTIME_COMPAT, "-W", "error")
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(
            ["*record_xml_attribute is an experimental feature*"]
        )

    def test_cases_skipped_or_erroring_at_setup_carry_the_same_shape(self, pytester):
        # A function-scoped fixture never runs for these; the report has to be
        # shaped by hooks, or one report mixes 1-based and 0-based lines and,
        # under Bazel, cut and uncut paths -- which moves a deterministic ID.
        result, root = _run(pytester, SKIPPED)
        result.assert_outcomes(passed=1, skipped=1, xfailed=1, errors=1)
        cases = _cases(root)
        for name, line in SKIPPED_LINES.items():
            assert cases[name].get("line") == str(line), name
        assert _properties(cases["test_skipped"]) == {"PartiallyVerifies": "REQ_1"}
        assert _properties(cases["test_setup_error"]) == {"FullyVerifies": "REQ_2"}

    def test_an_inner_pytest_session_leaves_the_model_intact(self, pytester):
        result, root = _run(pytester, NESTED)
        result.assert_outcomes(passed=3)
        assert _properties(_cases(root)["test_after"]) == {"PartiallyVerifies": "REQ_2"}

    def test_an_inner_session_that_fails_to_configure_leaves_it_intact(self, pytester):
        # Its pytest_configure raises on the bad ini line; pytest_unconfigure
        # still runs and must pop what that session pushed, not the outer entry.
        broken = NESTED.replace(
            'write_text("[pytest]\\n")',
            'write_text("[pytest]\\ntest_reports_properties = a, set\\n")',
        ).replace("str(inner)]) == 0", "str(inner)]) == 4")
        assert broken != NESTED
        result, root = _run(pytester, broken)
        result.assert_outcomes(passed=3)
        assert _properties(_cases(root)["test_after"]) == {"PartiallyVerifies": "REQ_2"}

    def test_the_marker_is_registered(self, pytester):
        result, _ = _run(pytester, DECORATED, "--strict-markers")
        result.assert_outcomes(passed=2)

    def test_the_record_xml_attribute_notice_is_silenced(self, pytester):
        # pytest flags record_xml_attribute as experimental once per test; the
        # plugin exists to use it, so that notice must not reach the user.
        result, _ = _run(pytester, DECORATED)
        noisy = [
            line
            for line in result.stdout.lines
            if "record_xml_attribute is an experimental feature" in line
        ]
        assert noisy == []

    def test_xunit2_is_warned_about_at_configure_time(self, pytester):
        result, root = _run(pytester, DECORATED, family="xunit2")
        result.stdout.fnmatch_lines(["*junit_family is 'xunit2'*xunit1*"])
        assert _cases(root)["test_plain"].get("file") is None


class TestPropertyModel:
    """The model is pytest configuration; the plugin ships no names of its own."""

    def test_a_line_declares_keyword_name_and_arity(self):
        assert parse_properties(
            ["partially_verifies = PartiallyVerifies, list", "test_type = TestType"]
        ) == {
            "partially_verifies": Property("PartiallyVerifies", multi=True),
            "test_type": Property("TestType"),
        }

    def test_the_name_defaults_to_the_keyword(self):
        assert parse_properties(["reviewers, list", "Owner"]) == {
            "reviewers": Property("reviewers", multi=True),
            "Owner": Property("Owner"),
        }

    def test_blank_lines_are_skipped(self):
        assert parse_properties(["", "  ", "Owner"]) == {"Owner": Property("Owner")}

    @pytest.mark.parametrize(
        "line",
        ["a = b = c", "a, list, extra", "= Name", "a, set"],
        ids=["two-equals", "two-flags", "no-keyword", "unknown-flag"],
    )
    def test_a_line_outside_the_grammar_is_an_error(self, line):
        with pytest.raises(ValueError, match="test_reports_properties"):
            parse_properties([line])

    def test_a_keyword_given_twice_is_an_error(self):
        with pytest.raises(ValueError, match="twice"):
            parse_properties(["a = A", "a = B"])

    def test_two_keywords_for_one_xml_name_is_an_error(self):
        # _normalise would keep only the later value, silently.
        with pytest.raises(ValueError, match="'B'"):
            parse_properties(["a = B", "c = B"])

    def test_a_custom_profile_drives_the_xml(self, pytester):
        profile = "test_reports_properties =\n    satisfies = Satisfies, list\n    reviewers, list\n"
        result, root = _run(pytester, CUSTOM, profile=profile)
        result.assert_outcomes(passed=1)
        assert _properties(_cases(root)["test_custom"]) == {
            "Satisfies": "REQ_1, REQ_2",
            "reviewers": "ann, bob",
            "Owner": "x",
        }

    def test_the_profile_may_come_from_pyproject(self, pytester):
        pytester.makepyprojecttoml(
            "[tool.pytest.ini_options]\n"
            "test_reports_properties = [\n"
            '    "partially_verifies = PartiallyVerifies, list",\n'
            '    "test_type = TestType",\n'
            "]\n"
        )
        pytester.makepyfile(DECORATED)
        report = pytester.path / "report.xml"
        result = pytester.runpytest_subprocess(
            "-p", PLUGIN, "--junitxml", str(report), "-o", "junit_family=xunit1"
        )
        result.assert_outcomes(passed=2)
        written = _properties(_cases(ET.parse(report).getroot())["test_addition"])
        assert written["PartiallyVerifies"] == "REQ_1, REQ_2"
        # Not configured: written under its own name, as a single value.
        assert written["derivation_technique"] == "requirements-analysis"

    def test_a_decorator_may_run_before_configuration_is_read(self, pytester):
        # A conftest.py that imports a helper module runs during pytest's
        # pre-parse, before pytest_configure installs the model. The decorator
        # keeps the keywords as given, so that shape neither crashes collection
        # nor loses the properties, which are written at setup.
        pytester.makepyfile(
            helpers=(
                "from sphinxcontrib.test_reports.pytest_plugin import add_test_properties\n"
                "\n"
                '@add_test_properties(partially_verifies=["REQ_1"], test_type="interface-test")\n'
                "def test_from_helper():\n"
                "    assert True\n"
            )
        )
        pytester.makeconftest("import helpers  # decorates at pre-parse time\n")
        result, root = _run(pytester, "from helpers import test_from_helper\n")
        result.assert_outcomes(passed=1)
        assert _properties(_cases(root)["test_from_helper"]) == {
            "PartiallyVerifies": "REQ_1",
            "TestType": "interface-test",
        }

    def test_without_a_profile_a_list_is_an_error_naming_the_option(self, pytester):
        # Silently writing "['REQ_1', 'REQ_2']" is the bug this replaces.
        result, root = _run(pytester, DECORATED, profile="")
        result.assert_outcomes(passed=1, errors=1)
        result.stdout.fnmatch_lines(
            ["*TypeError*'partially_verifies'*test_reports_properties*"]
        )
        assert _properties(_cases(root)["test_plain"]) == {}

    def test_a_bad_line_is_a_usage_error_at_start_up(self, pytester):
        result, _ = _run(pytester, PLAIN, profile="test_reports_properties = a, set\n")
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["ERROR: test_reports_properties*'set'*"])


class TestPropertyValues:
    """How a keyword's value reaches the XML: declared per property, not guessed."""

    def test_a_bare_string_is_one_requirement_id(self, score_model):
        # str is a Sequence[str]; it must not be exploded character by character.
        assert properties_mapping(partially_verifies="REQ_1") == {
            "PartiallyVerifies": "REQ_1"
        }

    def test_a_list_for_a_single_valued_property_is_an_error(self, score_model):
        with pytest.raises(TypeError, match="test_type.*single value"):
            properties_mapping(test_type=["a", "b"])

    def test_an_unconfigured_keyword_takes_a_single_value(self, score_model):
        assert properties_mapping(Owner="team-a") == {"Owner": "team-a"}

    def test_a_list_under_an_unconfigured_keyword_is_an_error(self, score_model):
        with pytest.raises(TypeError, match="Satisfies.*test_reports_properties"):
            properties_mapping(Satisfies=["REQ_1", "REQ_2"])

    def test_the_xml_name_of_a_configured_property_works_as_keyword(self, score_model):
        assert properties_mapping(PartiallyVerifies=["REQ_1", "REQ_2"]) == {
            "PartiallyVerifies": "REQ_1, REQ_2"
        }

    def test_numbers_are_written_as_text(self, score_model):
        assert properties_mapping(Priority=3) == {"Priority": "3"}

    def test_bytes_are_an_error(self, score_model):
        # bytes is a Sequence of ints: b"REQ_1" would join to "82, 69, 81, 95, 49".
        with pytest.raises(TypeError, match="bytes"):
            properties_mapping(fully_verifies=b"REQ_1")

    def test_every_item_of_a_list_must_be_a_string(self, score_model):
        # A list of lists is one indentation away in a spec file; it used to be
        # written as its repr and split into bogus IDs on the build side.
        with pytest.raises(TypeError, match="partially_verifies.*item.*list"):
            properties_mapping(partially_verifies=[["REQ_1", "REQ_2"]])
        with pytest.raises(TypeError, match="item.*int"):
            properties_mapping(partially_verifies=[1, 2])

    def test_an_empty_list_under_any_keyword_writes_nothing(self, score_model):
        # A parser returning [] for an absent field is the documented pattern;
        # the arity check must not fire before the items are looked at.
        assert properties_mapping(test_type=[], fully_verifies=["R"]) == {
            "FullyVerifies": "R"
        }
        assert properties_mapping(Owner=[None, ""], fully_verifies=["R"]) == {
            "FullyVerifies": "R"
        }
        with pytest.raises(TypeError, match="test_type.*single value"):
            properties_mapping(test_type=["a"])

    def test_an_empty_nested_list_is_not_written_as_brackets(self, score_model):
        with pytest.raises(TypeError, match="item"):
            properties_mapping(partially_verifies=[[]], fully_verifies=["R"])

    # The decorator builds the marker here, outside a session that registers it.
    @pytest.mark.filterwarnings("ignore::pytest.PytestUnknownMarkWarning")
    def test_the_import_gate_and_the_writer_agree_on_emptiness(self, score_model):
        # Only None, "" and sequences of those count as empty. Anything else
        # passes the decorator and is then judged by the writer.
        with pytest.raises(ValueError, match="no test properties"):
            pytest_plugin.add_test_properties(partially_verifies=[""], test_type=None)
        decorator = pytest_plugin.add_test_properties(partially_verifies=[[]])
        assert callable(decorator)
        with pytest.raises(TypeError):
            properties_mapping(partially_verifies=[[]])

    def test_an_unordered_collection_is_an_error(self, score_model):
        # str(set) would be written otherwise, and a set has no stable order.
        with pytest.raises(TypeError, match="partially_verifies"):
            properties_mapping(partially_verifies={"REQ_1", "REQ_2"})

    def test_empty_values_are_dropped(self, score_model):
        assert properties_mapping(fully_verifies=["R"], test_type="") == {
            "FullyVerifies": "R"
        }

    def test_nothing_to_record_is_an_error(self, score_model):
        with pytest.raises(ValueError, match="no test properties"):
            properties_mapping(partially_verifies=[])

    def test_the_decorator_rejects_an_empty_call_without_a_model(self, monkeypatch):
        # Import time, before any configuration is read: emptiness needs none.
        monkeypatch.setattr(pytest_plugin, "PROPERTIES", {})
        with pytest.raises(ValueError, match="no test properties"):
            pytest_plugin.add_test_properties(partially_verifies=[], test_type="")


class TestRuntimeMetadata:
    def test_all_empty_metadata_records_nothing(self, score_model):
        # A spec file with an empty metadata block must not fail the test --
        # whether the parser hands back "" or [] for an absent field.
        recorded = []
        apply_test_metadata(
            record_property=lambda name, value: recorded.append((name, value)),
            metadata={"fully_verifies": [], "test_type": "", "Owner": []},
        )
        apply_test_metadata(
            record_property=lambda name, value: recorded.append((name, value)),
            metadata={"test_type": [], "derivation_technique": [None]},
        )
        assert recorded == []

    def test_the_location_is_applied_without_metadata(self, pytester):
        source = RUNTIME.replace(
            'metadata={"fully_verifies": ["REQ_9"], "test_type": "interface-test"}',
            "metadata={}",
        )
        result, root = _run(pytester, source)
        result.assert_outcomes(passed=2)
        case = _cases(root)["test_driven_by_a_file[a.rst]"]
        assert _properties(case) == {}
        assert (case.get("file"), case.get("line")) == ("specs/a.rst", "7")


BAD_SHAPE_AND_BROKEN_FIXTURE = """
import pytest
from sphinxcontrib.test_reports.pytest_plugin import add_test_properties


@pytest.fixture
def broken():
    raise RuntimeError("no database")


@add_test_properties(test_type=["a", "b"])
def test_both(broken):
    assert True
"""


class TestBadShape:
    def test_a_bad_shape_errors_the_case_at_setup(self, pytester):
        result, root = _run(
            pytester,
            "from sphinxcontrib.test_reports.pytest_plugin import add_test_properties\n\n@add_test_properties(test_type=['a', 'b'])\ndef test_shape():\n    assert True\n",
        )
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*TypeError*'test_type' takes a single value*"])

    def test_a_bad_shape_is_appended_to_a_fixture_error(self, pytester):
        # Replacing the fixture's error would hide it until the shape is fixed.
        result, _ = _run(pytester, BAD_SHAPE_AND_BROKEN_FIXTURE)
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(
            ["*RuntimeError: no database*", "*TypeError*'test_type'*"]
        )


class TestMarkerMerge:
    def test_class_and_method_markers_are_merged(self, pytester):
        # A classification on the class and links on each method is the natural
        # way to use the decorator; get_closest_marker kept only the innermost.
        result, root = _run(pytester, STACKED)
        result.assert_outcomes(passed=3)
        cases = _cases(root)
        assert _properties(cases["test_one"]) == {
            "PartiallyVerifies": "REQ_1",
            "TestType": "requirements-based",
            "Owner": "team-a",
        }

    def test_the_innermost_marker_wins_per_key(self, pytester):
        _, root = _run(pytester, STACKED)
        assert _properties(_cases(root)["test_two"])["Owner"] == "team-b"

    def test_stacked_decorators_on_a_function_are_merged(self, pytester):
        _, root = _run(pytester, STACKED)
        assert _properties(_cases(root)["test_stacked"]) == {
            "FullyVerifies": "REQ_3",
            "TestType": "interface-test",
        }


class TestStartUp:
    """The plugin's own notices, and pytest's about its fixtures, never take the
    run down -- whatever the project's warning policy."""

    def test_filterwarnings_error_in_the_ini_keeps_the_run_alive(self, pytester):
        result, root = _run(pytester, DECORATED, ini="filterwarnings = error\n")
        result.assert_outcomes(passed=2)
        assert _cases(root)["test_plain"].get("line") == str(PLAIN_LINE)

    def test_w_error_on_the_command_line_keeps_the_run_alive(self, pytester):
        # An appended ini filter cannot silence the record_xml_attribute notice
        # here: command-line filters take precedence over every ini line.
        result, root = _run(pytester, DECORATED, "-W", "error")
        result.assert_outcomes(passed=2)
        assert _cases(root)["test_plain"].get("line") == str(PLAIN_LINE)

    def test_a_strict_filterwarnings_mark_keeps_the_test_alive(self, pytester):
        result, root = _run(pytester, MARKED_STRICT)
        result.assert_outcomes(passed=1)
        assert _cases(root)["test_strict"].get("file") is not None

    def test_xunit2_under_filterwarnings_error_is_a_clean_usage_error(self, pytester):
        # The project asked for warnings to be errors; the plugin's advice is
        # one, delivered as a usage error rather than an INTERNALERROR trace.
        result, _ = _run(
            pytester, PLAIN, family="xunit2", ini="filterwarnings = error\n"
        )
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["ERROR: *junit_family is 'xunit2'*xunit1*"])
        assert "INTERNALERROR" not in result.stdout.str()

    def test_the_notice_can_be_silenced_by_its_class(self, pytester):
        result, _ = _run(
            pytester,
            PLAIN,
            family="xunit2",
            ini=f"filterwarnings =\n    error\n    ignore::{PLUGIN}.TestReportsConfigWarning\n",
        )
        result.assert_outcomes(passed=1, warnings=0)

    def test_xunit2_gives_no_per_test_fixture_warnings(self, pytester):
        # pytest drops the attributes under xunit2 anyway and would warn per test
        # that record_xml_attribute is incompatible; the plugin says it once.
        result, _ = _run(pytester, PLAIN, family="xunit2")
        result.assert_outcomes(passed=1, warnings=1)
        assert not [
            line for line in result.stdout.lines if "is incompatible with" in line
        ]

    def test_legacy_is_an_alias_of_xunit1(self, pytester):
        result, root = _run(pytester, DECORATED, family="legacy")
        result.assert_outcomes(passed=2, warnings=0)
        assert _cases(root)["test_plain"].get("line") == str(PLAIN_LINE)

    def test_the_junitxml_plugin_may_be_disabled(self, pytester):
        # config.option.xmlpath exists only while pytest's junitxml plugin is
        # registered, and so do the record_* fixtures.
        pytester.makeini("[pytest]\n" + SCORE_PROFILE)
        pytester.makepyfile(DECORATED)
        result = pytester.runpytest_subprocess("-p", PLUGIN, "-p", "no:junitxml")
        result.assert_outcomes(passed=2)

    def test_xdist_gets_the_full_shape(self, pytester):
        # pytest builds the XML writer on the controller only, so nothing a
        # worker records as an attribute survives; the location is written on
        # the controller from the report instead, and the model reaches the
        # workers for the properties.
        pytest.importorskip("xdist")
        result, root = _run(pytester, DECORATED, "-n", "1")
        result.assert_outcomes(passed=2, warnings=0)
        case = _cases(root)["test_addition"]
        assert case.get("line") == str(ADDITION_LINE)
        assert _properties(case)["PartiallyVerifies"] == "REQ_1, REQ_2"

    def test_xdist_issues_the_xunit2_notice_once(self, pytester):
        pytest.importorskip("xdist")
        result, _ = _run(pytester, PLAIN, "-n", "1", family="xunit2")
        result.assert_outcomes(passed=1, warnings=1)

    def test_xdist_gets_the_runtime_location_override(self, pytester):
        pytest.importorskip("xdist")
        result, root = _run(pytester, RUNTIME, "-n", "1")
        result.assert_outcomes(passed=2)
        case = _cases(root)["test_driven_by_a_file[a.rst]"]
        assert (case.get("file"), case.get("line")) == ("specs/a.rst", "7")


class TestSourcePath:
    def test_the_runfiles_prefix_is_cut_at_a_path_component(self):
        assert clean_source_path("../_main/pkg/test_x.py") == "pkg/test_x.py"
        assert clean_source_path("_main/pkg/test_x.py") == "pkg/test_x.py"
        assert (
            clean_source_path("/cache/bin/t.runfiles/_main/pkg/test_x.py")
            == "pkg/test_x.py"
        )
        assert clean_source_path("pkg/test_x.py") == "pkg/test_x.py"

    def test_a_directory_merely_ending_in_main_is_kept(self):
        # Two files under app_main/ and domain_main/ used to collapse onto the
        # same path -- and, with tr_deterministic_case_ids, onto the same ID.
        assert (
            clean_source_path("services/app_main/tests/test_api.py")
            == "services/app_main/tests/test_api.py"
        )
        assert clean_source_path("domain_main/test_api.py") == "domain_main/test_api.py"

    def test_the_last_runfiles_component_wins(self):
        # Under bzlmod the execroot's workspace directory is _main as well.
        assert (
            clean_source_path("execroot/_main/bazel-out/bin/t.runfiles/_main/pkg/t.py")
            == "pkg/t.py"
        )

    def test_windows_separators_count_as_boundaries(self):
        assert clean_source_path("..\\_main\\pkg\\test_x.py") == "pkg\\test_x.py"


class TestHelpers:
    def test_the_plugin_does_not_import_sphinx(self):
        script = (
            "import sys;"
            f"import {PLUGIN};"
            "leaked = sorted(m for m in sys.modules"
            " if m in ('sphinx', 'docutils')"
            " or m.startswith(('sphinx.', 'sphinx_needs', 'docutils.')));"
            "print(','.join(leaked))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == ""
