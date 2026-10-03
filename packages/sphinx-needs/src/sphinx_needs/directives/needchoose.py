"""Directives for including one of several branches of content based on variant data.

A ``choose`` holds ``when`` and ``otherwise`` directives (its branches) and comments,
written in its own body, and nothing else.
The first ``when`` whose condition holds is included;
an ``otherwise``, which takes no condition, is the default,
and must be the last branch.

A branch does not parse its content.
Inside a ``choose`` body it returns a transient :class:`_BranchPlaceholder`
carrying its kind, its condition and its raw content,
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

import re
from collections.abc import Sequence
from itertools import islice
from typing import ClassVar, Literal

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

A branch is a child of a ``choose`` body exactly when the count is above 0.
A ``choose`` raises it only around the parse of its own body,
and parses the content of the branch it takes at 0,
so a branch written loose in a branch's content is reported as well.
"""

_BranchKind = Literal["when", "otherwise"]
"""The directive a branch is written with."""

_BRANCH_LIKE_COMMENT = re.compile(r"(when|otherwise)\s*:", re.IGNORECASE)
"""The start of a comment that is a branch directive written with one colon.

``.. when: <condition>`` (one colon) and ``.. when::<condition>`` (no space after
``::``) are comments in reStructuredText, and swallow the indented content under them;
both begin with ``when`` and a colon. Matched against the comment's text after its
leading whitespace, so a comment that merely begins with the word is not matched.
"""

_BRANCH_DIRECTIVE_LINE = re.compile(r"(when|otherwise) ?::( |$)", re.IGNORECASE)
"""What follows ``.. `` on a line that docutils reads as a branch directive."""


class _BranchPlaceholder(nodes.Element):
    """What a branch leaves in the body of its ``choose``; it never reaches a doctree.

    The payload is held in plain Python attributes rather than docutils attributes:
    the ``choose`` reads it once and discards it with the body.
    """

    kind: _BranchKind
    """The directive the branch is written with."""
    condition: str | None
    """The condition, or ``None`` if the directive has none (or only whitespace).

    The ``choose`` refuses a ``when`` without one and an ``otherwise`` with one,
    so after its checks ``None`` marks the ``otherwise``.
    """
    content: StringList
    """The raw content of the branch, parsed only if the branch is taken."""
    content_offset: int
    """The ``content_offset`` of the branch directive."""
    lineno: int
    """The ``lineno`` of the branch directive."""
    location: str | None
    """Where warnings about the branch are reported."""
    source: str | None
    """The file the branch directive is written in, as docutils or MyST reports it."""
    owner: nodes.Element | None
    """The node the branch directive's result is appended to.

    That is the body of its ``choose`` exactly when the branch is written directly
    in it, rather than inside another directive whose content was parsed into a node
    of its own.
    """


class _ChooseBody(nodes.Element):
    """The detached node a ``choose`` parses its own body into; it is never returned."""


class _BranchDirective(SphinxDirective):
    """What ``when`` and ``otherwise`` share: a deferred branch of a ``choose``.

    The content is not parsed here: the ``choose`` parses it if it takes the branch.
    Both directives declare one optional argument, and the ``choose`` checks it,
    so that a missing condition on a ``when``, or one on an ``otherwise``,
    is warned about once, in the words of this extension, at the branch:
    a required argument would make docutils (or MyST) reject a ``when`` without one
    with an error of its own, and with no argument declared at all,
    both would move a condition written on an ``otherwise`` into its content,
    where it would be taken, silently, as the default's first paragraph.
    """

    branch_kind: ClassVar[_BranchKind]
    """The directive name, which the placeholder and the warnings carry."""

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        kind = self.branch_kind
        if self.env.temp_data.get(_DEPTH_KEY, 0) <= 0:
            article = "an" if kind == "otherwise" else "a"
            log_warning(
                LOGGER,
                f"'{kind}' directive outside a 'choose' ({article} '{kind}' must be a "
                "direct child of a 'choose'); its content is skipped",
                "choose",
                location=self.get_location(),
            )
            return []

        placeholder = _BranchPlaceholder()
        placeholder.kind = kind
        # an argument of only whitespace is no condition: docutils and MyST already drop
        # a whitespace-only argument; kept as the contract's guard
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


class WhenDirective(_BranchDirective):
    """A branch of a ``choose``, included if it is the first whose condition holds.

    The directive argument is a condition, exactly as for the ``if`` directive,
    and a ``when`` must have one: its ``choose`` refuses a ``when`` without one,
    since ``otherwise`` is the default.

    Example::

        .. choose::

           .. when:: var.arch == "arm"

              ARM content.

           .. otherwise::

              Content for every other architecture.
    """

    branch_kind = "when"


class OtherwiseDirective(_BranchDirective):
    """The default branch of a ``choose``, included when no ``when`` before it holds.

    It takes no condition (its ``choose`` refuses one), must be the last branch,
    and a ``choose`` has at most one.
    """

    branch_kind = "otherwise"


class ChooseDirective(SphinxDirective):
    """Include the first ``when`` whose condition holds, or else the ``otherwise``.

    The content may hold only ``when`` and ``otherwise`` directives and comments.
    Every mistake is warned about once, and skips the whole ``choose``:
    content that is neither a branch nor a comment, a branch inside another
    directive or supplied through an include, no branch at all,
    a ``when`` without a condition, an ``otherwise`` with one,
    an ``otherwise`` that is not the last branch or is not the only one,
    variant data that is not configured,
    and a condition that cannot be evaluated before a branch is taken.
    So a mistake that makes a condition unevaluable, such as a misspelt key
    or a syntax error, never renders a later branch or the ``otherwise`` in its place.

    Example::

        .. choose::

           .. when:: var.arch == "arm"

              ARM content.

           .. when:: var.arch == "x86"

              x86 content.

           .. otherwise::

              Content for every other architecture.
    """

    required_arguments = 0
    # declared only to be refused: with no argument declared, docutils and MyST both move
    # the text into the content, which would then be reported only as a stray paragraph
    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self) -> Sequence[nodes.Node]:
        # docutils and MyST already drop a whitespace-only argument; kept as the
        # contract's guard
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
                # the otherwise: the checks leave no other branch without a condition
                return self._parse_branch(branch)
            taken = evaluate_variant_condition(
                self.env,
                branch.condition,
                directive="when",
                subtype="choose",
                location=branch.location,
            )
            if taken is None:
                # poisoned: no later branch is evaluated or taken, nor the otherwise
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
        a branch inside another directive (one whose content is parsed into a node
        of its own, even if it then returns that node's children, such as a true ``if``)
        is refused, and so is a branch an ``.. include::`` supplies,
        so that one ``choose`` is one directive in one file.
        Then every ``when`` must have a condition and the ``otherwise`` none,
        and there may be one ``otherwise`` at most, as the last branch.

        :param source: The file this ``choose`` is written in,
            as its branches report theirs.
        :return: The branches, in order,
            or ``None`` if the body is not a valid ``choose``
            (a warning has been emitted).
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
                        f"'{child.kind}' supplied through an include is not supported "
                        "(write the branches in the body of the 'choose'); the whole "
                        "choose is skipped",
                        child.location,
                    )
                    return None
                if child.owner is not body:
                    self._warn(
                        f"'{child.kind}' directive is not a direct child of its "
                        "'choose' (it is inside another directive); the whole choose "
                        "is skipped",
                        child.location,
                    )
                    return None
                branches.append(child)
            elif isinstance(child, nodes.comment):
                like = _BRANCH_LIKE_COMMENT.match(child.astext().lstrip())
                if like is None:
                    continue
                # a branch written with one colon would hand the choice to the otherwise
                kind = like.group(1).lower()
                write = (
                    "'.. when:: <condition>'" if kind == "when" else "'.. otherwise::'"
                )
                self._warn(
                    f"'choose' directive has a comment that begins with '{kind}:' "
                    f"(a branch written with one colon? write {write}); the whole "
                    "choose is skipped",
                    self._branch_like_comment_location(child),
                )
                return None
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
                    "'choose' directive may contain only 'when' and 'otherwise' "
                    f"directives and comments, got <{tagname}>; the whole choose is "
                    "skipped",
                    self._location_of(children[index:]),
                )
                return None

        if not branches:
            self._warn("'choose' directive has no 'when' or 'otherwise'")
            return None

        for branch in branches:
            if branch.kind == "when" and branch.condition is None:
                # a forgotten condition must not make a catch-all of this branch
                self._warn(
                    "'when' directive has no condition (use 'otherwise' for the "
                    "default); the whole choose is skipped",
                    branch.location,
                )
                return None
            if branch.kind == "otherwise" and branch.condition is not None:
                # the text is named: it may be content that the parser took for the
                # argument (written on the line after the directive, with no blank line)
                self._warn(
                    "'otherwise' directive takes no condition, got "
                    f"{branch.condition!r}; the whole choose is skipped",
                    branch.location,
                )
                return None

        otherwises = [branch for branch in branches if branch.kind == "otherwise"]
        if len(otherwises) > 1:
            self._warn(
                "'choose' directive has more than one 'otherwise'; the whole choose "
                "is skipped",
                otherwises[1].location,
            )
            return None
        if otherwises and otherwises[0] is not branches[-1]:
            self._warn(
                "'choose' directive has an 'otherwise' that is not its last branch; "
                "the whole choose is skipped",
                otherwises[0].location,
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

    def _branch_like_comment_location(
        self, comment: nodes.comment, /
    ) -> nodes.Node | str | None:
        """Where to report the first comment of the body that reads like a branch.

        A comment carries no line of its own (docutils and MyST give it the line
        being parsed when it is appended, which is after it, or the ``choose``'s),
        so its line is found in the content of the ``choose``:
        the first line at the level of the body whose comment text the rule matches.
        That is the line of ``comment``, the first such comment the body holds.
        Under docutils the lines of the body are those not indented,
        and a line that docutils reads as a ``when`` or ``otherwise`` directive
        (a name, an optional space, ``::``, then a space or the end of the line)
        is not a comment;
        under MyST, the lines of the body are those outside the fences
        of the directives in it, and a ``%`` line (or a ``+++`` block break)
        is a comment.

        :param comment: The comment, used as the location if no line is found
            (for one an include supplied).
        :return: ``"<source>:<line>"``, or the fallback.
        """
        rst = isinstance(self.state, RSTState)
        fence: str | None = None
        for index, line in enumerate(self.content):
            text: str | None = None
            if rst:
                markup = re.match(r"\.\.[ ]+(.*)", line)
                text = markup.group(1) if markup else None
                if text is not None and _BRANCH_DIRECTIVE_LINE.match(text):
                    continue
            elif fence is not None:
                closing = line.rstrip()
                if closing.startswith(fence) and set(closing) == {fence[0]}:
                    fence = None
                continue
            elif opening := re.match(r"(`{3,}|~{3,}|:{3,})", line):
                fence = opening.group(1)
                continue
            elif line.startswith("%"):
                text = line[1:]
            elif line.startswith("+++"):
                text = line[3:]
            if text is not None and _BRANCH_LIKE_COMMENT.match(text.lstrip()):
                source, offset = self.content.info(index)
                if not rst:
                    # MyST numbers the lines of a directive's content from 0
                    offset = self.lineno + index
                if source and offset is not None:
                    return f"{source}:{offset + 1}"
                break
        source, line = get_source_line(comment)
        return comment if source and line else self.get_location()

    def _parse_branch(self, branch: _BranchPlaceholder) -> list[nodes.Node]:
        """Parse the content of the branch that is taken, with section titles allowed.

        It is parsed outside every ``choose`` body (at depth 0),
        whatever encloses this ``choose``,
        so that a branch written loose in it is reported rather than collected.

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
