"""Multi-line needs in source comments: comment runs, prefix stripping, the block grammar.

A multi-line need is one need written across the lines of a comment. This module turns
the comment nodes of one file into comment RUNS, strips each line's comment prefix by the
comment's kind, and parses a run's lines with the block grammar. It knows nothing of
Sphinx or of a need's fields: the record is built by ``analyse.py``, and the need is
validated and its content parsed by whoever consumes the record.

**Runs.** One block comment (``/* … */``, ``/** … */``, ``/*! … */``) or one Python string
statement (a docstring or any bare string statement) is a run on its own. Consecutive line comments form one run when they sit on consecutive rows,
use the same delimiter, and have only whitespace before them on their rows; a line
comment after code on its row neither starts nor continues a run.

**Prefix stripping** follows the comment's kind and never searches the text, so each
logical line maps to exactly one source row:

========================================  ==================================================  ===========================================
comment kind                              stripped from each line                             languages
========================================  ==================================================  ===========================================
line comment ``//``, ``///``, ``//!``     the delimiter, then ONE space if present            C/C++, C#, Rust, Go, JSONC
line comment ``#``                        the delimiter, then ONE space if present            Python, YAML, Bash
block comment ``/* … */``, ``/** … */``,  a first row holding only the opener (``/*`` with  C/C++, C#, Rust, Go, JSONC
``/*! … */``                              any stars, or ``/*!``) and a last row holding only
                                          the closer (stars then ``*/``) are dropped; the
                                          delimiters are removed; then a ``*`` leader (``*``
                                          and one space, or a lone ``*``) only if EVERY
                                          remaining non-blank line after the opener's row
                                          carries one (the doxygen rule)
Python docstring                          the quotes and any string prefix; the interior      Python
                                          dedented as ``inspect.cleandoc`` does (no line is
                                          removed)
line comment ``--``                       one row to add when the language lands              VHDL, SQL (sphinx-needs #2077)
block comment ``<!-- … -->``              one row to add when the language lands              Markdown (sphinx-needs #1895)
========================================  ==================================================  ===========================================

A comment whose text does not start with a delimiter its kind allows -- impossible for a
tree-sitter node, possible for a libclang one -- keeps its lines unstripped, and a debug
message says so.

**The grammar** (after stripping) is the one in ``docs/components/analyse.rst``: the open
line ``<open>[<markup>] <type>: <title>``, option lines ``:key: value`` (a line indented
deeper than its option line continues the value), the body in the declared markup, and the
close word alone on its line. :func:`parse_run` returns the blocks, the refusals and the
rows a block claims; the claimed rows are hidden from the one-line and ``@need-ids:``
extractors.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from sphinx_codelinks.analyse.models import SourceComment, WarningSubTypeEnum
from sphinx_codelinks.config import CommentCategory, MultilineNeedsConfig
from sphinx_codelinks.logger import get_logger

logger = get_logger(__name__)

CommentKind = Literal["line", "block", "docstring", "unknown"]

#: line-comment delimiters, longest first so that ``///`` is not read as ``//``
LINE_DELIMITERS: tuple[str, ...] = ("///", "//!", "//", "#")

_LEADER = re.compile(r"^[ \t]*\*(?: |$)")
"""A doxygen leader: optional whitespace, ``*``, then one space or the line end."""

_OPENER_ONLY = re.compile(r"^/\*+!?\s*$")
"""A block comment's first row holding nothing but its opener (``/*``, ``/*****``, ``/*!``)."""

_CLOSER_ONLY = re.compile(r"^\s*\*+/\s*$")
"""A block comment's last row holding nothing but its closer (``*/``, `` ***/``)."""

_STARS = re.compile(r"^\s*\*+\s*")

_STARS_ONLY = re.compile(r"^\s*\*+\s*$")
"""A line of stars only: a separator, counted as a leader line and read as blank."""
"""Stars at the start of a line, with the whitespace around them."""

_DOCSTRING_OPEN = re.compile(r"""^([rRuUbBfF]{0,2})(\"\"\"|'''|"|')""")

_HEADER = re.compile(r"^(?:\[([^\]]*)\])?[ \t]+([\w-]+):(?:[ \t]+(.*))?$")
"""What follows the open word: ``[<markup>]``, whitespace, ``<type>:``, the title."""

_OPTION = re.compile(r"^:([\w-]+):(?:[ \t]+(.*))?$")
"""An option line, leading whitespace removed: ``:<key>:`` then the value."""

RESERVED_KEYS: frozenset[str] = frozenset({"type", "title", "content", "doctype"})
"""Keys the record sets itself: an option naming one duplicates it."""


@dataclass(frozen=True)
class LogicalLine:
    """One line of a comment run with its comment prefix stripped."""

    row: int
    """The 0-based source row."""
    col: int
    """The 0-based source column (in characters) of ``text[0]``."""
    text: str
    """The line after prefix stripping."""


@dataclass
class CommentRun:
    """The comments one block grammar pass reads, and their logical lines."""

    comments: list[SourceComment]
    lines: list[LogicalLine]
    leaderless_block: bool = False
    """A block comment whose lines did not all carry a ``*`` leader, so none was
    stripped: an open word behind a star is reported, not silently lost."""


@dataclass
class ParsedBlock:
    """One multi-line need as the grammar found it, in source coordinates (0-based)."""

    open_row: int
    open_col: int
    close_row: int
    end_col: int
    """One past the close word's last character."""
    markup: str
    doctype: str
    need: dict[str, str]
    option_rows: dict[str, int]
    content_start: tuple[int, int] | None


@dataclass(frozen=True)
class ParseIssue:
    """A refusal or a note of the grammar, at a 0-based source row."""

    kind: WarningSubTypeEnum
    row: int
    msg: str


@dataclass
class ParseResult:
    blocks: list[ParsedBlock] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    claimed_rows: set[int] = field(default_factory=set)


@dataclass
class _Comment:
    comment: SourceComment
    row: int
    col: int
    text: str
    kind: CommentKind
    delimiter: str
    alone: bool
    """Only whitespace before the comment on its row (or not knowable: libclang
    without the row's text)."""


def _text(comment: SourceComment) -> str:
    raw = comment.node.text or b""
    return raw.decode("utf-8", errors="replace")


def _column(comment: SourceComment, text: str, row_text: str | None) -> int | None:
    """The comment's 0-based column in characters, or ``None`` when not knowable.

    A tree-sitter node gives a byte column; a libclang comment gives none, so its
    column is read from the row: its first line is the row's suffix, or else its first
    occurrence in the row (a one-row block comment followed by code).
    """
    node = comment.node
    if getattr(node, "is_libclang", False):
        if row_text is None:
            return None
        first = text.split("\n", 1)[0]
        if row_text.endswith(first):
            return len(row_text) - len(first)
        index = row_text.find(first)
        return index if index != -1 else None
    byte_col = node.start_point.column
    if row_text is None:
        return byte_col
    return len(row_text.encode("utf-8")[:byte_col].decode("utf-8", errors="replace"))


def _classify(comment: SourceComment, text: str) -> tuple[CommentKind, str]:
    # a libclang comment has no ``type``; only tree-sitter's Python grammar has docstrings
    if getattr(comment.node, "type", None) == CommentCategory.docstring:
        return "docstring", ""
    stripped = text.lstrip()
    if stripped.startswith("/*"):
        return "block", "/*"
    for delimiter in LINE_DELIMITERS:
        if stripped.startswith(delimiter):
            return "line", delimiter
    return "unknown", ""


def _view(comment: SourceComment, source_lines: Sequence[str] | None) -> _Comment:
    text = _text(comment)
    row = comment.node.start_point.row
    row_text = (
        source_lines[row]
        if source_lines is not None and row < len(source_lines)
        else None
    )
    col = _column(comment, text, row_text)
    kind, delimiter = _classify(comment, text)
    alone = True
    if row_text is not None and col is not None:
        alone = not row_text[:col].strip()
    return _Comment(comment, row, col or 0, text, kind, delimiter, alone)


def form_runs(
    comments: Iterable[SourceComment], source_lines: Sequence[str] | None = None
) -> list[CommentRun]:
    """Group one file's comments into runs, in source order.

    :param comments: The file's comment nodes, in any order (tree-sitter's captures are
        not in source order).
    :param source_lines: The file's rows, for what precedes a comment on its row; without
        them every line comment counts as alone on its row.
    """
    views = sorted(
        (_view(comment, source_lines) for comment in comments),
        key=lambda view: (view.row, view.col),
    )
    runs: list[CommentRun] = []
    current: list[_Comment] = []
    for view in views:
        if current and _continues(current[-1], view):
            current.append(view)
            continue
        if current:
            runs.append(_make_run(current))
        current = [view]
    if current:
        runs.append(_make_run(current))
    return runs


def _continues(previous: _Comment, view: _Comment) -> bool:
    return (
        previous.kind == "line"
        and view.kind == "line"
        and previous.alone
        and view.alone
        and previous.delimiter == view.delimiter
        and view.row == previous.row + 1
    )


def _make_run(views: list[_Comment]) -> CommentRun:
    if len(views) == 1 and views[0].kind == "block":
        lines, leader_stripped = _block_comment_lines(views[0])
        return CommentRun([views[0].comment], lines, not leader_stripped)
    run_lines: list[LogicalLine] = []
    for view in views:
        run_lines.extend(_logical_lines(view))
    return CommentRun([view.comment for view in views], run_lines)


def _logical_lines(view: _Comment) -> list[LogicalLine]:
    if view.kind == "line":
        return [_line_comment_line(view)]
    if view.kind == "block":
        return _block_comment_lines(view)[0]
    if view.kind == "docstring":
        return _docstring_lines(view)
    logger.debug(
        f"codelinks: a comment at row {view.row + 1} starts with no comment delimiter; "
        "its lines are read unstripped"
    )
    return [
        LogicalLine(view.row + offset, view.col if offset == 0 else 0, line)
        for offset, line in enumerate(view.text.split("\n"))
    ]


def _line_comment_line(view: _Comment) -> LogicalLine:
    text = view.text[:-1] if view.text.endswith("\n") else view.text
    stripped = text.lstrip()
    col = view.col + len(text) - len(stripped) + len(view.delimiter)
    rest = stripped[len(view.delimiter) :]
    if rest.startswith(" "):
        rest = rest[1:]
        col += 1
    return LogicalLine(view.row, col, rest)


def _block_comment_lines(view: _Comment) -> tuple[list[LogicalLine], bool]:
    """The block comment's logical lines, and whether a ``*`` leader was stripped."""
    texts = view.text.split("\n")
    count = len(texts)
    cols = [view.col] + [0] * (count - 1)
    keep = [True] * count
    if count > 1 and _OPENER_ONLY.match(texts[0].strip()):
        keep[0] = False
    else:
        lead = len(texts[0]) - len(texts[0].lstrip())
        body = texts[0].lstrip()
        if body.startswith("/*!"):
            opener = "/*!"
        elif body.startswith("/**") and len(view.text.strip()) > 4:
            opener = "/**"
        else:
            opener = "/*"
        cols[0] += lead + len(opener)
        texts[0] = body[len(opener) :]
    if count > 1 and _CLOSER_ONLY.match(texts[-1]):
        keep[-1] = False
    else:
        last = texts[-1].rstrip()
        if last.endswith("*/"):
            texts[-1] = last[: -len("*/")]

    # the leader test reads the rows after the opener's, delimiter-only rows dropped
    later = [i for i in range(1, count) if keep[i]]
    non_blank = [i for i in later if texts[i].strip()]
    leader_stripped = bool(non_blank) and all(
        _LEADER.match(texts[i]) or _STARS_ONLY.match(texts[i]) for i in non_blank
    )
    if leader_stripped:
        for i in later:
            match = _LEADER.match(texts[i])
            if match:
                cols[i] += match.end()
                texts[i] = texts[i][match.end() :]
            elif _STARS_ONLY.match(texts[i]):
                texts[i] = ""

    if not texts[0].strip():
        keep[0] = False
    if count > 1 and not texts[-1].strip():
        keep[-1] = False
    lines = [
        LogicalLine(view.row + i, cols[i], texts[i]) for i in range(count) if keep[i]
    ]
    return lines, leader_stripped


def _docstring_lines(view: _Comment) -> list[LogicalLine]:
    match = _DOCSTRING_OPEN.match(view.text)
    if match is None:
        return [LogicalLine(view.row, view.col, view.text)]
    quote = match.group(2)
    inner = view.text[match.end() :]
    if inner.endswith(quote):
        inner = inner[: -len(quote)]
    raw = inner.split("\n")
    first = raw[0]
    lines = [
        LogicalLine(
            view.row,
            view.col + match.end() + len(first) - len(first.lstrip()),
            first.lstrip(),
        )
    ]
    indents = [len(line) - len(line.lstrip()) for line in raw[1:] if line.strip()]
    margin = min(indents, default=0)
    for offset, line in enumerate(raw[1:], start=1):
        text = line[margin:] if line.strip() else ""
        lines.append(LogicalLine(view.row + offset, margin, text))
    return lines


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip())


def open_rest(text: str, start_sequence: str) -> str | None:
    """What follows the open word, if ``text`` starts with it as a whole word.

    The word must be followed by ``[``, whitespace or the line end. So the default
    reference marker ``@need-ids:``, which starts with the default open word, does not
    open a block, and neither does ``@needle``.
    """
    stripped = text.lstrip()
    if not stripped.startswith(start_sequence):
        return None
    rest = stripped[len(start_sequence) :]
    if rest and rest[0] != "[" and not rest[0].isspace():
        return None
    return rest


# @Parse multi-line need blocks in a comment run, IMPL_MLN_2, impl, [FE_MULTILINE_NEEDS]
def parse_run(
    lines: Sequence[LogicalLine],
    config: MultilineNeedsConfig,
    *,
    leaderless_block: bool = False,
) -> ParseResult:
    """Find the multi-line needs in one comment run.

    At each line opening a block: the close word ending the same line is the one-line
    form, refused, and its line is claimed; no close line further down the run is an
    unterminated block, refused, and the rest of the run is not scanned; an open line
    that does not match the grammar is refused, and the lines up to its close are still
    consumed. A block, a refused header and a refused one-line form claim their lines.

    :param leaderless_block: The run is one block comment whose ``*`` leader was not
        stripped: an open word behind a star is refused as a header, with the cause, and
        consumed up to the first close line, which may then carry the stars too; an
        unterminated open names the leader as the likely cause.
    """
    result = ParseResult()
    start, end = config.start_sequence, config.end_sequence
    unterminated = f"no '{end}' line before the comment ends; the block is skipped"
    if leaderless_block:
        unterminated += (
            "; the likely cause: the block comment's lines do not all carry the '*' "
            "leader"
        )
    index = 0
    while index < len(lines):
        line = lines[index]
        rest = open_rest(line.text, start)
        if rest is None:
            stars = _STARS.match(line.text) if leaderless_block else None
            if stars and open_rest(line.text[stars.end() :], start) is not None:
                close = next(
                    (
                        k
                        for k in range(index + 1, len(lines))
                        if _is_close(lines[k].text, end, starred=True)
                    ),
                    None,
                )
                if close is None:
                    result.issues.append(
                        ParseIssue(
                            WarningSubTypeEnum.multiline_need_unterminated,
                            line.row,
                            unterminated,
                        )
                    )
                    break
                result.issues.append(
                    ParseIssue(
                        WarningSubTypeEnum.multiline_need_header,
                        line.row,
                        f"'{start}' sits behind a '*' leader in a block comment "
                        "whose other lines carry none; give every line the leader "
                        "or none",
                    )
                )
                result.claimed_rows.update(
                    lines[k].row for k in range(index, close + 1)
                )
                index = close + 1
                continue
            index += 1
            continue
        if _ends_with_word(rest, end):
            result.issues.append(
                ParseIssue(
                    WarningSubTypeEnum.multiline_need_oneline_form,
                    line.row,
                    f"'{start}' and '{end}' on one line: a one-line need is written "
                    "with the one-line marker; the block is skipped",
                )
            )
            result.claimed_rows.add(line.row)
            index += 1
            continue
        close = next(
            (
                k
                for k in range(index + 1, len(lines))
                if _is_close(lines[k].text, end, starred=False)
            ),
            None,
        )
        if close is None:
            result.issues.append(
                ParseIssue(
                    WarningSubTypeEnum.multiline_need_unterminated,
                    line.row,
                    unterminated,
                )
            )
            break
        result.claimed_rows.update(lines[k].row for k in range(index, close + 1))
        header = _HEADER.match(rest.rstrip())
        if header is None:
            result.issues.append(
                ParseIssue(
                    WarningSubTypeEnum.multiline_need_header,
                    line.row,
                    f"the open line does not match '{start}[<markup>] <type>: <title>'; "
                    f"the block up to '{end}' is skipped",
                )
            )
        else:
            result.blocks.append(
                _block(lines, index, close, header, config, result.issues)
            )
        index = close + 1
    return result


def _is_close(text: str, end: str, *, starred: bool) -> bool:
    """Whether ``text`` is a close line; ``starred`` also accepts stars before the word."""
    stripped = text.strip()
    if stripped == end:
        return True
    if starred:
        stars = _STARS.match(stripped)
        return stars is not None and stripped[stars.end() :] == end
    return False


def _ends_with_word(text: str, word: str) -> bool:
    """Whether ``text`` ends with ``word`` preceded by whitespace or nothing."""
    stripped = text.rstrip()
    if not stripped.endswith(word):
        return False
    before = stripped[: -len(word)]
    return not before or before[-1].isspace()


def _block(
    lines: Sequence[LogicalLine],
    open_index: int,
    close_index: int,
    header: re.Match[str],
    config: MultilineNeedsConfig,
    issues: list[ParseIssue],
) -> ParsedBlock:
    open_line, close_line = lines[open_index], lines[close_index]
    tag, need_type, title = header.group(1), header.group(2), header.group(3) or ""
    markup = config.default_markup
    if tag is not None:
        if tag in config.markups:
            markup = tag
        else:
            issues.append(
                ParseIssue(
                    WarningSubTypeEnum.multiline_need_markup,
                    open_line.row,
                    f"unknown markup '{tag}' (known: "
                    f"{', '.join(sorted(config.markups))}); the project default "
                    f"'{config.default_markup}' is used",
                )
            )

    options: dict[str, str] = {}
    option_rows: dict[str, int] = {}
    index = open_index + 1
    # the option a continuation line extends: its key (None when the option was
    # refused as a duplicate) and its indentation
    current: tuple[str | None, int] | None = None
    while index < close_index:
        text = lines[index].text
        if current is not None and text.strip() and _indent(text) > current[1]:
            key = current[0]
            if key is not None:
                options[key] = " ".join(filter(None, (options[key], text.strip())))
            index += 1
            continue
        option = _OPTION.match(text.strip())
        if option is None:
            break
        key, value = option.group(1), (option.group(2) or "").strip()
        if key in options or key in RESERVED_KEYS:
            what = "the block's own" if key in RESERVED_KEYS else "an earlier"
            issues.append(
                ParseIssue(
                    WarningSubTypeEnum.multiline_need_duplicate_option,
                    lines[index].row,
                    f"option '{key}' repeats {what} '{key}'; the first value is kept",
                )
            )
            current = (None, _indent(text))
        else:
            options[key] = value
            option_rows[key] = lines[index].row + 1
            current = (key, _indent(text))
        index += 1

    body = list(lines[index:close_index])
    while body and not body[0].text.strip():
        body.pop(0)
    while body and not body[-1].text.strip():
        body.pop()
    content_lines: list[str] = []
    content_start: tuple[int, int] | None = None
    if body:
        content_start = (body[0].row, body[0].col + _indent(body[0].text))
        margin = min(_indent(line.text) for line in body if line.text.strip())
        for line in body:
            text = line.text[margin:] if line.text.strip() else ""
            stripped = text.lstrip()
            if stripped.startswith("\\" + config.end_sequence):
                # tested past the indentation, as the close is; the indentation stays
                text = text[: len(text) - len(stripped)] + stripped[1:]
            elif open_rest(text, config.start_sequence) is not None:
                issues.append(
                    ParseIssue(
                        WarningSubTypeEnum.multiline_need_nested_open,
                        line.row,
                        f"'{config.start_sequence}' inside a multi-line need's body is "
                        "body text: one need per block",
                    )
                )
            content_lines.append(text)

    need: dict[str, str] = {"type": need_type, "title": title.strip()}
    need.update(options)
    need["content"] = "\n".join(content_lines)
    need["doctype"] = config.markups[markup]
    return ParsedBlock(
        open_row=open_line.row,
        open_col=open_line.col + _indent(open_line.text),
        close_row=close_line.row,
        end_col=close_line.col
        + close_line.text.index(config.end_sequence)
        + len(config.end_sequence),
        markup=markup,
        doctype=need["doctype"],
        need=need,
        option_rows=option_rows,
        content_start=content_start,
    )


def blank_rows(text: str, first_row: int, rows: set[int]) -> str:
    """``text`` with each of ``rows`` (0-based source rows) replaced by an empty line.

    The text keeps its line count, so the row arithmetic of the other extractors holds.
    """
    lines = text.split("\n")
    return "\n".join(
        "" if first_row + offset in rows else line for offset, line in enumerate(lines)
    )
