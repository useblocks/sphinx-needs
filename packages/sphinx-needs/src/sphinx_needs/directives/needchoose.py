"""Directives for including one of several branches of content based on variant data.

A ``choose`` holds ``when`` directives and comments, written in its own body,
and nothing else.
The first ``when`` whose condition holds is included;
a ``when`` with no condition is the default, and must be the last.

A ``when`` does not parse its content.
Inside a ``choose`` body it returns a transient :class:`_BranchPlaceholder`
carrying its condition and its raw content,
and the ``choose`` parses its own body into a detached :class:`_ChooseBody`
that it never returns.
Having seen every branch at once, the ``choose`` checks the structure,
evaluates the conditions in order with the evaluator of the ``if`` directive
(:func:`~sphinx_needs.directives.needif.evaluate_variant_condition`),
and parses only the content of the branch it takes, returning those nodes.
So the content of every other branch is never parsed:
the needs in it are never created and its mistakes are never reported,
exactly as for the body of a false ``if``.

Neither node class reaches a doctree or the need-node cache,
so neither is registered with Sphinx:
one that ever escaped would make a writer fail loudly rather than render silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import islice

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from docutils.utils import Reporter, get_source_line
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needif import evaluate_variant_condition
from sphinx_needs.logging import get_logger, log_warning

LOGGER = get_logger(__name__)

_DEPTH_KEY = "sphinx_needs_choose_depth"
"""The ``env.temp_data`` key counting the ``choose`` bodies being parsed.

A ``when`` is a child of a ``choose`` body exactly when the count is above 0.
A ``choose`` raises it only around the parse of its own body,
and parses the content of the branch it takes at 0,
so a ``when`` written loose in a branch's content is reported as well.
"""


class _BranchPlaceholder(nodes.Element):
    """What a ``when`` leaves in the body of its ``choose``; it never reaches a doctree.

    The payload is held in plain Python attributes rather than docutils attributes:
    the ``choose`` reads it once and discards it with the body.
    """

    condition: str | None
    """The condition, or ``None`` for the default branch."""
    content: StringList
    """The raw content of the branch, parsed only if the branch is taken."""
    content_offset: int
    """The ``content_offset`` of the ``when`` directive."""
    lineno: int
    """The ``lineno`` of the ``when`` directive."""
    location: str | None
    """Where warnings about the branch are reported."""
    source: str | None
    """The file the ``when`` directive is written in, as docutils or MyST reports it."""
    owner: nodes.Element | None
    """The node the ``when`` directive's result is appended to.

    That is the body of its ``choose`` exactly when the ``when`` is written directly in it,
    rather than inside another directive whose content was parsed into a node of its own.
    """


class _ChooseBody(nodes.Element):
    """The detached node a ``choose`` parses its own body into; it is never returned."""


class WhenDirective(SphinxDirective):
    """One branch of a ``choose``, included if it is the first whose condition holds.

    The directive argument is a condition, exactly as for the ``if`` directive;
    a ``when`` with no argument is the default of its ``choose``.
    Its content is not parsed here: the ``choose`` parses it if it takes the branch.

    Example::

        .. choose::

           .. when:: var.arch == "arm"

              ARM content.

           .. when::

              Content for every other architecture.
    """

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        if self.env.temp_data.get(_DEPTH_KEY, 0) <= 0:
            log_warning(
                LOGGER,
                "'when' directive outside a 'choose' (a 'when' must be a direct child "
                "of a 'choose'); its content is skipped",
                "choose",
                location=self.get_location(),
            )
            return []

        placeholder = _BranchPlaceholder()
        # an argument of only whitespace is no condition: the default branch
        has_condition = bool(self.arguments and self.arguments[0].strip())
        placeholder.condition = self.arguments[0] if has_condition else None
        placeholder.content = self.content
        placeholder.content_offset = self.content_offset
        placeholder.lineno = self.lineno
        placeholder.location = self.get_location()
        placeholder.source = self.get_source_info()[0]
        # docutils' `RSTState.parent` is this very node, and MyST's mock state machine
        # holds the renderer's current node here, which is where MyST appends the result
        placeholder.owner = self.state_machine.node
        return [placeholder]


class ChooseDirective(SphinxDirective):
    """Include the content of the first ``when`` whose condition holds.

    The content may hold only ``when`` directives and comments.
    Every mistake is warned about once, and skips the whole ``choose``:
    content that is neither a ``when`` nor a comment, a ``when`` inside another
    directive or supplied through an include,
    a default ``when`` that is not the last or is not the only one,
    variant data that is not configured,
    and a condition that cannot be evaluated before a branch is taken.
    So a mistake that makes a condition unevaluable, such as a misspelt key
    or a syntax error, never renders a later branch or the default in its place.

    Example::

        .. choose::

           .. when:: var.arch == "arm"

              ARM content.

           .. when:: var.arch == "x86"

              x86 content.

           .. when::

              Content for every other architecture.
    """

    required_arguments = 0
    # reserved, and refused: with no argument declared, MyST would move the text into
    # the content and docutils would reject the directive, so neither could say why
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        if self.arguments and self.arguments[0].strip():
            self._warn(
                f"'choose' directive takes no argument, got {self.arguments[0]!r} "
                "(write a condition on each 'when'); the whole choose is skipped"
            )
            return []

        branches = self._collect_branches(self.get_source_info()[0])
        if branches is None:
            return []

        if NeedsSphinxConfig(self.env.config).variant_data_proxy is None:
            self._warn(
                "'choose' directive used but needs_variant_data is not configured; "
                "the whole choose is skipped"
            )
            return []

        for branch in branches:
            if branch.condition is None:
                return self._parse_branch(branch)
            taken = evaluate_variant_condition(
                self.env,
                branch.condition,
                directive="when",
                subtype="choose",
                location=branch.location,
            )
            if taken is None:
                # poisoned: no later branch is evaluated or taken, the default included
                return []
            if taken:
                # the first branch that holds wins; the later ones are not evaluated
                return self._parse_branch(branch)
        return []

    def _warn(self, message: str, location: str | nodes.Node | None = None, /) -> None:
        log_warning(
            LOGGER,
            message,
            "choose",
            location=self.get_location() if location is None else location,
        )

    def _parse_body(self) -> _ChooseBody:
        """Parse the content into a detached node, with every branch deferred.

        Because the content of every branch is deferred,
        a need created while the body is parsed can only come from content
        written outside a branch, which is a mistake that skips the whole ``choose``:
        such needs are removed again, so that the mistake creates none.

        :return: The parsed body.
        """
        body = _ChooseBody()
        body.document = self.state.document

        data = SphinxNeedsData(self.env)
        # outside the read phase no need can be added, so there is nothing to undo
        needs = None if data.needs_is_post_processed else data.get_needs_mutable()
        before = 0 if needs is None else len(needs)

        temp_data = self.env.temp_data
        depth = temp_data.get(_DEPTH_KEY, 0)
        temp_data[_DEPTH_KEY] = depth + 1
        try:
            self.state.nested_parse(self.content, self.content_offset, body)
        finally:
            temp_data[_DEPTH_KEY] = depth

        if needs is not None and len(needs) > before:
            # the newest entries are the ones the body added: O(new needs)
            for need_id in list(islice(reversed(needs), len(needs) - before)):
                data.remove_need(need_id)

        return body

    def _collect_branches(
        self, source: str | None, /
    ) -> list[_BranchPlaceholder] | None:
        """Parse the body and check its structure.

        The branches must be written in the body itself:
        a ``when`` inside another directive (one whose content is parsed into a node
        of its own, even if it then returns that node's children, such as a true ``if``)
        is refused, and so is a ``when`` an ``.. include::`` supplies,
        so that one ``choose`` is one directive in one file.

        :param source: The file this ``choose`` is written in,
            as its branches report theirs.
        :return: The branches, in order,
            or ``None`` if the body is not a valid ``choose`` (a warning has been emitted).
        """
        body = self._parse_body()
        children = list(body.children)
        branches: list[_BranchPlaceholder] = []
        for index, child in enumerate(children):
            if isinstance(child, _BranchPlaceholder):
                # the source first: a branch an include supplies is reported as such,
                # also when the include stands inside another directive
                if child.source != source:
                    self._warn(
                        "'when' supplied through an include is not supported (write "
                        "the branches in the body of the 'choose'); the whole choose "
                        "is skipped",
                        child.location,
                    )
                    return None
                if child.owner is not body:
                    self._warn(
                        "'when' directive is not a direct child of its 'choose' (it is "
                        "inside another directive); the whole choose is skipped",
                        child.location,
                    )
                    return None
                branches.append(child)
            elif isinstance(child, nodes.comment):
                continue
            elif isinstance(child, nodes.system_message):
                reported = max(
                    self.state.document.reporter.report_level, Reporter.WARNING_LEVEL
                )
                if child["level"] < reported:
                    # never shown as a problem (below the report level, or below WARNING
                    # however low that level is set): judge what follows it instead
                    # (docutils puts an INFO before the paragraph of a `---` line)
                    continue
                # reported by docutils or MyST when it was created: skip, silently
                return None
            else:
                offender = self._offender(children[index:])
                tagname = (
                    offender.tagname if isinstance(offender, nodes.Element) else "#text"
                )
                self._warn(
                    "'choose' directive may contain only 'when' directives and "
                    f"comments, got <{tagname}>; the whole choose is skipped",
                    self._location_of(children[index:]),
                )
                return None

        if not branches:
            self._warn("'choose' directive has no 'when'")
            return None

        defaults = [branch for branch in branches if branch.condition is None]
        if len(defaults) > 1:
            self._warn(
                "'choose' directive has more than one default 'when' (a 'when' with "
                "no condition); the whole choose is skipped",
                defaults[1].location,
            )
            return None
        if defaults and defaults[0] is not branches[-1]:
            self._warn(
                "'choose' directive has a default 'when' (a 'when' with no condition) "
                "that is not its last 'when'; the whole choose is skipped",
                defaults[0].location,
            )
            return None

        return branches

    @staticmethod
    def _offender(candidates: Sequence[nodes.Node]) -> nodes.Node:
        """The node a warning about the first of ``candidates`` names.

        A need directive emits a target before the need,
        which carries no line and is nothing the author wrote:
        such leading targets are passed over, so that the warning names the need.

        :param candidates: The offending child and the children after it.
        """
        for node in candidates:
            if isinstance(node, nodes.target) and not get_source_line(node)[1]:
                continue
            if isinstance(node, _BranchPlaceholder | nodes.comment):
                break
            return node
        return candidates[0]

    def _location_of(self, candidates: Sequence[nodes.Node]) -> nodes.Node | str | None:
        """Where to report the first of ``candidates``.

        That is the first node, in or under them, that knows its source and line:
        the body is detached, so no node can inherit them from an ancestor,
        and some nodes carry none of their own
        (such as the target a need directive emits before the need).

        :param candidates: The offending child and the children after it.
        :return: That node, or the location of the ``choose`` if none has both.
        """
        for candidate in candidates:
            for node in candidate.findall(nodes.Element):
                source, line = get_source_line(node)
                if source and line:
                    return node
        return self.get_location()

    def _parse_branch(self, branch: _BranchPlaceholder) -> list[nodes.Node]:
        """Parse the content of the branch that is taken, with section titles allowed.

        It is parsed outside every ``choose`` body (at depth 0),
        whatever encloses this ``choose``,
        so that a ``when`` written loose in it is reported rather than collected.

        :param branch: The branch that is taken.
        :return: The parsed nodes.
        """
        node = nodes.container()
        node.document = self.state.document
        temp_data = self.env.temp_data
        depth = temp_data.get(_DEPTH_KEY, 0)
        temp_data[_DEPTH_KEY] = 0
        try:
            nested_parse_with_titles(
                self.state, branch.content, node, self._content_offset_of(branch)
            )
        finally:
            temp_data[_DEPTH_KEY] = depth
        return node.children

    def _content_offset_of(self, branch: _BranchPlaceholder) -> int:
        """The offset at which this directive's state parses the content of ``branch``.

        Under docutils a directive's ``content_offset`` is absolute in the input,
        so the branch's own offset is valid for any state.
        Under MyST it is relative to the directive's own line
        (the mock state adds the line it was created at),
        so it is re-based from the branch's line onto this directive's line.

        :param branch: The branch that is taken.
        """
        if isinstance(self.state, RSTState):
            return branch.content_offset
        return branch.lineno - self.lineno + branch.content_offset
