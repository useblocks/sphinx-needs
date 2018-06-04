
import os
xml_path = os.path.join(os.path.dirname(__file__), "data", "xml_data.xml")
xml_pytest_path = os.path.join(os.path.dirname(__file__), "data", "pytest_data.xml")
xml_nose_path = os.path.join(os.path.dirname(__file__), "data", "nose_data.xml")


def test_init_parser():
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_path)

    assert parser is not None


def test_xml_object():
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_path)
    obj = parser.junit_xml_object
    assert obj.tag == "testsuite"
    assert len(obj.testcase) == 3
    assert obj.testcase[2].failure.text == " details about failure "


def test_parse_easy_xml():
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "unknown"
    assert results[0]["tests"] == "3"
    assert results[0]["testcases"][0]["name"] == "ASuccessfulTest"
    assert results[0]["testcases"][0]["classname"] == "foo1"


def test_parse_nosetest_xml():
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_nose_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "nosetests"
    assert results[0]["tests"] == "5"
    assert results[0]["errors"] == "0"
    assert results[0]["failures"] == "0"
    assert results[0]["skips"] == "0"
    assert results[0]["time"] == "-1"
    assert results[0]["testcases"][0]["name"] == "test_doc_build_html"
    assert results[0]["testcases"][0]["classname"] == "test_basic_doc"
    assert results[0]["testcases"][0]["time"] == "0.283"


def test_parse_pytest_xml():
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_pytest_path)
    assert hasattr(parser, "parse")
    results = parser.parse()

    assert len(results) == 1
    assert results[0]["name"] == "pytest"
    assert results[0]["tests"] == "10"
    assert results[0]["errors"] == "0"
    assert results[0]["failures"] == "0"
    assert results[0]["skips"] == "10"
    assert results[0]["time"] == "0.054"
    assert results[0]["testcases"][0]["name"] == "FLAKE8"
    assert results[0]["testcases"][0]["classname"] == "setup"
    assert results[0]["testcases"][0]["time"] == "0.000252246856689"
    assert results[0]["testcases"][0]["line"] == "-1"
    assert results[0]["testcases"][0]["file"] == "setup.py"
