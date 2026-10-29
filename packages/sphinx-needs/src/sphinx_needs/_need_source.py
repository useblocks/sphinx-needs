"""Where a need's text came from: its source, as a list of hops.

**Provisional.** Every ``NeedItemSource*`` class of :mod:`sphinx_needs.need_item` carries
``hops``, innermost first: ``hops[0]`` is where the text is written, and the last hop
with a ``document`` is the page the need is placed on (its *placement*, a role rather
than a hop kind). The legacy location keys of a need -- ``docname``, ``lineno``,
``lineno_content``, ``is_import``, ``is_external``, ``external_url`` -- are computed from
the hops plus a few stored legacy facts, and are unchanged. Nothing here is re-exported
from a public module, and the shape may change in a minor release until it reaches
``needs.json``.

This module holds the hop types and what the source classes and the producers share:
the placement lookup, the builders of a directive's hops, the doctree walk that finds the
placement's semantic location, and the projection of that location onto the legacy
``sections`` and ``signature``. It never imports :mod:`sphinx_needs.need_item`, which
imports it.

A hop's ``start_line`` / ``end_line`` is recorded only where it is a true 1-based line of
that hop's file, the end inclusive; everywhere else it is ``None``. Every path is POSIX
and relative to the Sphinx source directory (the one root, ``"srcdir"``), with ``..`` for
a file outside it.
"""

from __future__ import annotations

import copy
import dataclasses
import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import TYPE_CHECKING, Final

from docutils import nodes
from docutils.parsers.rst.states import RSTState
from docutils.statemachine import string2lines
from sphinx import addnodes

if TYPE_CHECKING:
    from typing import Self

    from sphinx.environment import BuildEnvironment
    from sphinx.util.docutils import SphinxDirective

SRCDIR_ROOT: Final = "srcdir"
"""The key of the one root slice 1 has: the Sphinx source directory."""

NON_BREAKING_SPACE: Final = re.compile("\xa0+")
"""What auto-numbered section titles carry, replaced by one space (as the legacy walk does)."""

_DOCSTRING_OF: Final = "docstring of "
"""What autodoc puts in the source of a docstring: ``<file>:docstring of <object>``."""


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedSourcePhysical:
    """Where a hop's text physically is: a file under a named root, or a URL.

    **Provisional**: it may change without a deprecation until it reaches
    ``needs.json``.
    """

    root: str | None = None
    """The key of the root ``path`` is relative to: ``"srcdir"``, the Sphinx source
    directory."""
    path: str | None = None
    """POSIX, relative to ``root``, with ``..`` for a file outside it."""
    url: str | None = None
    """For a file that is not on this machine: a downloaded ``needs.json``, the page of
    an external need."""
    start_line: int | None = None
    """1-based; recorded only where it is a true line of the file."""
    end_line: int | None = None
    """1-based and inclusive; recorded only where it is a true line of the file."""


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedSourceSemantic:
    """One entry of a hop's semantic location: a section, a domain object, a service.

    **Provisional**: it may change without a deprecation until it reaches
    ``needs.json``.
    """

    kind: str
    """What the entry is: ``"section"``, ``"<domain>:<objtype>"`` (``"py:method"``),
    ``"service"``, ``"py:docstring"``; it describes the entry, the name identifies it."""
    name: str
    extras: tuple[tuple[str, str], ...] = ()
    """Identity-bearing extras, e.g. ``("id", <the first signature id>)``."""


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedSourceHop:
    """One place a need's text passed through.

    **Provisional**: it may change without a deprecation until it reaches
    ``needs.json``.
    """

    kind: str
    """``"page"``, ``"file"``, ``"code"``, ``"external"``, ``"generated"`` (the
    vocabulary is open)."""
    origin: str | None = None
    """A key into a registry of origins (a repository, a test run); ``None`` for now."""
    physical: NeedSourcePhysical | None = None
    semantic: tuple[NeedSourceSemantic, ...] | None = None
    """Outermost to innermost; ``None`` until it is determined (the placement's, until
    the doctree has been read)."""
    document: str | None = None
    """The docname, on the hop of a page the need is placed on."""
    language: str | None = None
    """The file's suffix: ``".rst"``, ``".md"``, ``".json"``, ``".py"``."""


def placement_index(hops: tuple[NeedSourceHop, ...]) -> int | None:
    """The index of the placement: the last hop with a ``document``."""
    for index in range(len(hops) - 1, -1, -1):
        if hops[index].document is not None:
            return index
    return None


def placement_of(hops: tuple[NeedSourceHop, ...]) -> NeedSourceHop | None:
    """The placement hop, or ``None`` if no hop has a ``document``."""
    index = placement_index(hops)
    return None if index is None else hops[index]


def first_line(hops: tuple[NeedSourceHop, ...]) -> int | None:
    """The start line of ``hops[0]``, where it has one."""
    if hops and (physical := hops[0].physical) is not None:
        return physical.start_line
    return None


def checked_hops(hops: Iterable[NeedSourceHop]) -> tuple[NeedSourceHop, ...]:
    """``hops`` as a tuple, each one a :class:`NeedSourceHop`.

    :raises TypeError: if one is not.
    """
    result = tuple(hops)
    for hop in result:
        if not isinstance(hop, NeedSourceHop):
            raise TypeError(f"a hop must be a NeedSourceHop, not {hop!r}")
    return result


class HopsSource:
    """What every source class with hops shares: the placement, and the one way to
    replace the hops (the doctree walk's, through ``NeedItem._set_placement_semantic``).

    A base class rather than a protocol: :class:`~sphinx_needs.need_item.NeedItem`
    tests for it, and a third party's source, which obeys only
    ``NeedItemSourceProtocol``, has no hops.
    """

    __slots__ = ()

    hops: tuple[NeedSourceHop, ...]

    @property
    def placement(self) -> NeedSourceHop | None:
        """The hop of the page the need is placed on: the last hop with a ``document``.

        **Provisional**, as ``hops`` is.
        """
        return placement_of(self.hops)

    def _with_placement_semantic(
        self, semantic: tuple[NeedSourceSemantic, ...]
    ) -> Self:
        """A copy of this source whose placement hop has ``semantic``.

        :raises ValueError: if there is no placement, or its semantic location is
            already set: it is written once per need.
        """
        index = placement_index(self.hops)
        if index is None:
            raise ValueError("the source has no placement hop")
        hop = self.hops[index]
        if hop.semantic is not None:
            raise ValueError(
                "the semantic location of the placement hop is already set"
            )
        hops = (
            *self.hops[:index],
            dataclasses.replace(hop, semantic=semantic),
            *self.hops[index + 1 :],
        )
        new = copy.copy(self)
        object.__setattr__(new, "hops", hops)
        return new


def physical_for(
    srcdir: str | os.PathLike[str],
    path: str | os.PathLike[str],
    start_line: int | None = None,
    end_line: int | None = None,
) -> NeedSourcePhysical | None:
    """A file's physical location under the ``"srcdir"`` root.

    The path is POSIX and relative to ``srcdir``, with ``..`` for a file outside it;
    ``None`` where no relative path exists (another drive, on Windows).
    """
    try:
        relative = os.path.relpath(os.path.abspath(path), os.path.abspath(srcdir))
    except ValueError:
        return None
    return NeedSourcePhysical(
        root=SRCDIR_ROOT,
        path=PurePath(relative).as_posix(),
        start_line=start_line,
        end_line=end_line,
    )


def _suffix(path: str | os.PathLike[str]) -> str | None:
    return os.path.splitext(path)[1] or None


LineCheck = Callable[[Sequence[str], int, int | None], bool]
"""Whether a file's lines (``lines[0]`` is line 1) hold the text at ``start..end``."""

_LINES_KEY: Final = "sphinx_needs_source_hop_lines"
"""The key of the file lines read for the document being read, in ``env.temp_data``
(which Sphinx clears after each document, so nothing outlives the read)."""


def _file_lines(env: BuildEnvironment, path: str, tab_width: int) -> list[str] | None:
    """The lines of a file as docutils numbers them, read once per document.

    Read with the project's ``source_encoding`` and split by docutils' own
    ``string2lines`` (form feeds and vertical tabs become spaces, tabs are expanded
    at the document's ``tab_width``), so that line *n* here is the line *n* the parser
    numbers. ``None`` if the file cannot be read.
    """
    cache: dict[tuple[str, int], list[str] | None] = env.temp_data.setdefault(
        _LINES_KEY, {}
    )
    key = (os.path.abspath(path), tab_width)
    if key not in cache:
        try:
            with open(key[0], encoding=env.config.source_encoding) as stream:
                text = stream.read()
        except (OSError, UnicodeDecodeError, LookupError):
            cache[key] = None
        else:
            cache[key] = string2lines(
                text, tab_width=tab_width, convert_whitespace=True
            )
    return cache[key]


def _checked_lines(
    env: BuildEnvironment,
    path: str,
    start_line: int | None,
    end_line: int | None,
    check: LineCheck,
    tab_width: int,
) -> tuple[int | None, int | None]:
    """``(start_line, end_line)`` if the file holds the text there, else ``(None, None)``.

    The line a parser reports is the line of what it was handed, which is not the
    file's wherever the text was changed on the way: an include's ``:start-after:`` or
    ``:start-line:``, a ``source-read`` handler, myst-parser's nested colon fences. So a
    line is recorded only where the file, read from disk, holds the text there, by the
    producer's ``check``.
    """
    if not start_line:
        return None, None
    lines = _file_lines(env, path, tab_width)
    if lines is None or not check(lines, start_line, end_line):
        return None, None
    return start_line, end_line


_LIST_MARKERS: Final = re.compile(r"((?:[-*+]|#\.|\d+[.)]|\(\d+\))\s+)+")
"""Bullets and enumerators before a directive that opens a list item (``- .. req::``,
a list table's ``* - .. req::``)."""


def _normalised(line: str) -> str:
    """A file line as the parser hands its text on: stripped, and without a MyST block
    quote's leading ``>`` or a grid-table cell's ``|`` borders, where the line has them."""
    text = line.strip()
    while text.startswith(">"):
        text = text[1:].strip()
    if text.startswith("|"):
        text = text[1:].strip()
        if text.endswith("|"):
            text = text[:-1].strip()
    return text


def block_check(block_text: str) -> LineCheck:
    """The check of a docutils directive: each non-blank line of its block, stripped,
    EQUALS the file's line it is numbered at, normalised (:func:`_normalised`); its first
    line may also follow the bullets or enumerators of the list item it opens.

    Whole lines, never a part of one: a line that only contains the text (``:id: A``
    in ``:id: AB``) does not hold it.
    """
    block = [line.strip() for line in block_text.rstrip().splitlines()]

    def check(lines: Sequence[str], start: int, end: int | None) -> bool:
        if start + len(block) - 1 > len(lines):
            return False
        for index, text in enumerate(block):
            if not text:
                continue
            line = _normalised(lines[start - 1 + index])
            if line != text and not (
                index == 0
                and _LIST_MARKERS.sub("", line, count=1) == text
                and _LIST_MARKERS.match(line)
            ):
                return False
        return True

    return check


def fence_check(name: str, argument: str) -> LineCheck:
    """The check of a myst-parser directive (myst-parser hands a directive its content
    only, not its fence): the start line, normalised (:func:`_normalised`), opens a
    fence of the directive -- backticks, tildes or colons, then ``{name}`` -- followed
    by exactly its argument (the title, as the directive received it), whitespace
    collapsed.

    A need nested at once inside a need of the same name and the same title cannot be
    told from it: that is a known gap.
    """
    pattern = re.compile(rf"(`{{3,}}|~{{3,}}|:{{3,}})\s*\{{{re.escape(name)}\}}(.*)")
    expected = " ".join(argument.split())

    def check(lines: Sequence[str], start: int, end: int | None) -> bool:
        if start > len(lines):
            return False
        match = pattern.fullmatch(_normalised(lines[start - 1]))
        return match is not None and " ".join(match.group(2).split()) == expected

    return check


def item_check(first: str, last: str) -> LineCheck:
    """The check of a ``list2need`` item: its first and its last line, stripped, EQUAL
    the file's lines they are numbered at, normalised (:func:`_normalised`)."""
    first, last = first.strip(), last.strip()

    def check(lines: Sequence[str], start: int, end: int | None) -> bool:
        if start > len(lines) or _normalised(lines[start - 1]) != first:
            return False
        return end is None or (
            end <= len(lines) and _normalised(lines[end - 1]) == last
        )

    return check


def located_hops(
    env: BuildEnvironment,
    docname: str,
    source: str | None,
    start_line: int | None,
    end_line: int | None = None,
    *,
    check: LineCheck,
    tab_width: int,
    fragment_lines: bool,
    first: NeedSourceHop | None = None,
) -> tuple[NeedSourceHop, ...]:
    """The hops of text written at ``source:start_line`` and placed on ``docname``.

    :param source: The file the text is written in, as ``get_source_info()`` gives it
        (relative to the working directory, for an included file), or ``None``.
    :param start_line: Its 1-based line there, as the parser reports it.
    :param end_line: The last line of the text, as the parser reports it.
    :param check: Whether the file's lines hold the text at ``start_line..end_line``:
        the lines are recorded only if they do (:func:`_checked_lines`).
    :param tab_width: The document's ``tab_width``, which the file is read with.
    :param fragment_lines: Whether the lines are true in an included file too. They are
        under docutils; myst-parser reports an included file's lines one late, so a
        hop of an included file takes no line there.
    :param first: A hop before the file, if any: an imported ``needs.json``, the
        service that made the need.
    :return: ``[first], file, page`` for text in an included file (the page hop then
        has no line: the ``include`` line is not recoverable), ``[first], page``
        otherwise. A docstring (autodoc) is a ``code`` hop of the Python file, with no
        line: the one autodoc gives counts from the docstring, not the file.
    """
    srcdir = env.srcdir
    host = os.path.abspath(env.doc2path(docname))
    hops: list[NeedSourceHop] = [] if first is None else [first]

    def page(start: int | None = None, end: int | None = None) -> NeedSourceHop:
        return NeedSourceHop(
            kind="page",
            document=docname,
            physical=physical_for(srcdir, host, start, end),
            language=_suffix(host),
        )

    if not source or not start_line:
        # the state machine could not map the line (``get_source_info`` gives
        # ``(None, None)``)
        hops.append(page())
    elif _DOCSTRING_OF in source:
        file, _, name = source.partition(_DOCSTRING_OF)
        file = file.removesuffix(":")
        hops.append(
            NeedSourceHop(
                kind="code",
                physical=physical_for(srcdir, file) if file else None,
                semantic=(NeedSourceSemantic(kind="py:docstring", name=name),),
                language=_suffix(file) if file else None,
            )
        )
        hops.append(page())
    elif os.path.abspath(source) == host:
        hops.append(
            page(*_checked_lines(env, host, start_line, end_line, check, tab_width))
        )
    elif os.path.isfile(source):
        lines = (
            _checked_lines(env, source, start_line, end_line, check, tab_width)
            if fragment_lines
            else (None, None)
        )
        hops.append(
            NeedSourceHop(
                kind="file",
                physical=physical_for(srcdir, source, *lines),
                language=_suffix(source),
            )
        )
        hops.append(page())
    else:
        # a source that names no file (generated text): no line is a true one
        hops.append(page())
    return tuple(hops)


def document_tab_width(state: object) -> int:
    """The ``tab_width`` of the document a parser state is reading (docutils' 8 by
    default)."""
    document = getattr(state, "document", None)
    return getattr(getattr(document, "settings", None), "tab_width", 8)


def directive_hops(
    directive: SphinxDirective, *, first: NeedSourceHop | None = None
) -> tuple[NeedSourceHop, ...]:
    """The hops of the text of ``directive``, placed on the document being read.

    Under docutils the end line is the last non-blank line of the directive's block,
    and the lines are recorded where the file holds the block there
    (:func:`block_check`, whole lines). myst-parser hands a directive its content only,
    so there the end line is ``None``, and the start line is recorded where the file
    opens the directive's fence there, with its name and its title
    (:func:`fence_check`).
    """
    source, start_line = directive.get_source_info()
    rst = isinstance(directive.state, RSTState)
    end_line = None
    if rst and start_line:
        length = len(directive.block_text.rstrip().splitlines())
        end_line = start_line + max(length, 1) - 1
    return located_hops(
        directive.env,
        directive.env.docname,
        source,
        start_line,
        end_line,
        check=block_check(directive.block_text)
        if rst
        else fence_check(directive.name, " ".join(directive.arguments)),
        tab_width=document_tab_width(directive.state),
        fragment_lines=rst,
        first=first,
    )


def placement_semantic(need_node: nodes.Node) -> tuple[NeedSourceSemantic, ...]:
    """The semantic location of a need node in its doctree, outermost to innermost.

    The section chain and the domain objects (``desc`` nodes) above the node, in their
    nesting order. A domain object is ``"<domain>:<objtype>"`` named by the last of its
    first signature's ``_toc_parts`` (else its ``desc_name`` text), with that
    signature's first id as an ``("id", …)`` extra where it has one. Where the legacy
    ``signature`` rule reads a name at that object (:func:`legacy_signature_text`, the
    last ``desc_name`` of the first signature that has one), the entry carries it as a
    ``("signature", …)`` extra, which is what :func:`project_legacy` reads.

    Signatures are read only under an ``addnodes.desc``: a ``desc_signature`` an
    extension places outside one is read by the legacy walk and not by this one.

    Computed from the doctree alone, independently of the legacy walk
    (``get_sections_and_signature_and_needs``), so that the fence comparing the two
    is not a tautology.
    """
    inner_first: list[NeedSourceSemantic] = []
    child: nodes.Node = need_node
    parent = child.parent
    while parent is not None:
        if isinstance(parent, addnodes.desc) and not isinstance(
            child, addnodes.desc_signature
        ):
            inner_first.append(_domain_entry(parent, child))
        if isinstance(parent, nodes.section):
            title = NON_BREAKING_SPACE.sub(" ", parent.children[0].astext())
            inner_first.append(NeedSourceSemantic(kind="section", name=title))
        child, parent = parent, parent.parent
    return tuple(reversed(inner_first))


def _domain_entry(node: addnodes.desc, below: nodes.Node) -> NeedSourceSemantic:
    """The entry of a domain object, from the signatures before ``below``."""
    signatures: list[addnodes.desc_signature] = []
    for child in node.children:
        if child is below:
            break
        if isinstance(child, addnodes.desc_signature):
            signatures.append(child)
    name = ""
    extras: list[tuple[str, str]] = []
    if signatures:
        first = signatures[0]
        toc_parts = first.get("_toc_parts")
        if toc_parts:
            name = str(toc_parts[-1])
        elif (
            desc_name := next(iter(first.findall(addnodes.desc_name)), None)
        ) is not None:
            name = desc_name.astext()
        if ids := first.get("ids"):
            extras.append(("id", str(ids[0])))
    legacy: str | None = None
    for signature in signatures:
        for part in _signature_parts(signature):
            if (
                isinstance(part, addnodes.desc_name)
                and (text := legacy_signature_text(part)) is not None
            ):
                legacy = text
        if legacy:
            break
    if legacy:
        extras.append(("signature", legacy))
    return NeedSourceSemantic(
        kind=f"{node.get('domain', '')}:{node.get('objtype', '')}",
        name=name,
        extras=tuple(extras),
    )


def legacy_signature_text(desc_name: addnodes.desc_name) -> str | None:
    """The name the legacy ``signature`` reads from a ``desc_name``, if it reads one.

    The legacy rule (``get_sections_and_signature_and_needs``), held here for the walk:
    the ``desc_name``'s first child when it is text (even an empty one, which
    overwrites, as the legacy walk's does); otherwise its text, as the c, cpp and js
    domains write it (a ``desc_sig_name`` inside); an empty name is no name. Which
    ``desc_name`` it is asked about is :func:`_signature_parts`' part of the rule: a
    change to the legacy rule changes both, and the fence holds them together.
    """
    if desc_name.children and isinstance(desc_name.children[0], nodes.Text):
        return str(desc_name.children[0])
    if text := desc_name.astext():
        return text
    return None


def _signature_parts(signature: addnodes.desc_signature) -> Iterator[nodes.Node]:
    """The children of a signature, a ``desc_signature_line``'s in its place.

    The c and cpp domains put the ``desc_name`` in a ``desc_signature_line``, which the
    legacy walk descends into.
    """
    for child in signature.children:
        if isinstance(child, addnodes.desc_signature_line):
            yield from child.children
        else:
            yield child


def project_legacy(
    semantic: tuple[NeedSourceSemantic, ...],
) -> tuple[tuple[str, ...], str | None]:
    """The legacy ``sections`` (innermost first) and ``signature`` of a semantic list.

    ``signature`` is the ``("signature", …)`` extra of the innermost domain object
    that has one, as the legacy walk reads the innermost signature it can.
    """
    sections = tuple(
        entry.name for entry in reversed(semantic) if entry.kind == "section"
    )
    signature = None
    for entry in reversed(semantic):
        if entry.kind != "section" and (value := dict(entry.extras).get("signature")):
            signature = value
            break
    return sections, signature
