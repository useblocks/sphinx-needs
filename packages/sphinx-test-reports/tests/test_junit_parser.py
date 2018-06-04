

def test_init_parser(xml_path):
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_path)

    assert parser is not None


def test_xml_object(xml_path):
    from sphinxcontrib.test_reports.junitparser import JUnitParser
    parser = JUnitParser(xml_path)
    obj = parser.junit_xml_object
    assert obj.tag == "testsuite"
    assert len(obj.testcase) == 3
    assert obj.testcase[2].failure.text == " details about failure "
