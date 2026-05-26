"""Directive for conditionally including content based on variant data."""

from __future__ import annotations

from collections.abc import Sequence

from docutils import nodes
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)


class IfDirective(SphinxDirective):
    """Conditionally include content based on a variant data expression.

    The directive argument is a Python expression evaluated against the
    ``var`` namespace (from :confval:`needs_variant_data`).
    If the expression evaluates to a truthy value, the directive content
    is parsed and included in the document. Otherwise it is skipped entirely.

    Example::

        .. if:: var.arch == "arm"

           This content only appears when arch is "arm".
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        expression = self.arguments[0]
        config = NeedsSphinxConfig(self.env.config)
        var_proxy = config.variant_data_proxy

        if var_proxy is None:
            log_warning(
                LOGGER,
                f"'if' directive used but needs_variant_data is not configured: "
                f"{expression!r}",
                "if",
                location=self.get_location(),
            )
            return []

        context: dict[str, object] = {"var": var_proxy, "__builtins__": {}}
        try:
            raw_result = eval(expression, context)
        except Exception as e:
            log_warning(
                LOGGER,
                f"'if' directive expression failed: {expression!r} — {e}",
                "if",
                location=self.get_location(),
            )
            return []

        if not isinstance(raw_result, bool):
            log_warning(
                LOGGER,
                f"'if' directive expression did not return a bool, "
                f"got {type(raw_result).__name__}: {raw_result!r} "
                f"(coercing to bool): {expression!r}",
                "if",
                location=self.get_location(),
            )

        if not raw_result:
            return []

        # Parse the content into a container node
        node = nodes.container()
        node.document = self.state.document
        nested_parse_with_titles(self.state, self.content, node, self.content_offset)
        return node.children
