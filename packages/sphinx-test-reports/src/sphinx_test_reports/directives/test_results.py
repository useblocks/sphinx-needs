import os

from docutils import nodes
from docutils.parsers.rst import Directive

from sphinx_test_reports.directives.test_common import error_node, new_section, warn
from ub_test_reports.junitparser import JUnitParser, ReportReadError


class TestResults(nodes.General, nodes.Element):
    pass


class _NoOptions(dict):
    """An option spec that declares no option, and is still TRUE.

    docutils parses a directive's option block only ``if option_spec:``
    (``parse_directive_block``), so an EMPTY spec is the same as none -- and with
    ``final_argument_whitespace`` an option line written under the directive is folded
    into the path, which then names no file (#2138). Truthy and empty, every option is
    docutils' own ``unknown option: "<name>"`` directive error, as for any directive.
    """

    def __bool__(self) -> bool:
        return True


class TestResultsDirective(Directive):
    """
    Directive for showing test results.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    # No options -- and declared as such, so that docutils refuses one (#2138).
    option_spec = _NoOptions()

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.header = ("class", "name", "status", "reason")
        self.colwidths = (1, 1, 1, 2)

    def run(self):
        env = self.state.document.settings.env

        xml_path = self.arguments[0]
        root_path = env.app.config.tr_rootdir
        if not os.path.isabs(xml_path):
            xml_path = os.path.join(root_path, xml_path)

        # Every refusal is a located `test_reports.*` warning and an error box in place of
        # the sections; the build goes on.
        if not os.path.exists(xml_path):
            return self._refuse("report_missing", f"Test file not found: {xml_path}")
        if os.path.splitext(xml_path)[1] == ".json":
            # Refused by name: lxml's message for a JSON file, "Start tag expected, '<'
            # not found", blames the wrong thing.
            return self._refuse(
                "report_unreadable",
                f"test-results reads JUnit XML reports; {xml_path} is a JSON file",
            )
        try:
            results = JUnitParser(xml_path).parse()
        except ReportReadError as error:
            return self._refuse("report_unreadable", str(error))

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/

        main_section = []

        for testsuite in results:
            main_section.append(self._suite_section(testsuite))

        return main_section

    def _refuse(self, subtype: str, message: str) -> list[nodes.Node]:
        warn(self, subtype, message)
        return [error_node(message)]

    def _suite_section(self, testsuite) -> nodes.section:
        """A suite's section: its counters, its ``Time:``, the table of its DIRECT cases,
        then a section of the same shape inside it for each nested suite, at every depth.
        """
        section = new_section(self.state, testsuite["name"])
        section += nodes.paragraph(
            text="Tests: {tests}, Failures: {failure}, Errors: {error}, "
            "Skips: {skips}".format(
                tests=testsuite["tests"],
                failure=testsuite["failures"],
                error=testsuite["errors"],
                skips=testsuite["skips"],
            )
        )
        section += nodes.paragraph(text="Time: {time}".format(time=testsuite["time"]))

        table = nodes.table()
        section += table

        tgroup = nodes.tgroup(cols=len(self.header))
        table += tgroup
        for colwidth in self.colwidths:
            tgroup += nodes.colspec(colwidth=colwidth)

        thead = nodes.thead()
        tgroup += thead
        thead += self._create_table_row(self.header)

        tbody = nodes.tbody()
        tgroup += tbody
        for testcase in testsuite["testcases"]:
            tbody += self._create_testcase_row(testcase)

        for nested in testsuite.get("testsuite_nested", []):
            section.append(self._suite_section(nested))

        return section

    def _create_testcase_row(self, testcase):
        row_cells = (
            testcase["classname"],
            testcase["name"],
            testcase["result"],
            "\n\n".join(
                [
                    testcase["message"] if testcase["message"] != "unknown" else "",
                    testcase["text"] if testcase["text"] is not None else "",
                ]
            ),
        )

        row = nodes.row(classes=["tr_" + testcase["result"]])
        for index, cell in enumerate(row_cells):
            entry = nodes.entry(
                classes=["tr_" + testcase["result"], self.header[index]]
            )
            row += entry
            entry += nodes.paragraph(text=cell, classes=["tr_" + testcase["result"]])
        return row

    def _create_table_row(self, row_cells):
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            row += entry
            entry += nodes.paragraph(text=cell)
        return row
