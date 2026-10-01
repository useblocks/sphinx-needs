import os

xml_path = os.path.join(os.path.dirname(__file__), "fixtures", "xml_data.xml")
xml_pytest_path = os.path.join(os.path.dirname(__file__), "fixtures", "pytest_data.xml")
xml_pytest51_path = os.path.join(
    os.path.dirname(__file__), "fixtures", "pytest_data_5_1.xml"
)
xml_pytest62_path = os.path.join(
    os.path.dirname(__file__), "fixtures", "pytest_data_6_2.xml"
)

xml_nose_path = os.path.join(os.path.dirname(__file__), "fixtures", "nose_data.xml")

xml_ctest_path = os.path.join(os.path.dirname(__file__), "fixtures", "ctest.xml")
xml_error_path = os.path.join(
    os.path.dirname(__file__), "fixtures", "xml_data_error.xml"
)


def test_init_parser():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_path)

    assert parser is not None


def test_xml_object():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_path)
    obj = parser.junit_xml_object
    assert obj.tag == "testsuite"
    assert len(obj.testcase) == 3
    assert obj.testcase[2].failure.text == " details about failure "


def test_parse_easy_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "unknown"
    assert results[0]["tests"] == 3
    assert results[0]["testcases"][0]["name"] == "ASuccessfulTest"
    assert results[0]["testcases"][0]["classname"] == "foo1"


def test_parse_nosetest_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_nose_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "nosetests"
    assert results[0]["tests"] == 5
    assert results[0]["errors"] == 0
    assert results[0]["failures"] == 0
    assert results[0]["skips"] == 0
    assert results[0]["time"] == -1
    assert results[0]["testcases"][0]["name"] == "test_doc_build_html"
    assert results[0]["testcases"][0]["classname"] == "test_basic_doc"
    assert results[0]["testcases"][0]["time"] == 0.283


def test_parse_pytest_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_pytest_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "pytest"
    assert results[0]["tests"] == 10
    assert results[0]["errors"] == 0
    assert results[0]["failures"] == 0
    assert results[0]["skips"] == 10
    assert results[0]["time"] == 0.054
    assert results[0]["testcases"][0]["name"] == "FLAKE8"
    assert results[0]["testcases"][0]["classname"] == "setup"
    assert results[0]["testcases"][0]["time"] == 0.000252246856689
    assert results[0]["testcases"][0]["line"] == -1
    assert results[0]["testcases"][0]["file"] == "setup.py"


def test_parse_pytest_51_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_pytest51_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "pytest"


def test_parse_pytest_61_gets_test_suite_attributes():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_pytest62_path)
    test_suites = parser.parse()

    assert len(test_suites) == 1
    test_suite = test_suites[0]

    assert test_suite["name"] == "pytest62"
    assert test_suite["tests"] == 6
    assert test_suite["errors"] == 0
    assert test_suite["failures"] == 2
    assert test_suite["skips"] == 3
    assert test_suite["passed"] == 1
    assert test_suite["time"] == 4.088


def test_parse_ctest_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_ctest_path)
    test_suites = parser.parse()

    assert len(test_suites) == 1
    test_suite = test_suites[0]

    print(test_suite["testcases"])

    assert test_suite["tests"] == 5
    assert test_suite["errors"] == -1
    assert test_suite["failures"] == 1
    assert test_suite["skips"] == 1
    assert test_suite["passed"] == 3

    assert test_suite["testcases"][0]["name"] == "usage_test"
    assert test_suite["testcases"][0]["result"] == "passed"
    assert test_suite["testcases"][1]["name"] == "success_test"
    assert test_suite["testcases"][1]["result"] == "passed"
    assert (
        test_suite["testcases"][2]["name"] == "fail_test"
    )  # fail in name, but nowhere in status, faked fail
    assert test_suite["testcases"][2]["result"] == "passed"
    assert test_suite["testcases"][3]["name"] == "fail_test_output"
    assert test_suite["testcases"][3]["result"] == "failed"
    assert test_suite["testcases"][4]["name"] == "skipped_test"
    assert test_suite["testcases"][4]["result"] == "skipped"


def test_parse_error_xml():
    from ub_test_reports.junitparser import JUnitParser

    parser = JUnitParser(xml_error_path)
    test_suites = parser.parse()

    assert len(test_suites) == 1
    test_suite = test_suites[0]

    assert test_suite["name"] == "error_suite"
    assert test_suite["tests"] == 4
    assert test_suite["errors"] == 1
    assert test_suite["failures"] == 1

    assert test_suite["testcases"][0]["name"] == "ASuccessfulTest"
    assert test_suite["testcases"][0]["result"] == "passed"

    assert test_suite["testcases"][1]["name"] == "AFailingTest"
    assert test_suite["testcases"][1]["result"] == "failed"

    assert test_suite["testcases"][2]["name"] == "AnErrorTest"
    assert test_suite["testcases"][2]["result"] == "error"
    assert test_suite["testcases"][2]["type"] == "RuntimeError"
    assert test_suite["testcases"][2]["message"] == "unexpected crash"
    assert test_suite["testcases"][2]["text"] == "stack trace here"

    assert test_suite["testcases"][3]["name"] == "ASkippedTest"
    assert test_suite["testcases"][3]["result"] == "skipped"


xml_runner_error_path = os.path.join(
    os.path.dirname(__file__), "fixtures", "runner_error_data.xml"
)


def _runner_error_case(name):
    from ub_test_reports.junitparser import JUnitParser

    suite = JUnitParser(xml_runner_error_path).parse()[0]
    return next(case for case in suite["testcases"] if case["name"] == name)


def test_signal_killed_testcase_is_reported_as_error():
    """A crashed or signal-killed test must not read as passed.

    ``<error>`` is not a googletest construct -- the *runner* synthesizes a
    report of this shape when the test binary dies without writing one (Bazel
    does this from the test log on a crash or timeout).
    """
    case = _runner_error_case("KilledBySigterm")

    assert case["result"] == "error"
    assert case["message"] == "exited with error code 143"
    assert "Received SIGTERM" in case["text"]


def test_error_testcase_keeps_its_source_location_and_captured_output():
    case = _runner_error_case("KilledBySigterm")

    assert case["file"] == "src/crash_test.cc"
    assert case["line"] == 7
    assert case["system-err"] == "shutting down worker pool"


def test_all_error_parts_are_kept():
    """Only the first ``<error>`` used to be read, like failures and skips."""
    case = _runner_error_case("ReportsTwoErrors")

    assert case["result"] == "error"
    assert [part["message"] for part in case["parts"]] == [
        "first error",
        "second error",
    ]
    assert [part["kind"] for part in case["parts"]] == ["error", "error"]


def test_a_passing_testcase_next_to_errors_is_still_passed():
    case = _runner_error_case("Survivor")

    assert case["result"] == "passed"
    assert case["parts"] == []


def test_error_counts_are_taken_from_the_testsuite():
    from ub_test_reports.junitparser import JUnitParser

    suite = JUnitParser(xml_runner_error_path).parse()[0]

    assert suite["errors"] == 2
    assert suite["failures"] == 0
    assert suite["passed"] == 1


#: The smallest report the shipped Apache Ant JUnit schema accepts: every required
#: attribute of `<testsuite>` and `<testcase>`, and the four child elements in order.
CONFORMING_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="suite" timestamp="2026-10-01T12:00:00" hostname="host" tests="1"
           failures="0" errors="0" time="0.1">
  <properties/>
  <testcase name="test_one" classname="pkg.Suite" time="0.1"/>
  <system-out/>
  <system-err/>
</testsuite>
"""


class TestSchemaValidation:
    """`validate()` reads `schemas/JUnit.xsd` from the installed package.

    The schema is package data, so it is what an artefact check must not lose: these
    tests are the ones that fail when a built wheel ships without it.
    """

    def test_the_shipped_schema_accepts_a_conforming_report(self, tmp_path):
        from pathlib import Path

        from ub_test_reports.junitparser import JUnitParser

        report = tmp_path / "conforming.xml"
        report.write_text(CONFORMING_REPORT, encoding="utf-8")
        parser = JUnitParser(str(report))

        assert Path(parser.junit_xsd_path).is_file()
        assert parser.validate() is True

    def test_the_shipped_schema_rejects_a_report_without_its_required_attributes(
        self,
    ):
        from ub_test_reports.junitparser import JUnitParser

        # pytest's report has no `hostname` or `timestamp` on its `<testsuite>`
        parser = JUnitParser(xml_pytest_path)

        assert parser.validate() is False
        assert len(parser.xmlschema.error_log) > 0
