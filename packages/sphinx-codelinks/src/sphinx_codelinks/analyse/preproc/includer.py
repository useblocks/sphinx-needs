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

import enum
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from sphinx_codelinks.analyse.preproc.compile_db import (
    WORKING_DIRECTORY_FLAG,
    working_directory,
)

# A directive line: a `#` at the start of the line after optional whitespace,
# optional whitespace, `include` as a whole word, then a quoted or angled name.
_DIRECTIVE = re.compile(
    r'[ \t]*#[ \t]*include(?![A-Za-z0-9_])[ \t]*(?:"([^"\r\n]*)"|<([^>\r\n]*)>)'
)
# The same, `#include_next` too (group 1 holds `_next`).
_DIRECTIVE_OR_NEXT = re.compile(
    r"[ \t]*#[ \t]*include(_next)?(?![A-Za-z0-9_])[ \t]*"
    r'(?:"([^"\r\n]*)"|<([^>\r\n]*)>)'
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
    next: bool = False
    """``True`` for ``#include_next``."""


def scan_include_directives(
    text: str, *, include_next: bool = False
) -> list[IncludeDirective]:
    """The ``#include "…"`` and ``#include <…>`` directive lines of ``text``, and its
    ``#include_next`` lines too with ``include_next``.

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
            match = (_DIRECTIVE_OR_NEXT if include_next else _DIRECTIVE).match(line)
            if match is not None:
                groups = match.groups()
                is_next, (quoted, angled) = (
                    (groups[0] is not None, groups[1:])
                    if include_next
                    else (False, groups)
                )
                out.append(
                    IncludeDirective(
                        name=quoted if quoted is not None else angled,
                        angled=quoted is None,
                        line=number,
                        next=is_next,
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
    """``-I`` directories, then ``-isystem`` directories (then the ``-idirafter`` ones,
    in :func:`compiler_search_path`): searched for both forms."""


def search_path(args: list[str]) -> SearchPath:
    """The include search path of a database entry's (filtered) arguments.

    ``-iquote``, ``-I`` and ``-isystem`` are read in their joined (``-Idir``) and
    separate (``-I dir``) forms, each kind in argument order, and a relative
    directory is taken against the entry's working directory (its last
    ``-working-directory=``; the process' working directory without one, as
    libclang takes it). No other form names a directory here: ``-idirafter``,
    ``--include-directory=``, ``-I=`` (sysroot-relative) and MSVC's ``/I`` are not
    read, nor a ``cd`` in a ``command`` (every one is in :func:`compiler_search_path`).
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


class _Kind(enum.IntEnum):
    """Which list of the search path an include-path flag adds to."""

    quote = 0
    """``-iquote``: a quoted name only."""
    angled = 1
    """``-I`` and its spellings."""
    system = 2
    """``-isystem`` and its spellings, after the ``-I`` ones."""
    after = 3
    """``-idirafter`` and its spellings, last."""


_INCLUDE_PATH_FLAGS: tuple[tuple[str, _Kind | None], ...] = (
    ("-iquote", _Kind.quote),
    ("--include-directory-after=", _Kind.after),
    ("--include-directory-after", _Kind.after),
    ("--include-directory=", _Kind.angled),
    ("--include-directory", _Kind.angled),
    ("-iwithprefixbefore", _Kind.angled),
    ("-iwithprefix", _Kind.after),
    ("-iwithsysroot", _Kind.system),
    ("-isystem-after", _Kind.after),
    ("-isystem", _Kind.system),
    ("-cxx-isystem", _Kind.system),
    ("-idirafter", _Kind.after),
    ("-imsvc", _Kind.system),
    ("/imsvc", _Kind.system),
    ("/external:I", _Kind.system),
    ("-external:I", _Kind.system),
    ("-I", _Kind.angled),
    ("/I", _Kind.angled),
    ("-iframework", None),
    ("-iprefix", None),
)
"""Every include-path flag :func:`compiler_search_path` reads, the first that starts an
argument winning (so a longer spelling comes before its prefix), and the list it adds
to; ``None`` for the two that add none (``-iprefix``, ``-iframework``). A spelling that
ends in ``=`` takes its value joined only."""


def compiler_search_path(args: list[str]) -> SearchPath:
    """The include search path of a database entry's (filtered) arguments as the
    compiler reads it, for a unit whose arms no parse decides (a header's lexical
    closure, useblocks/ubcode#4866): ``-iquote``; then ``-I``, clang-cl's ``/I``,
    ``--include-directory`` (``=`` or separate) and ``-iwithprefixbefore``; then
    ``-isystem``, ``-cxx-isystem``, ``-iwithsysroot`` and clang-cl's ``/imsvc``
    (``-imsvc``) and ``/external:I`` (``-external:I``); then ``-idirafter``, ``--include-directory-after`` (``=`` or
    separate), ``-isystem-after`` and ``-iwithprefix``, last.
    Each is read joined or separate, each kind in argument order. A value that starts
    with ``=`` is under the sysroot (``-isysroot``, else ``--sysroot``), as is every
    ``-iwithsysroot`` one; an ``-iwithprefix`` or ``-iwithprefixbefore`` one comes
    after the last ``-iprefix`` before it (a string prefix); any other relative
    directory is taken against the entry's working directory. ``-iframework`` is not
    read (a framework's headers are named ``<Name/header.h>`` and live in
    ``Name.framework/Headers``)."""
    working = working_directory(args)
    sysroot = _sysroot(args)
    kinds: list[list[Path]] = [[], [], [], []]
    prefix = ""
    arguments = iter(args)
    for arg in arguments:
        if arg.startswith(WORKING_DIRECTORY_FLAG):
            continue
        match = next(
            (
                (flag, kind)
                for flag, kind in _INCLUDE_PATH_FLAGS
                if arg.startswith(flag)
            ),
            None,
        )
        if match is None:
            continue
        flag, kind = match
        joined = arg[len(flag) :]
        if joined or flag.endswith("="):
            given = joined
        else:
            value = next(arguments, None)
            if value is None:
                break
            given = value
        if flag == "-iprefix":
            prefix = given
            continue
        if kind is None:
            continue  # -iframework
        if flag.startswith("-iwithprefix"):
            spelled = prefix + given
        elif flag == "-iwithsysroot":
            spelled = (sysroot or "") + given
        elif given.startswith("="):
            spelled = (sysroot or "") + given[1:]
        else:
            spelled = given
        kinds[kind].append(working / spelled)
    quote, angled, system, after = kinds
    return SearchPath(quote=tuple(quote), angled=(*angled, *system, *after))


def _sysroot(args: list[str]) -> str | None:
    """The sysroot of ``args`` for headers: the last ``-isysroot``, else the last
    ``--sysroot`` (``=`` or separate)."""
    isysroot: str | None = None
    sysroot: str | None = None
    arguments = iter(args)
    for arg in arguments:
        if arg == "-isysroot":
            isysroot = next(arguments, None)
        elif arg.startswith("-isysroot"):
            isysroot = arg[len("-isysroot") :]
        elif arg == "--sysroot":
            sysroot = next(arguments, None)
        elif arg.startswith("--sysroot="):
            sysroot = arg[len("--sysroot=") :]
    return isysroot if isysroot is not None else sysroot


class Found(NamedTuple):
    """A file an ``#include`` names, found."""

    spelled: Path
    """The directory it was found in joined with the name, as the compiler names it."""
    canonical: Path
    """The file, canonical."""


def find_include(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> Found | None:
    """The file ``directive`` names, as the compiler finds it; or ``None``.

    A quoted name is looked up in the including file's directory first, then in the
    ``-iquote`` directories; both forms then in the ``-I`` and ``-isystem``
    directories. The first existing file wins.
    """
    for directory in _found_directories(directive, including_file, path):
        candidate = directory / directive.name
        if candidate.is_file():
            return Found(candidate, candidate.resolve())
    return None


def _found_directories(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> list[Path]:
    """The directories a lookup of ``directive``'s name runs over, in order: the
    including file's directory and the ``-iquote`` directories for a quoted name,
    then the include path (:func:`find_include` resolves against this list)."""
    directories: list[Path] = []
    if not directive.angled:
        directories += [including_file.parent, *path.quote]
    directories += path.angled
    return directories


def lookup_directories(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> list[Path]:
    """Where the compiler would have found ``directive``'s name, in search order
    (useblocks/sphinx-needs#2584): a quoted name in the including file's
    directory, then ``-iquote``, then the include path -- an angled name too, a
    failed angled lookup being retried as a quoted one; an ``#include_next``'s in
    the directories after the one the including file was found in, the whole
    lookup for a file found on none, as clang then searches from the start."""
    if directive.next:
        after = _include_next_directories(directive, including_file, path)
        if after is not None:
            return after
    return [including_file.parent, *path.quote, *path.angled]


def resolve_include(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> Path | None:
    """The file ``directive`` names, canonical, as the compiler finds it
    (:func:`find_include`); or ``None``."""
    found = find_include(directive, including_file, path)
    return found.canonical if found is not None else None


def find_include_next(
    directive: IncludeDirective, including_file: Path, path: SearchPath
) -> Found | None:
    """The file an ``#include_next`` ``directive`` in ``including_file`` (canonical)
    names, as the compiler continues: in the search-path directories after the one the
    including file was found in (the first whose join with the name is the including
    file), never the including file itself, each directory once (the first of those
    that resolve alike: a directory listed again, or a symbolic link to an earlier one,
    is dropped, as clang drops it). In a file found on no search directory, as
    :func:`find_include` looks a name up (clang warns that it searches from the start:
    a quoted name in the file's own directory first)."""
    listed = [*path.quote, *path.angled] if not directive.angled else [*path.angled]
    directories = _include_next_directories(
        directive, including_file, path, listed=listed
    )
    if directories is None:
        return find_include(directive, including_file, path)
    for directory in directories:
        candidate = directory / directive.name
        if candidate.is_file() and (canonical := candidate.resolve()) != including_file:
            return Found(candidate, canonical)
    return None


def _include_next_directories(
    directive: IncludeDirective,
    including_file: Path,
    path: SearchPath,
    *,
    listed: Sequence[Path] | None = None,
) -> list[Path] | None:
    """The directories an ``#include_next`` continues in: those after the one
    whose join with the directive's name is ``including_file`` (canonical), each
    listed once as clang lists it. ``None`` when the including file sits on none
    (clang then searches from the start, as a plain lookup does)."""
    if listed is None:
        listed = [*path.quote, *path.angled] if not directive.angled else path.angled
    directories: list[Path] = []
    resolved: set[Path] = set()
    for directory in listed:
        key = directory.resolve()
        if key not in resolved:
            resolved.add(key)
            directories.append(directory)
    start = next(
        (
            at + 1
            for at, directory in enumerate(directories)
            if (directory / directive.name).is_file()
            and (directory / directive.name).resolve() == including_file
        ),
        None,
    )
    if start is None:
        return None
    return directories[start:]


_FORCED_INCLUDE_FLAGS = (
    "--include=",
    "--include",
    "-include",
    "-imacros",
    "/FI",
    "-FI",
)
"""The flags that include a file ahead of the main file, the first that starts an
argument winning; a spelling that ends in ``=`` takes its value joined only."""


def forced_includes(args: list[str]) -> list[str]:
    """The files ``args`` include ahead of the main file, in order: each ``-include``,
    ``--include`` (``=`` or separate), ``-imacros`` and clang-cl ``/FI`` (``-FI``)
    value, separate or joined (never ``-include-*`` nor ``--include-*``, such as
    ``-include-pch``)."""
    names: list[str] = []
    arguments = iter(args)
    for arg in arguments:
        flag = next((f for f in _FORCED_INCLUDE_FLAGS if arg.startswith(f)), None)
        if flag is None or arg.startswith(("-include-", "--include-")):
            continue
        joined = arg[len(flag) :]
        if joined or flag.endswith("="):
            names.append(joined)
        elif (value := next(arguments, None)) is not None:
            names.append(value)
    return names


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


PENDING_PATH_CAP = 64
"""The most candidate paths of unresolved includes one record keeps one by one
(useblocks/sphinx-needs#2584); past it, :func:`pending_signature` keeps the
directories' times instead, so an armada of generated headers cannot make a
record grow without bound."""


def pending_signature(candidates: Iterable[Path]) -> dict[Path, int | None]:
    """The signature of the places a parse's unresolved includes would resolve
    (useblocks/sphinx-needs#2584): each candidate path to its ``st_mtime_ns`` as
    a file -- ``None`` while it holds none, a directory named like the include
    counting for nothing as the compiler's lookup skips it. Past
    :data:`PENDING_PATH_CAP` paths, the nearest existing directory of each to its
    ``st_mtime_ns`` instead, so a file created under one (or the directory itself
    appearing) is still seen."""
    paths = {path.resolve() for path in candidates}
    if len(paths) > PENDING_PATH_CAP:
        watched: dict[Path, int | None] = {}
        for directory in {path.parent for path in paths}:
            while not directory.is_dir():
                if directory.parent == directory:
                    break
                directory = directory.parent
            if directory.is_dir():
                watched[directory] = directory.stat().st_mtime_ns
        return watched
    return {path: path.stat().st_mtime_ns if path.is_file() else None for path in paths}
