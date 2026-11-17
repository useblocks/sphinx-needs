"""The ``c.id`` facets and ``c.in_namespace()`` of a filter: a need's id, by its parts.

``c`` is the need's check context, which the filter context sets over every field, so
no field a project declares can shadow these, as for ``c.source`` (``_source_facets``,
whose mechanism this module follows: one table of readers that the ``eval`` tier's
``NeedCheckContext.id``, the portable tier's ``c.id.<facet>`` chain, the did-you-mean of
an unknown facet and a derived field's whitelist all read):

- ``c.id.ns``: the need's namespace, as text (``"nc::m2"``), ``""`` for a plain id;
- ``c.id.local``: the need's local id, the whole id for a plain id;
- ``c.in_namespace("<ns>")``: whether the need's namespace is ``<ns>`` or below it,
  compared by segments (``c.in_namespace("nc")`` is true of ``nc::X`` and ``nc::m2::X``,
  not of ``ncx::X``).

A part reads its need's. Each reads what the need stored when it was created
(``NeedItem.id_ns_segments``, ``NeedItem.id_local``): the project's
``needs_namespaced_ids`` decided it there, so with the switch off every need is plain
and the names stay defined. Root ``id`` is the full id, as ever.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Mapping
from typing import Any, Final

from ub_needs_exchange import parse_namespace

ID_NAME: Final = "id"
"""The attribute of the check context a filter reads the id facets by, ``c.id.<facet>``."""

ID_FACETS: Final = ("local", "ns")
"""The facets a filter reads as ``c.id.<facet>``, sorted."""

IN_NAMESPACE: Final = "in_namespace"
"""The check of the check context, ``c.in_namespace("<ns>")``."""


def _read_local(need: Any) -> str:
    return need.id_local


def _read_ns(need: Any) -> str:
    return need.id_ns


READERS: Final[Mapping[str, Callable[[Any], Any]]] = {
    "local": _read_local,
    "ns": _read_ns,
}
"""Each facet's reader of a need (a part's need, for a part): one per name of
:data:`ID_FACETS`."""


def unknown_facet(name: str) -> str:
    """The error of ``c.id.<name>`` naming no facet, with the closest facet."""
    close = difflib.get_close_matches(name, ID_FACETS, 1, 0.6)
    if close:
        return f"c.id has no facet {name!r} (did you mean {close[0]!r}?)"
    return f"c.id has no facet {name!r} (its facets: {', '.join(ID_FACETS)})"


#: the error of reading ``c.id`` itself as a value: it holds the facets, not the id
_NOT_THE_ID: Final = (
    "c.id holds the facets of the id, not the id: compare id, c.id.local or c.id.ns"
)


class IdFacets:
    """What ``c.id`` is in a filter ``eval`` evaluates (``NeedCheckContext.id``)."""

    __slots__ = ("_need",)

    def __init__(self, need: Any) -> None:
        """:param need: The need (a part's need, for a part)."""
        self._need = need

    def __getattr__(self, name: str) -> Any:
        reader = READERS.get(name)
        if reader is None:
            raise AttributeError(unknown_facet(name))
        return reader(self._need)

    def __eq__(self, other: object) -> bool:
        """``c.id`` is the facets of the id, not the id: compared with anything else
        (``c.id == "nc::REQ_1"``, ``c.id in [...]``) it is an error of the filter, not
        a silent "no need"."""
        if not isinstance(other, IdFacets):
            raise TypeError(_NOT_THE_ID)
        return other._need is self._need

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        """Hashed (a set member, a dict key: ``c.id in {"nc::REQ_1"}``), ``c.id`` is an
        error of the filter as it is compared: it is not the id. Its text
        (``str(c.id)``) stays printable, for messages."""
        raise TypeError(_NOT_THE_ID)

    def __repr__(self) -> str:
        return f"<c.id of {self._need['id']!r}>"


def namespace_argument(text: object) -> tuple[str, ...]:
    """The segments of the namespace ``c.in_namespace(text)`` names.

    :raises ValueError: For a text that names no namespace: the empty text (a need in
        no namespace is ``c.id.ns == ""``), or one that is not a namespace.
    :raises TypeError: For an argument that is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"c.in_namespace takes a namespace as a string, not {type(text).__name__}"
        )
    if not text:
        raise ValueError(
            "c.in_namespace('') names no namespace; a need in no namespace is "
            "c.id.ns == ''"
        )
    try:
        return parse_namespace(text)
    except ValueError as err:
        raise ValueError(f"c.in_namespace: {err}") from None


def in_namespace(need_namespace: tuple[str, ...], namespace: tuple[str, ...]) -> bool:
    """Whether a need in *need_namespace* is in *namespace* or below it, by segments."""
    return need_namespace[: len(namespace)] == namespace
