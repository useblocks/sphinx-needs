"""In-file namespace macros: a C++ file that opens its namespaces with an object-like
macro it defines itself (``json.hpp``'s ``NLOHMANN_JSON_NAMESPACE_BEGIN``, defined as
``namespace nlohmann { inline namespace … {``) is read as the compiler reads it, by
name.

tree-sitter cannot expand a macro: each invocation stands alone on its line as an
unknown identifier, and the error recovery around it can turn the whole file into one
``ERROR`` node, losing every namespace and class around the functions. :func:`prepare`
finds those macros and their invocations in the text alone, and gives the parse a copy
of the buffer in which each opening invocation is overwritten by ``extern"C++"{``
padded with spaces to its exact length, and each closing one by ``}`` and spaces: a
name-neutral block, so the tree parses and names nothing after it. Only the PARSE
reads that copy. Every read of the tree (comments, names, tagged scopes, excerpts)
reads the file as written, by byte range (``SourceFile.node_text``,
:class:`~sphinx_codelinks.analyse.entity.CppNames`): the copy has the same length and
the same bytes outside the invocations, so every offset, line, marker and name end
stays valid. A comment can hold an invocation: tree-sitter ends a directive's argument
at ``/*`` even inside a string (``#define OPEN "/*"``), where this lexer reads a string,
so ``node.text`` of such a comment is the copy's. The namespaces each pair opens are a
byte range (:class:`MacroScopes`); an entity whose name ends inside one is named in
them, outermost first.

The rules fail closed: whatever does not fit them leaves the file as it is (F7 alone
keeps the rewrite and drops only the names).

- F1. Object-like macros only (``#define NAME`` not followed by ``(``).
- F2. An opening body (continuations joined, comments dropped) is one or more
  ``namespace N {`` (``N`` an identifier or ``a::b``, no part all capitals, none
  ``#define``\\ d in the file) or ``inline namespace … {`` (its name is left out of
  every name: an inline namespace is); a closing body is only ``}``. An anonymous
  namespace, ``extern "C"`` or any other token is neither.
- F3. Every ``#define`` of the name in the file is the same opening (the same named
  path and brace count) or the same closing, whatever ``#if`` is around it; else the
  name is not used.
- F4. An invocation before the name's first definition, or after an ``#undef`` of it,
  makes the name unused.
- F5. An invocation is a logical line that is exactly the name once comments are
  dropped, in code: not in a directive, a comment, a string, a raw string or a
  character literal. A name the code uses anywhere else (``void f(); NS_END``) is not
  used.
- F6. Openings and closings pair in file order, a closing with the last opening of the
  same brace count; a mismatch, a closing with nothing open, or an opening left open
  leaves the whole file unchanged.
- F7. A pair whose opening lies inside a real scope (a namespace, a class, a function,
  another ``extern`` block) is not used for names (:meth:`MacroScopes.validate`); its
  rewrite stays.
- F7b. A pair whose opening the tree does not read as the block it was rewritten to
  (the ``extern`` of a ``linkage_specification`` starting there: a macro statement on
  the line before, ``WARNINGS_PUSH``, makes ``WARNINGS_PUSH extern"C++"{`` one
  declaration) is left as written, with every pair inside it and every pair whose
  opening follows one of its invocations with only blanks and comments between
  (written out, that invocation would break the next block in turn); the copy is made
  again without them and parsed once more. If a pair still does not read as its block,
  the file is parsed as written, with no macro namespace (:func:`parse`: at most three
  parses, never a function lost).
- F8. C++ files only: a ``.c`` file is never rewritten (:func:`applies`).
- F9. Nothing is lexed unless a line starting with ``#`` holds ``define`` and the
  buffer holds ``namespace``.
- F10. The parsed copy has the same length as the buffer and the same bytes outside
  the invocations.

One rule more keeps a marker where it was: an opening invocation shorter than
``extern"C++"{`` (12 bytes) is not rewritten, nor is its closing one, nor any pair
inside them. Blanking it instead would put a blank line between a comment above it and
the first declaration inside, which the attachment reads as a comment on that
declaration (or on the file): a marker would move to code its author did not mark.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from tree_sitter import Parser, Tree

OPENING = b'extern"C++"{'
"""What an opening invocation becomes in the parsed copy, padded with spaces."""

CLOSING = b"}"
"""What a closing invocation becomes, padded with spaces."""

# The real scopes an opening invocation must not be inside for its names to be used
# (F7).
_REAL_SCOPES = frozenset(
    {
        "namespace_definition",
        "class_specifier",
        "struct_specifier",
        "union_specifier",
        "function_definition",
        "linkage_specification",
    }
)


@dataclass(frozen=True)
class Pair:
    """One pair of invocations: an opening and its closing."""

    opening: tuple[int, int]
    """The opening invocation's bytes, ``(start, end)``."""
    closing: tuple[int, int]
    """The closing invocation's bytes, ``(start, end)``."""
    lines: tuple[int, int]
    """The 1-based lines of the opening and of the closing (each stands alone on its
    line, F5): what an entity with no name is placed by."""
    namespaces: tuple[str, ...]
    """The named namespaces the opening opens, outermost first."""


@dataclass(frozen=True)
class MacroScopes:
    """The namespaces a file's in-file namespace macros open, by byte range: what the
    names of the entities between an opening and its closing are prefixed with. Empty
    for a file with none (or one the rules leave unchanged)."""

    pairs: tuple[Pair, ...] = ()

    def namespaces_at(self, name_end: int) -> list[str]:
        """The namespaces around a name that ends at byte ``name_end``, outermost
        first: those of every pair it lies between."""
        return [
            namespace
            for pair in self.pairs
            if pair.opening[1] <= name_end <= pair.closing[0]
            for namespace in pair.namespaces
        ]

    def namespaces_at_line(self, line: int) -> list[str]:
        """The namespaces around an entity with no name (an anonymous namespace) that
        starts on the 1-based ``line``: those of every pair whose opening and closing
        lines are before and after it."""
        return [
            namespace
            for pair in self.pairs
            if pair.lines[0] < line < pair.lines[1]
            for namespace in pair.namespaces
        ]

    def validate(self, tree: Tree) -> MacroScopes:
        """F7: these scopes without every pair whose opening lies inside a real scope of
        ``tree`` (the tree of the prepared text): a namespace, a class, a function, or
        an ``extern`` block that is not another pair's; and without every pair whose
        opening the tree does not read as its block (:func:`_opens_a_block`). Their
        names are not used; their rewrite stays."""
        openings = {pair.opening[0] for pair in self.pairs}
        root = tree.root_node
        kept: list[Pair] = []
        for pair in self.pairs:
            if not _opens_a_block(tree, pair):
                continue
            start = pair.opening[0]
            node = root.descendant_for_byte_range(start, start + 1)
            if node is None:
                continue
            ancestor = node.parent
            # the pair's own block
            if (
                ancestor is not None
                and ancestor.type == "linkage_specification"
                and ancestor.start_byte == start
            ):
                ancestor = ancestor.parent
            inside = False
            while ancestor is not None:
                ours = (
                    ancestor.type == "linkage_specification"
                    and ancestor.start_byte in openings
                )
                if ancestor.type in _REAL_SCOPES and not ours:
                    inside = True
                    break
                ancestor = ancestor.parent
            if not inside:
                kept.append(pair)
        return MacroScopes(tuple(kept))


@dataclass(frozen=True)
class Prepared:
    """A buffer prepared for a C++ parse: the text tree-sitter parses, and the
    namespaces its macros open."""

    parse_text: bytes
    """The buffer, with each used invocation overwritten (same length, F10)."""
    scopes: MacroScopes
    """The namespaces each pair of invocations opens."""


def applies(path: PurePath) -> bool:
    """Whether the namespace macros of a file at ``path`` are read: every C or C++ file
    but a ``.c`` one (F8), which is C."""
    return path.suffix != ".c"


def prepare(source: bytes) -> Prepared:
    """``source`` ready for a C++ parse: unchanged, with no scopes, when it has no
    in-file namespace macro the rules accept."""
    return _rewrite(source, _accepted(source))


def parse(parser: Parser, source: bytes) -> tuple[Tree, MacroScopes]:
    """The one C++ parse of ``source`` with ``parser``: the tree of its
    :func:`prepare`\\ d copy, whose offsets are ``source``'s, and the namespaces its
    macros open, checked against that tree (:meth:`MacroScopes.validate`).

    Every reader of the tree reads ``source``, never the copy. An opening the tree does
    not read as the block it was rewritten to (a macro statement on the line before it,
    ``WARNINGS_PUSH``, makes tree-sitter read ``WARNINGS_PUSH extern"C++"{`` as one
    declaration, and the first function inside is lost) is left as written, and so is
    every pair the parse would then break in turn (:func:`_left_as_written`): the copy
    is made again without them and parsed once more. If a pair still does not read as
    its block, the file is parsed as written, with no macro namespace: at most three
    parses, never a function lost.
    """
    tree, scopes, _ = _parse_macros(parser, source, _left_as_written)
    return tree, scopes


def _parse_macros(
    parser: Parser,
    source: bytes,
    leave: Callable[[bytes, tuple[Pair, ...], set[int]], set[int]],
) -> tuple[Tree, MacroScopes, int]:
    """:func:`parse`'s tree and macro namespaces, and how many parses it took (1, 2,
    or 3 when the file is parsed as written in the end); ``leave`` picks the pairs to
    leave as written once some do not read as blocks (:func:`_left_as_written`)."""
    prepared = prepare(source)
    tree = parser.parse(prepared.parse_text)
    scopes = prepared.scopes
    if not scopes.pairs:
        return tree, scopes, 1
    unread = {
        pair.opening[0] for pair in scopes.pairs if not _opens_a_block(tree, pair)
    }
    if not unread:
        return tree, scopes.validate(tree), 1
    dropped = leave(source, scopes.pairs, unread)
    prepared = _rewrite(
        source, [pair for pair in scopes.pairs if pair.opening[0] not in dropped]
    )
    tree = parser.parse(prepared.parse_text)
    if any(not _opens_a_block(tree, pair) for pair in prepared.scopes.pairs):
        return parser.parse(source), MacroScopes(), 3
    return tree, prepared.scopes.validate(tree), 2


def _left_as_written(
    source: bytes, pairs: tuple[Pair, ...], unread: set[int]
) -> set[int]:
    """The openings of ``pairs`` to leave as written once those in ``unread`` (which
    the tree did not read as blocks) are: those, every pair inside one of them, and
    every pair whose opening follows the opening or the closing of one left as written
    with only whitespace and comments between (written out, that invocation would read
    as the declaration of the next opening's block in turn).

    One pass in file order: whether a pair is left as written depends only on the pairs
    that open before it. Only the nearest preceding invocation of a pair left as
    written can be followed by blanks and comments alone, since any later invocation
    is a word between them.
    """
    dropped: set[int] = set()
    ends: list[int] = []  # the invocation ends of the pairs left as written, sorted
    around: list[Pair] = []  # the pairs left as written still open, outermost first
    for pair in sorted(pairs, key=lambda pair: pair.opening[0]):
        start = pair.opening[0]
        while around and around[-1].closing[0] < start:
            around.pop()
        nearest = bisect.bisect_right(ends, start) - 1
        if (
            start in unread
            or (around and pair.closing[1] <= around[-1].closing[0])
            or (nearest >= 0 and _only_trivia(source, ends[nearest], start))
        ):
            dropped.add(start)
            around.append(pair)
            bisect.insort(ends, pair.opening[1])
            bisect.insort(ends, pair.closing[1])
    return dropped


# What may stand between two invocations for one to follow the other: whitespace (any
# Unicode white space, UTF-8 encoded), backslashes (line splices), ``//`` comments
# (continued over a splice) and block comments (an unclosed one runs to the end).
_TRIVIA = re.compile(
    rb"(?:[ \t\n\r\x0b\x0c\\]"
    rb"|\xc2[\x85\xa0]|\xe1\x9a\x80|\xe2\x80[\x80-\x8a\xa8\xa9\xaf]|\xe2\x81\x9f"
    rb"|\xe3\x80\x80"
    rb"|//(?:\\\r?\n|[^\n])*"
    rb"|/\*[\s\S]*?(?:\*/|\Z))*"
)


def _only_trivia(source: bytes, start: int, end: int) -> bool:
    """Whether ``source[start:end]`` holds only whitespace, line splices and comments
    (read in place, never copied)."""
    found = _TRIVIA.match(source, start, end)
    return found is not None and found.end() == end


def _opens_a_block(tree: Tree, pair: Pair) -> bool:
    """Whether ``tree`` reads ``pair``'s opening as the block it was rewritten to: its
    ``extern`` is the first token of a ``linkage_specification`` starting there. (Not
    that the block ends at the closing: under the error recovery around other macros,
    many real blocks do not.)"""
    start = pair.opening[0]
    token = tree.root_node.descendant_for_byte_range(start, start + 1)
    if token is None or token.type != "extern":
        return False
    block = token.parent
    return (
        block is not None
        and block.type == "linkage_specification"
        and block.start_byte == start
    )


def _accepted(source: bytes) -> list[Pair]:
    """The pairs the rules accept in ``source`` and that are to be rewritten: none when
    the file is to be read as written."""
    if not _worth_lexing(source):
        return []
    pairs = _pairs(_scan(source), source)
    if pairs is None:
        return []
    # An opening shorter than the rewrite is left as written, with its closing (see the
    # module docs), and so is every pair inside it: a pair rewritten inside one left as
    # written reads as the macro statement's declaration and breaks the first function
    # in it.
    short = [pair for pair in pairs if pair.opening[1] - pair.opening[0] < len(OPENING)]
    return [
        pair
        for pair in pairs
        if pair.opening[1] - pair.opening[0] >= len(OPENING)
        and not any(
            outer.opening[1] <= pair.opening[0] and pair.closing[1] <= outer.closing[0]
            for outer in short
        )
    ]


def _rewrite(source: bytes, pairs: list[Pair]) -> Prepared:
    """``source`` with ``pairs`` rewritten; ``source`` itself, with no scopes, when
    there is none."""
    if not pairs:
        return Prepared(source, MacroScopes())
    copy = bytearray(source)
    for pair in pairs:
        for (start, end), with_ in ((pair.opening, OPENING), (pair.closing, CLOSING)):
            copy[start:end] = with_.ljust(end - start)[: end - start]
    parse_text = bytes(copy)
    if len(parse_text) != len(source):  # F10, which the slices above keep
        msg = "the parsed copy of a C++ file must have the file's length"
        raise ValueError(msg)
    return Prepared(parse_text, MacroScopes(tuple(pairs)))


_DEFINE_LINE = re.compile(rb"(?m)^[ \t\r\x0b\x0c]*#[^\n]*define")


def _worth_lexing(source: bytes) -> bool:
    """F9: a buffer with no ``namespace``, or no line starting with ``#`` that holds
    ``define``, has no namespace macro."""
    return b"namespace" in source and _DEFINE_LINE.search(source) is not None


# ---------------------------------------------------------------------------
# The lexer: logical lines of tokens, comments, strings and splices handled
# ---------------------------------------------------------------------------

_WORD, _LITERAL, _PUNCT = 0, 1, 2

# One token: its kind and its bytes in the buffer, ``(kind, start, end)``.
_Token = tuple[int, int, int]

_TOKEN = re.compile(
    rb"(?P<splice>\\\r?\n)"
    rb"|(?P<newline>\n)"
    rb"|(?P<space>[ \t\r\x0c]+)"
    rb"|(?P<line_comment>//(?:\\\r?\n|[^\n])*)"
    rb"|(?P<block_comment>/\*)"
    rb"|(?P<quote>[\"'])"
    rb"|(?P<word>[A-Za-z_][A-Za-z0-9_]*)"
    # a pp-number, digit separators (``1'000``) and exponents included
    rb"|(?P<number>(?:[0-9]|\.[0-9])(?:[eEpP][+-]|[A-Za-z0-9_.'])*)"
    rb"|(?P<scope>::)"
    # one character, whole (a non-ASCII one is a punctuation here)
    rb"|(?P<punct>[\x00-\x7f]|[\xc0-\xff][\x80-\xbf]*|[\x80-\xbf])"
)

# A string or character literal: past its closing quote, or up to the end of its line
# when it has none (an escaped line break does not end it).
_QUOTED = {
    ord('"'): re.compile(rb'"(?:\\[\s\S]?|[^"\\\n])*"?'),
    ord("'"): re.compile(rb"'(?:\\[\s\S]?|[^'\\\n])*'?"),
}

# A raw string literal's prefixes, and a string or character literal's.
_RAW_PREFIXES = frozenset({b"R", b"LR", b"uR", b"UR", b"u8R"})
_PREFIXES = frozenset({b"L", b"u", b"U", b"u8"})


def _quoted(source: bytes, at: int) -> int:
    """Where the string or character literal opening at ``at`` ends."""
    found = _QUOTED[source[at]].match(source, at)
    return found.end() if found is not None else len(source)


def _raw_string(source: bytes, at: int) -> int:
    """Where the raw string whose ``"`` is at ``at`` ends: past ``)delimiter"``."""
    open_at = source.find(b"(", at)
    if open_at < 0:
        return _quoted(source, at)
    delimiter = source[at + 1 : open_at]
    if len(delimiter) > 16 or re.search(rb"[ \t\n\r\x0c]", delimiter):
        return _quoted(source, at)
    closing = b")" + delimiter + b'"'
    end = source.find(closing, open_at + 1)
    return len(source) if end < 0 else end + len(closing)


def _logical_lines(source: bytes) -> list[list[_Token]]:
    """The logical lines of ``source``: lines joined at their ``\\``-newline splices,
    each as its tokens; comments are left out, and a block comment or a raw string
    spanning lines joins them (no line break is inside one)."""
    lines: list[list[_Token]] = []
    line: list[_Token] = []
    at = 0
    size = len(source)
    while at < size:
        token = _TOKEN.match(source, at)
        if token is None:  # the last alternative matches every byte
            break
        kind = token.lastgroup
        end = token.end()
        if kind == "newline":
            lines.append(line)
            line = []
        elif kind == "block_comment":
            found = source.find(b"*/", at + 2)
            end = size if found < 0 else found + 2
        elif kind == "quote":
            end = _quoted(source, at)
            line.append((_LITERAL, at, end))
        elif kind == "word":
            word = source[at:end]
            if end < size and source[end] == ord('"') and word in _RAW_PREFIXES:
                end = _raw_string(source, end)
                line.append((_LITERAL, at, end))
            elif end < size and source[end] in _QUOTED and word in _PREFIXES:
                end = _quoted(source, end)
                line.append((_LITERAL, at, end))
            else:
                line.append((_WORD, at, end))
        elif kind == "number":
            line.append((_LITERAL, at, end))
        elif kind in ("scope", "punct"):
            line.append((_PUNCT, at, end))
        at = end
    lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Opening:
    """A body that opens these named namespaces (outermost first), with this many
    braces."""

    named: tuple[str, ...]
    braces: int


@dataclass(frozen=True)
class _Closing:
    """A body that closes this many braces."""

    braces: int


_Body = _Opening | _Closing


@dataclass
class _Scan:
    """What the lexer found of the macros of a file."""

    definitions: dict[str, list[tuple[int, _Body | None]]]
    """Every object-like ``#define``: the name's definitions, in order, with their
    start and what each body does (``None``: neither)."""
    defined: set[str]
    """Every name ``#define``\\ d in the file, function-like ones included."""
    undefinitions: dict[str, list[int]]
    """The start of each ``#undef`` of a name."""
    alone: list[tuple[tuple[int, int], str]]
    """Every logical line of code that is one word alone: its bytes and the word."""
    used: set[str]
    """Every word of code on a line with more than that word: a macro name among them
    is used other than alone (F5), and is not read."""


def _scan(source: bytes) -> _Scan:
    """The macros, their definitions and the lines that may invoke them."""
    found = _Scan({}, set(), {}, [], set())

    def text(token: _Token) -> str:
        return source[token[1] : token[2]].decode("utf-8", "replace")

    for line in _logical_lines(source):
        directive = bool(line) and text(line[0]) == "#"
        if not directive and len(line) > 1:
            found.used.update(text(token) for token in line if token[0] == _WORD)
        if (
            len(line) >= 3
            and text(line[0]) == "#"
            and line[1][0] == _WORD
            and line[2][0] == _WORD
        ):
            hash_, keyword, name, *body = line
            name_text = text(name)
            if text(keyword) == "define":
                found.defined.add(name_text)
                function_like = bool(body) and (
                    text(body[0]) == "(" and body[0][1] == name[2]
                )
                if not function_like:
                    found.definitions.setdefault(name_text, []).append(
                        (hash_[1], _classify([text(token) for token in body]))
                    )
            elif text(keyword) == "undef":
                found.undefinitions.setdefault(name_text, []).append(hash_[1])
        elif len(line) == 1 and line[0][0] == _WORD and not directive:
            found.alone.append(((line[0][1], line[0][2]), text(line[0])))
    return found


def _classify(tokens: list[str]) -> _Body | None:
    """What a macro body of these tokens does (F2), ``None`` when it is neither an
    opening nor a closing."""
    if not tokens:
        return None
    if all(token == "}" for token in tokens):
        return _Closing(len(tokens))
    named: list[str] = []
    braces = at = 0
    size = len(tokens)
    while at < size:
        inline = tokens[at] == "inline"
        if inline:
            at += 1
        if at >= size or tokens[at] != "namespace":
            return None
        at += 1
        if inline:
            # its name is left out of every name: anything but a brace or ``;``
            while at < size and tokens[at] not in ("{", "}", ";"):
                at += 1
        else:
            # ``a`` or ``a::b``: an anonymous namespace is not accepted
            while True:
                if at >= size or not _is_namespace_name(tokens[at]):
                    return None
                named.append(tokens[at])
                at += 1
                if at >= size or tokens[at] != "::":
                    break
                at += 1
        if at >= size or tokens[at] != "{":
            return None
        at += 1
        braces += 1
    return _Opening(tuple(named), braces)


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ALL_CAPITALS = re.compile(r"[A-Z0-9_]*")


def _is_namespace_name(word: str) -> bool:
    """A name a namespace macro may open: an identifier, not a keyword the syntax could
    take for something else, and not all capitals (``NS``, which looks like a macro of
    its own)."""
    return (
        _IDENTIFIER.fullmatch(word) is not None
        and word not in ("inline", "namespace")
        and _ALL_CAPITALS.fullmatch(word) is None
    )


_NEWLINE = re.compile(rb"\n")


def _line_of(breaks: list[int], at: int) -> int:
    """The 1-based line of the byte ``at``, from the offsets of the buffer's line
    breaks, in order."""
    return bisect.bisect_left(breaks, at) + 1


def _pairs(scan: _Scan, source: bytes) -> list[Pair] | None:
    """The pairs of invocations the rules accept (F3, F4, F6), in file order of their
    openings; ``None`` when the file is to be left unchanged (F6)."""
    # F3, F2's ``#define``d namespace names, F4: the names that may be used
    bodies: dict[str, _Body] = {}
    for name, definitions in scan.definitions.items():
        first, body = definitions[0]
        if body is None or any(other != body for _, other in definitions):
            continue
        if isinstance(body, _Opening) and any(
            part in scan.defined for part in body.named
        ):
            continue
        if name in scan.used:
            continue
        undefinitions = scan.undefinitions.get(name, [])
        misplaced = any(
            word == name
            and (start < first or any(undef < start for undef in undefinitions))
            for (start, _), word in scan.alone
        )
        if not misplaced:
            bodies[name] = body
    if not bodies:
        return None
    # F6
    breaks = [newline.start() for newline in _NEWLINE.finditer(source)]
    open_: list[tuple[tuple[int, int], _Opening]] = []
    found: list[Pair] = []
    for invocation, word in scan.alone:
        body = bodies.get(word)
        if isinstance(body, _Opening):
            open_.append((invocation, body))
        elif isinstance(body, _Closing):
            if not open_:
                return None
            opening, opened = open_.pop()
            if opened.braces != body.braces:
                return None
            found.append(
                Pair(
                    opening=opening,
                    closing=invocation,
                    lines=(
                        _line_of(breaks, opening[0]),
                        _line_of(breaks, invocation[0]),
                    ),
                    namespaces=opened.named,
                )
            )
    if open_ or not found:
        return None
    return sorted(found, key=lambda pair: pair.opening[0])
