"""Provide a role which resolves a variant data reference inline.

The ``variant`` role takes a dotted path into the configured
:confval:`needs_variant_data` (e.g. ``:variant:`build.opt_level```) and is
resolved *immediately* during parsing into a plain text node holding the
looked-up value. Unlike :class:`~sphinx_needs.roles.need_func.NeedFunc`, no
placeholder node is left in the doctree for later post-processing.
"""

from __future__ import annotations

from docutils import nodes
from sphinx.util.docutils import SphinxRole

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.utils import add_doc
from sphinx_needs.variant_data import VariantDataError, lookup_variant_data

LOGGER = get_logger(__name__)


class VariantRole(SphinxRole):
    """Role that resolves a ``var.*`` reference to its value.

    The role text is a dotted path into :confval:`needs_variant_data`,
    rooted at ``var`` (the ``var`` root is implicit). For example, given::

        needs_variant_data = {"build": {"opt_level": 2}}

    ``:variant:`build.opt_level``` resolves immediately to the text ``2``.
    """

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        add_doc(self.env, self.env.docname)

        expression = self.text.strip()
        # The lookup is always rooted at ``var``.
        lookup_expression = f"var.{expression}"

        config = NeedsSphinxConfig(self.env.config)
        variant_data = config.variant_data

        if not variant_data:
            log_warning(
                LOGGER,
                f"'variant' role used but no variant data is available: {self.text!r}",
                "variant",
                location=self.get_location(),
            )
            return [nodes.Text("")], []

        try:
            value = lookup_variant_data(variant_data, lookup_expression)
        except VariantDataError as exc:
            log_warning(
                LOGGER,
                f"'variant' role could not resolve {self.text!r}: {exc}",
                "variant",
                location=self.get_location(),
            )
            return [nodes.Text("")], []

        if isinstance(value, list):
            text = ", ".join(str(item) for item in value)
        else:
            text = str(value)

        return [nodes.Text(text)], []
