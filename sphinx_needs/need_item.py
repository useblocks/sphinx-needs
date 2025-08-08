# To maintain back-compatibility,
# we need to implement MutableMapping semantics, these are the methods that need to be implemented:
# - implement immutable: __getitem__, __iter__, __len__
# - implement mutable: __setitem__, __delitem__
# - inherit immutable: __contains__, keys, items, values, get, __eq__, and __ne__
# - inherit mutable: pop, popitem, clear, update, and setdefault
#
# For NeedPartItem, we should not allow any mutability, as it is a view into a need.
# For NeedItem, we allow mutability, but only for values, i.e. it should not allow adding or removing keys.
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, Literal, overload

from sphinx_needs.data import NeedsInfoType, NeedsPartType


class NeedItem:
    """A class representing a single need item."""

    __slots__ = ("_data",)

    _immutable = {
        "id",
        "type",
        "docname",
        "lineno",
        "lineno_content",
        "id_complete",
        "id_parent",
        "is_need",
        "is_part",
        "is_external",
        "is_import",
        "template",
        "pre_template",
        "post_template",
    }

    def __init__(self, data: NeedsInfoType) -> None:
        """Initialize the NeedItem instance."""
        self._data = data

    def __repr__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem({self._data!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem({self._data!s})"

    def copy(self) -> NeedItem:
        """Return a copy of the NeedItem."""
        return NeedItem(self._data.copy())

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedItem):
            return False
        return self._data == other._data

    def __ne__(self, other: object) -> bool:
        """Check if two NeedItems are not equal."""
        return not self.__eq__(other)

    def __contains__(self, key: str) -> bool:
        """Check if the need item contains a key."""
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        return self._data.__iter__()

    @overload
    def __getitem__(
        self,
        key: Literal[
            "collapse",
            "hide",
            "is_import",
            "is_external",
            "is_modified",
            "is_need",
            "is_part",
            "jinja_content",
            "has_dead_links",
            "has_forbidden_dead_links",
            "constraints_passed",
        ],
    ) -> bool: ...

    @overload
    def __getitem__(
        self,
        key: Literal[
            "id",
            "id_parent",
            "id_complete",
            "type",
            "type_name",
            "type_prefix",
            "type_color",
            "type_style",
            "content",
            "pre_content",
            "post_content",
            "doctype",
            "external_url",
            "external_css",
        ],
    ) -> str: ...

    @overload
    def __getitem__(
        self,
        key: Literal[
            "status",
            "docname",
            "external_url",
            "layout",
            "style",
            "template",
            "post_template",
            "pre_template",
            "constraints_error",
            "section_name",
            "parent_need",
        ],
    ) -> str | None: ...

    @overload
    def __getitem__(self, key: Literal["modifications"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["lineno", "lineno_content"]) -> int | None: ...

    @overload
    def __getitem__(self, key: Literal["tags"]) -> Sequence[str]: ...

    @overload
    def __getitem__(self, key: Literal["arch"]) -> dict[str, str]: ...

    @overload
    def __getitem__(self, key: Literal["parts"]) -> dict[str, NeedsPartType]: ...

    @overload
    def __getitem__(self, key: str) -> Any: ...

    def __getitem__(self, key: str) -> Any:
        """Get an item by key."""
        return self._data[key]  # type: ignore[literal-required]

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item by key with a default value."""
        return self._data.get(key, default)

    def keys(self) -> Iterable[str]:
        """Return the keys of the need item."""
        return self._data.keys()

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        return self._data.values()

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        return self._data.items()

    def __setitem__(self, key: str, value: Any) -> None:
        """Set an item by key."""
        if key not in self._data:
            raise KeyError(
                f"Cannot add new key {key!r} to NeedItem, only existing keys can be modified."
            )
        if key in self._immutable:
            raise KeyError(f"Cannot modify immutable key {key!r} in NeedItem.")
        self._data[key] = value  # type: ignore[literal-required]

    def get_part(self, part_id: str) -> NeedPartItem | None:
        """Get a part by its ID."""
        if part_id not in self._data.get("parts", {}):
            return None
        part_data = self._data["parts"][part_id]
        # TODO when creating a part, links/links_back are set to empty, but what about other link fields?
        full_part: NeedsInfoType = {**self._data, **part_data}  # type: ignore[typeddict-unknown-key]
        full_part["id_complete"] = f"{self._data['id']}.{part_data['id']}"
        full_part["id_parent"] = self._data["id"]
        full_part["is_need"] = False
        full_part["is_part"] = True
        return NeedPartItem(full_part)

    def iter_parts(self) -> Iterable[NeedPartItem]:
        """Yield all parts, a.k.a sub-needs, from a need."""
        for part_id in self._data.get("parts", {}):
            if (part := self.get_part(part_id)) is not None:
                yield part


class NeedPartItem:
    """A class representing a part of a need, which is a sub-need."""

    __slots__ = ("_data",)

    def __init__(self, data: NeedsInfoType) -> None:
        """Initialize the NeedPartItem instance."""
        self._data = data

    def __repr__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem({self._data!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem({self._data!s})"

    def copy(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem."""
        return NeedPartItem(self._data.copy())

    def copy_for_needtable(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem with specific fields for needtable."""
        # TODO this is a hack for current logic in the needtable processing
        # but we don't want to start exposing mutability on the part just for this
        part_data = self._data.copy()
        part_data["id"] = part_data["id_complete"]
        part_data["title"] = part_data["content"]
        return NeedPartItem(part_data)

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedPartItem):
            return False
        return self._data == other._data

    def __ne__(self, other: object) -> bool:
        """Check if two NeedItems are not equal."""
        return not self.__eq__(other)

    def __contains__(self, key: str) -> bool:
        """Check if the need item contains a key."""
        return key in self._data

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        return self._data.__iter__()

    @overload
    def __getitem__(
        self,
        key: Literal[
            "collapse",
            "hide",
            "is_import",
            "is_external",
            "is_modified",
            "is_need",
            "is_part",
            "jinja_content",
            "has_dead_links",
            "has_forbidden_dead_links",
            "constraints_passed",
        ],
    ) -> bool: ...

    @overload
    def __getitem__(
        self,
        key: Literal[
            "id",
            "id_parent",
            "id_complete",
            "type",
            "type_name",
            "type_prefix",
            "type_color",
            "type_style",
            "content",
            "doctype",
            "external_css",
        ],
    ) -> str: ...

    @overload
    def __getitem__(
        self,
        key: Literal[
            "status",
            "docname",
            "external_url",
            "layout",
            "style",
            "template",
            "post_template",
            "pre_template",
            "constraints_error",
            "parent_need",
            "pre_content",
            "post_content",
            "section_name",
        ],
    ) -> str | None: ...

    @overload
    def __getitem__(self, key: Literal["modifications"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["lineno", "lineno_content"]) -> int | None: ...

    @overload
    def __getitem__(self, key: Literal["tags"]) -> Sequence[str]: ...

    @overload
    def __getitem__(self, key: Literal["arch"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(self, key: str) -> Any: ...

    def __getitem__(self, key: str) -> Any:
        """Get an item by key."""
        return self._data[key]  # type: ignore[literal-required]

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item by key with a default value."""
        return self._data.get(key, default)

    def keys(self) -> Iterable[str]:
        """Return the keys of the need item."""
        return self._data.keys()

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        return self._data.values()

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        return self._data.items()
