
import os
xml_path = os.path.join(os.path.dirname(__file__), "data", "xml_data.xml")


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
