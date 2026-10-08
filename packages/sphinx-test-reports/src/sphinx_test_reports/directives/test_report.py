# fmt: off
import pathlib
import re

from docutils import nodes
from docutils.parsers.rst import directives

from sphinx_test_reports.directives.test_common import TestCommonDirective, error_node
from sphinx_test_reports.exceptions import InvalidConfigurationError

# fmt: on


class TestReport(nodes.General, nodes.Element):
    pass


#: The leading whitespace of the template line that holds ``{content}``.
_CONTENT_INDENT = re.compile(r"^([ \t]*).*\{content\}", re.MULTILINE)


def _indented_body(lines, template: str) -> str:
    """The directive's body as the text for ``{content}``, at the template's indentation.

    The template places ``{content}`` inside the generated test-file directive, so its
    first line takes the indentation written before the placeholder and every further
    line has to be given the same, or it would end that directive. Blank lines stay
    empty.
    """
    match = _CONTENT_INDENT.search(template)
    indent = match.group(1) if match else ""
    first, *rest = list(lines) or [""]
    return "\n".join([first, *(indent + line if line.strip() else "" for line in rest)])


class TestReportDirective(TestCommonDirective):
    """
    Directive for showing test suites.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "id": directives.unchanged_required,
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "links": directives.unchanged_required,
        "collapse": directives.unchanged_required,
        "file": directives.unchanged_required,
    }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self.prepare_basic_options()
        # A refused option (no `:file:`, an invalid `:collapse:`) is reported here, not
        # handed on to a generated test-file that would carry it.
        if self.refusal is not None:
            return self.refuse(*self.refusal)
        # A report that does not exist or cannot be read: `load_test_file` has warned,
        # once; nothing is generated (a generated test-file would warn a second time).
        if self.load_test_file() is None:
            return [error_node(self.report_error)]

        # if user provides a custom template, use it
        tr_template = pathlib.Path(self.app.config.tr_report_template)

        if tr_template.is_absolute():
            template_path = tr_template
        else:
            template_path = pathlib.Path(self.app.confdir) / tr_template

        if not template_path.is_file():
            raise InvalidConfigurationError(
                f"could not find a template file with name {template_path} in conf.py directory"
            )

        with template_path.open(
            encoding=self.app.config.tr_import_encoding
        ) as template_file:
            template = "".join(template_file.readlines())

        if self.test_links is not None and len(self.test_links) > 0:
            links_string = f"\n   :links: {self.test_links}"
        else:
            links_string = ""

        template_data = {
            # The path as WRITTEN, not the resolved `self.test_file`: the generated
            # test-file resolves it against `tr_rootdir` exactly as this directive did,
            # and records it as written, as a hand-written test-file does.
            "file": self.test_file_given,
            "id": self.test_id,
            "file_type": self.app.config.tr_file[0],
            "suite_need": self.app.config.tr_suite[1],
            "case_need": self.app.config.tr_case[1],
            "tags": (
                ";".join([self.test_tags, self.test_id])
                if len(self.test_tags) > 0
                else self.test_id
            ),
            "links_string": links_string,
            "title": self.test_name,
            "content": _indented_body(self.content, template),
            "template_path": str(template_path),
        }

        template_ready = template.format(**template_data)
        # What `state_machine.insert_input` does -- the generated lines, a blank line
        # before and after them -- with every line attributed to THIS directive's own
        # source and line, so a warning of the generated test-file (a duplicate id of its
        # expansion, a need sphinx-needs refuses) is located on the test-report.
        # `insert_input` numbered them by the template's own lines, a line the page does
        # not have.
        source, line = self.state_machine.get_source_and_line(self.lineno)
        lines = ["", *template_ready.split("\n"), ""]
        input_lines = self.state_machine.input_lines
        # Both are set while a document is being parsed; the types allow `None`.
        if input_lines is not None and line is not None:
            start = self.state_machine.line_offset + 1
            for index, text in enumerate(lines):
                input_lines.insert(start + index, text, source=source, offset=line - 1)

        return []
