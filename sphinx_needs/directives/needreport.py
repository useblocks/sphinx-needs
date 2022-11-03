import os
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import Template
from sphinx.errors import SphinxError

from sphinx_needs.directives.utils import analyse_needs_metrics
from sphinx_needs.utils import add_doc


class NeedsReportException(SphinxError):
    pass


class NeedReportDirective(Directive):
    final_argument_whitespace = True
    option_spec = {
        "types": directives.unchanged,
        "links": directives.unchanged,
        "options": directives.unchanged,
        "usage": directives.unchanged,
    }

    def run(self) -> Sequence[nodes.raw]:
        env = self.state.document.settings.env

        if len(self.options.keys()) == 0:  # Check if options is empty
            error_file, error_line = self.state_machine.input_lines.items[0]
            error_msg = "{}:{}: NeedReportError: No options specified to generate need report.".format(
                error_file, error_line + self.state_machine.input_lines.data.index(".. needreport::") + 1
            )
            raise NeedsReportException(error_msg)

        types = self.options.get("types")
        extra_links = self.options.get("links")
        extra_options = self.options.get("options")
        usage = self.options.get("usage")

        needs_types = []
        needs_extra_links = []
        needs_extra_options = []
        needs_metrics = {}

        if types is not None and isinstance(types, str):
            needs_types = env.app.config.needs_types
        if extra_links is not None and isinstance(extra_links, str):
            needs_extra_links = env.app.config.needs_extra_links
        if extra_options is not None and isinstance(extra_options, str):
            needs_extra_options = env.app.config.needs_extra_options
        if usage is not None and isinstance(usage, str):
            needs_metrics = analyse_needs_metrics(env)

        report_info = {
            "types": needs_types,
            "options": needs_extra_options,
            "links": needs_extra_links,
            "usage": needs_metrics,
        }
        report_info.update(**env.app.config.needs_render_context)

        need_report_template_path: str = env.app.config.needs_report_template
        # Absolute path starts with /, based on the conf.py directory. The / need to be striped
        correct_need_report_template_path = os.path.join(env.app.srcdir, need_report_template_path.lstrip("/"))

        if len(need_report_template_path) == 0:
            default_template_path = "needreport_template.rst"
            correct_need_report_template_path = os.path.join(os.path.dirname(__file__), default_template_path)

        if not os.path.exists(correct_need_report_template_path):
            raise ReferenceError(f"Could not load needs report template file {correct_need_report_template_path}")

        with open(correct_need_report_template_path) as needs_report_template_file:
            needs_report_template_file_content = needs_report_template_file.read()

        template = Template(needs_report_template_file_content, autoescape=True)

        text = template.render(**report_info)
        self.state_machine.insert_input(text.split("\n"), self.state_machine.document.attributes["source"])

        report_node = nodes.raw()

        add_doc(env, env.docname)

        return [report_node]
