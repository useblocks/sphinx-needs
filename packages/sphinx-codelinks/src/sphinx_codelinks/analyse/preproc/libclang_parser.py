"""Parse a C/C++ TU via libclang and yield ACTIVE comment tokens only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sphinx_codelinks.analyse.preproc import loader
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

    :raises clang.cindex.TranslationUnitLoadError: libclang could not load it.
    """
    cx = loader.load_clang_cindex()
    index = cx.Index.create()
    return index.parse(str(file_path), args=args, options=loader.PARSE_OPTIONS)


# @Drop comments inside inactive preprocessor branches, IMPL_PREPROC_2, impl, [FE_PREPROC]
def extract_active_comments(file_path: Path, args: list[str]) -> list[LibclangComment]:
    """Return one LibclangComment per ACTIVE comment token in ``file_path``.

    Comments inside the ranges the file's own pass through the preprocessor
    skipped (its inactive branches) are dropped; what a later pass through the
    same file skips is not (see :func:`_main_file_skipped`).
    """
    tu = parse_translation_unit(file_path, args)
    skipped = _main_file_skipped(loader.get_all_skipped_ranges(tu))
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
        included = cursor.get_included_file()
        if included is None:
            continue
        out.add((working_directory / included.name).resolve())
    return out


# @Read a source through a compile-database entry that includes it, IMPL_PREPROC_7, impl, [FE_PREPROC]
def extract_included_active_comments(tu: Any, file_path: Path) -> list[LibclangComment]:
    """Return the ACTIVE comment tokens of ``file_path``, a file ``tu`` includes.

    Active means outside the ranges the preprocessor skipped in the file's FIRST
    inclusion into ``tu``, the configuration its includer compiled it in first;
    what a later inclusion skips is not (see
    :func:`~sphinx_codelinks.analyse.preproc.loader.get_first_inclusion_skipped_ranges`).
    Only the file's own comments are read, never its includer's.

    :param tu: A translation unit whose main file includes ``file_path``
        (:func:`main_file_inclusions`).
    :param file_path: The included file.
    """
    file = tu.get_file(str(file_path))
    skipped = [
        (sr.start_line, sr.end_line)
        for sr in loader.get_first_inclusion_skipped_ranges(tu, file)
    ]
    return _active_comments(tu, file_path, skipped)


def _active_comments(
    tu: Any, file_path: Path, skipped: list[tuple[int, int]]
) -> list[LibclangComment]:
    """One LibclangComment per comment token of ``file_path`` outside ``skipped``."""
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
    extent = cx.SourceRange.from_locations(
        cx.SourceLocation.from_position(tu, file, 1, 1),
        cx.SourceLocation.from_position(tu, file, line_count + 1, 1),
    )

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
