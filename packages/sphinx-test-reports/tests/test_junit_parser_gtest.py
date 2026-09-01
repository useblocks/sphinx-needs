"""Tests for the googletest XML dialect (TR-C).

googletest deviates from the pytest/nose JUnit flavour in ways that silently
produced wrong data before:

* disabled tests are reported as ``status="notrun"`` (previously classified as
  ``passed``, because no ``<failure>``/``<skipped>`` child is present);
* a single test case may carry *several* ``<failure>``/``<skipped>`` parts, of
  which only the first one was read;
* ``RecordProperty`` values arrive as **attributes** rather than
  ``<properties>`` children -- on ``<testcase>`` for googletest < 1.8.1 (the
  form the official docs still show) and on ``<testsuite>`` for suite-level
  properties up to 1.15.x;
* parameterised tests carry ``value_param``/``type_param``, and cases carry
  their own ``timestamp``.
"""

import os

xml_gtest_path = os.path.join(
    os.path.dirname(__file__), "doc_test/utils", "gtest_data.xml"
)


def _suites():
    from sphinxcontrib.test_reports.junitparser import JUnitParser

    return JUnitParser(xml_gtest_path).parse()


def _case(suite_name, case_name):
    for suite in _suites():
        if suite["name"] == suite_name:
            for case in suite["testcases"]:
                if case["name"] == case_name:
                    return case
    raise AssertionError(f"case {suite_name}/{case_name} not found")


def test_notrun_status_is_reported_as_disabled():
    """``status="notrun"`` must not fall through to ``passed``."""
    assert _case("MathTest", "DISABLED_Division")["result"] == "disabled"


def test_all_failure_parts_are_kept():
    """googletest emits one ``<failure>`` per assertion; keep every one."""
    case = _case("MathTest", "Subtraction")

    parts = case["parts"]
    assert len(parts) == 2
    assert parts[0]["kind"] == "failure"
    assert parts[0]["message"].startswith("src/math_test.cc:22")
    assert "Expected equality of these values" in parts[0]["text"]
    assert parts[1]["message"].startswith("src/math_test.cc:23")
    assert "Actual: false" in parts[1]["text"]


def test_first_failure_part_stays_in_the_legacy_flat_keys():
    """``text``/``message`` keep their meaning for existing consumers."""
    case = _case("MathTest", "Subtraction")

    assert case["result"] == "failure"
    assert case["message"] == case["parts"][0]["message"]
    assert case["text"] == case["parts"][0]["text"]


def test_all_skipped_parts_are_kept():
    case = _case("ParamTest/0", "Legacy")

    assert case["result"] == "skipped"
    assert [part["message"] for part in case["parts"]] == [
        "Skipped via GTEST_SKIP",
        "second skip part",
    ]


def test_system_err_is_captured():
    """``system-out`` was read, ``system-err`` was dropped entirely."""
    case = _case("MathTest", "Subtraction")

    assert case["system-out"] == "computing sums"
    assert case["system-err"] == "overflow guard hit"


def test_testcase_attributes_are_read_as_properties():
    """The pre-1.8.1 / documented attribute form of ``RecordProperty``."""
    case = _case("ParamTest/0", "Legacy")

    assert case["properties"]["Requirement"] == "REQ_9"
    assert case["properties"]["TestType"] == "interface-test"


def test_known_testcase_attributes_are_not_mistaken_for_properties():
    """Only *unknown* attributes are properties; the dialect's own are not."""
    case = _case("MathTest", "Addition")

    assert case["properties"] == {
        "PartiallyVerifies": "REQ_1, REQ_2",
        "TestType": "requirements-based",
    }


def test_testsuite_attributes_are_read_as_properties():
    """Suite-level ``RecordProperty`` is attribute-only up to googletest 1.15."""
    suite = next(s for s in _suites() if s["name"] == "MathTest")

    assert suite["properties"]["Owner"] == "platform-team"
    assert suite["properties"]["Component"] == "math"
    assert "tests" not in suite["properties"]
    assert "timestamp" not in suite["properties"]


def test_parameterised_and_timestamp_attributes_are_parsed():
    works = _case("ParamTest/0", "Works/0")

    assert works["value_param"] == "42"
    assert works["type_param"] == "int"
    assert _case("MathTest", "Addition")["timestamp"] == "2026-08-31T10:00:01"


def test_absent_optional_attributes_are_empty_not_missing():
    """Converters must be able to emit every field unconditionally."""
    case = _case("MathTest", "Subtraction")

    assert case["value_param"] == ""
    assert case["type_param"] == ""
    assert case["timestamp"] == ""


def test_a_testcase_without_any_properties_yields_an_empty_dict():
    """Known dialect attributes must not leak in as properties.

    ``Works/0`` carries ``value_param``/``type_param`` and no ``<properties>``
    element, so the result has to be an empty dict rather than those two
    attributes.
    """
    assert _case("ParamTest/0", "Works/0")["properties"] == {}
