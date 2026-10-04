"""Directive for conditionally including content based on variant data."""

from __future__ import annotations

from collections.abc import Sequence

from docutils import nodes
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning

LOGGER = get_logger(__name__)


def evaluate_variant_condition(
    env: BuildEnvironment,
    expression: str,
    /,
    *,
    directive: str,
    subtype: WarningSubTypes,
    location: str | tuple[str | None, int | None] | nodes.Node | None,
) -> bool | None:
    """Evaluate a variant condition, as the ``if`` directive and a ``when`` do.

    The expression is Python, evaluated with ``var`` (the proxy over
    :confval:`needs_variant_data`) as its only name and no builtins.
    This is the one evaluator of both directives,
    so that a condition means the same thing whichever of them it is written on.

    Every problem is warned about here, once, naming ``directive``:
    variant data that is not configured, and an expression that raises,
    make the condition unevaluable;
    a result that is not a ``bool`` is warned about and then used as its truth value.

    :param env: The build environment, whose config holds the variant data.
    :param expression: The condition, as written.
    :param directive: The directive name the warnings give, e.g. ``"if"``.
    :param subtype: The warning subtype, ``needs.<subtype>``.
    :param location: Where the warnings are reported.
    :return: The truth value of the condition,
        or ``None`` when it could not be evaluated (a warning has been emitted).
    """
    config = NeedsSphinxConfig(env.config)
    var_proxy = config.variant_data_proxy

    if var_proxy is None:
        log_warning(
            LOGGER,
            f"'{directive}' directive used but needs_variant_data is not configured: "
            f"{expression!r}",
            subtype,
            location=location,
        )
        return None

    context: dict[str, object] = {"var": var_proxy, "__builtins__": {}}
    try:
        raw_result = eval(expression, context)
    except Exception as e:
        log_warning(
            LOGGER,
            f"'{directive}' directive expression failed: {expression!r} — {e}",
            subtype,
            location=location,
        )
        return None

    if not isinstance(raw_result, bool):
        log_warning(
            LOGGER,
            f"'{directive}' directive expression did not return a bool, "
            f"got {type(raw_result).__name__}: {raw_result!r} "
            f"(coercing to bool): {expression!r}",
            subtype,
            location=location,
        )

    return bool(raw_result)


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
        if not evaluate_variant_condition(
            self.env,
            self.arguments[0],
            directive="if",
            subtype="if",
            location=self.get_location(),
        ):
            return []

        # Parse the content into a container node
        node = nodes.container()
        node.document = self.state.document
        nested_parse_with_titles(self.state, self.content, node, self.content_offset)
        return node.children
