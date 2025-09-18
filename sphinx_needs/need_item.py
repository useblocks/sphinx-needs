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
from dataclasses import dataclass, field
from itertools import chain
from typing import TYPE_CHECKING, Any, Literal, Protocol, overload, runtime_checkable

from sphinx_needs.data import (
    NeedsContentInfoType,
    NeedsInfoComputedType,
    NeedsInfoType,
    NeedsPartType,
    NeedsSourceInfoType,
)

if TYPE_CHECKING:
    from sphinx_needs.needs_schema import (
        AllowedTypes,
        FieldFunctionArray,
        LinksFunctionArray,
    )


@runtime_checkable
class NeedItemSourceProtocol(Protocol):
    """Protocol for need item source types."""

    @property
    def dict_repr(self) -> NeedsSourceInfoType:
        """Return a dictionary representation of the source."""
        ...


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedItemSourceUnknown:
    """A class representing the source of a need item, from an unknown source."""

    docname: str | None = None
    lineno: int | None = None
    lineno_content: int | None = None
    external_url: str | None = None
    is_import: bool = False
    is_external: bool = False
    dict_repr: NeedsSourceInfoType = field(init=False, default_factory=dict, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsSourceInfoType = {
            "docname": self.docname,
            "lineno": self.lineno,
            "lineno_content": self.lineno_content,
            "external_url": self.external_url,
            "is_import": self.is_import,
            "is_external": self.is_external,
        }
        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedItemSourceDirective:
    """A class representing the source of a need item, from a need directive."""

    docname: str
    lineno: int
    lineno_content: int
    dict_repr: NeedsSourceInfoType = field(init=False, default_factory=dict, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsSourceInfoType = {
            "docname": self.docname,
            "lineno": self.lineno,
            "lineno_content": self.lineno_content,
            "external_url": None,
            "is_import": False,
            "is_external": False,
        }
        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedItemSourceService:
    """A class representing the source of a need item, from a service directive."""

    docname: str
    lineno: int
    dict_repr: NeedsSourceInfoType = field(init=False, default_factory=dict, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsSourceInfoType = {
            "docname": self.docname,
            "lineno": self.lineno,
            "lineno_content": None,
            "external_url": None,
            "is_import": False,
            "is_external": False,
        }
        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedItemSourceExternal:
    """A class representing the source of a need item, from an external source."""

    url: str
    dict_repr: NeedsSourceInfoType = field(init=False, default_factory=dict, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsSourceInfoType = {
            "docname": None,
            "lineno": None,
            "lineno_content": None,
            "external_url": self.url,
            "is_import": False,
            "is_external": True,
        }
        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedItemSourceImport:
    """A class representing the source of a need item, from an import directive."""

    docname: str
    lineno: int
    path: str
    dict_repr: NeedsSourceInfoType = field(init=False, default_factory=dict, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsSourceInfoType = {
            "docname": self.docname,
            "lineno": self.lineno,
            "lineno_content": None,
            "external_url": None,
            "is_import": True,
            "is_external": False,
        }

        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedsContent:
    """A class representing the content of a need item."""

    doctype: str
    content: str
    pre_content: str | None = None
    post_content: str | None = None
    jinja_content: bool = False
    template: str | None = None
    pre_template: str | None = None
    post_template: str | None = None

    dict_repr: NeedsContentInfoType = field(
        init=False, default_factory=dict, repr=False
    )  # type: ignore[assignment]

    def __post_init__(self) -> None:
        d: NeedsContentInfoType = {
            "doctype": self.doctype,
            "content": self.content,
            "pre_content": self.pre_content,
            "post_content": self.post_content,
            "jinja_content": self.jinja_content,
            "template": self.template,
            "pre_template": self.pre_template,
            "post_template": self.post_template,
        }
        self.dict_repr.update(d)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedPartData:
    """A class representing a part of a need, which is generally derived from ``:np:`` role within the parent need."""

    id: str
    content: str
    backlinks: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedModification:
    """A class representing a modification to a need item, by a needextend directive."""

    docname: str | None = None
    lineno: int | None = None


class NeedConstraintResults(Mapping[str, tuple[tuple[str, bool, str | None], ...]]):
    """A class representing the results of constraints on a need item."""

    __slots__ = ("_data",)

    def __init__(
        self, constraints: Mapping[str, tuple[tuple[str, bool, str | None], ...]]
    ) -> None:
        self._data = constraints

    def __getitem__(self, key: str) -> tuple[tuple[str, bool, str | None], ...]:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"NeedConstraintResults({self._data!r})"

    def to_dict(self) -> dict[str, dict[str, bool]]:
        """Convert the constraint results to a dictionary."""
        return {
            constraint: {check: result for check, result, _ in results}
            for constraint, results in self._data.items()
        }

    def first_error(self) -> str | None:
        """Return the first error message found in the constraint results, or None if none found."""
        for results in self._data.values():
            for _, passed, error in results:
                if not passed and error is not None:
                    return error
        return None

    def all_passed(self) -> bool:
        """Return True if all constraints passed, False otherwise."""
        return all(
            passed for results in self._data.values() for _, passed, _ in results
        )


class NeedItem:
    """A class representing a single need item."""

    __slots__ = (
        "_backlinks",
        "_backlinks_keymap",
        "_computed",
        "_constraint_results",
        "_content",
        "_core",
        "_dynamic_fields",
        "_extras",
        "_links",
        "_modifications",
        "_parts",
        "_source",
    )

    _immutable_core = {"id", "type"}

    def __init__(
        self,
        *,
        source: NeedItemSourceProtocol | None,
        content: NeedsContent,
        core: NeedsInfoType,
        extras: dict[str, AllowedTypes | None],
        links: dict[str, list[str]],
        backlinks: dict[str, list[str]] | None = None,
        parts: Sequence[NeedPartData] = (),
        modifications: Sequence[NeedModification] = (),
        constraint_results: None | NeedConstraintResults = None,
        dynamic_fields: dict[str, FieldFunctionArray | LinksFunctionArray]
        | None = None,
        _validate: bool = True,
    ) -> None:
        """Initialize the NeedItem instance.

        :param source: The source of the need item.
        :param core: The core data of the need item.
        :param extras: Additional data for the need item.
            This should contain all extra keys that are defined in the configuration,
            and should not contain any keys that are in core, links or backlinks.
        :param links: Links associated with the need item.
            This should contain all link keys that are defined in the configuration,
            and should not contain any keys that are in core or extras.
        :param backlinks: Backlinks associated with the need item.
           If set, this must contain all keys that are in links,
           and should not contain any keys that are in core or extras.
        :param _validate: Perform runtime type validation of initialisation inputs
        """
        if _validate:
            # run pre-checks
            if not isinstance(core, dict):
                raise TypeError("NeedItem core must be a dictionary.")
            if missing_core := set(NeedsInfoType.__annotations__).difference(core):
                raise ValueError(
                    f"NeedItem core missing required keys: {sorted(missing_core)}"
                )
            if extra_core := set(core).difference(NeedsInfoType.__annotations__):
                raise ValueError(
                    f"NeedItem core contains extra keys: {sorted(extra_core)}"
                )
            if not isinstance(extras, dict):
                raise TypeError("NeedItem extras must be a dictionary.")
            if not isinstance(links, dict):
                raise TypeError("NeedItem links must be a dictionary.")
            if backlinks is not None and not isinstance(backlinks, dict):
                raise TypeError("NeedItem backlinks must be a dictionary.")
            if source is not None and not isinstance(source, NeedItemSourceProtocol):
                raise TypeError("NeedItem source must obey the NeeItemSourceProtocol.")
            if not isinstance(content, NeedsContent):
                raise TypeError("NeedItem content must be a NeedsContent instance.")
            if not isinstance(modifications, Sequence) or any(
                not isinstance(m, NeedModification) for m in modifications
            ):
                raise TypeError(
                    "NeedItem modifications must be a sequence of NeedModification instances."
                )
            if not isinstance(dynamic_fields, None | dict):
                raise TypeError("NeedItem dynamic_fields must be a dictionary or None.")

        # set internal fields
        self._dynamic_fields = (
            dynamic_fields.copy() if dynamic_fields is not None else {}
        )
        self._core = core.copy()
        self._extras = extras.copy()
        self._links = links.copy()
        if backlinks is None:
            self._backlinks: dict[str, list[str]] = {li: [] for li in self._links}
        else:
            self._backlinks = backlinks.copy()
        self._backlinks_keymap = {f"{key}_back": key for key in self._links}
        """mapping of exposed backlink keys to actual link keys, e.g. {'link_type_back': 'link_type'}
        
        This is required for distinct access to backlinks in the NeedItem API.

        """
        self._content = content
        self._source = source if source is not None else NeedItemSourceUnknown()
        self.set_parts(parts, _recompute=False)
        self._modifications = tuple(modifications)
        self.set_constraint_results(constraint_results, _recompute=False)
        self._recompute()

        # consistency checks for data, this is optional so that we don't have to re-run when copying an instance.
        if _validate:
            if not all(
                isinstance(v, list) and all(isinstance(i, str) for i in v)
                for v in self._links.values()
            ):
                raise TypeError(
                    "NeedItem links must be a dictionary of lists of strings."
                )
            if not all(
                isinstance(v, list) and all(isinstance(i, str) for i in v)
                for v in self._backlinks.values()
            ):
                raise TypeError(
                    "NeedItem backlinks must be a dictionary of lists of strings."
                )
            if set(self._backlinks) != set(self._links):
                raise ValueError(
                    f"Backlink keys must be the same as link keys, difference found: {sorted(set(self._backlinks) ^ set(self._links))}"
                )
            all_keys = [
                *self._core,
                *self._extras,
                *self._links,
                *self._backlinks_keymap,
                *self._source.dict_repr,
                *self._content.dict_repr,
                *self._computed,
            ]
            if len(all_keys) != len(set(all_keys)):
                duplicates = sorted(
                    key for key in set(all_keys) if all_keys.count(key) > 1
                )
                raise ValueError(
                    f"NeedItem keys must be unique across core, computed, extras, links, and backlinks. Duplicate keys: {duplicates}"
                )
            if constraint_results is not None and set(constraint_results) != set(
                self._core.get("constraints", [])
            ):
                raise ValueError(
                    "constraint_results keys must match the constraints defined in the need."
                )

    def _recompute(self) -> None:
        parts: Mapping[str, NeedsPartType] = {
            p.id: {
                "id": p.id,
                "content": p.content,
                **(
                    {f"{k}_back": v for k, v in p.backlinks.items() if v}  # type: ignore[typeddict-item]
                    if p.backlinks is not None
                    else {}
                ),
            }
            for p in self._parts.values()
        }
        self._computed: NeedsInfoComputedType = {
            "is_need": True,
            "is_part": False,
            "modifications": len(self._modifications),
            "is_modified": bool(self._modifications),
            "id_parent": self._core["id"],
            "id_complete": self._core["id"],
            "parts": parts,
            "constraints_results": self._constraint_results.to_dict()
            if self._constraint_results is not None
            else None,
            "constraints_error": self._constraint_results.first_error()
            if self._constraint_results is not None
            else None,
            "constraints_passed": self._constraint_results.all_passed()
            if self._constraint_results is not None
            else None,
            "section_name": sections[0]
            if (sections := self._core["sections"])
            else None,
            "parent_need": parent_needs[0]
            if (parent_needs := self._links.get("parent_needs"))
            else None,
        }

    @property
    def id(self) -> str:
        """Return the ID of the need item."""
        return self._core["id"]

    @property
    def source(self) -> NeedItemSourceProtocol:
        """Return the source of the need item."""
        return self._source

    @property
    def content(self) -> NeedsContent:
        """Return the content of the need item."""
        return self._content

    @property
    def parts(self) -> Iterable[NeedPartData]:
        """Return the parts of the need item."""
        yield from self._parts.values()

    @property
    def has_dynamic_fields(self) -> bool:
        """Return True if the need item has dynamic fields, False otherwise."""
        return bool(self._dynamic_fields)

    @property
    def modifications(self) -> tuple[NeedModification, ...]:
        """Return the modifications of the need item."""
        return self._modifications

    @property
    def constraint_results(self) -> None | NeedConstraintResults:
        """Return the constraint results of the need item."""
        return self._constraint_results

    def __repr__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem(core={self._core!r}, extras={self._extras!r}, links={self._links!r}, backlinks={self._backlinks!r}, source={self._source!r}, content={self._content!r}, parts={self._parts!r}, modifications={self._modifications!r}, dynamic_fields={self._dynamic_fields!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedItem."""
        return f"NeedItem(core={self._core!s}, extras={self._extras!s}, links={self._links!s}, backlinks={self._backlinks!s}, source={self._source!s}, content={self._content!s}, parts={self._parts!s}, modifications={self._modifications!s}, dynamic_fields={self._dynamic_fields!s})"

    def copy(self) -> NeedItem:
        """Return a copy of the NeedItem."""
        return NeedItem(
            core=self._core,
            extras=self._extras,
            links=self._links,
            backlinks=self._backlinks,
            source=self._source,
            content=self._content,
            parts=list(self._parts.values()),
            modifications=self._modifications,
            constraint_results=self._constraint_results,
            dynamic_fields=self._dynamic_fields,
            _validate=False,
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
            and self._source == other._source
            and self._content == other._content
            and self._parts == other._parts
            and self._modifications == other._modifications
            and self._constraint_results == other._constraint_results
            and self._dynamic_fields == other._dynamic_fields
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
            or key in self._backlinks_keymap
            or key in self._source.dict_repr
            or key in self._content.dict_repr
            or key in self._computed
        )

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        return chain(
            self._core,
            self._extras,
            self._links,
            self._backlinks_keymap,
            self._source.dict_repr,
            self._content.dict_repr,
            self._computed,
        )

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
    def __getitem__(self, key: Literal["tags", "constraints"]) -> Sequence[str]: ...

    @overload
    def __getitem__(self, key: Literal["arch"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(self, key: Literal["parts"]) -> Mapping[str, NeedsPartType]: ...

    @overload
    def __getitem__(
        self, key: Literal["constraints_results"]
    ) -> Mapping[str, Mapping[str, bool]]: ...

    @overload
    def __getitem__(self, key: str) -> Any: ...

    def __getitem__(self, key: str) -> Any:
        """Get an item by key."""
        if key in self._computed:
            return self._computed[key]  # type: ignore[literal-required]
        if key in self._core:
            return self._core[key]  # type: ignore[literal-required]
        elif key in self._extras:
            return self._extras[key]
        elif key in self._links:
            return self._links[key]
        elif key in self._backlinks_keymap:
            return self._backlinks[self._backlinks_keymap[key]]
        elif key in self._source.dict_repr:
            return self._source.dict_repr[key]  # type: ignore[literal-required]
        elif key in self._content.dict_repr:
            return self._content.dict_repr[key]  # type: ignore[literal-required]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item by key with a default value."""
        if key in self:
            return self[key]
        return default

    def keys(self) -> Iterable[str]:
        """Return the keys of the need item."""
        return chain(
            self._core.keys(),
            self._extras.keys(),
            self._links.keys(),
            self._backlinks_keymap.keys(),
            self._source.dict_repr.keys(),
            self._content.dict_repr.keys(),
            self._computed.keys(),
        )

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        return chain(
            self._core.values(),
            self._extras.values(),
            self._links.values(),
            self._backlinks.values(),
            self._source.dict_repr.values(),
            self._content.dict_repr.values(),
            self._computed.values(),
        )

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        return chain(
            self._core.items(),
            self._extras.items(),
            self._links.items(),
            ((k1, self._backlinks[k2]) for k1, k2 in self._backlinks_keymap.items()),
            self._source.dict_repr.items(),
            self._content.dict_repr.items(),
            self._computed.items(),
        )

    def __setitem__(self, key: str, value: Any) -> None:
        """Set an item by key."""
        if key in self._immutable_core:
            raise KeyError(f"Cannot modify immutable key {key!r} in NeedItem.")
        elif key == "constraints":
            if self._constraint_results is not None:
                raise KeyError(
                    "Cannot modify 'constraints' if 'constraints_results' has already been computed."
                )
        elif key in self._computed:
            raise KeyError(f"Cannot modify computed key {key!r} in NeedItem.")
        elif key in self._source.dict_repr:
            raise KeyError(f"Cannot modify source key {key!r} in NeedItem.")
        elif key in self._content.dict_repr:
            raise KeyError(f"Cannot modify content key {key!r} in NeedItem.")
        elif key in self._core:
            self._core[key] = value  # type: ignore[literal-required]
        elif key in self._extras:
            self._extras[key] = value
        elif key in self._links:
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                raise TypeError(
                    f"Value for link key {key!r} must be a list of strings."
                )
            self._links[key] = value
        elif key in self._backlinks_keymap:
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                raise TypeError(
                    f"Value for backlink key {key!r} must be a list of strings."
                )
            self._backlinks[self._backlinks_keymap[key]] = value
        else:
            raise KeyError(f"Only existing keys can be set, not: {key!r}")
        self._recompute()

    def reset_backlinks(self) -> None:
        """Reset all backlinks to empty lists (including parts)."""
        for key in self._backlinks:
            self._backlinks[key] = []
        for part in self._parts.values():
            for k in part.backlinks:
                part.backlinks[k] = []

    def add_backlink(self, link_type: str, backlink: str) -> None:
        """Add a backlink to the need."""
        if link_type not in self._backlinks:
            raise KeyError(f"Link type {link_type!r} does not exist in backlinks.")
        if backlink not in self._backlinks[link_type]:
            self._backlinks[link_type].append(backlink)

    def get_part_item(self, part_id: str) -> NeedPartItem | None:
        """Get a part, merged with its parent need, by its ID."""
        try:
            return NeedPartItem(self, part_id)
        except KeyError:
            return None

    def iter_part_items(self) -> Iterable[NeedPartItem]:
        """Yield all parts, merged with the parent part, from a need."""
        for part in self.parts:
            if (part_item := self.get_part_item(part.id)) is not None:
                yield part_item

    def get_extra(self, key: str) -> AllowedTypes | None:
        """Get an extra by key.

        :raises KeyError: If the key is not an extra.
        """
        return self._extras[key]

    def iter_extra_keys(self) -> Iterable[str]:
        """Yield all extra keys."""
        yield from self._extras.keys()

    def iter_extra_items(self) -> Iterable[tuple[str, AllowedTypes | None]]:
        """Yield all extras as key-value pairs."""
        yield from self._extras.items()

    def get_links(self, link_type: str) -> list[str]:
        """Get link references by link_type key.

        :raises KeyError: If the link_type is not a link type.
        """
        return self._links[link_type]

    def iter_links_keys(self) -> Iterable[str]:
        """Yield all link_type keys."""
        yield from self._links.keys()

    def iter_links_items(self) -> Iterable[tuple[str, list[str]]]:
        """Yield all links as (link_type, references) pairs."""
        yield from self._links.items()

    def get_backlinks(self, link_type: str) -> list[str]:
        """Get backlink references by link_type key.

        :raises KeyError: If the link_type is not a backlink type.
        """
        return self._backlinks[link_type]

    def iter_backlinks_items(self) -> Iterable[tuple[str, list[str]]]:
        """Yield all backlinks as (link_type, references) pairs."""
        for key in self._backlinks:
            yield (key, self._backlinks[key])

    def set_content(self, content: NeedsContent) -> None:
        """Replace the content of the need item.

        :param new_content: The new content to set.
        """
        if not isinstance(content, NeedsContent):
            raise TypeError("new_content must be a NeedsContent instance.")
        self._content = content

    def _validate_part(self, part: NeedPartData) -> None:
        """Add a part to the need item."""
        if not isinstance(part, NeedPartData):
            raise TypeError("part must be a NeedPartData instance.")
        if not isinstance(part.id, str) or not part.id:
            raise ValueError(f"Part must have a non-empty string ID: {part.id!r}")
        if not isinstance(part.content, str):
            raise ValueError(f"Part {part.id!r} must have content of string type")
        if not isinstance(part.backlinks, dict) or any(
            not isinstance(k, str)
            or not isinstance(v, list)
            or any(not isinstance(i, str) for i in v)
            for k, v in part.backlinks.items()
        ):
            raise ValueError(
                f"Part {part.id!r} backlinks must be a dictionary of lists of strings."
            )
        if unknown_part_links := (set(part.backlinks) - set(self._links)):
            raise ValueError(
                f"Part {part.id!r} backlinks keys must be a subset of the need's link types, got unknown keys: {sorted(unknown_part_links)}"
            )

    def set_parts(
        self, parts: Sequence[NeedPartData], *, _recompute: bool = True
    ) -> None:
        """Set the parts of the need item.

        :param parts: The parts to set.
        """
        if not isinstance(parts, Sequence):
            raise TypeError("parts must be a sequence of NeedPartData instances.")
        for part in parts:
            self._validate_part(part)
        if len({p.id for p in parts}) != len(parts):
            raise ValueError("NeedItem parts must have unique IDs.")
        self._parts = {part.id: part for part in parts}
        if _recompute:
            self._recompute()

    def get_part(self, part_id: str) -> NeedPartData | None:
        """Get a part by its ID."""
        return self._parts.get(part_id)

    def add_modification(self, modification: NeedModification) -> None:
        """Add a modification to the need item.

        :param modification: The modification to add.
        """
        if not isinstance(modification, NeedModification):
            raise TypeError("modification must be a NeedModification instance.")
        self._modifications += (modification,)
        self._recompute()

    def set_constraint_results(
        self,
        constraint_results: None | NeedConstraintResults,
        *,
        _recompute: bool = True,
    ) -> None:
        """Set the constraint results for the need item.

        :param constraint_results: The constraint results to set.
        """
        if constraint_results is not None and not isinstance(
            constraint_results, NeedConstraintResults
        ):
            raise TypeError(
                "constraint_results must be a NeedConstraintResults instance or None."
            )
        if constraint_results is not None and set(constraint_results) != set(
            self._core.get("constraints", [])
        ):
            raise ValueError(
                "constraint_results keys must match the constraints defined in the need."
            )
        self._constraint_results = constraint_results
        if _recompute:
            self._recompute()


class NeedPartItem:
    """A class representing a part of a need, which is a sub-need, merged with the parent need.

    Any data coming from the part will override the data from the parent need.

    Note this is a read-only view into a need part.
    It does not allow modification of the underlying data.
    """

    __slots__ = ("_need", "_overrides", "_part")

    def __init__(self, need: NeedItem, part_id: str) -> None:
        """Initialize the NeedPartItem instance."""
        if not isinstance(need, NeedItem):
            raise TypeError("NeedPartItem requires a NeedItem instance.")
        if (part := need.get_part(part_id)) is None:
            raise KeyError(f"Part ID {part_id!r} does not exist in NeedItem parts.")
        self._need = need.copy()
        self._part = part

        self._overrides = {
            "id": part.id,
            "id_complete": f"{need.id}.{part.id}",
            "id_parent": need.id,
            "is_need": False,
            "is_part": True,
            "parent_need": None,
            "parts": {},  # parts cannot have parts
            "content": part.content,
            # parts cannot link to anything
            **{name: [] for name in need.iter_links_keys()},
            # backlinks should be what links to the part and not what links to the parent need
            **{
                f"{name}_back": []
                if part.backlinks is None or not (blinks := part.backlinks.get(name))
                else blinks
                for name in need.iter_links_keys()
            },
        }

    @property
    def part_id(self) -> str:
        """Return the part ID."""
        return self._part.id

    def __repr__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem(part={self.part_id!r}, need={self._need!r})"

    def __str__(self) -> str:
        """Return a string representation of the NeedPartItem."""
        return f"NeedPartItem(part={self.part_id!s}, need={self._need!s})"

    def copy(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem."""
        return NeedPartItem(self._need, self.part_id)

    def copy_for_needtable(self) -> NeedPartItem:
        """Return a copy of the NeedPartItem with specific fields for needtable."""
        # TODO this is a hack for current logic in the needtable processing
        # but we don't want to start exposing mutability on the part just for this
        new_part = self.copy()
        new_part._overrides["id"] = new_part["id_complete"]
        new_part._overrides["title"] = new_part["content"]
        return new_part

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedPartItem):
            return False
        return self._need == other._need and self.part_id == other.part_id

    def __ne__(self, other: object) -> bool:
        """Check if two NeedItems are not equal."""
        return not self.__eq__(other)

    def __contains__(self, key: str) -> bool:
        """Check if the need item contains a key."""
        return key in self._need or key in self._overrides

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the need item."""
        yield from set(chain(self._need, self._overrides))

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
    def __getitem__(self, key: Literal["tags", "constraints"]) -> Sequence[str]: ...

    @overload
    def __getitem__(self, key: Literal["parts"]) -> Mapping[str, NeedsPartType]: ...

    @overload
    def __getitem__(self, key: Literal["arch"]) -> Mapping[str, str]: ...

    @overload
    def __getitem__(
        self, key: Literal["constraints_results"]
    ) -> Mapping[str, Mapping[str, bool]]: ...

    @overload
    def __getitem__(self, key: str) -> Any: ...

    def __getitem__(self, key: str) -> Any:
        """Get an item by key."""
        if key in self._overrides:
            return self._overrides[key]
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
        yield from self

    def values(self) -> Iterable[Any]:
        """Return the values of the need item."""
        for key in self:
            if key in self._overrides:
                yield self._overrides[key]
            else:
                yield self._need[key]

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        for key in self:
            if key in self._overrides:
                yield (key, self._overrides[key])
            else:
                yield (key, self._need[key])

    def get_extra(self, key: str) -> str:
        """Get an extra by key.

        :raises KeyError: If the key is not an extra.
        """
        if key not in self._need._extras:
            raise KeyError(key)
        return self[key]  # type: ignore[no-any-return]

    def iter_extra_keys(self) -> Iterable[str]:
        """Yield all extra keys."""
        yield from self._need._extras.keys()

    def iter_extra_items(self) -> Iterable[tuple[str, str]]:
        """Yield all extras as key-value pairs."""
        for key in self._need._extras:
            yield (key, self[key])

    def get_links(self, link_type: str) -> list[str]:
        """Get link references by link_type key.

        :raises KeyError: If the link_type is not a link type.
        """
        if link_type not in self._need._links:
            raise KeyError(link_type)
        return self[link_type]  # type: ignore[no-any-return]

    def iter_links_keys(self) -> Iterable[str]:
        """Yield all link_type keys."""
        yield from self._need._links.keys()

    def iter_links_items(self) -> Iterable[tuple[str, list[str]]]:
        """Yield all links as (link_type, references) pairs."""
        for key in self._need._links:
            yield (key, self[key])

    def get_backlinks(self, link_type: str) -> list[str]:
        """Get backlink references by link_type key.

        :raises KeyError: If the link_type is not a backlink type.
        """
        if link_type not in self._need._backlinks:
            raise KeyError(link_type)
        return self[f"{link_type}_back"]  # type: ignore[no-any-return]

    def iter_backlinks_items(self) -> Iterable[tuple[str, list[str]]]:
        """Yield all backlinks as (link_type, references) pairs."""
        for key in self._need._backlinks:
            yield (key, self.get_backlinks(key))
