"""The grammar of a need id: a namespace and a local id, separated by ``::``.

The one place in this package that knows the separator. An id that holds ``::`` splits at
its LAST ``::`` into a namespace -- one or more segments, each made of ASCII letters,
digits, ``_`` and ``-`` -- and a local id; ``nc::m2::REQ_1`` is the namespace ``nc::m2``
and the local id ``REQ_1``. An id that holds ``::`` and does not split cleanly is a plain
id, with a problem whose class this module names. Splitting never fails. The rules are
section 14 of the package's contract, ``design/exchange-contract.md``, and the corpus
``tests/fixtures/need_id_conformance.toml`` pins them.

It decides no policy. Whether a project reads a namespace out of its ids at all, what an
id that does not split cleanly costs (a warning, or nothing), and what a namespace means
are each consumer's to decide; this module only says how an id splits. It splits an id,
not a link target: a consumer strips a target's ``[condition]`` and splits its part off
at the first ``.`` before splitting what remains here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

__all__ = (
    "EMPTY_LOCAL",
    "EMPTY_SEGMENT",
    "SEGMENT_CHARACTER",
    "SEPARATOR",
    "format_namespace",
    "id_problem",
    "is_segment",
    "join_id",
    "parse_namespace",
    "split_id",
)

SEPARATOR: Final = "::"
"""The separator between a namespace's segments, and between a namespace and a local id."""

#: A segment: one or more ASCII letters, ASCII digits, ``_`` or ``-``, in any position.
#: Spelled out rather than ``\w``, which accepts non-ASCII letters and digits, and matched
#: with ``fullmatch``, so that a trailing line feed is not let through as ``$`` would.
_SEGMENT: Final = re.compile(r"[A-Za-z0-9_-]+")

# the classes of an id that holds ``::`` and does not split cleanly, tested in this order
EMPTY_LOCAL: Final = "empty_local"
"""Nothing follows the id's last ``::``."""
EMPTY_SEGMENT: Final = "empty_segment"
"""The text before the id's last ``::`` is empty, or has an empty piece between two
``::``."""
SEGMENT_CHARACTER: Final = "segment_character"
"""A piece of the text before the id's last ``::`` holds a character that is not an ASCII
letter, an ASCII digit, ``_`` or ``-``."""


def _segments(namespace: Iterable[str]) -> tuple[str, ...]:
    """*namespace* as a tuple of segments; a bare ``str`` is refused, since iterating it
    would give its characters (``"nc"`` would be the namespace ``n::c``)."""
    if isinstance(namespace, str):
        raise TypeError(
            f"a namespace is a sequence of segments, not the string {namespace!r}: "
            f"pass [{namespace!r}] for one segment, or parse_namespace({namespace!r}) "
            "for a namespace's text"
        )
    return tuple(namespace)


def is_segment(text: str) -> bool:
    """Whether *text* is a namespace segment: one or more ASCII letters, ASCII digits,
    ``_`` or ``-``, in any position (contract section 14)."""
    return _SEGMENT.fullmatch(text) is not None


def _split(id: str) -> tuple[tuple[str, ...], str, str | None]:
    """The namespace, the local id and the problem of *id*, as section 14 gives them."""
    at = id.rfind(SEPARATOR)
    if at < 0:
        return (), id, None
    head, local = id[:at], id[at + len(SEPARATOR) :]
    if not local:
        return (), id, EMPTY_LOCAL
    pieces = head.split(SEPARATOR)
    if not all(pieces):
        return (), id, EMPTY_SEGMENT
    if not all(is_segment(piece) for piece in pieces):
        return (), id, SEGMENT_CHARACTER
    return tuple(pieces), local, None


def split_id(id: str) -> tuple[tuple[str, ...], str]:
    """Split a need id into its namespace's segments and its local id (contract section
    14): at the LAST ``::``, so ``"nc::m2::REQ_1"`` is ``(("nc", "m2"), "REQ_1")``.

    An id with no ``::``, and one that holds ``::`` but does not split cleanly (see
    :func:`id_problem`), is a plain id: ``((), id)``. It never raises. It splits an ID,
    not a link target, whose condition and part a consumer strips first.
    """
    namespace, local, _ = _split(id)
    return namespace, local


def id_problem(id: str) -> str | None:
    """Why an id that holds ``::`` does not split cleanly (contract section 14), or
    ``None`` when it does or holds no ``::``: :data:`EMPTY_LOCAL`, :data:`EMPTY_SEGMENT`
    or :data:`SEGMENT_CHARACTER`, the first that applies in that order. It never raises."""
    return _split(id)[2]


def join_id(namespace: Iterable[str], local: str) -> str:
    """Join a namespace's segments and a local id into an id (contract section 14), so
    that :func:`split_id` gives the pair back.

    An empty namespace gives *local* unchanged, whatever it holds, so that
    ``join_id(*split_id(x)) == x`` for every text.

    :raises TypeError: If *namespace* is a ``str``: it is a sequence of segments (parse a
        namespace's text with :func:`parse_namespace` first).
    :raises ValueError: With a non-empty namespace, if a segment is not a segment (see
        :func:`is_segment`), or *local* is empty, holds ``::`` or starts with ``:`` --
        any of which would split back differently. The message names the value and the
        rule.
    """
    segments = _segments(namespace)
    if not segments:
        return local
    for segment in segments:
        if not is_segment(segment):
            raise ValueError(
                f"{segment!r} is not a namespace segment: a segment is one or more "
                "ASCII letters, ASCII digits, '_' or '-'"
            )
    if not local:
        raise ValueError("the local id of a namespaced id must not be empty")
    if SEPARATOR in local:
        raise ValueError(
            f"the local id {local!r} holds {SEPARATOR!r}: a namespaced id splits at its "
            "last separator, so its local id holds none"
        )
    if local.startswith(SEPARATOR[0]):
        raise ValueError(
            f"the local id {local!r} starts with {SEPARATOR[0]!r}: joined, it would make a "
            f"later {SEPARATOR!r}, and the id would split there"
        )
    return SEPARATOR.join(segments) + SEPARATOR + local


def parse_namespace(text: str) -> tuple[str, ...]:
    """The segments of a namespace given as text (contract section 14): *text* cut at
    every ``::``, from the left. The empty text is the empty namespace, ``()``.

    :raises ValueError: If a piece is not a segment (see :func:`is_segment`). The
        message names the text, the piece and the rule.
    """
    if not text:
        return ()
    pieces = text.split(SEPARATOR)
    for piece in pieces:
        if not is_segment(piece):
            raise ValueError(
                f"{text!r} is not a namespace: its piece {piece!r} is not a segment, "
                "which is one or more ASCII letters, ASCII digits, '_' or '-'"
            )
    return tuple(pieces)


def format_namespace(namespace: Iterable[str]) -> str:
    """A namespace's text: its segments joined by ``::``, and ``""`` for the empty
    namespace (contract section 14). It does not check the segments, but refuses a bare
    ``str`` with a ``TypeError`` (it is a sequence of segments); ``format_namespace(
    parse_namespace(text)) == text`` for every text :func:`parse_namespace` accepts."""
    return SEPARATOR.join(_segments(namespace))
