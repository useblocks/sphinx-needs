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

from functools import lru_cache

from ub_needs_exchange import (
    EMPTY_LOCAL,
    EMPTY_SEGMENT,
    SEGMENT_CHARACTER,
    SEPARATOR,
    id_problem,
    split_id,
)

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
