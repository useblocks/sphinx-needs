"""The ``result`` field's vocabulary, and the one place it is decided.

A test case's ``result`` used to be whatever the input spelled it: the JUnit
parser passed the name of the ``<testcase>`` child element through verbatim
(``failure``), the JSON parser passed the report's own value through, and the
two states with no element of their own -- ``passed`` and ``disabled`` -- were
spelled as participles because nothing forced a choice. So one product said
``failure`` for a single case and ``failed`` for the count of them
(``fields.FIELDS``), and the documented value and the documented example
disagreed.

These tests pin the vocabulary down: every parser maps its input onto the same
participles, and the mapping is the only place that decides. The part-level
``kind`` is deliberately *not* normalised -- it names the XML element the
evidence came from, which is what the rendered evidence heading reports.
"""

import os

import pytest

UTILS = os.path.join(os.path.dirname(__file__), "doc_test", "utils")
XML_PATH = os.path.join(UTILS, "xml_data.xml")
JSON_PATH = os.path.join(UTILS, "json_data.json")

#: The mapping the JSON parser needs, as ``tr_json_mapping`` declares it.
JSON_MAPPING = {
    "testsuite": {
        "name": (["name"], "unknown"),
        "tests": (["tests"], "unknown"),
        "errors": (["errors"], "unknown"),
        "failures": (["failures"], "unknown"),
        "skips": (["skips"], "unknown"),
        "passed": (["passed"], "unknown"),
        "time": (["time"], "unknown"),
        "testcases": (["testcase"], "unknown"),
    },
    "testcase": {
        "name": (["name"], "unknown"),
        "classname": (["classname"], "unknown"),
        "file": (["file"], "unknown"),
        "line": (["line"], "unknown"),
        "time": (["time"], "unknown"),
        "result": (["result"], "unknown"),
        "type": (["type"], "unknown"),
        "text": (["text"], "unknown"),
        "message": (["message"], "unknown"),
        "system-out": (["system-out"], "unknown"),
    },
}


class TestNormalisation:
    """One function decides the vocabulary, so both parsers cannot disagree."""

    def test_the_junit_failure_element_name_becomes_failed(self):
        from sphinxcontrib.test_reports.results import normalize_result

        assert normalize_result("failure") == "failed"

    def test_normalising_the_canonical_spelling_changes_nothing(self):
        """Normalisation runs on already-canonical values too, so it must be
        idempotent -- a JSON report may already spell the result ``failed``."""
        from sphinxcontrib.test_reports.results import normalize_result

        assert normalize_result("failed") == "failed"

    @pytest.mark.parametrize("result", ["passed", "skipped", "error", "disabled"])
    def test_the_other_states_are_already_canonical(self, result):
        from sphinxcontrib.test_reports.results import normalize_result

        assert normalize_result(result) == result

    def test_a_vocabulary_this_extension_does_not_know_is_left_alone(self):
        """``tr_json_mapping`` points at an arbitrary report, so a project may
        feed in states of its own. Rewriting those would break its filters."""
        from sphinxcontrib.test_reports.results import normalize_result

        assert normalize_result("flaky") == "flaky"

    def test_the_canonical_states_are_the_documented_ones(self):
        """Ordered, because the declared field description is built from it and
        the converter's output has to be byte-stable."""
        from sphinxcontrib.test_reports.results import CANONICAL_RESULTS

        assert CANONICAL_RESULTS == (
            "passed",
            "failed",
            "error",
            "skipped",
            "disabled",
        )


class TestDeclaredSchema:
    """The converter writes the field declarations into the ``needs.json`` it
    produces, so that a consumer which never loads this extension -- a schema
    check, a metamodel validator -- learns the fields from the file. Naming the
    states in the ``result`` description tells it the field's domain too.
    """

    def test_the_result_declaration_names_every_state(self):
        from sphinxcontrib.test_reports.fields import declaration
        from sphinxcontrib.test_reports.results import CANONICAL_RESULTS

        _, description = declaration("result")

        assert all(state in description for state in CANONICAL_RESULTS), description


class TestJUnitParser:
    """The JUnit dialect is where the old spelling came from."""

    def test_a_failure_child_yields_the_failed_result(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        suite = JUnitParser(XML_PATH).parse()[0]

        assert suite["testcases"][2]["result"] == "failed"

    def test_a_result_part_keeps_the_name_of_its_xml_element(self):
        """``kind`` reports which element the evidence came from -- the
        converter capitalises it into the evidence heading -- so it stays the
        XML name even though ``result`` no longer is."""
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        suite = JUnitParser(XML_PATH).parse()[0]

        assert suite["testcases"][2]["parts"][0]["kind"] == "failure"


class TestJsonParser:
    """The JSON parser's API is documented as being in sync with the JUnit
    parser's, so the same report content has to produce the same result."""

    def test_the_failure_spelling_in_a_json_report_is_normalised(self):
        from sphinxcontrib.test_reports.jsonparser import JsonParser

        parser = JsonParser(JSON_PATH, json_mapping=JSON_MAPPING)
        suite = parser.parse()[0]

        assert suite["testcases"][0]["result"] == "failed"

    def test_the_results_needing_no_normalisation_are_untouched(self):
        from sphinxcontrib.test_reports.jsonparser import JsonParser

        parser = JsonParser(JSON_PATH, json_mapping=JSON_MAPPING)
        suite = parser.parse()[0]

        assert suite["testcases"][1]["result"] == "passed"
        assert suite["testcases"][2]["result"] == "skipped"


@pytest.mark.toolchain
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/default_tr_template"}],
    indirect=True,
)
def test_the_shipped_report_template_counts_a_failed_case(test_app):
    """The template that ``tr_report_template`` defaults to filters on the
    ``result`` value, and every fixture that exercises ``test-report`` used to
    override it -- so a rename could empty its "Failed test cases" table and
    its count without a single test noticing.
    """
    from pathlib import Path

    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    assert "Failed test cases: 1" in html
