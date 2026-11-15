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

from ub_needs_exchange import id_problem, split_id


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
