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

import warnings
from collections.abc import Iterable, Iterator, Mapping, Sequence
from itertools import chain
from typing import Any, Literal, overload

from sphinx_needs.data import NeedsInfoType, NeedsPartType


class NeedItem:
    """A class representing a single need item."""

    __slots__ = ("_backlinks", "_core", "_extras", "_links")

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

    def __init__(
        self,
        *,
        core: NeedsInfoType,
        extras: dict[str, str],
        links: dict[str, list[str]],
        backlinks: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the NeedItem instance.

        :param core: The core data of the need item.
        :param extras: Additional data for the need item.
            This should contain all extra keys that are defined in the configuration,
            and should not contain any keys that are in core, links or backlinks.
        :param links: Links associated with the need item.
            This should contain all link keys that are defined in the configuration,
            and should not contain any keys that are in core or extras.
        :param backlinks: Backlinks associated with the need item.
           If set, this must contain all keys that are in links, with the suffix '_back',
           and should not contain any keys that are in core or extras.
        """
        self._core = core
        self._extras = extras
        self._links = links
        if backlinks is None:
            self._backlinks: dict[str, list[str]] = {
                f"{li}_back": [] for li in self._links
            }
        else:
            if set(backlinks) != {f"{li}_back" for li in self._links}:
                raise ValueError(
                    "Backlinks must contain all keys from links with '_back' suffix."
                )
            self._backlinks = backlinks
        # consistency checks for data
        all_keys = [
            *self._core.keys(),
            *self._extras.keys(),
            *self._links.keys(),
            *self._backlinks.keys(),
        ]
        if len(all_keys) != len(set(all_keys)):
            duplicates = [key for key in set(all_keys) if all_keys.count(key) > 1]
            raise ValueError(
                f"NeedItem keys must be unique across core, extras, links, and backlinks. Duplicate keys: {duplicates}"
            )
        if not self._core["is_need"]:
            raise ValueError(
                "NeedItem core must have 'is_need' set to True for a need item."
            )
        if self._core["is_part"]:
            raise ValueError(
                "NeedItem core must have 'is_part' set to False for a need item."
            )

    def __repr__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem(core={self._core!r}, extras={self._extras!r}, links={self._links!r}, backlinks={self._backlinks!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem(core={self._core!s}, extras={self._extras!s}, links={self._links!s}, backlinks={self._backlinks!s})"

    def copy(self) -> NeedItem:
        """Return a copy of the NeedItem."""
        return NeedItem(
            core=self._core.copy(),
            extras=self._extras.copy(),
            links=self._links.copy(),
            backlinks=self._backlinks.copy(),
        )

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedItem):
            return False
        return (
            self._core == other._core
            and self._extras == other._extras
            and self._links == other._links
            and self._backlinks == other._backlinks
        )

    def __ne__(self, other: object) -> bool:
        """Check if two NeedItems are not equal."""
        return not self.__eq__(other)

    def __contains__(self, key: str) -> bool:
        """Check if the need item contains a key."""
        return (
            key in self._core
            or key in self._extras
            or key in self._links
            or key in self._backlinks
        )

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        return chain(self._core, self._extras, self._links, self._backlinks)

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
        if key in self._core:
            return self._core[key]  # type: ignore[literal-required]
        elif key in self._extras:
            warnings.warn(
                "Direct access to extras via __getitem__ is deprecated. Use get_extra() method instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._extras[key]
        elif key in self._links:
            warnings.warn(
                "Direct access to links via __getitem__ is deprecated. Use get_links() method instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._links[key]
        elif key in self._backlinks:
            warnings.warn(
                "Direct access to backlinks via __getitem__ is deprecated. Use get_backlinks() method instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self._backlinks[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item by key with a default value."""
        if key in self:
            return self[key]
        return default

    def get_extra(self, key: str) -> str:
        """Get an extra by key.

        :raises KeyError: If the key is not an extra.
        """
        return self._extras[key]

    def get_links(self, link_type: str) -> list[str]:
        """Get links by key.

        :raises KeyError: If the link_type is not a link type.
        """
        return self._links[link_type]

    def get_backlinks(self, link_type: str) -> list[str]:
        """Get backlinks by key.

        :raises KeyError: If the link_type is not a backlink type.
        """
        return self._backlinks[link_type + "_back"]

    def keys(self) -> Iterable[str]:
        """Return the keys of the need item."""
        return chain(
            self._core.keys(),
            self._extras.keys(),
            self._links.keys(),
            self._backlinks.keys(),
        )

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        return chain(
            self._core.values(),
            self._extras.values(),
            self._links.values(),
            self._backlinks.values(),
        )

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        return chain(
            self._core.items(),
            self._extras.items(),
            self._links.items(),
            self._backlinks.items(),
        )

    def __setitem__(self, key: str, value: Any) -> None:
        """Set an item by key."""
        if key in self._immutable:
            raise KeyError(f"Cannot modify immutable key {key!r} in NeedItem.")
        if key in self._core:
            self._core[key] = value  # type: ignore[literal-required]
        elif key in self._extras:
            self._extras[key] = value
        elif key in self._links:
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                raise TypeError(f"Value for key {key!r} must be a list of strings.")
            self._links[key] = value
        elif key in self._backlinks:
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                raise TypeError(f"Value for key {key!r} must be a list of strings.")
            self._backlinks[key]
        else:
            raise KeyError(f"Only existing keys can be set, not: {key!r}")

    def get_part(self, part_id: str) -> NeedPartItem | None:
        """Get a part by its ID."""
        try:
            return NeedPartItem(self, part_id)
        except KeyError:
            return None

    def iter_parts(self) -> Iterable[NeedPartItem]:
        """Yield all parts, a.k.a sub-needs, from a need."""
        for part_id in self._core.get("parts", {}):
            if (part := self.get_part(part_id)) is not None:
                yield part


class NeedPartItem:
    """A class representing a part of a need, which is a sub-need.

    Any data coming from the part will override the data from the parent need.

    Note this is a read-only view into a need part.
    It does not allow modification of the underlying data.
    """

    __slots__ = ("_need", "_part_data", "_part_id")

    def __init__(self, need: NeedItem, part_id: str) -> None:
        """Initialize the NeedPartItem instance."""
        if not isinstance(need, NeedItem):
            raise TypeError("NeedPartItem requires a NeedItem instance.")
        self._need = need
        self._part_id = part_id
        try:
            self._part_data: dict[str, Any] = need._core["parts"][part_id].copy()  # type: ignore[assignment]
        except KeyError:
            raise KeyError(f"Part ID {part_id!r} does not exist in NeedItem.")

        self._part_data["id_complete"] = f"{self._need['id']}.{self._part_data['id']}"
        self._part_data["id_parent"] = self._need["id"]
        self._part_data["is_need"] = False
        self._part_data["is_part"] = True

        # TODO part data gets created with links / links_back set to empty, so these will be overriden, but what about other link types

    def __repr__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem(part={self._part_id!r}, need={self._need!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem(part={self._part_id!s}, need={self._need!s})"

    def copy(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem."""
        return NeedPartItem(self._need, self._part_id)

    def copy_for_needtable(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem with specific fields for needtable."""
        # TODO this is a hack for current logic in the needtable processing
        # but we don't want to start exposing mutability on the part just for this
        new_part = self.copy()
        new_part._part_data["id"] = new_part._part_data["id_complete"]
        new_part._part_data["title"] = new_part._part_data["content"]
        return new_part

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedPartItem):
            return False
        return self._need == other._need and self._part_id == other._part_id

    def __ne__(self, other: object) -> bool:
        """Check if two NeedItems are not equal."""
        return not self.__eq__(other)

    def __contains__(self, key: str) -> bool:
        """Check if the need item contains a key."""
        return key in self._need

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        return iter(self._need)

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
        if key in self._part_data:
            return self._part_data[key]
        elif key in self._need:
            return self._need[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item by key with a default value."""
        if key in self:
            return self[key]
        return default

    def keys(self) -> Iterable[str]:
        """Return the keys of the need item."""
        return self._need.keys()

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        for key in self._need:
            if key in self._part_data:
                yield self._part_data[key]
            else:
                yield self._need[key]

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        for key in self._need:
            if key in self._part_data:
                yield (key, self._part_data[key])
            else:
                yield (key, self._need[key])
