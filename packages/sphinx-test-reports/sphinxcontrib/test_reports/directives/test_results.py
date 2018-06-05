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
        results = parser.parse()

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/

        main_section = []

        header = ('class', 'name', 'status', 'reason')
        colwidths = (1, 1, 1, 2)

        for testsuite in results:
            section = nodes.section()
            section += nodes.title(text=testsuite["name"])
            section += nodes.paragraph(text="Tests: {tests}, Failure: {failure}, Error: {error}, "
                                            "Skipped: {skipped}".format(tests=testsuite["tests"],
                                                                        failure=testsuite["failures"],
                                                                        error=testsuite["errors"],
                                                                        skipped=testsuite["skips"]
                                                                        ))
            section += nodes.paragraph(text="Time: {time}".format(time=testsuite["time"]))

            table = nodes.table()
            section += table

            tgroup = nodes.tgroup(cols=len(header))
            table += tgroup
            for colwidth in colwidths:
                tgroup += nodes.colspec(colwidth=colwidth)

            thead = nodes.thead()
            tgroup += thead
            thead += self._create_table_row(header)

            tbody = nodes.tbody()
            tgroup += tbody
            for testcase in testsuite["testcases"]:
                tbody += self._create_table_row((testcase["classname"], testcase["name"],
                                                testcase["result"], testcase["text"],))

            main_section += section

        return main_section

    def _create_table_row(self, row_cells):
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            row += entry
            entry += nodes.paragraph(text=cell)
        return row