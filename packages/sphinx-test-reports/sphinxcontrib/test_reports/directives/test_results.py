import os
from docutils import nodes
from docutils.parsers.rst import Directive

from sphinxcontrib.test_reports.junitparser import JUnitParser


class TestResults(nodes.General, nodes.Element):
    pass


class TestResultsDirective(Directive):
    """
    Directive for showing test results.
    """
    has_content = True
    required_arguments = 1
    optional_arguments = 0

    final_argument_whitespace = True

    def run(self):
        env = self.state.document.settings.env

        xml_path = self.arguments[0]
        root_path = env.app.config.test_reports_rootdir
        if not os.path.isabs(xml_path):
            xml_path = os.path.join(root_path, xml_path)
        parser = JUnitParser(xml_path)

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/

        # for testsuite in parser.junit_xml_object.testsuite:
        #     # table = nodes.table
        #     pass

        return [nodes.Text(parser.junit_xml_string, parser.junit_xml_string)]
