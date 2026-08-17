from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import add_doc

LOGGER = logging.getLogger(__name__)

#: Context names the directive fills in itself.
#: :ref:`needs_render_context` is merged over the whole context, which is the
#: documented way to choose ``report_directive`` and a mistake for the rest,
#: so the rest are warned about.
RESERVED_CONTEXT_KEYS = ("types", "links", "options", "usage")

#: The directive the packaged template wraps each of its sections in.
#: Neither Sphinx nor this extension provides it -- it comes from an extension
#: such as sphinx-design -- so it may not be registered at render time.
DEFAULT_REPORT_DIRECTIVE = "dropdown"

#: Used in place of :data:`DEFAULT_REPORT_DIRECTIVE` when nothing provides it.
#: Sphinx always registers ``admonition``, and it is the only always-available
#: directive that renders as a titled block; core has no collapsible one.
FALLBACK_REPORT_DIRECTIVE = "admonition"

#: Recognises :data:`DEFAULT_REPORT_DIRECTIVE` used as a directive in *rendered*
#: text, the way docutils recognises one: an explicit markup start (``..``) at the
#: beginning of a possibly indented line, whitespace, the name, and the ``::``
#: marker -- which docutils lets a single space precede.
DROPDOWN_MARKER = re.compile(
    rf"^[ \t]*\.\.[ \t]+{re.escape(DEFAULT_REPORT_DIRECTIVE)}[ \t]?::",
    re.MULTILINE,
)


class NeedReportDirective(SphinxDirective):
    final_argument_whitespace = True
    option_spec = {
        "types": directives.flag,
        "links": directives.flag,
        "options": directives.flag,
        "usage": directives.flag,
        "template": directives.unchanged,
    }

    def _render(self, template: str, context: dict[str, Any], path: Path) -> str | None:
        """Render the report template, or warn and return ``None``.

        A template that could not be rendered used to escape ``run()`` and end the
        whole build, which is what :pr:`1105` set out to stop for this directive;
        the missing-file path got that treatment, the render path did not.

        :param template: The template source.
        :param context: The render context.
        :param path: The file the template was read from, named in the warning.
        :returns: The rendered text, or ``None`` if it could not be rendered.
        """
        try:
            return render_template_string(template, context, autoescape=False)
        except Exception as exc:
            # deliberately broad: MiniJinja raises ``TemplateError`` for a syntax
            # error or for an operation on an undefined value, but the context also
            # carries arbitrary objects from :ref:`needs_render_context`, and a
            # filter applied to one of those -- or a callable in it -- can raise
            # anything at all.  None of it should end the build.
            try:
                detail = str(getattr(exc, "message", exc))  # MiniJinja's summary
            except Exception:
                # asking the exception to describe itself raised in turn, and
                # letting that escape would be the very failure being handled
                detail = type(exc).__name__
            log_warning(
                LOGGER,
                f"Could not render needs report template file {path}: {detail}",
                "needreport",
                location=self.get_location(),
            )
            return None

    def run(self) -> Sequence[nodes.raw]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)
        needs_schema = SphinxNeedsData(env).get_schema()

        if not set(self.options).intersection({"types", "links", "options", "usage"}):
            log_warning(
                LOGGER,
                "No options specified to generate need report",
                "needreport",
                location=self.get_location(),
            )
            return []

        report_info = {
            "types": needs_config.types if "types" in self.options else [],
            "options": list(needs_schema.iter_extra_field_names())
            if "options" in self.options
            else [],
            "links": [
                {
                    "option": link.name,
                    "incoming": link.display.incoming,
                    "outgoing": link.display.outgoing,
                    "copy": link.copy,
                    "allow_dead_links": link.allow_dead_links,
                }
                for link in needs_schema.iter_link_fields()
            ]
            if "links" in self.options
            else [],
            # note the usage dict format here is just to keep backwards compatibility,
            # but actually this is now post-processed so we only really need the need types
            "usage": {
                "needs_amount": 0,
                "needs_types": {t["directive"]: 0 for t in needs_config.types},
            }
            if "usage" in self.options
            else {},
            "report_directive": DEFAULT_REPORT_DIRECTIVE,
        }
        if replaced := [
            key for key in RESERVED_CONTEXT_KEYS if key in needs_config.render_context
        ]:
            # warn only; which value wins is long-standing behaviour that projects
            # may well be relying on, so the swap is made visible rather than undone.
            # ``once=True`` because the collision is a property of the configuration
            # and not of any one directive: a project with a report on every page
            # would otherwise get the identical line once per directive.  Sphinx
            # resets that filter per application, so a later build in the same
            # process still reports.
            log_warning(
                LOGGER,
                "needs_render_context replaces the needreport context "
                f"{'keys' if len(replaced) > 1 else 'key'} "
                f"{', '.join(repr(key) for key in replaced)}; "
                "only 'report_directive' is meant to be set this way",
                "needreport",
                location=self.get_location(),
                once=True,
            )
        report_info.update(**needs_config.render_context)

        configured_template = ""
        if "template" in self.options:
            need_report_template_path = Path(
                self.env.relfn2path(self.options["template"], self.env.docname)[1]
            )
        elif needs_config.report_template:
            # always relative to the source directory; a leading / is merely stripped
            configured_template = needs_config.report_template
            need_report_template_path = Path(
                str(env.app.srcdir)
            ) / configured_template.lstrip("/")
        else:
            need_report_template_path = (
                Path(__file__).parent / "needreport_template.rst"
            )

        if not need_report_template_path.is_file():
            message = (
                f"Could not load needs report template file {need_report_template_path}"
            )
            if (
                configured_template
                and (configured := Path(configured_template)).is_absolute()
                and configured.is_file()
            ):
                # the configured value names a real file, just not the one that was
                # looked for: it was rebased under the source directory like any
                # other value, and the path above is the nonsense that comes out
                message += (
                    "; needs_report_template is resolved relative to the source "
                    f"directory, so {configured_template!r} was appended to it "
                    "rather than read from where it points"
                )
            log_warning(
                LOGGER,
                message,
                "needreport",
                location=self.get_location(),
            )
            return []

        needs_report_template_file_content = need_report_template_path.read_text(
            encoding="utf8"
        )

        text = self._render(
            needs_report_template_file_content, report_info, need_report_template_path
        )
        if text is None:
            return []

        if (
            # an explicit choice is never second-guessed, even if it is unavailable
            "report_directive" not in needs_config.render_context
            # only a report that actually renders the directive can be helped, and
            # only the rendered text knows that: the name may be shadowed by a
            # ``{% set %}``, or merely mentioned in a comment or in prose
            and DROPDOWN_MARKER.search(text)
            and directives.directive(
                DEFAULT_REPORT_DIRECTIVE,
                self.state.memo.language,
                self.state.document,
            )[0]
            is None
        ):
            # rendered again rather than patched, because the name reaches the
            # output through the template's own logic and only the template can
            # apply it.  Any callable in :ref:`needs_render_context` is therefore
            # invoked a second time, on this path alone -- the path that produces
            # an empty report today (:issue:`899`), so the repeat is the cheaper
            # of the two costs.
            fallback_text = self._render(
                needs_report_template_file_content,
                {**report_info, "report_directive": FALLBACK_REPORT_DIRECTIVE},
                need_report_template_path,
            )
            if fallback_text is None:
                return []
            if not DROPDOWN_MARKER.search(fallback_text):
                # the substitution reached the output, so it is worth making and
                # worth reporting.  If the marker survived it, the template wrote
                # the directive itself, nothing was fixed, and announcing a
                # substitution would be false -- so that report keeps the default
                # render and the diagnostics it has always had.
                text = fallback_text
                log_warning(
                    LOGGER,
                    f"No loaded extension provides a {DEFAULT_REPORT_DIRECTIVE!r} "
                    f"directive, so the needs report is rendered with "
                    f"{FALLBACK_REPORT_DIRECTIVE!r} instead. Load an extension that "
                    "provides it, for example sphinx-design, or choose the directive "
                    "yourself with needs_render_context = {'report_directive': ...}",
                    "needreport",
                    location=self.get_location(),
                )

        self.state_machine.insert_input(
            text.split("\n"), self.state_machine.document.attributes["source"]
        )

        report_node = nodes.raw()

        add_doc(env, env.docname)

        return [report_node]
