"""The field reads a call of the dynamic-function pass makes, seen as it makes them.

``resolve_functions`` opens a watch around one call: around the whole call of your own
function, or, for a built-in function or derive rule of a step that computes values
after the built-in functions, around each evaluation of a filter or ``where`` only
(``filters_only``: the filter functions mark the watch :attr:`Watch.active` while they
evaluate). While a read is watched, every ``NeedItem.__getitem__`` (and so ``.get``, and
the fast path of a filter) and every name the ``eval`` of a filter looks up on a need
is passed to the watch, as the need's id and the name. A read returns what it returns
without the watch.

With no watch open nothing is replaced: ``NeedItem.__getitem__`` is the class's own,
and the filter functions test one module attribute, :data:`current`.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Container, Iterator
from contextlib import contextmanager
from typing import Any

from sphinx_needs.need_item import NeedItem

OnRead = Callable[[str, str], bool]
"""Called with the id of the need read and the name read; returns whether the read
was noted (a read the check reports)."""


class Watch:
    """One open watch.

    :ivar notify: What a read is passed to.
    :ivar active: The reads are watched now: always for a watch of a whole call, while
        a filter or ``where`` is evaluated for one of its filters only.
    :ivar names: The names a read of which is passed on; any other is not.
    :ivar replayed: What reads recorded for an earlier call are passed to, at once
        (:func:`replay`); by default, each to :attr:`notify`.
    """

    __slots__ = ("active", "names", "notify", "replayed")

    def __init__(
        self,
        notify: OnRead,
        *,
        active: bool,
        names: Container[str],
        replayed: Callable[[list[tuple[str, str]]], None] | None = None,
    ) -> None:
        self.notify = notify
        self.active = active
        self.names = names
        self.replayed = replayed


#: the watch open, if any
current: Watch | None = None

#: the ``NeedItem.__getitem__`` the open watch replaced, which a read still calls
_getitem: Callable[[NeedItem, str], Any] = NeedItem.__getitem__


def _watched_getitem(self: NeedItem, key: str) -> Any:
    if (watch := current) is not None and watch.active and key in watch.names:
        watch.notify(self._core["id"], key)
    return _getitem(self, key)


def _set_getitem(getitem: Callable[[NeedItem, str], Any]) -> None:
    # through ``type.__setattr__``: the type checker refuses assigning a method
    type.__setattr__(NeedItem, "__getitem__", getitem)


@contextmanager
def watching(
    on_read: OnRead,
    *,
    filters_only: bool,
    names: Container[str],
    replayed: Callable[[list[tuple[str, str]]], None] | None = None,
) -> Iterator[Watch]:
    """Watch the reads of one call while the block runs.

    :param on_read: What each read is passed to.
    :param filters_only: Watch only while a filter or ``where`` is evaluated (the
        filter functions set :attr:`Watch.active` around it), not the whole call.
    :param names: The names worth passing on: a read of any other is not.
    :param replayed: What reads recorded for an earlier call are passed to at once.
    """
    global current, _getitem
    assert current is None, "a watch is already open"
    current = watch = Watch(
        on_read, active=not filters_only, names=names, replayed=replayed
    )
    # the one in place now, which an extension or a test may have replaced since import
    _getitem = previous = vars(NeedItem)["__getitem__"]
    _set_getitem(_watched_getitem)
    try:
        yield watch
    finally:
        current = None
        _set_getitem(previous)


@contextmanager
def recording() -> Iterator[list[tuple[str, str]]]:
    """Keep the noted reads made while the block runs, to replay them
    (:func:`replay`) where a result computed once is used again, such as a ``links``
    rule's candidates."""
    found: list[tuple[str, str]] = []
    if (watch := current) is None:
        yield found
        return
    notify = watch.notify

    def record(need_id: str, name: str) -> bool:
        if noted := notify(need_id, name):
            found.append((need_id, name))
        return noted

    watch.notify = record
    try:
        yield found
    finally:
        watch.notify = notify


def replay(reads: list[tuple[str, str]]) -> None:
    """Pass reads made for an earlier call to the watch open, as if made again."""
    if (watch := current) is None:
        return
    if watch.replayed is not None:
        watch.replayed(reads)
        return
    for need_id, name in reads:
        watch.notify(need_id, name)


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
        if (
            (watch := current) is not None
            and watch.active
            and key in watch.names
            and key not in self._not_fields
        ):
            watch.notify(self._need_id, key)
        return super().__getitem__(key)
