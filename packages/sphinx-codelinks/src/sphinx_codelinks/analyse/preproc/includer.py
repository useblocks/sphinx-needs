"""Find the compilation-database entries that directly include a source file.

A C/C++ source with no database entry of its own (a file a unity or "jumbo" source
``#include``s, for example) is read through an **includer**: an entry whose main
file directly includes it. This module finds the candidates, lexically and without
parsing: each entry's main file is scanned for ``#include`` directive lines, and each
target is resolved as the compiler resolves it. The scan cannot see ``#if`` arms, so
a candidate is only a candidate: the includer is the first one, by path, whose parse
confirms the inclusion (see ``SourceAnalyse.create_src_objects_libclang``).

Nothing here needs libclang, but the module lives in the optional engine's package.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from sphinx_codelinks.analyse.preproc.compile_db import (
    WORKING_DIRECTORY_FLAG,
    working_directory,
)

# A directive line: a `#` at the start of the line after optional whitespace,
# optional whitespace, `include` as a whole word, then a quoted or angled name.
_DIRECTIVE = re.compile(
    r'[ \t]*#[ \t]*include(?![A-Za-z0-9_])[ \t]*(?:"([^"\r\n]*)"|<([^>\r\n]*)>)'
)
_LINE_BREAK = re.compile(r"\r\n|\r|\n")


@dataclass(frozen=True)
class IncludeDirective:
    """One ``#include`` directive line of a file."""

    name: str
    """The name as written between the quotes or angle brackets."""
    angled: bool
    """``True`` for ``#include <…>``, ``False`` for ``#include "…"``."""
    line: int
    """The 1-based line of the directive."""


def scan_include_directives(text: str) -> list[IncludeDirective]:
    """The ``#include "…"`` and ``#include <…>`` directive lines of ``text``.

    A directive line starts, after optional whitespace, with ``#``, optional
    whitespace and ``include``. A line inside a block comment is not one. Line
    comments and string or character literals are skipped while looking for the
    start of a block comment, so a ``"/*"`` in a string opens none. ``#if`` arms are
    not evaluated: a directive in an ``#if 0`` arm is returned.
    """
    out: list[IncludeDirective] = []
    in_block = False
    for number, line in enumerate(_LINE_BREAK.split(text), start=1):
        position = 0
        if not in_block:
            match = _DIRECTIVE.match(line)
            if match is not None:
                quoted, angled = match.group(1), match.group(2)
                out.append(
                    IncludeDirective(
                        name=quoted if quoted is not None else angled,
                        angled=quoted is None,
                        line=number,
                    )
                )
                position = match.end()
        in_block = _block_comment_open_after(line, position, in_block)
    return out


def _block_comment_open_after(line: str, position: int, in_block: bool) -> bool:
    """Whether a block comment is open at the end of ``line``, read from ``position``."""
    length = len(line)
    while position < length:
        if in_block:
            end = line.find("*/", position)
            if end < 0:
                return True
            in_block = False
            position = end + 2
            continue
        char = line[position]
        pair = line[position : position + 2]
        if pair == "//":
            return False
        if pair == "/*":
            in_block = True
            position += 2
        elif char in "\"'":
            position = _literal_end(line, position)
        else:
            position += 1
    return in_block


def _literal_end(line: str, position: int) -> int:
    """The index after the string or character literal opening at ``position``.

    A literal that does not close on its line ends with the line.
    """
    quote = line[position]
    position += 1
    while position < len(line):
        char = line[position]
        if char == "\\":
            position += 2
            continue
        if char == quote:
            return position + 1
        position += 1
    return len(line)


@dataclass(frozen=True)
class SearchPath:
    """Where an entry's ``#include`` names are looked up, in the compiler's order."""

    quote: tuple[Path, ...]
    """``-iquote`` directories: searched for a quoted name only."""
    angled: tuple[Path, ...]
    """``-I`` directories, then ``-isystem`` directories: searched for both forms."""


def search_path(args: list[str]) -> SearchPath:
    """The include search path of a database entry's (filtered) arguments.

    ``-iquote``, ``-I`` and ``-isystem`` are read in their joined (``-Idir``) and
    separate (``-I dir``) forms, each kind in argument order, and a relative
    directory is taken against the entry's working directory (its last
    ``-working-directory=``; the process' working directory without one, as
    libclang takes it). No other form names a directory here: ``-idirafter``,
    ``--include-directory=``, ``-I=`` (sysroot-relative) and MSVC's ``/I`` are not
    read, nor a ``cd`` in a ``command``.
    """
    working = working_directory(args)
    quote: list[Path] = []
    angled: list[Path] = []
    system: list[Path] = []
    kinds = {"-iquote": quote, "-isystem": system, "-I": angled}
    pending: list[Path] | None = None
    for arg in args:
        if pending is not None:
            pending.append(Path(arg))
            pending = None
            continue
        if arg.startswith(WORKING_DIRECTORY_FLAG):
            continue
        for flag, directories in kinds.items():
            if arg == flag:
                pending = directories
                break
            if arg.startswith(flag):
                directories.append(Path(arg[len(flag) :]))
                break
    return SearchPath(
        quote=tuple(working / d for d in quote),
        angled=tuple(working / d for d in (*angled, *system)),
    )


def resolve_include(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> Path | None:
    """The file ``directive`` names, canonical, as the compiler finds it; or ``None``.

    A quoted name is looked up in the including file's directory first, then in the
    ``-iquote`` directories; both forms then in the ``-I`` and ``-isystem``
    directories. The first existing file wins.
    """
    directories: list[Path] = []
    if not directive.angled:
        directories += [including_file.parent, *path.quote]
    directories += path.angled
    for directory in directories:
        candidate = directory / directive.name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _path_key(path: Path) -> bytes:
    return os.fsencode(path)


def inclusion_index(flags: dict[Path, list[str]]) -> dict[Path, list[Path]]:
    """Map each file a database entry's main file directly includes to its includers.

    :param flags: The database, as ``load_flags_map`` returns it (canonical main
        file -> arguments).
    :return: canonical included file -> the main files whose own ``#include``
        lines name it, ordered by path (canonical, byte order). A main file that
        cannot be read includes nothing.
    """
    index: dict[Path, list[Path]] = {}
    for main, args in flags.items():
        try:
            text = main.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        path = search_path(args)
        for directive in scan_include_directives(text):
            target = resolve_include(directive, main, path)
            if target is None:
                continue
            includers = index.setdefault(target, [])
            if main not in includers:
                includers.append(main)
    for includers in index.values():
        includers.sort(key=_path_key)
    return index
