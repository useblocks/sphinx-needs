from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from itertools import chain
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sphinx_needs.data import NeedsInfoType


_IdSet = list[tuple[str, Optional[str]]]
"""Set of (need, part) ids."""


class _Indexes:
    """Indexes of common fields for fast filtering of needs."""

    __slots__ = (
        "is_external",
        "parts_to_needs",
        "status",
        "tags",
        "type_names",
        "types",
    )

    def __init__(
        self,
        *,
        is_external: dict[bool, _IdSet],
        types: dict[str, _IdSet],
        type_names: dict[str, _IdSet],
        status: dict[str | None, _IdSet],
        tags: dict[str, _IdSet],
        parts_to_needs: dict[str, list[str]],
    ) -> None:
        self.is_external = is_external
        """Mapping of `is_external` values to (need, part) ids."""
        self.types = types
        """Mapping of `type` values to (need, part) ids."""
        self.type_names = type_names
        """Mapping of `type_name` values to (need, part) ids."""
        self.status = status
        """Mapping of `status` values to (need, part) ids."""
        self.tags = tags
        """Mapping of `tags` values to (need, part) ids that contain them."""
        self.parts_to_needs = parts_to_needs
        """Mapping of part ids to the needs that contain them."""


class _LazyIndexes:
    """A lazily computed view of indexes for needs."""

    __slots__ = ("_indexes", "_needs")

    def __init__(self, needs: Mapping[str, NeedsInfoType]) -> None:
        self._needs = needs
        self._indexes: _Indexes | None = None

    @property
    def needs(self) -> Mapping[str, NeedsInfoType]:
        """Get the needs."""
        return self._needs

    @property
    def indexes(self) -> _Indexes:
        """Get the indexes, computing them if necessary."""
        if self._indexes is None:
            self._indexes = self._compute()
        return self._indexes

    def _compute(self) -> _Indexes:
        """Lazily compute the indexes for the needs, when first requested."""
        _idx_is_external: dict[bool, _IdSet] = {}
        _idx_types: dict[str, _IdSet] = {}
        _idx_type_names: dict[str, _IdSet] = {}
        _idx_status: dict[str | None, _IdSet] = {}
        _idx_tags: dict[str, _IdSet] = {}
        _idx_parts_to_needs: dict[str, list[str]] = {}

        for id, need in self._needs.items():
            _idx_is_external.setdefault(need["is_external"], []).append((id, None))
            _idx_types.setdefault(need["type"], []).append((id, None))
            _idx_type_names.setdefault(need["type_name"], []).append((id, None))
            _idx_status.setdefault(need["status"], []).append((id, None))
            for tag in need["tags"]:
                _idx_tags.setdefault(tag, []).append((id, None))

            for part_id, part in need["parts"].items():
                _idx_parts_to_needs.setdefault(part_id, []).append(id)
                # In principle, parts should not have the fields below (and thus should be copied from the need),
                # but there is currently no validation for this, so we also record them.
                _idx_is_external.setdefault(
                    part.get("is_external", need["is_external"]),  # type: ignore[arg-type]
                    [],
                ).append((id, part_id))
                _idx_types.setdefault(
                    part.get("type", need["type"]),  # type: ignore[arg-type]
                    [],
                ).append((id, part_id))
                _idx_type_names.setdefault(
                    part.get("type_name", need["type_name"]),  # type: ignore[arg-type]
                    [],
                ).append((id, part_id))
                _idx_status.setdefault(
                    part.get("status", need["status"]),  # type: ignore[arg-type]
                    [],
                ).append((id, part_id))
                for tag in part.get("tags", need["tags"]):  # type: ignore[attr-defined]
                    _idx_tags.setdefault(tag, []).append((id, part_id))

        return _Indexes(
            is_external=_idx_is_external,
            types=_idx_types,
            type_names=_idx_type_names,
            status=_idx_status,
            tags=_idx_tags,
            parts_to_needs=_idx_parts_to_needs,
        )


class NeedsView(Mapping[str, "NeedsInfoType"]):
    """A read-only view of needs, mapping need ids to need data,
    with "fast" filtering methods.

    The needs are read-only and fully resolved
    (e.g. dynamic values and back links have been computed etc)
    """

    __slots__ = ("_indexes", "_maybe_len", "_selected_ids")

    @classmethod
    def _from_needs(cls, needs: Mapping[str, NeedsInfoType], /) -> NeedsView:
        """Create a new view of needs from a mapping of needs."""
        return cls(_indexes=_LazyIndexes(needs), _selected_ids=None)

    def __init__(
        self,
        *,
        _indexes: _LazyIndexes,
        _selected_ids: dict[str, None] | None,
    ) -> None:
        """Create a new view of needs,

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, use the filter methods to create new views.
        """
        self._indexes = _indexes
        self._selected_ids = (
            _selected_ids  # note we use a dict here like an ordered set
        )
        # Cache the length of the needs when first requested
        self._maybe_len: int | None = None

    @property
    def _all_needs(self) -> Mapping[str, NeedsInfoType]:
        return self._indexes.needs

    def __getitem__(self, key: str) -> NeedsInfoType:
        if self._selected_ids is not None and key not in self._selected_ids:
            raise KeyError(key)
        return self._all_needs[key]

    def __iter__(self) -> Iterator[str]:
        if self._selected_ids is None:
            yield from self._all_needs
        else:
            for id in self._selected_ids:
                if id in self._all_needs:
                    yield id

    def __len__(self) -> int:
        if self._maybe_len is None:
            self._maybe_len = sum(1 for _ in self)
        return self._maybe_len

    def __bool__(self) -> bool:
        try:
            next(iter(self))
        except StopIteration:
            return False
        return True

    def to_list_with_parts(self) -> NeedsAndPartsListView:
        """Create a new view with needs and parts."""
        if self._selected_ids is None:
            return NeedsAndPartsListView(_indexes=self._indexes, _selected_ids=None)
        _selected_ids: dict[tuple[str, str | None], None] = {}
        for id in self._selected_ids:
            if need := self._all_needs.get(id):
                _selected_ids[(id, None)] = None
                for part_id in need["parts"]:
                    _selected_ids[(id, part_id)] = None
        return NeedsAndPartsListView(
            _indexes=self._indexes, _selected_ids=_selected_ids
        )

    def _copy_filtered(self, ids: Iterable[tuple[str, str | None]]) -> NeedsView:
        """Create a new view with only the needs with the given ids.

        This is a helper method for the filter methods,
        it ensures that the lazy indexing is copied over,
        so that they are not recomputed.
        """
        selected_ids = {n: None for n, p in ids if p is None and n in self._all_needs}
        if self._selected_ids is not None:
            selected_ids = {n: None for n in self._selected_ids if n in selected_ids}
        return NeedsView(_indexes=self._indexes, _selected_ids=selected_ids)

    def filter_ids(self, values: Iterable[str]) -> NeedsView:
        """Create new view with needs filtered by the ``id`` field."""
        return self._copy_filtered((v, None) for v in values)

    def filter_is_external(self, value: bool) -> NeedsView:
        """Create new view with only needs where ``is_external`` field is true/false."""
        return self._copy_filtered(self._indexes.indexes.is_external.get(value, []))

    def filter_types(self, values: list[str], or_type_names: bool = False) -> NeedsView:
        """Create new view with only needs that have certain ``type`` field values.

        :param values: List of types to filter by.
        :param or_type_names: If True, filter by both ``type`` and ``type_name`` field
        """
        if or_type_names:
            return self._copy_filtered(
                i
                for value in values
                for i in chain(
                    self._indexes.indexes.types.get(value, []),
                    self._indexes.indexes.type_names.get(value, []),
                )
            )
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.types.get(value, [])
        )

    def filter_statuses(self, values: list[str]) -> NeedsView:
        """Create new view with only needs that have certain ``status`` field values."""
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.status.get(value, [])
        )

    def filter_has_tag(self, values: list[str]) -> NeedsView:
        """Create new view with only needs that have at least one of these values in the ``tags`` field list."""
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.tags.get(value, [])
        )


class NeedsAndPartsListView:
    """A read-only view of needs and parts,
    after resolution (e.g. back links have been computed etc)

    The parts are created by creating a copy of the need for each item in ``parts``,
    and then overwriting a subset of fields with the values from the part.
    """

    __slots__ = ("_indexes", "_maybe_len", "_selected_ids")

    def __init__(
        self,
        *,
        _indexes: _LazyIndexes,
        _selected_ids: dict[tuple[str, str | None], None] | None,
    ):
        """Initialize a new view of needs.

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, create from a NeedsView instance.
        """
        self._indexes = _indexes
        self._selected_ids = (
            _selected_ids  # note we use a dict here like an ordered set
        )
        # Cache the length of the needs when first requested
        self._maybe_len: int | None = None

    @property
    def _all_needs(self) -> Mapping[str, NeedsInfoType]:
        return self._indexes.needs

    def __iter__(self) -> Iterator[NeedsInfoType]:
        """Iterate over the needs and parts in the view."""
        from sphinx_needs.roles.need_part import create_need_from_part

        if self._selected_ids is None:
            for need in self._all_needs.values():
                yield need
                for part in need["parts"].values():
                    yield create_need_from_part(need, part)
        else:
            for id, part_id in self._selected_ids:
                if id not in self._all_needs:
                    continue
                if part_id is None:
                    yield self._all_needs[id]
                else:
                    need = self._all_needs[id]
                    if part_id in need["parts"]:
                        yield create_need_from_part(need, need["parts"][part_id])

    def __bool__(self) -> bool:
        try:
            next(iter(self))
        except StopIteration:
            return False
        return True

    def __len__(self) -> int:
        if self._maybe_len is None:
            self._maybe_len = sum(1 for _ in self)
        return self._maybe_len

    def get_need(self, id: str, part_id: str | None = None) -> NeedsInfoType | None:
        """Get a need by id, or return None if it does not exist.

        If ``part_id`` is provided, return the part of the need with that id, or None if it does not exist.
        """
        from sphinx_needs.roles.need_part import create_need_from_part

        if part_id is None:
            if self._selected_ids is None or (id, None) in self._selected_ids:
                return self._all_needs.get(id)
        else:
            if (
                (self._selected_ids is None or (id, part_id) in self._selected_ids)
                and (need := self._all_needs.get(id))
                and (part := need["parts"].get(part_id))
            ):
                return create_need_from_part(need, part)

        return None

    def _copy_filtered(
        self, ids: Iterable[tuple[str, str | None]]
    ) -> NeedsAndPartsListView:
        """Create a new view with only the needs/parts with the given ids."""
        if self._selected_ids is None:
            selected_ids = {n: None for n in ids}
        else:
            selected_ids = {n: None for n in ids if n in self._selected_ids}
        return NeedsAndPartsListView(_indexes=self._indexes, _selected_ids=selected_ids)

    def filter_ids(self, values: Iterable[str]) -> NeedsAndPartsListView:
        """Create new view with needs/parts filtered by the ``id`` field."""
        selected_ids: Iterable[tuple[str, str | None]]
        if self._selected_ids is None:
            # the id can either be a need or a part id
            selected_ids = [
                (need_id, None) for need_id in values if need_id in self._all_needs
            ]
            for part_id in values:
                selected_ids.extend(
                    (need_id, part_id)
                    for need_id in self._indexes.indexes.parts_to_needs.get(part_id, [])
                )
        else:
            val_set = set(values)
            selected_ids = (
                v for v in self._selected_ids if v[0] in val_set or v[1] in val_set
            )
        return self._copy_filtered(selected_ids)

    def filter_is_external(self, value: bool) -> NeedsAndPartsListView:
        """Create new view with only needs/parts where ``is_external`` field is true/false."""
        return self._copy_filtered(self._indexes.indexes.is_external.get(value, []))

    def filter_types(
        self, values: list[str], or_type_names: bool = False
    ) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have certain ``type`` field values.

        :param values: List of types to filter by.
        :param or_type_names: If True, filter by both ``type`` and ``type_name`` field
        """
        if or_type_names:
            return self._copy_filtered(
                i
                for value in values
                for i in chain(
                    self._indexes.indexes.types.get(value, []),
                    self._indexes.indexes.type_names.get(value, []),
                )
            )
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.types.get(value, [])
        )

    def filter_statuses(self, values: list[str]) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have certain ``status`` field values."""
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.status.get(value, [])
        )

    def filter_has_tag(self, values: list[str]) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have at least one of these values in the ``tags`` field list."""
        return self._copy_filtered(
            i for value in values for i in self._indexes.indexes.tags.get(value, [])
        )
