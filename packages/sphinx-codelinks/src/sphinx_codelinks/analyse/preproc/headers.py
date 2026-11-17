"""A header read through every compilation-database entry that includes it
(useblocks/ubcode#4866).

A compilation database lists translation units, never headers. A header the database
does not list is read through the **units** that include it: every entry of its own
database (of every database the analysis found, when the walk-up finds none of its
own) whose parse includes it, at any depth, whatever its main file (one outside the
source directory too), a file compiled twice once per entry.

Each unit contributes to each project file it includes (:class:`Contribution`): its
target known, the ranges its preprocessor skipped in the file's first inclusion; or the
file as written, when it includes the file twice or more without an include guard (an
X-macro header), when its target is unknown, or when every parse of it is refused. The
last two include, besides what a host parse includes, every file their ``#include``
lines name (:func:`lexical_closure`): a parse for another target decides none of their
arms.

A header leaves out only what every unit that includes it skipped
(:func:`union_of_arms`: the intersection of their skipped ranges, the union of the arms
they compile), read from one of them, its **reader**. A header no unit includes keeps
its read with the ``[preprocessor]`` defines.

Nothing here needs libclang (what a parse contributes is
:func:`.libclang_parser.unit_contributions`), so the records the Sphinx environment
keeps load without it.
"""

from __future__ import annotations

import enum
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sphinx_codelinks.analyse.preproc import includer
from sphinx_codelinks.analyse.preproc.compile_db import working_directory

if TYPE_CHECKING:
    from sphinx_codelinks.analyse.preproc.target import Decision


@dataclass(frozen=True, order=True)
class SkippedSpan:
    """A range the preprocessor skipped in a file: from a directive's ``#`` to the end
    of the keyword of the directive that closes it."""

    start_byte: int
    end_byte: int
    start_line: int
    """The 1-based line of its start."""
    end_line: int
    """The 1-based line of its end."""


class ContributionKind(enum.Enum):
    """How a unit reads a file it includes."""

    skipped = "skipped"
    """Its target known: the file's first inclusion, without the ranges it skipped."""
    repeated = "repeated"
    """Its target known, the file entered again by an entry that compiles some of it
    (an X-macro header): each entry compiles other arms, so as written."""
    unknown = "unknown"
    """Its target unknown: as written."""
    refused = "refused"
    """Every parse of it refused: as written."""


@dataclass(frozen=True)
class Contribution:
    """What one unit contributes to one file it includes."""

    kind: ContributionKind
    ranges: tuple[SkippedSpan, ...] = ()
    """The ranges skipped in its first inclusion (:attr:`ContributionKind.skipped`)."""


REPEATED = Contribution(ContributionKind.repeated)
UNKNOWN = Contribution(ContributionKind.unknown)
REFUSED = Contribution(ContributionKind.refused)


def skipped(ranges: Iterable[SkippedSpan]) -> Contribution:
    """A :attr:`ContributionKind.skipped` contribution of ``ranges``, sorted."""
    return Contribution(ContributionKind.skipped, tuple(sorted(ranges)))


def contribution(later: Iterable[bool], first: Iterable[SkippedSpan]) -> Contribution:
    """What a unit whose target is known contributes to a file it includes, whose first
    entry skipped ``first``, and whose later entries (by ``-include`` or ``#include``)
    each are wholly skipped or not (``later``, :func:`wholly_skipped`): the first
    entry's ranges when every later entry is wholly skipped (a guard whose macro the
    first entry defined: that one decides), else the file as written, as each entry
    compiles other arms (an X-macro header, or a whole-file ``#ifndef`` wrapper whose
    macro nothing defines, which ``clang_isFileMultipleIncludeGuarded`` calls guarded
    all the same)."""
    if not all(later):
        return REPEATED
    return skipped(first)


def wholly_skipped(code: Iterable[int], ranges: Iterable[tuple[int, int]]) -> bool:
    """Whether an entry of a file whose skipped byte ranges are ``ranges`` compiles
    nothing of it: every token of the file but its comments (``code``, their start
    offsets) starts inside one of them, bounds included. A guard whose macro the first
    entry defined skips the whole body of every later one; a whole-file ``#ifndef``
    whose macro nothing defines does not."""
    spans = list(ranges)
    return all(any(start <= at <= end for start, end in spans) for at in code)


def intersect(
    left: Iterable[SkippedSpan], right: Iterable[SkippedSpan]
) -> list[SkippedSpan]:
    """The ranges ``left`` and ``right`` (each sorted, disjoint) both cover: each
    overlap, from the later start to the earlier end, with those ends' lines; only an
    overlap of at least one byte. A range runs from a directive's ``#`` to the end of a
    directive's keyword, so an overlap does too."""
    one_side, other_side = list(left), list(right)
    on_left = on_right = 0
    out: list[SkippedSpan] = []
    while on_left < len(one_side) and on_right < len(other_side):
        one, other = one_side[on_left], other_side[on_right]
        start, start_line = (
            (one.start_byte, one.start_line)
            if one.start_byte >= other.start_byte
            else (other.start_byte, other.start_line)
        )
        end, end_line = (
            (one.end_byte, one.end_line)
            if one.end_byte <= other.end_byte
            else (other.end_byte, other.end_line)
        )
        if start < end:
            out.append(SkippedSpan(start, end, start_line, end_line))
        if one.end_byte <= other.end_byte:
            on_left += 1
        else:
            on_right += 1
    return out


def union_of_arms(contributions: Iterable[Contribution]) -> list[SkippedSpan]:
    """The ranges of a header every one of ``contributions`` (one per unit that
    includes it) skipped: none when one of them reads it as written, else the
    intersection of their ranges (:func:`intersect`). An arm is left out only when no
    unit compiles it."""
    kept: list[SkippedSpan] | None = None
    for each in contributions:
        if each.kind is not ContributionKind.skipped:
            return []
        ranges = sorted(each.ranges)
        kept = ranges if kept is None else intersect(kept, ranges)
    return kept or []


def lexical_closure(
    main: Path, args: list[str], keep: Callable[[Path], bool]
) -> set[Path]:
    """Every file a unit whose arms no parse decides may include, canonical, that
    ``keep`` keeps, but its main file ``main``: its ``-include`` and ``-imacros`` files
    (the working directory first, then the search path), and every file their and
    ``main``'s ``#include`` and ``#include_next`` lines name, at any depth, as the
    compiler finds it with ``args``' include path (:func:`.includer.resolve_include`,
    ``-idirafter`` included: a project file on any search path counts).
    Files ``keep`` does not keep are followed too (an SDK header that includes a project
    one), and nothing cuts the walk short: each file is read once. ``#if`` arms are not
    read, a computed ``#include MACRO`` is not resolved."""
    search = includer.search_path(args, after=True)
    working = working_directory(args)
    seen: set[Path] = {main}
    stack: list[Path] = []
    # as if the first lines of the main file, looked up from the working directory
    command_line = working / "<command line>"
    for name in includer.forced_includes(args):
        found = includer.resolve_include(
            includer.IncludeDirective(name, angled=False, line=0), command_line, search
        )
        if found is not None and found not in seen:
            seen.add(found)
            stack.append(found)
    stack.append(main)
    while stack:
        file = stack.pop()
        try:
            text = file.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        for directive in includer.scan_include_directives(text, include_next=True):
            found = (
                includer.resolve_include_next(directive, file, search)
                if directive.next
                else includer.resolve_include(directive, file, search)
            )
            if found is None or found in seen:
                continue
            seen.add(found)
            stack.append(found)
    return {path for path in seen if path != main and keep(path)}


@dataclass(frozen=True)
class UnitKey:
    """A unit: one entry of a compilation database."""

    database: Path
    """The database, canonical."""
    main: Path
    """The entry's main file, canonical."""
    ordinal: int
    """Its position among the database's entries for the same main file."""

    def order(self) -> tuple[bytes, bytes, int]:
        """The units' order: by main file, then database (byte order), then ordinal."""
        return (os.fsencode(self.main), os.fsencode(self.database), self.ordinal)


@dataclass
class UnitRecord:
    """What a unit contributes, and what it was read from."""

    fingerprint: tuple[Any, ...]
    """Its arguments, its target decision, its database, the loaded libclang and the
    project root: a record of another is not this unit's."""
    main_mtime: int
    """Its main file's ``st_mtime_ns`` when it was read."""
    decision: Decision
    """The target decision of the parse that read it (after the parses made again), or
    of the last one refused."""
    triple: str | None
    """The triple it was parsed for, its target known; ``None`` when it reads the files
    it includes as written."""
    contributions: dict[Path, Contribution] = field(default_factory=dict)
    """What it contributes to each project file it includes (canonical), but its main
    file."""
    deps: dict[Path, int] = field(default_factory=dict)
    """Each of those files' ``st_mtime_ns`` when it was read."""

    def fresh(self, fingerprint: tuple[Any, ...], main_mtime: int) -> bool:
        """Whether the record still holds: the same fingerprint, its main file and every
        file it includes unchanged."""
        return (
            self.fingerprint == fingerprint
            and self.main_mtime == main_mtime
            and all(mtime_ns(path) == mtime for path, mtime in self.deps.items())
        )


def mtime_ns(path: Path) -> int | None:
    """``path``'s ``st_mtime_ns``; ``None`` when it cannot be read."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None
