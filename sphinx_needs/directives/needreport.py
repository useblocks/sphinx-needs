from __future__ import annotations

from pathlib import Path
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
        "template": directives.unchanged,
    }

    def run(self) -> Sequence[nodes.raw]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)

        if not set(self.options).intersection({"types", "links", "options", "usage"}):
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

        if "template" in self.options:
            need_report_template_path = Path(
                self.env.relfn2path(self.options["template"], self.env.docname)[1]
            )
        elif needs_config.report_template:
            # Absolute path starts with /, based on the conf.py directory. The / need to be striped
            need_report_template_path = Path(
                str(env.app.srcdir)
            ) / needs_config.report_template.lstrip("/")
        else:
            need_report_template_path = (
                Path(__file__).parent / "needreport_template.rst"
            )

        if not need_report_template_path.is_file():
            LOGGER.warning(
                f"Could not load needs report template file {need_report_template_path} [needs.report]",
                location=self.get_location(),
                type="needs",
                subtype="report",
            )
            return []

        needs_report_template_file_content = need_report_template_path.read_text(
            encoding="utf8"
        )

        template = Template(needs_report_template_file_content, autoescape=True)
        text = template.render(**report_info)
        self.state_machine.insert_input(
            text.split("\n"), self.state_machine.document.attributes["source"]
        )

        report_node = nodes.raw()

        add_doc(env, env.docname)

        return [report_node]
