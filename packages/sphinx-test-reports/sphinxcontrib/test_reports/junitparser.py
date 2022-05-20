import os

from lxml import etree, objectify


class JUnitParser:
    def __init__(self, junit_xml, junit_xsd=None):
        self.junit_xml_path = junit_xml

        if junit_xsd is None:
            junit_xsd = os.path.join(os.path.dirname(__file__), "schemas", "JUnit.xsd")
        self.junit_xsd_path = junit_xsd

        self.junit_schema_doc = None
        self.xmlschema = None
        self.valid_xml = None

        if not os.path.exists(self.junit_xml_path):
            raise JUnitFileMissing(
                f"The given file does not exist: {self.junit_xml_path}"
            )
        self.junit_xml_doc = etree.parse(self.junit_xml_path)

        self.junit_xml_string = etree.tostring(self.junit_xml_doc)
        self.junit_xml_object = objectify.fromstring(self.junit_xml_string)
        if self.junit_xml_object.tag == "testsuites":
            self.junit_xml_object = self.junit_xml_object.testsuite
        self.junit_xml_string = str(self.junit_xml_string)

    def validate(self):
        self.junit_schema_doc = etree.parse(self.junit_xsd_path)
        self.xmlschema = etree.XMLSchema(self.junit_schema_doc)
        self.valid_xml = self.xmlschema.validate(self.junit_xml_doc)

        return self.valid_xml

    def parse(self):
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed xml file for test results junit().

        :return: list of test suites as dictionaries
        """

        def parse_testcase(xml_object):

            testcase = xml_object

            tc_dict = {
                "classname": testcase.attrib.get("classname", "unknown"),
                "file": testcase.attrib.get("file", "unknown"),
                "line": int(testcase.attrib.get("line", -1)),
                "name": testcase.attrib.get("name", "unknown"),
                "time": float(testcase.attrib.get("time", -1)),
            }

            # The following data is normally a subnode (e.g. skipped/failure).
            # We integrate it right into the testcase for better handling
            if hasattr(testcase, "skipped"):
                result = testcase.skipped
                tc_dict["result"] = "skipped"
                tc_dict["type"] = result.attrib.get("type", "unknown")
                # tc_dict["text"] = re.sub(r"[\n\t]*", "", result.text)  # Removes newlines  and tabs
                # result.text can be None for pytest xfail test cases
                tc_dict["text"] = result.text or ""
                tc_dict["message"] = result.attrib.get("message", "unknown")
            elif hasattr(testcase, "failure"):
                result = testcase.failure
                tc_dict["result"] = "failure"
                tc_dict["type"] = result.attrib.get("type", "unknown")
                # tc_dict["text"] = re.sub(r"[\n\t]*", "", result.text)  # Removes newlines and tabs
                tc_dict["text"] = result.text
                tc_dict["message"] = ""
            else:
                tc_dict["result"] = "passed"
                tc_dict["type"] = ""
                tc_dict["text"] = ""
                tc_dict["message"] = ""

            if hasattr(testcase, "system-out"):
                tc_dict["system-out"] = testcase["system-out"].text
            else:
                tc_dict["system-out"] = ""

            return tc_dict

        def parse_testsuite(xml_object):

            testsuite = xml_object

            tests = int(testsuite.attrib.get("tests", -1))
            errors = int(testsuite.attrib.get("errors", -1))
            failures = int(testsuite.attrib.get("failures", -1))

            # fmt: off
            skips = int(
                testsuite.attrib.get("skips") or testsuite.attrib.get("skip") or testsuite.attrib.get("skipped") or -1
            )
            # fmt: on

            passed = int(tests - sum(x for x in [errors, failures, skips] if x > 0))

            ts_dict = {
                "name": testsuite.attrib.get("name", "unknown"),
                "tests": tests,
                "errors": errors,
                "failures": failures,
                "skips": skips,
                "passed": passed,
                "time": float(testsuite.attrib.get("time", -1)),
                "testcases": [],
                "testsuites": [],
            }

            # add nested testsuite objects to
            if hasattr(testsuite, "testsuite"):

                for ts in testsuite.testsuite:
                    # dict from inner parse
                    inner_testsuite = parse_testsuite(ts)
                    ts_dict["testsuites"].append(inner_testsuite)

            elif hasattr(testsuite, "testcase"):

                for tc in testsuite.testcase:
                    new_testcase = parse_testcase(tc)
                    ts_dict["testcases"].append(new_testcase)

            return ts_dict

        # main flow starts here

        junit_dict = []
        complete_testsuite = parse_testsuite(self.junit_xml_object)
        junit_dict.append(complete_testsuite)

        return junit_dict

    def docutils_table(self):
        pass


class JUnitFileMissing(BaseException):
    pass
