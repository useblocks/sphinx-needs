"""Find, load, select and anchor: the plumbing every reader of ``ubproject.toml`` repeats.

**Nothing in this package may import Sphinx, docutils or any other distribution** -- only
the standard library. The file describes a project to tools that run with no documentation
toolchain installed (a converter, a build action, a CI step that only reads the file), and a
shared reader that pulled Sphinx in would take that away from all of them at once.

What this module deliberately does NOT decide is policy. Whether a consumer walks up to
find the file or reads it from its ``confdir``, whether a missing file is worth a warning,
whether a ``-D`` on the command line beats a key in the file: those are the consumer's
decisions, and they differ today for reasons each consumer owns. This module provides the
mechanisms, and reports through return values and :class:`ProjectConfigError` -- never through
a logger.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

#: The file name every useblocks tool reads by default.
DEFAULT_FILENAME = "ubproject.toml"

#: Directory entries that end the upward search of :func:`find_project_config`. A
#: directory carrying one is the repository root, and nothing above it belongs to the
#: project, so a consumer never adopts the configuration of an unrelated parent.
#: ``pyproject.toml`` is deliberately *not* a marker here: it marks a Python distribution,
#: not the project. A ``docs/`` directory with its own ``pyproject.toml``, or a workspace
#: member (``packages/<name>/pyproject.toml`` with the docs below it), sits *inside* the
#: project whose shared file is at the repository root, and a marker there would end the
#: search before it reached the file -- silently. It does bound the walk where there is no
#: repository at all, see :data:`_DIST_MARKERS`.
_ROOT_MARKERS = (".git",)

#: Directory entries that end the search when *no* :data:`_ROOT_MARKERS` marker exists
#: anywhere above the starting directory. A tree outside any repository -- an unpacked
#: sdist, a CI artefact directory, an exported docs tree -- has nothing else to bound the
#: walk, so it would reach the filesystem root and adopt whatever unrelated file sits
#: above it. The distribution root is the outermost thing that still belongs to such a
#: tree.
_DIST_MARKERS = ("pyproject.toml",)

#: A TOML bare key; any other key is written quoted (:func:`render_path`).
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")

#: The TOML basic-string escapes with a short form; other control characters use ``\\uXXXX``.
_TOML_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}

#: ``tomllib.TOMLDecodeError`` bound through an annotation, so that the ``except`` clause
#: below is typed as precisely as everything else in the module.
_TOML_DECODE_ERROR: type[Exception] = tomllib.TOMLDecodeError


class ProjectConfigError(Exception):
    """The one exception this package raises, for every hard failure.

    Each message names the file (or the dotted path inside it) and the rule that was
    broken. A consumer re-raises it in its own vocabulary -- a Sphinx extension as a
    configuration error, a command line as a non-zero exit -- which is why it derives from
    nothing more specific than :class:`Exception`.
    """


def find_project_config(
    start: Path,
    filename: str = DEFAULT_FILENAME,
    report: Callable[[str], None] | None = None,
) -> Path | None:
    """Search *start* and its parents for *filename*.

    The file conventionally sits at the repository root while its consumers run from
    below it -- ``conf.py`` in ``docs/``, a build action from wherever CI invoked it -- so
    anchoring strictly at the caller's own directory would leave the shared file unread
    by one of them, silently.

    The walk ends at the first directory holding *filename*, or at the project boundary
    when that does not hold the file either. The boundary is the repository root
    (a directory holding ``.git``), or -- outside any repository only -- the distribution
    root (a directory holding ``pyproject.toml``).

    Whether to call this at all is the consumer's decision: providing the walk is not a
    ruling that every consumer should walk.

    :param start: Directory to start from. Made absolute -- without resolving symlinks --
        so that a relative path has parents to walk.
    :param filename: The file to look for.
    :param report: Called with one message when the search ends without the file, naming
        the directory whose marker ended it; ``None`` discards it. A missing file is not
        necessarily a problem, but a fruitless search must be diagnosable.
    :return: The file, or ``None`` when the search reached the project boundary or the
        filesystem root without finding one.
    """
    start = start.absolute()
    directories = (start, *start.parents)
    boundary, described = _boundary(directories)
    for directory in directories:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
        if directory == boundary:
            break
    if report is not None:
        report(f"no {filename} in {start} or its parents up to {described}")
    return None


def _boundary(directories: tuple[Path, ...]) -> tuple[Path | None, str]:
    """The directory the upward search must not walk past, and its description.

    A repository root anywhere above the start wins: inside a repository the only thing
    that bounds the project is the repository itself. Only when there is none does the
    distribution root bound the walk.
    """
    for markers, label in (
        (_ROOT_MARKERS, "repository"),
        (_DIST_MARKERS, "distribution"),
    ):
        for directory in directories:
            marker = _marker(directory, markers)
            if marker is not None:
                return directory, f"the {label} root {directory} (holding {marker})"
    return None, "the filesystem root"


def _marker(directory: Path, markers: tuple[str, ...]) -> str | None:
    """The entry of *markers* that *directory* holds, if any."""
    for marker in markers:
        if (directory / marker).exists():
            return marker
    return None


def load_toml(path: Path) -> dict[str, object]:
    """Parse *path*, reporting every failure as an :class:`ProjectConfigError` naming it.

    A missing file is a failure here too: whether an absent file is fine is the
    consumer's decision, taken before it calls this.

    :raises ProjectConfigError: If the file cannot be read, is not UTF-8, or is not valid TOML.
    """
    try:
        with path.open("rb") as handle:
            # tomllib is typed ``-> dict[str, Any]``; everything downstream is ``object``
            data: dict[str, object] = tomllib.load(handle)
    except _TOML_DECODE_ERROR as error:
        msg = f"{path}: invalid TOML: {error}"
        raise ProjectConfigError(msg) from error
    except UnicodeDecodeError as error:
        # tomllib decodes the bytes itself, and a file saved in another encoding raises
        # neither of the two errors around it
        msg = f"{path}: not valid UTF-8 TOML: {error}"
        raise ProjectConfigError(msg) from error
    except OSError as error:
        msg = f"{path}: cannot be read: {error}"
        raise ProjectConfigError(msg) from error
    return data


def _basic_string(key: str) -> str:
    """*key* as a TOML basic string: only ``"``, ``\\`` and control characters escaped.

    Everything else is written as itself -- ``café`` is ``"café"``, not the ``\\u00e9``
    that ``json.dumps`` would produce -- because that is how the user wrote the key.
    """
    out = []
    for char in key:
        if char in _TOML_ESCAPES:
            out.append(_TOML_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def render_path(segments: Sequence[str]) -> str:
    """Spell a table path the way TOML does: dotted, a segment that is not a bare key quoted.

    A segment matching ``[A-Za-z0-9_-]+`` is written bare; any other is a TOML basic string
    (:func:`_basic_string`). ``("tool", "acme.docs", "needs")`` renders as
    ``tool."acme.docs".needs`` -- joined naively it would read as four segments, and name
    a table that does not exist.
    """
    return ".".join(
        segment if _BARE_KEY.fullmatch(segment) else _basic_string(segment)
        for segment in segments
    )


def table_path(table: str | Sequence[str]) -> tuple[str, ...]:
    """The segments of a table path, given dotted (``"a.b.c"``) or as a sequence.

    The sequence form exists for a key that itself contains a dot, which the dotted
    spelling cannot express -- TOML allows ``[tool."acme.docs".needs]``.

    :raises ValueError: If the path is empty or has an empty segment -- a caller's
        mistake, not a problem with the file.
    """
    segments = tuple(table.split(".")) if isinstance(table, str) else tuple(table)
    if not segments or any(not segment for segment in segments):
        msg = f"invalid table path {table!r}: expected one or more non-empty segments"
        raise ValueError(msg)
    return segments


def select_table(
    data: Mapping[str, object],
    table: str | Sequence[str],
    *,
    source: Path | None = None,
) -> dict[str, object] | None:
    """Select the table at *table* inside *data*.

    :param data: A parsed TOML document, or any table inside one.
    :param table: The path to select, dotted (``"tool.acme.needs"``) or as a sequence of
        keys.
    :param source: The file *data* came from, for error messages only.
    :return: The table, or ``None`` when any segment of the path is absent.
    :raises ProjectConfigError: If a segment is present but is not a table.
    """
    segments = table_path(table)
    current: Mapping[str, object] = data
    for depth, segment in enumerate(segments):
        value = current.get(segment)
        if value is None:
            return None
        if not isinstance(value, dict):
            where = "" if source is None else f"{source}: "
            dotted = render_path(segments[: depth + 1])
            msg = f"{where}[{dotted}] must be a table, got {type(value).__name__}"
            raise ProjectConfigError(msg)
        current = value
    return dict(current)


def anchor(value: str | Path, base: Path) -> Path:
    """Anchor a path read from the file at *base*, the file's own directory.

    A relative *value* is joined onto *base*; an absolute one is returned untouched.
    Joined, deliberately never ``resolve()``\\ d and never normalised: whether symlinks
    are collapsed, or ``..`` folded away, is the consumer's decision -- one resolves for
    symlink confinement, another keeps the form it was handed -- and the reader must not
    take it behind their back.
    """
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path
