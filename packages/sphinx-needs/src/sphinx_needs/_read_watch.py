"""The field reads a call of the dynamic-function pass makes, seen as it makes them.

``resolve_functions`` opens a watch around one call: around the whole call of your own
function, or, for a built-in function or derive rule of a step that computes values
after the built-in functions, around each evaluation of a filter or ``where``
(``filters_only``). While a read is watched, every ``NeedItem.__getitem__`` (and so
``.get``, and the fast path of a filter) and every name the ``eval`` of a filter looks
up on a need is passed to the watch, as the need's id and the name. A read returns what
it returns without the watch.

With no watch open nothing is replaced: ``NeedItem.__getitem__`` is the class's own,
and the filter functions test one module attribute, :data:`current`.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager
from typing import Any

from sphinx_needs.need_item import NeedItem

OnRead = Callable[[str, str], bool]
"""Called with the id of the need read and the name read; returns whether the read
was noted (a read the check reports)."""


class Watch:
    """One open watch.

    :ivar on_read: What a read is passed to.
    :ivar filters_only: Only the reads of a filter or ``where`` are watched, not those
        of the rest of the call.
    :ivar recorded: The noted reads also kept while :func:`recording`, to replay them.
    """

    __slots__ = ("filters_only", "on_read", "recorded")

    def __init__(self, on_read: OnRead, *, filters_only: bool) -> None:
        self.on_read = on_read
        self.filters_only = filters_only
        self.recorded: list[tuple[str, str]] | None = None

    def read(self, need_id: str, name: str) -> None:
        if self.on_read(need_id, name) and self.recorded is not None:
            self.recorded.append((need_id, name))


#: the watch open, if any
current: Watch | None = None

_GETITEM = NeedItem.__getitem__


def _watched_getitem(self: NeedItem, key: str) -> Any:
    if current is not None:
        current.read(self.id, key)
    return _GETITEM(self, key)


def _set_getitem(getitem: Callable[[NeedItem, str], Any]) -> None:
    # through ``type.__setattr__``: the type checker refuses assigning a method
    type.__setattr__(NeedItem, "__getitem__", getitem)


@contextmanager
def watching(on_read: OnRead, *, filters_only: bool) -> Iterator[Watch]:
    """Watch the reads of one call while the block runs.

    :param on_read: What each read is passed to.
    :param filters_only: Watch only the evaluation of a filter or ``where``
        (:func:`in_filter`), not the whole call.
    """
    global current
    assert current is None, "a watch is already open"
    current = watch = Watch(on_read, filters_only=filters_only)
    if not filters_only:
        _set_getitem(_watched_getitem)
    try:
        yield watch
    finally:
        current = None
        _set_getitem(_GETITEM)


@contextmanager
def in_filter() -> Iterator[None]:
    """Watch every read while one filter or ``where`` is evaluated, under a watch that
    watches the filters only."""
    watch = current
    assert watch is not None and watch.filters_only, "a watch of filters"
    watch.filters_only = False
    _set_getitem(_watched_getitem)
    try:
        yield
    finally:
        _set_getitem(_GETITEM)
        watch.filters_only = True


def filters_watched() -> bool:
    """Whether a watch of filters is open, and no filter is evaluated under it yet."""
    return current is not None and current.filters_only


@contextmanager
def recording() -> Iterator[list[tuple[str, str]]]:
    """Keep the noted reads made while the block runs, to replay them
    (:func:`replay`) where a result computed once is used again, such as a ``links``
    rule's candidates."""
    watch = current
    found: list[tuple[str, str]] = []
    if watch is None:
        yield found
        return
    outer, watch.recorded = watch.recorded, found
    try:
        yield found
    finally:
        watch.recorded = outer
        if outer is not None:
            outer.extend(found)


def replay(reads: Collection[tuple[str, str]]) -> None:
    """Pass reads made for an earlier call to the watch open, as if made again."""
    if (watch := current) is not None:
        for need_id, name in reads:
            watch.read(need_id, name)


class ReadingContext(dict[str, Any]):
    """The names a filter's ``eval`` reads, as a dict passed as its globals.

    Every name the expression looks up is passed to the watch, but for ``not_fields``
    (what the context sets over the need's fields). ``eval`` looks a name up through
    ``__getitem__`` when its globals are not exactly a dict, a comprehension's and a
    lambda's names included, and only the names the evaluation reaches: what a ``and``
    or ``or`` skips is not read.
    """

    __slots__ = ("_need_id", "_not_fields")

    def __init__(
        self, context: dict[str, Any], need_id: str, not_fields: Collection[str]
    ) -> None:
        super().__init__(context)
        self._need_id = need_id
        self._not_fields = not_fields

    def __getitem__(self, key: str) -> Any:
        if current is not None and key not in self._not_fields:
            current.read(self._need_id, key)
        return super().__getitem__(key)
