"""Parse a C/C++ TU via libclang and yield ACTIVE comment tokens only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sphinx_codelinks.analyse.preproc import loader
from sphinx_codelinks.analyse.preproc.headers import (
    Contribution,
    SkippedSpan,
    contribution,
    lexical,
    wholly_skipped,
)
from sphinx_codelinks.analyse.preproc.loader import SkippedRange


@dataclass
class _Point:
    row: int


class LibclangComment:
    """Minimal stand-in for a tree-sitter comment node.

    Exposes exactly the two attributes the existing extract_* chain reads:
    ``.text`` (bytes) and ``.start_point.row`` (0-indexed). ``is_libclang``
    lets extract_marked_content skip tree-sitter scope association.
    """

    is_libclang = True

    def __init__(self, text: bytes, row: int, column: int = 0) -> None:
        self.text: bytes = text
        self.start_point = _Point(row)
        # The column, in characters, at which the comment starts on its line.
        self.column: int = column


def _main_file_skipped(skipped: list[SkippedRange]) -> list[tuple[int, int]]:
    """The line spans the main file's own pass through the preprocessor skipped.

    The translation unit's skipped ranges are every pass's, and a file its own
    include chain enters again (a guarded header whose includes include it back,
    a file that includes itself) passes through a second time, which skips the
    guarded body the first pass compiled: the union of both covers the whole
    file. So only the main file's own pass decides, selected by where a range
    starts (``clang_Location_isFromMainFile``), never by its path, which a later
    inclusion of the main file shares. The ranges of every other file go too:
    only the main file's comments are read.

    A file read through a translation unit that includes it is the other case:
    there its first inclusion's pass decides (:func:`extract_included_active_comments`).
    """
    return [(sr.start_line, sr.end_line) for sr in skipped if sr.from_main_file]


def _is_in_skipped(line: int, skipped: list[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in skipped)


def parse_translation_unit(file_path: Path, args: list[str]) -> Any:
    """Parse ``file_path`` as a translation unit with ``args``.

    :raises clang.cindex.TranslationUnitLoadError: libclang could not load it; the
        error says why (:func:`.loader.parse_error`).
    """
    return loader.parse_translation_unit(file_path, args, loader.PARSE_OPTIONS)


# @Drop comments inside inactive preprocessor branches, IMPL_PREPROC_2, impl, [FE_PREPROC]
def extract_active_comments(
    file_path: Path,
    args: list[str],
    on_parse: Callable[[Any], None] | None = None,
    *,
    as_written: bool = False,
) -> list[LibclangComment]:
    """Return one LibclangComment per ACTIVE comment token in ``file_path``.

    Comments inside the ranges the file's own pass through the preprocessor
    skipped (its inactive branches) are dropped; what a later pass through the
    same file skips is not (see :func:`_main_file_skipped`).

    :param on_parse: Called with the translation unit once it is parsed (to read
        its diagnostics).
    :param as_written: The file's target is unknown: no range is skipped, every
        comment is returned, the file as written.
    """
    tu = parse_translation_unit(file_path, args)
    if on_parse is not None:
        on_parse(tu)
    skipped = (
        [] if as_written else _main_file_skipped(loader.get_all_skipped_ranges(tu))
    )
    return _active_comments(tu, file_path, skipped)


def main_file_inclusions(tu: Any, working_directory: Path) -> set[Path]:
    """The files the translation unit's main file itself ``#include``s, canonical.

    libclang names a file found through a relative include directory relative to
    the unit's working directory, so a relative name is taken against
    ``working_directory`` (the ``-working-directory`` it was parsed with).

    Read from the inclusion directives of the parse, so an ``#include`` in a branch
    the preprocessor skipped (``#if 0``) or in a comment is not one; an include of a
    file the parse did not find is not one either. Directives of included files are
    not the main file's (``clang_Location_isFromMainFile``).
    """
    cx = loader.load_clang_cindex()
    loader._bind()
    is_from_main = cx.conf.lib.clang_Location_isFromMainFile
    out: set[Path] = set()
    for cursor in tu.cursor.get_children():
        if cursor.kind != cx.CursorKind.INCLUSION_DIRECTIVE:
            continue
        if not is_from_main(cursor.location):
            continue
        included = loader.included_file(cursor)
        if included is None:
            continue  # an include libclang could not find names no file
        out.add((working_directory / included).resolve())
    return out


def included_files(
    tu: Any,
    working_directory: Path,
    starts: dict[tuple[int, int, int], Any] | None = None,
) -> set[Path]:
    """Every file the unit included, at any depth, that is not a system header,
    canonical: what the unit's preprocessing read besides its main file.

    A relative name (a file found through a relative include directory) is taken
    against ``working_directory``, as in :func:`main_file_inclusions`.

    :param starts: :func:`unit_starts` of ``tu``, if the caller has them.
    """
    included = [i.include for i in tu.get_includes() if i.include is not None]
    if starts is None:
        starts = loader.entry_starts(tu, included)
    # each file's answer, once: asked at the start of its (first) entry, as clang's
    # characteristic of a file can change within it (``#pragma GCC system_header``, a
    # line marker); a file entered once has the start made, every other one looks it up
    system: dict[tuple[int, int, int], bool] = {}
    out: set[Path] = set()
    for file in included:
        key = loader.file_id(file)
        if key is not None and key in system:
            in_system = system[key]
        else:
            start = starts.get(key) if key is not None else None
            if start is None:
                start = loader.looked_up(tu, file, offset=0)
            in_system = bool(start.is_in_system_header)
            if key is not None:
                system[key] = in_system
        if in_system:
            continue
        out.add((working_directory / file.name).resolve())
    return out


def unit_starts(tu: Any) -> dict[tuple[int, int, int], Any]:
    """:func:`.loader.entry_starts` of every file ``tu`` includes, computed once for a
    unit that is asked about many (:func:`included_files`) and reads several
    (:func:`extract_included_active_comments`). Valid while ``tu`` lives."""
    return loader.entry_starts(
        tu, [i.include for i in tu.get_includes() if i.include is not None]
    )


def starts_of(tu: Any, paths: list[Path]) -> dict[tuple[int, int, int], Any]:
    """:func:`.loader.entry_starts` of the files at ``paths``, which ``tu`` includes,
    computed once for a unit that reads them all (:func:`extract_comments_outside`).
    Valid while ``tu`` lives."""
    return loader.entry_starts(tu, [tu.get_file(str(path)) for path in paths])


def project_included_files(
    tu: Any, working_directory: Path, keep: Callable[[Path], bool]
) -> set[Path]:
    """Every file the unit included, at any depth, canonical, system headers too, that
    ``keep`` keeps by its canonical path or by the path the compiler names it by
    (:func:`.headers.lexical`: a project directory that is a symbolic link to
    elsewhere)."""
    out: set[Path] = set()
    for inclusion in tu.get_includes():
        file = inclusion.include
        if file is None:
            continue
        spelled = working_directory / file.name
        path = spelled.resolve()
        if keep(path) or keep(lexical(spelled)):
            out.add(path)
    return out


def unit_contributions(
    tu: Any, working_directory: Path, main: Path, keep: Callable[[Path], bool]
) -> dict[Path, Contribution]:
    """What the unit ``tu``, its target known, contributes to each file it includes
    (every one, with ``working_directory``: system headers too, as a project file found
    through ``-isystem`` is one) that ``keep`` keeps by its canonical
    path or by the path the compiler names it by (:func:`.headers.lexical`), keyed by
    the canonical one, but its main file ``main`` (canonical): the ranges its preprocessor skipped in the file's
    first entry, or the file as written when a later entry (an ``#include`` or a
    ``-include``) compiles some of it (:func:`.headers.contribution`,
    useblocks/ubcode#4866). A later entry is told from the first by where its skipped
    ranges are in the unit (:func:`.loader.entry_base`); one with no skipped range
    compiles the file, unless the file holds nothing but comments."""
    entries: dict[Path, int] = {}
    files: dict[Path, Any] = {}
    # each file's canonical path, and whether it is the project's: by its canonical
    # path, or by the path the compiler names it by (a project directory that is a
    # symbolic link to elsewhere)
    kept: dict[Path, bool] = {}
    for inclusion in tu.get_includes():
        file = inclusion.include
        if file is None:
            continue
        spelled = working_directory / file.name
        path = spelled.resolve()
        files.setdefault(path, file)
        entries[path] = entries.get(path, 0) + 1
        kept[path] = kept.get(path, False) or keep(path) or keep(lexical(spelled))
    later_ranges: dict[Path, dict[int, list[tuple[int, int]]]] = {}
    if any(count > 1 for count in entries.values()):
        for sr in loader.get_all_skipped_ranges(tu):
            if sr.file is None:
                continue
            path = (working_directory / sr.file).resolve()
            if entries.get(path, 0) > 1:
                later_ranges.setdefault(path, {}).setdefault(sr.entry, []).append(
                    (sr.start_offset, sr.end_offset)
                )
    contributions: dict[Path, Contribution] = {}
    for path, file in files.items():
        if path == main or not kept[path]:
            continue
        first = [
            SkippedSpan(sr.start_offset, sr.end_offset, sr.start_line, sr.end_line)
            for sr in loader.get_first_inclusion_skipped_ranges(tu, file)
        ]
        later: list[bool] = []
        if entries[path] > 1:
            first_entry = loader.first_entry_base(tu, file)
            by_entry = later_ranges.get(path, {})
            code = _code_offsets(tu, path)
            ranged = [
                wholly_skipped(code, ranges)
                for entry, ranges in by_entry.items()
                if entry != first_entry
            ]
            # a later entry with no skipped range at all
            unranged = entries[path] - 1 - len(ranged)
            later = ranged + [wholly_skipped(code, [])] * max(unranged, 0)
        contributions[path] = contribution(later, first)
    return contributions


def _code_offsets(tu: Any, file_path: Path) -> list[int]:
    """The start offsets of every token of ``file_path`` but its comments."""
    cx = loader.load_clang_cindex()
    return [
        tok.extent.start.offset
        for tok in tu.get_tokens(extent=_file_extent(tu, file_path))
        if tok.kind != cx.TokenKind.COMMENT
    ]


def _file_extent(tu: Any, file_path: Path) -> Any:
    """The extent of the whole of ``file_path`` in its first entry into ``tu``."""
    cx = loader.load_clang_cindex()
    raw = file_path.read_bytes()
    line_count = len(raw.decode("utf-8", errors="replace").splitlines())
    file = tu.get_file(str(file_path))
    return cx.SourceRange.from_locations(
        loader.looked_up(tu, file, line=1),
        loader.looked_up(tu, file, line=line_count + 1),
    )


def extract_comments_outside(
    tu: Any,
    file_path: Path,
    ranges: list[SkippedSpan],
    starts: dict[tuple[int, int, int], Any] | None = None,
) -> list[LibclangComment]:
    """The comment tokens of ``file_path``, a header ``tu`` includes, outside
    ``ranges``: the ranges every unit that includes it skipped in its first inclusion
    (useblocks/ubcode#4866), by their lines, as
    :func:`extract_included_active_comments` reads by its first inclusion's.

    :param starts: :func:`starts_of` ``tu`` for every file read through it.
    """
    return _active_comments(
        tu, file_path, [(span.start_line, span.end_line) for span in ranges], starts
    )


# @Read a source through a compile-database entry that includes it, IMPL_PREPROC_7, impl, [FE_PREPROC]
def extract_included_active_comments(
    tu: Any,
    file_path: Path,
    *,
    as_written: bool = False,
    starts: dict[tuple[int, int, int], Any] | None = None,
) -> list[LibclangComment]:
    """Return the ACTIVE comment tokens of ``file_path``, a file ``tu`` includes.

    Active means outside the ranges the preprocessor skipped in the file's FIRST
    inclusion into ``tu``, the configuration its includer compiled it in first;
    what a later inclusion skips is not (see
    :func:`~sphinx_codelinks.analyse.preproc.loader.get_first_inclusion_skipped_ranges`).
    Only the file's own comments are read, never its includer's.

    :param tu: A translation unit whose main file includes ``file_path``
        (:func:`main_file_inclusions`).
    :param file_path: The included file.
    :param as_written: The includer's target is unknown: no range is skipped.
    :param starts: :func:`unit_starts` of ``tu``, if the caller has them.
    """
    file = tu.get_file(str(file_path))
    skipped = (
        []
        if as_written
        else [
            (sr.start_line, sr.end_line)
            for sr in loader.get_first_inclusion_skipped_ranges(tu, file)
        ]
    )
    return _active_comments(tu, file_path, skipped, starts)


def _whole_file(
    tu: Any,
    file: Any,
    end_line: int,
    starts: dict[tuple[int, int, int], Any] | None = None,
    contents: bytes | None = None,
    path: Path | None = None,
) -> Any:
    """The range of ``file`` in its first entry into ``tu``, from its start to line
    ``end_line``, column 1.

    For a file the unit entered once both ends are made from where its entry starts
    (:func:`.loader.entry_starts`), the end at the offset clang gives the line
    (:func:`.loader.line_offset`) in the file's bytes, and checked to decode to the
    file at that offset; any other file is looked up (:func:`.loader.looked_up`):
    the same range, without the lookup's walk of the file's macro expansions
    (useblocks/ubcode#4982). Bytes read from ``path`` stand for the bytes clang read
    only while the file's modification time is the one clang saw and its entry holds
    as many bytes (:func:`.loader.unchanged_since_parse`); a file changed since the
    parse is looked up. A rewrite to as many bytes within the second of the parse
    goes unseen: the race master has too, which slices the comments' text out of the
    bytes read from ``path``.

    :param starts: the starts of the unit (:func:`unit_starts`, :func:`starts_of`),
        when the caller reads several files through it; else found for ``file`` alone.
    :param contents: the file's bytes, as the caller read them from ``path``; else
        clang's own (``clang_getFileContents``, which walks every entry of the unit to
        find it).
    :param path: where ``contents`` were read from.
    """
    cx = loader.load_clang_cindex()
    key = loader.file_id(file)
    if starts is None:
        starts = loader.entry_starts(tu, [file])
    start = starts.get(key) if key is not None else None
    from_disk = contents is not None
    if start is not None and contents is None:
        contents = loader.file_contents(tu, file)
    if (
        start is not None
        and contents is not None
        and loader.entry_has(start, len(contents))
        and (
            not from_disk
            or (path is not None and loader.unchanged_since_parse(file, path))
        )
    ):
        end = loader.made_at(start, loader.line_offset(contents, end_line))
        if end is not None:
            return cx.SourceRange.from_locations(start, end)
    return cx.SourceRange.from_locations(
        loader.looked_up(tu, file, line=1), loader.looked_up(tu, file, line=end_line)
    )


def _active_comments(
    tu: Any,
    file_path: Path,
    skipped: list[tuple[int, int]],
    starts: dict[tuple[int, int, int], Any] | None = None,
) -> list[LibclangComment]:
    """One LibclangComment per comment token of ``file_path`` outside ``skipped``.

    :param starts: the unit's starts, if the caller has them (:func:`_whole_file`).
    """
    cx = loader.load_clang_cindex()
    # Read the raw source bytes once. We derive the token extent from them
    # (lossily, so a non-UTF-8 byte can't raise and abort the run) AND slice each
    # comment's text out of them by byte offset below — never via ``tok.spelling``,
    # which decodes the comment as strict UTF-8 and raises UnicodeDecodeError on a
    # non-UTF-8 byte inside a comment.
    raw = file_path.read_bytes()
    line_count = len(raw.decode("utf-8", errors="replace").splitlines())
    # a location in a file the unit includes is in its first inclusion
    # (``clang_getLocation``), the one whose skipped ranges ``skipped`` holds
    file = tu.get_file(str(file_path))
    extent = _whole_file(tu, file, line_count + 1, starts, raw, file_path)

    out: list[LibclangComment] = []
    for tok in tu.get_tokens(extent=extent):
        if tok.kind != cx.TokenKind.COMMENT:
            continue
        loc = tok.location
        if loc.file is None:
            continue
        if _is_in_skipped(loc.line, skipped):
            continue  # an inactive branch of the pass that decides -> excluded
        # Slice the comment text from the raw bytes by offset and decode lossily
        # (not via tok.spelling, which raises on a non-UTF-8 byte in the comment).
        # Then normalize CRLF/CR -> LF, matching get_src_strings on the tree-sitter
        # path: a multi-line block comment (e.g. a reST block) from a CRLF-saved
        # file otherwise carries embedded \r into the extracted marker text.
        text = raw[tok.extent.start.offset : tok.extent.end.offset].decode(
            "utf-8", errors="replace"
        )
        spelling = text.replace("\r\n", "\n").replace("\r", "\n")
        start = tok.extent.start.offset
        line_start = max(raw.rfind(b"\n", 0, start), raw.rfind(b"\r", 0, start)) + 1
        column = len(raw[line_start:start].decode("utf-8", errors="replace"))
        out.append(LibclangComment(spelling.encode("utf-8"), loc.line - 1, column))
    return out
