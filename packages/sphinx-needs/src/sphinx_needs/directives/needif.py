"""Directives for conditionally including content based on variant data.

``if``, ``elif`` and ``else`` form a chain, as in Python: at most one branch of a chain
is parsed, and the branches that are not taken are never parsed at all.

A directive cannot see its source siblings, but it can see the nodes already emitted
into its parent. So every directive of a chain returns an invisible
:class:`IfChainMarker` as its last node, recording the state of the chain so far, and
``elif`` / ``else`` read the marker left by the directive before them.
:class:`StripIfChainMarkers` removes every marker once the document is parsed, before
``doctree-read`` and before the doctree is pickled. A need's content is also copied into
the need-node cache while its directive runs, before any transform, so
:func:`~sphinx_needs.api.need.add_need` strips that subtree itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from sphinx.transforms import SphinxTransform
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)


class IfChainMarker(nodes.Invisible, nodes.Element):
    """The state of an ``if`` / ``elif`` / ``else`` chain, left after each branch.

    Attributes (docutils node attributes, so they survive a copy):

    - ``taken``: a branch of the chain has been parsed.
    - ``failed``: the chain is poisoned, so no later branch is evaluated or parsed.
    - ``closed``: the chain has seen its ``else``.
    """


def strip_if_chain_markers(node: nodes.Element) -> None:
    """Remove every :class:`IfChainMarker` under ``node``.

    Only call it on a subtree whose chains are complete: an ``elif`` or ``else`` parsed
    later into the same parent would no longer find its predecessor.

    :param node: The subtree to clean, in place.
    """
    for marker in list(node.findall(IfChainMarker)):
        marker.parent.remove(marker)


class StripIfChainMarkers(SphinxTransform):
    """Remove every :class:`IfChainMarker` once the document has been parsed."""

    default_priority = 200

    def apply(self, **kwargs: object) -> None:
        strip_if_chain_markers(self.document)


class _IfChainDirective(SphinxDirective):
    """Shared behaviour of the ``if``, ``elif`` and ``else`` directives."""

    has_content = True

    def _warn(self, message: str) -> None:
        log_warning(LOGGER, message, "if", location=self.get_location())

    def _evaluate(self, expression: str) -> bool | None:
        """Evaluate a condition against the ``var`` namespace.

        :param expression: The directive argument.
        :return: The truth value, or ``None`` when the condition could not be evaluated
            (a warning has then been emitted).
        """
        config = NeedsSphinxConfig(self.env.config)
        var_proxy = config.variant_data_proxy

        if var_proxy is None:
            self._warn(
                f"'{self.name}' directive used but needs_variant_data is not configured: "
                f"{expression!r}"
            )
            return None

        context: dict[str, object] = {"var": var_proxy, "__builtins__": {}}
        try:
            raw_result = eval(expression, context)
        except Exception as e:
            self._warn(
                f"'{self.name}' directive expression failed: {expression!r} — {e}"
            )
            return None

        if not isinstance(raw_result, bool):
            self._warn(
                f"'{self.name}' directive expression did not return a bool, "
                f"got {type(raw_result).__name__}: {raw_result!r} "
                f"(coercing to bool): {expression!r}"
            )

        return bool(raw_result)

    def _parent_node(self) -> nodes.Element:
        """The node this directive's result will be appended to.

        docutils' RST state holds it as ``parent``. MyST's mock state does not implement
        ``parent``, but it builds a fresh inliner for every directive, holding the
        renderer's current node, which is where MyST appends the result.
        """
        if isinstance(self.state, RSTState):
            return self.state.parent
        return self.state.inliner.parent

    def _preceding_marker(self) -> IfChainMarker | None:
        """The marker left by the previous branch of this chain, if there is one.

        Comments between branches are skipped; any other node breaks the chain.
        """
        for sibling in reversed(self._parent_node().children):
            if isinstance(sibling, nodes.comment):
                continue
            return sibling if isinstance(sibling, IfChainMarker) else None
        return None

    def _parse_body(self) -> list[nodes.Node]:
        node = nodes.container()
        node.document = self.state.document
        nested_parse_with_titles(self.state, self.content, node, self.content_offset)
        return node.children

    def _result(
        self,
        take: bool,
        /,
        *,
        taken: bool = False,
        failed: bool = False,
        closed: bool = False,
    ) -> list[nodes.Node]:
        """Parse the body if ``take``, and end with the marker for the next branch.

        :param take: Whether this branch is the one the chain takes.
        :param taken: An earlier branch of the chain was taken.
        :param failed: The chain is poisoned from here on.
        :param closed: The chain has seen its ``else``.
        """
        marker = IfChainMarker(taken=take or taken, failed=failed, closed=closed)
        return [*self._parse_body(), marker] if take else [marker]

    def _previous_state(self) -> IfChainMarker:
        """The state the previous branch left, for an ``elif`` or ``else``.

        A branch with no ``if`` / ``elif`` before it, or one after an ``else``, is warned
        about and sees a failed chain, so it is skipped and so is the rest of its chain.
        """
        marker = self._preceding_marker()
        if marker is None:
            self._warn(
                f"'{self.name}' directive without a preceding 'if' or 'elif' "
                "(check the indentation; only comments may separate the branches)"
            )
            return IfChainMarker(taken=False, failed=True, closed=False)
        if marker["closed"]:
            self._warn(f"'{self.name}' directive after 'else'")
            return IfChainMarker(taken=marker["taken"], failed=True, closed=True)
        return marker


class IfDirective(_IfChainDirective):
    """Conditionally include content based on a variant data expression.

    The directive argument is a Python expression evaluated against the
    ``var`` namespace (from :confval:`needs_variant_data`).
    If the expression evaluates to a truthy value, the directive content
    is parsed and included in the document. Otherwise it is skipped entirely.
    It may be followed by ``elif`` and ``else`` directives.

    Example::

        .. if:: var.arch == "arm"

           This content only appears when arch is "arm".
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    def run(self) -> Sequence[nodes.Node]:
        result = self._evaluate(self.arguments[0])
        if result is None:
            return self._result(False, failed=True)
        return self._result(result)


class ElifDirective(_IfChainDirective):
    """Include content if no earlier branch of the chain was taken and the condition holds.

    Example::

        .. if:: var.arch == "arm"

           ARM content.

        .. elif:: var.arch == "x86"

           x86 content.
    """

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    def run(self) -> Sequence[nodes.Node]:
        previous = self._previous_state()
        if previous["failed"]:
            return self._result(False, failed=True, closed=previous["closed"])
        if previous["taken"]:
            # short-circuit: the condition is not evaluated
            return self._result(False, taken=True)
        result = self._evaluate(self.arguments[0])
        if result is None:
            return self._result(False, failed=True)
        return self._result(result)


class ElseDirective(_IfChainDirective):
    """Include content if no earlier branch of the chain was taken.

    Example::

        .. if:: var.arch == "arm"

           ARM content.

        .. else::

           Content for every other architecture.
    """

    required_arguments = 0
    # ``else`` takes no condition, but it accepts one so that it can say so: with no
    # arguments at all, docutils would read ``.. else:: <condition>`` as body text
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self) -> Sequence[nodes.Node]:
        # checked first, so that a misplaced ``else`` with a condition warns once
        if self.arguments:
            self._warn(
                f"'else' directive takes no condition, got {self.arguments[0]!r} "
                "(use 'elif' for a condition)"
            )
            return self._result(False, failed=True, closed=True)
        previous = self._previous_state()
        if previous["failed"]:
            return self._result(False, failed=True, closed=True)
        return self._result(not previous["taken"], taken=previous["taken"], closed=True)
