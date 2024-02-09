import os
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.directives.utils import analyse_needs_metrics
from sphinx_needs.utils import add_doc

LOGGER = logging.getLogger(__name__)


class NeedReportDirective(SphinxDirective):
    final_argument_whitespace = True
    option_spec = {
        "types": directives.flag,
        "links": directives.flag,
        "options": directives.flag,
        "usage": directives.flag,
    }

    def run(self) -> Sequence[nodes.raw]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)

        if len(self.options.keys()) == 0:  # Check if options is empty
            LOGGER.warning(
                "No options specified to generate need report [needs.report]",
                location=self.get_location(),
                type="needs",
                subtype="report",
            )
            return []

        report_info = {
            "types": needs_config.types if "types" in self.options else [],
            "options": needs_config.extra_options if "options" in self.options else [],
            "links": needs_config.extra_links if "links" in self.options else [],
            "usage": analyse_needs_metrics(env) if "usage" in self.options else {},
            "report_directive": "dropdown",
        }
        report_info.update(**needs_config.render_context)

        need_report_template_path: str = needs_config.report_template
        # Absolute path starts with /, based on the conf.py directory. The / need to be striped
        correct_need_report_template_path = os.path.join(env.app.srcdir, need_report_template_path.lstrip("/"))

        if len(need_report_template_path) == 0:
            default_template_path = "needreport_template.rst"
            correct_need_report_template_path = os.path.join(os.path.dirname(__file__), default_template_path)

        if not os.path.exists(correct_need_report_template_path):
            LOGGER.warning(
                f"Could not load needs report template file {correct_need_report_template_path} [needs.report]",
                location=self.get_location(),
                type="needs",
                subtype="report",
            )
            return []

        with open(correct_need_report_template_path) as needs_report_template_file:
            needs_report_template_file_content = needs_report_template_file.read()

        template = Template(needs_report_template_file_content, autoescape=True)

        text = template.render(**report_info)
        self.state_machine.insert_input(text.split("\n"), self.state_machine.document.attributes["source"])

        report_node = nodes.raw()

        add_doc(env, env.docname)

        return [report_node]
