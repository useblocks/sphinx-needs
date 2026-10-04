"""Directives for including one of several branches of content based on variant data.

A ``choose`` holds ``when`` and ``otherwise`` directives (its branches) and comments,
written in its own body, and nothing else.
The first ``when`` whose condition holds is included;
an ``otherwise``, which takes no condition, is the default,
and must be the last branch.

Before anything in its body is parsed, a ``choose`` reads the body's top-level lines
(:func:`_gate`) and refuses the body at the first one that is neither the start of a
branch, a comment, nor blank. So nothing written outside a branch ever runs:
a need, a label, an ``.. include::`` or another extension's directive there
is refused with a warning, never executed and undone.

The gate's safety rule: it may refuse a line the parser would have accepted
(a refused line is never parsed, and the author gets a warning),
but it must never pass a line the parser would execute as something other than
a branch or a comment, and it must never believe it is inside a branch where the
parser is outside one (the lines it skips there would escape it).
So what it accepts mirrors the parser's own spelling rules exactly,
and where a MyST branch ends follows the CommonMark closing rule exactly.
Under MyST it reads the document's own parser configuration (front matter included;
the global configuration when the renderer does not expose it),
so that it opens a branch only with a fence kind the document's parser has
(colon, backtick or tilde), accepts ``%`` comments and ``+++`` block breaks indented
up to three spaces as myst-parser does (at any indentation when the document's parser
has its ``code`` rule disabled, as markdown-it then allows every construct),
and refuses an opener that markdown-it would take for the header of a table.
Under any other parser the ``choose`` is refused, with a warning: the gate
could not read the body, and nothing in it may run unread.

Then the body is parsed into a detached :class:`_ChooseBody` that is never returned.
A branch does not parse its content: in the body it returns a transient
:class:`_BranchPlaceholder` carrying its kind, its condition and its raw content.
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
from typing import ClassVar, Literal, NamedTuple

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import StringList
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.directives.needif import (
    _absolute_location,
    evaluate_variant_condition,
)
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

_BRANCH_KINDS: frozenset[str] = frozenset(("when", "otherwise"))

_ONE_COLON = re.compile(r"(when|otherwise)\s*:", re.IGNORECASE)
"""The start of a comment that is a branch directive written with one colon.

``.. when: <condition>`` (one colon) and ``.. when::<condition>`` (no space after
``::``) are comments in reStructuredText, and swallow the indented content under them;
both begin with ``when`` and a colon. Matched against the comment's text after its
leading whitespace, so a comment that merely begins with the word is not matched.
"""

# reStructuredText (docutils `parsers/rst/states.py`, `Body.patterns` and
# `Body.explicit.constructs`, and `directives.directive`, which lower-cases the name)
_RST_EXPLICIT = re.compile(r"\.\.( +|$)")
"""docutils' explicit markup start: ``..`` and then spaces or the end of the line."""

_RST_SIMPLENAME = r"(?:(?!_)\w)+(?:[-._+:](?:(?!_)\w)+)*"
_RST_DIRECTIVE = re.compile(rf"\.\.[ ]+({_RST_SIMPLENAME})[ ]?::([ ]+|$)")
"""docutils' directive line: a name, an optional space, ``::``, a space or the end."""

# MyST (CommonMark fences, the `colon_fence` extension, and myst-parser's
# `render_fence` / `render_colon_fence`, which take the first word of the stripped
# info string as the directive when it is `{name}`)


class _MystPatterns(NamedTuple):
    """The line patterns of the MyST gate, for one indentation rule."""

    opener: re.Pattern[str]
    """The first line of a branch: a fence whose info string starts with the name."""
    closer: re.Pattern[str]
    """A line that may close a fence: a run of one fence character (its length and
    character are compared with the opener's)."""
    comment: re.Pattern[str]
    """A line comment (myst's ``line_comment``), with its text."""
    block_break: re.Pattern[str]
    """The marker run of a block break (myst's ``block_break``): three ``+`` or more,
    mixed with spaces and tabs."""
    delimiter: re.Pattern[str]
    """A line markdown-it may take for the delimiter row of a table."""


def _myst_patterns(indent: str, /) -> _MystPatterns:
    """The MyST gate's patterns, with ``indent`` as their leading whitespace."""
    return _MystPatterns(
        opener=re.compile(
            indent + r"(:{3,}|`{3,}|~{3,})[ \t]*\{(when|otherwise)\}(?=\s|$)",
            re.IGNORECASE,
        ),
        closer=re.compile(indent + r"(:+|`+|~+)[ \t]*"),
        comment=re.compile(indent + r"%(.*)"),
        block_break=re.compile(indent + r"\+[+ \t]*"),
        delimiter=re.compile(indent + r"[|:-][|:\-\s]*"),
    )


# markdown-it-py's `StateBlock.is_code_block(line)` (3.0 and 4) is
# `_code_enabled and sCount - blkIndent >= 4`, and every rule the gate mirrors asks it
# (the fences and their closers, the colon fence through `mdit_py_plugins.utils`, the
# table's two lines, `line_comment`, `block_break`): with the `code` rule enabled a
# line indented four columns or more (a tab counts four) is a code block, and none of
# those constructs; with `code` disabled, indentation bounds none of them.
_MYST_INDENTED = _myst_patterns(r" {0,3}")
"""The MyST gate's patterns while the ``code`` rule is enabled (the default)."""
_MYST_UNBOUNDED = _myst_patterns(r"[ \t]*")
"""The MyST gate's patterns while the ``code`` rule is disabled."""

_TABLE_CELL = re.compile(r":?-+:?")


class _Stray(NamedTuple):
    """The first top-level line of a ``choose`` body that the gate refuses."""

    index: int
    """The line's index in the body."""
    one_colon: _BranchKind | None
    """The kind of branch the line is a comment for, written with one colon, if so."""


def _gate(
    lines: Sequence[str],
    /,
    *,
    syntax: Literal["rst", "myst"],
    colon_fence: bool = True,
    fence: bool = True,
    comment: bool = True,
    block_break: bool = True,
    code: bool = True,
) -> _Stray | None:
    """The first top-level line of a ``choose`` body that the parser must not see.

    That is the first line that is neither a branch start, a comment, nor blank.

    :param lines: The body, as the directive receives it.
    :param syntax: The markup the body is written in.
    :param colon_fence: Whether the document's MyST parser has colon fences
        (without them, a ``:::`` line opens nothing).
    :param fence: Whether it has backtick and tilde fences.
    :param comment: Whether it has ``%`` line comments.
    :param block_break: Whether it has ``+++`` block breaks.
    :param code: Whether it has indented code blocks, which bound the indentation
        of every other construct.
    :return: That line, or ``None`` if the body holds only branches and comments.
    """
    if syntax == "rst":
        return _gate_rst(lines)
    return _gate_myst(
        lines,
        colon_fence=colon_fence,
        fence=fence,
        comment=comment,
        block_break=block_break,
        code=code,
    )


def _gate_rst(lines: Sequence[str], /) -> _Stray | None:
    """The gate for a reStructuredText body, dedented and with tabs expanded.

    Only lines at column 0 start a construct; an indented line belongs to the
    explicit markup above it (a branch's content, a comment's text), except after
    an empty comment followed by a blank line, which docutils ends there, so that
    the indented block after it would be a block quote of the body.
    A column-0 explicit markup line is classified as docutils classifies it:
    a footnote or citation (``[``), a target (``_``) or a substitution definition
    (``|``) is refused, which is stricter than docutils when the rest of the line
    does not complete the construct; a directive is a branch start if it is
    ``when`` or ``otherwise``, and refused otherwise; anything else is a comment.
    """
    owned = False
    for index, line in enumerate(lines):
        if not line.strip(" "):
            continue
        if line.startswith(" "):
            if owned:
                continue
            return _Stray(index, None)
        start = _RST_EXPLICIT.match(line)
        if start is None:
            return _Stray(index, None)
        rest = line[start.end() :]
        if rest[:1] in ("[", "_", "|"):
            return _Stray(index, None)
        directive = _RST_DIRECTIVE.match(line)
        if directive is not None:
            if directive.group(1).lower() not in _BRANCH_KINDS:
                return _Stray(index, None)
            owned = True
            continue
        if rest.startswith('end of inclusion from "'):
            # docutils pops its include log for this comment rather than keeping it
            return _Stray(index, None)
        text = rest
        if not text.strip(" "):
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if not following.strip(" "):
                # an empty comment: docutils ends it here
                owned = False
                continue
            # the comment's text is the indented block on the next line, if any
            text = following if following.startswith(" ") else ""
        one_colon = _ONE_COLON.match(text.lstrip(" "))
        if one_colon is not None:
            return _Stray(index, _branch_kind(one_colon.group(1)))
        owned = True
    return None


def _gate_myst(
    lines: Sequence[str],
    /,
    *,
    colon_fence: bool,
    fence: bool,
    comment: bool,
    block_break: bool,
    code: bool,
) -> _Stray | None:
    """The gate for a MyST body, under the document's own parser configuration.

    A branch starts at a fence whose info string's first word is ``{when}`` or
    ``{otherwise}``, indented at most three spaces: a colon fence when the document's
    parser has ``colon_fence``, a backtick or tilde fence when it has ``fence``
    (a backtick fence may not have a backtick in its info string). It ends at the
    first later line of at least as many of the same fence character, indented at
    most three spaces, with nothing but spaces or tabs after them (the CommonMark
    closing rule); an unclosed branch runs to the end.
    markdown-it tries its ``table`` rule before any fence: an opener with a ``|``
    whose next line could be a table's delimiter row would be a table header, so it
    is refused (stricter than markdown-it, which also requires as many cells in both
    lines). Between branches, a ``%`` comment and a ``+++`` block break (three ``+``
    or more, mixed with spaces and tabs), each indented at most three spaces, are
    accepted as myst-parser's ``line_comment`` and ``block_break`` accept them.
    "At most three spaces" holds while the parser has its ``code`` rule (a line
    indented further is a code block, and none of these constructs); without it,
    markdown-it lets every one of them be indented by any spaces and tabs,
    and so does the gate.
    """
    patterns = _MYST_INDENTED if code else _MYST_UNBOUNDED
    marker: str | None = None
    for index, line in enumerate(lines):
        if marker is not None:
            closer = patterns.closer.fullmatch(line)
            if closer is not None:
                run = closer.group(1)
                if run[0] == marker[0] and len(run) >= len(marker):
                    marker = None
            continue
        if not line.strip(" \t"):
            continue
        opener = patterns.opener.match(line)
        if opener is not None:
            run = opener.group(1)
            # a backtick fence may not have a backtick in its info string (CommonMark)
            backtick_info = run[0] == "`" and "`" in line[opener.end(1) :]
            enabled = colon_fence if run[0] == ":" else fence
            following = lines[index + 1] if index + 1 < len(lines) else ""
            table = _table_header(line, following, patterns.delimiter)
            if not backtick_info and enabled and not table:
                marker = run
                continue
            return _Stray(index, None)
        text: str | None = None
        if comment and (line_comment := patterns.comment.match(line)) is not None:
            text = line_comment.group(1)
        elif (
            block_break
            and (markers := patterns.block_break.match(line)) is not None
            and markers.group(0).count("+") >= 3
        ):
            text = line[markers.end() :]
        if text is None:
            return _Stray(index, None)
        one_colon = _ONE_COLON.match(text.strip())
        if one_colon is not None:
            return _Stray(index, _branch_kind(one_colon.group(1)))
    return None


def _table_header(line: str, following: str, delimiter: re.Pattern[str], /) -> bool:
    """Whether markdown-it's ``table`` rule may take ``line`` for a table's header.

    That needs a ``|`` in the line and, on the next, a delimiter row (``delimiter``:
    indented as the ``code`` rule allows), made of ``|``, ``-``, ``:`` and whitespace
    only, with a ``-``, and every cell between the ``|`` that is not empty of the form
    ``:?-+:?``.
    """
    if "|" not in line or not delimiter.fullmatch(following):
        return False
    if "-" not in following:
        return False
    cells = [cell.strip() for cell in following.split("|")]
    return all(_TABLE_CELL.fullmatch(cell) for cell in cells if cell)


def _branch_kind(name: str, /) -> _BranchKind:
    """The branch kind a directive name (in any case) stands for."""
    return "when" if name.lower() == "when" else "otherwise"


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
                location=_absolute_location(self.get_location()),
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
    content that is neither a branch nor a comment (refused before anything in the
    body is parsed), a branch written with one colon, no branch at all,
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

        if not self._passes_gate():
            return []

        branches = self._collect_branches()
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
                location=_absolute_location(branch.location),
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
            location=_absolute_location(
                self.get_location() if location is None else location
            ),
        )

    def _syntax(self) -> Literal["rst", "myst"] | None:
        """The markup the body is written in (``None``: a parser of another kind)."""
        if isinstance(self.state, RSTState):
            return "rst"
        if type(self.state).__module__.split(".", 1)[0] == "myst_parser":
            return "myst"
        return None

    def _passes_gate(self) -> bool:
        """Read the body's top-level lines before anything in it is parsed.

        The body is refused, with one warning at the line, at the first one that is
        neither the start of a branch, a comment, nor blank.
        Under a parser other than docutils' and MyST's the body cannot be read,
        so the ``choose`` is refused, with one warning, and nothing in it is parsed.

        :return: Whether the body may be parsed.
        """
        syntax = self._syntax()
        if syntax is None:
            self._warn(
                "'choose' directive is supported under reStructuredText and MyST "
                "only; the whole choose is skipped"
            )
            return False
        stray = _gate(list(self.content), syntax=syntax, **self._myst_syntax())
        if stray is None:
            return True
        source, offset = self.content.info(stray.index)
        if syntax == "myst":
            # MyST numbers the lines of a directive's content from 0
            offset = self.lineno + stray.index
        location = (
            f"{source}:{offset + 1}"
            if source and offset is not None
            else self.get_location()
        )
        if stray.one_colon is not None:
            kind = stray.one_colon
            # the hint follows the syntax the comment is written in
            if syntax == "rst":
                write = (
                    "'.. when:: <condition>'" if kind == "when" else "'.. otherwise::'"
                )
            else:
                write = (
                    "a '{when} <condition>' fence"
                    if kind == "when"
                    else "an '{otherwise}' fence"
                )
            self._warn(
                f"'choose' directive has a comment that begins with '{kind}:' "
                f"(a branch written with one colon? write {write}); the whole "
                "choose is skipped",
                location,
            )
            return False
        # the indentation is kept: an opener indented four spaces is no branch
        text = self.content[stray.index].rstrip()
        shown = text if len(text) <= 40 else text[:40] + "…"
        self._warn(
            "'choose' directive may contain only 'when' and 'otherwise' directives "
            f"and comments, got {shown!r}; the whole choose is skipped",
            location,
        )
        return False

    def _myst_syntax(self) -> dict[str, bool]:
        """Which constructs the document's MyST parser has, for the gate.

        The document's own configuration (the global one merged with its front matter,
        whose ``enable_extensions`` replaces the global list) is held only by the
        renderer the directive's state belongs to; without it, the global
        ``myst_enable_extensions`` and ``myst_disable_syntax`` are read.
        ``disable_syntax`` can switch off a fence kind, line comments, block breaks,
        and the ``code`` rule, without which indentation bounds no construct.
        """
        config = getattr(getattr(self.state, "_renderer", None), "md_config", None)
        if config is not None:
            extensions = set(config.enable_extensions)
            disabled = set(config.disable_syntax)
        else:
            extensions = set(getattr(self.env.config, "myst_enable_extensions", ()))
            disabled = set(getattr(self.env.config, "myst_disable_syntax", ()))
        return {
            "colon_fence": "colon_fence" in extensions
            and "colon_fence" not in disabled,
            "fence": "fence" not in disabled,
            "comment": "myst_line_comment" not in disabled,
            "block_break": "myst_block_break" not in disabled,
            "code": "code" not in disabled,
        }

    def _parse_body(self) -> _ChooseBody:
        """Parse the content into a detached node, with every branch deferred.

        After the gate, the body holds only branches and comments,
        so nothing else runs while it is parsed.

        :return: The parsed body.
        """
        body = _ChooseBody()
        body.document = self.state.document
        temp_data = self.env.temp_data
        depth = temp_data.get(_DEPTH_KEY, 0)
        temp_data[_DEPTH_KEY] = depth + 1
        try:
            self.state.nested_parse(self.content, self.content_offset, body)
        finally:
            temp_data[_DEPTH_KEY] = depth
        return body

    def _collect_branches(self) -> list[_BranchPlaceholder] | None:
        """Parse the body and check its structure.

        Every ``when`` must have a condition and the ``otherwise`` none,
        and there may be one ``otherwise`` at most, as the last branch.

        :return: The branches, in order,
            or ``None`` if the body is not a valid ``choose``
            (a warning has been emitted).
        """
        branches: list[_BranchPlaceholder] = []
        for child in self._parse_body().children:
            if isinstance(child, _BranchPlaceholder):
                branches.append(child)
            elif not isinstance(child, nodes.comment):
                # past the gate only a message the parser made about a branch
                # directive, or a node of an ungated parser, can be here
                tagname = child.tagname if isinstance(child, nodes.Element) else "#text"
                self._warn(
                    "'choose' directive may contain only 'when' and 'otherwise' "
                    f"directives and comments, got <{tagname}>; the whole choose is "
                    "skipped"
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
