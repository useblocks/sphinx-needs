"""Namespaced ids: what sphinx-needs makes of a need id that holds ``::``.

The grammar is ``ub_needs_exchange.need_id``'s, the one module that knows the separator:
an id splits at its LAST ``::`` into a namespace (segments of ASCII letters, digits,
``_`` and ``-``) and a local id, and an id that holds ``::`` but does not split cleanly is
a plain id. This module holds sphinx-needs' policy over it: whether the project splits
at all (``needs_namespaced_ids``), and what an id that does not split cleanly costs.

A need's namespace and local id are read ONCE, where the need is created
(:func:`read_id`, called by ``api.need._generate_need``, the funnel every creation route
passes), and stored on the need (``NeedItem.id_ns_segments``, ``NeedItem.id_local``):
the id never changes after creation, so they cannot go stale. The design record is
``design/namespaced-ids.md``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from typing import TYPE_CHECKING

from ub_needs_exchange import (
    EMPTY_LOCAL,
    EMPTY_SEGMENT,
    SEGMENT_CHARACTER,
    SEPARATOR,
    id_problem,
    split_id,
)

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from sphinx_needs.need_item import NeedItem

#: the attribute of the application that holds the build's hints (never the
#: environment, which Sphinx pickles)
_HINTS_ATTRIBUTE = "_needs_local_id_hints"

#: what the warning of an id that does not split cleanly says of each class of problem
_REASONS = {
    EMPTY_LOCAL: f"nothing follows the last {SEPARATOR!r}",
    EMPTY_SEGMENT: "a namespace segment is empty",
    SEGMENT_CHARACTER: (
        "a namespace segment holds a character other than a letter, a digit, '_' or '-'"
    ),
}


@lru_cache(maxsize=4096)
def _shared(namespace: tuple[str, ...]) -> tuple[str, ...]:
    """One tuple per namespace: the first equal tuple met, so that the needs of a
    namespace share it. Bounded, as the namespaces of a build are few; a namespace
    dropped from the cache is only stored once more."""
    return namespace


def read_id(
    need_id: str, namespaced: bool, /
) -> tuple[tuple[str, ...], str, str | None]:
    """The namespace, the local id and the problem of a need's id, as the project reads
    it.

    :param need_id: The need's id, as written, generated or imported.
    :param namespaced: ``needs_namespaced_ids``: False reads every id as plain.
    :return: The namespace's segments (``()`` for a plain id), the local id (the whole
        id for a plain id), and, for an id that holds ``::`` but does not split cleanly
        (a plain id), the class of its problem (``ub_needs_exchange.EMPTY_LOCAL``,
        ``EMPTY_SEGMENT`` or ``SEGMENT_CHARACTER``); ``None`` otherwise, and always
        ``None`` with the switch off.
    """
    if not namespaced:
        return (), need_id, None
    namespace, local = split_id(need_id)
    if namespace:
        return _shared(namespace), local, None
    return (), need_id, id_problem(need_id)


def unclean_id_message(need_id: str, problem: str, /) -> str:
    """The ``needs.id_namespace`` warning of a need whose id holds ``::`` but does not
    split cleanly: the id is kept as a plain id, and the message names the class of the
    problem (never the offending segment, which would mean cutting the id outside
    ``ub_needs_exchange.need_id``) and the three ways out.

    :param problem: The class ``ub_needs_exchange.id_problem`` gives.
    """
    return (
        f"Need id {need_id!r} contains {SEPARATOR!r} but is not a namespaced id "
        f"({_REASONS[problem]}), so it is read as a plain id. Correct the id, set "
        "needs_namespaced_ids = False to read no id as namespaced, or suppress the "
        "warning type needs.id_namespace."
    )


def id_matched_by_patterns(
    pattern: str, need_id: str, local_id: str, /, *, full: bool = False
) -> bool:
    """Whether an id pattern accepts a need's id: :ref:`needs_id_regex` and a need
    type's ``id_regex`` accept an id whose LOCAL id matches, or which matches as a whole
    (an id master accepted as a whole stays accepted, whatever its local id).

    The one place both patterns read the id from, and ``needextract``'s test of an
    argument naming an id.

    :param pattern: The pattern.
    :param need_id: The id, as written or generated.
    :param local_id: Its local id, as the project reads it (:ref:`needs_namespaced_ids`):
        the whole id for a plain id, where local and whole are one test.
    :param full: Match the whole text (``re.fullmatch``), not its start (``re.match``).
    """
    match = re.fullmatch if full else re.match
    return match(pattern, local_id) is not None or (
        local_id != need_id and match(pattern, need_id) is not None
    )


def nor_local(need_id: str, local_id: str) -> str:
    """What a refusal by an id pattern adds for a namespaced id: its local id, which the
    pattern did not match either."""
    return "" if local_id == need_id else f", nor does its local id {local_id!r}"


class LocalIdHints:
    """The did-you-mean of a dead link target or a ``:need:`` role naming no need: the
    one need, if exactly one, in a namespace whose local id is the target's id.

    A target is hinted when its id names no need, holds no ``::``, and exactly one need
    has it as its local id in a non-empty namespace, and, where the target names a part,
    that need has the part. With ``needs_namespaced_ids`` off no need is in a namespace,
    so nothing is hinted: the switch is not read here. The index of local ids is built
    lazily, once, when the first such target is met: a build with no dead target never
    builds it. One per build, kept on the application (:func:`reset_local_id_hints`),
    never in the pickled environment. Nothing changes in what resolves.
    """

    __slots__ = ("_index", "_needs")

    def __init__(self, needs: Mapping[str, NeedItem]) -> None:
        """:param needs: The needs of the build, by id."""
        self._needs = needs
        self._index: dict[str, list[str]] | None = None

    def hint(self, need_id: str, part: str | None = None) -> str:
        """What a "not found" message about the target *need_id* gains: `` (did you mean
        'nc::REQ_2'?)`` (the full id, with *part* re-attached), or ``""``.

        :param need_id: The target's id, its part and condition stripped.
        :param part: The target's part, if it named one.
        """
        if SEPARATOR in need_id or need_id in self._needs:
            return ""
        if self._index is None:
            self._index = {}
            for key, need in self._needs.items():
                if need.id_ns_segments:
                    self._index.setdefault(need.id_local, []).append(key)
        candidates = self._index.get(need_id, ())
        if len(candidates) != 1:
            return ""
        (target,) = candidates
        if part is None:
            return f" (did you mean {target!r}?)"
        if part not in (self._needs[target]["parts"] or {}):
            return ""
        return f" (did you mean {f'{target}.{part}'!r}?)"


def reset_local_id_hints(app: Sphinx, needs: Mapping[str, NeedItem], /) -> LocalIdHints:
    """Start the did-you-mean of a build's dead targets afresh, when its needs are
    post-processed: one per build, kept on the application *app* (a server that builds
    twice gets a new one each time), never in the environment Sphinx pickles."""
    hints = LocalIdHints(needs)
    setattr(app, _HINTS_ATTRIBUTE, hints)
    return hints


def local_id_hints(app: Sphinx, needs: Mapping[str, NeedItem], /) -> LocalIdHints:
    """The build's did-you-mean, as :func:`reset_local_id_hints` made it for *app*; made
    over *needs* where there is none yet."""
    hints = getattr(app, _HINTS_ATTRIBUTE, None)
    if isinstance(hints, LocalIdHints):
        return hints
    return reset_local_id_hints(app, needs)
