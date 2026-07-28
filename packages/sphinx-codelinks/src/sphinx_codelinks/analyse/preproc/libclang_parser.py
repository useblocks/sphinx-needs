"""Parse a C/C++ TU via libclang and yield ACTIVE comment tokens only."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

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

    def __init__(self, text: bytes, row: int) -> None:
        self.text: bytes = text
        self.start_point = _Point(row)


def _group_skipped(skipped: list[SkippedRange]) -> dict[str, list[tuple[int, int]]]:
    """Group skipped ranges by normalised file path, built once per TU.

    A per-comment membership test then scans only its own file's ranges instead
    of every range in the translation unit (headers included). Normalising the
    key (``os.path.normpath``) also fixes clang spelling the same file two ways
    (``./x`` vs ``x``, ``a/../b``), which a naive compare would miss.
    """
    grouped: dict[str, list[tuple[int, int]]] = {}
    for sr in skipped:
        if sr.file is not None:
            grouped.setdefault(os.path.normpath(str(sr.file)), []).append(
                (sr.start_line, sr.end_line)
            )
    return grouped


def _is_in_skipped(
    file_path: str, line: int, grouped: dict[str, list[tuple[int, int]]]
) -> bool:
    return any(
        start <= line <= end
        for start, end in grouped.get(os.path.normpath(file_path), ())
    )


def extract_active_comments(file_path: Path, args: list[str]) -> list[LibclangComment]:
    """Return one LibclangComment per ACTIVE comment token in ``file_path``.

    Comments inside preprocessor-skipped (inactive) ranges are dropped.
    """
    cx = loader.load_clang_cindex()
    index = cx.Index.create()
    tu = index.parse(str(file_path), args=args, options=loader.PARSE_OPTIONS)
    skipped = _group_skipped(loader.get_all_skipped_ranges(tu))

    # Read the raw source bytes once. We derive the token extent from them
    # (lossily, so a non-UTF-8 byte can't raise and abort the run) AND slice each
    # comment's text out of them by byte offset below — never via ``tok.spelling``,
    # which decodes the comment as strict UTF-8 and raises UnicodeDecodeError on a
    # non-UTF-8 byte inside a comment.
    raw = file_path.read_bytes()
    line_count = len(raw.decode("utf-8", errors="replace").splitlines())
    main = tu.get_file(str(file_path))
    extent = cx.SourceRange.from_locations(
        cx.SourceLocation.from_position(tu, main, 1, 1),
        cx.SourceLocation.from_position(tu, main, line_count + 1, 1),
    )

    out: list[LibclangComment] = []
    for tok in tu.get_tokens(extent=extent):
        if tok.kind != cx.TokenKind.COMMENT:
            continue
        loc = tok.location
        if loc.file is None:
            continue
        if _is_in_skipped(str(loc.file.name), loc.line, skipped):
            continue  # inactive branch -> excluded
        # Slice the comment text from the raw bytes by offset and decode lossily
        # (not via tok.spelling, which raises on a non-UTF-8 byte in the comment).
        # Then normalize CRLF/CR -> LF, matching get_src_strings on the tree-sitter
        # path: a multi-line block comment (e.g. a reST block) from a CRLF-saved
        # file otherwise carries embedded \r into the extracted marker text.
        text = raw[tok.extent.start.offset : tok.extent.end.offset].decode(
            "utf-8", errors="replace"
        )
        spelling = text.replace("\r\n", "\n").replace("\r", "\n")
        out.append(LibclangComment(spelling.encode("utf-8"), loc.line - 1))
    return out
