"""Directive for conditionally including content based on variant data."""

from __future__ import annotations

import os
from collections.abc import Sequence

from docutils import nodes
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning

LOGGER = get_logger(__name__)


def _absolute_source(source: str | None, /) -> str | None:
    """``source`` made absolute, as Sphinx makes the source of a node's location.

    docutils records an included file relative to the working directory
    (``utils.relative_path``) whenever the two share their first two path components:
    a build run from the project's own directory, the common case, gives ``docs/inc.txt``,
    and a test run from a checkout under ``/tmp`` gives ``../…``.
    """
    return os.path.abspath(source) if source else source


def _absolute_location(location: str | nodes.Node | None, /) -> str | nodes.Node | None:
    """A ``"<source>:<line>"`` location with its source made absolute.

    Every location the ``if``, ``choose``, ``when`` and ``otherwise`` directives report
    goes through here.
    A node is returned as it is: Sphinx makes the source of a node absolute itself.
    """
    if not isinstance(location, str):
        return location
    source, colon, line = location.rpartition(":")
    if not colon or not source or source == "<unknown>":
        return location
    return f"{_absolute_source(source)}:{line}"


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
    variant data that is not configured, and an expression that raises
    (taking the truth value or the repr of its result included),
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
        # the truth value and the repr of the result run its own code, which may raise
        # (a NumPy array's ``__bool__`` does): both are taken here, so that such a
        # result fails like any other expression, before anything is reported about it
        result = bool(raw_result)
        not_a_bool = (
            None
            if isinstance(raw_result, bool)
            else f"'{directive}' directive expression did not return a bool, "
            f"got {type(raw_result).__name__}: {raw_result!r} "
            f"(coercing to bool): {expression!r}"
        )
    except Exception as e:
        log_warning(
            LOGGER,
            f"'{directive}' directive expression failed: {expression!r} — {e}",
            subtype,
            location=location,
        )
        return None

    if not_a_bool is not None:
        log_warning(LOGGER, not_a_bool, subtype, location=location)

    return result


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
            location=_absolute_location(self.get_location()),
        ):
            return []

        # Parse the content into a container node
        node = nodes.container()
        node.document = self.state.document
        nested_parse_with_titles(self.state, self.content, node, self.content_offset)
        return node.children
