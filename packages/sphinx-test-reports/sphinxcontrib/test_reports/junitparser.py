import os
from lxml import etree, objectify


class JUnitParser:
    def __init__(self, junit_xml, junit_xsd=None):
        self.junit_xml_path = junit_xml

        if junit_xsd is None:
            junit_xsd = os.path.join(os.path.dirname(__file__), "schemas", "JUnit.xsd")
        self.junit_xsd_path = junit_xsd

        if not os.path.exists(self.junit_xml_path):
            raise JUnitFileMissing("The given file does not exist: {0}".format(self.junit_xml_path))

        self.junit_schema_doc = etree.parse(self.junit_xsd_path)
        self.xmlschema = etree.XMLSchema(self.junit_schema_doc)
        self.junit_xml_doc = etree.parse(self.junit_xml_path)
        self.valid_xml = self.xmlschema.validate(self.junit_xml_doc)

        self.junit_xml_string = etree.tostring(self.junit_xml_doc)

        self.junit_xml_object = objectify.fromstring(self.junit_xml_string)


class JUnitFileMissing(BaseException):
    pass
