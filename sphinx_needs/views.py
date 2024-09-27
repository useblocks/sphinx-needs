from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Iterable, Iterator, Mapping

if TYPE_CHECKING:
    from sphinx_needs.data import NeedsInfoType


class _Indexes:
    """Indexes of common fields for fast filtering of needs."""

    __slots__ = (
        "is_external",
        "status",
        "tags",
        "types",
        "type_names",
        "parts_to_needs",
        "parts_differ",
    )

    def __init__(
        self,
        *,
        is_external: dict[bool, list[str]],
        types: dict[str, list[str]],
        type_names: dict[str, list[str]],
        status: dict[str | None, list[str]],
        tags: dict[str, list[str]],
        parts_to_needs: dict[str, list[str]],
        parts_differ: set[str],
    ) -> None:
        self.is_external = is_external
        self.types = types
        self.type_names = type_names
        self.status = status
        self.tags = tags
        self.parts_to_needs = parts_to_needs
        self.parts_differ = parts_differ


class NeedsView(Mapping[str, "NeedsInfoType"]):
    """A read-only view of needs, mapping need ids to need data,
    with "fast" filtering methods.

    The needs are read-only and fully resolved
    (e.g. dynamic values and back links have been computed etc)
    """

    __slots__ = ("_needs", "_maybe_indexes", "_maybe_len")

    def __init__(
        self,
        *,
        _needs: Mapping[str, NeedsInfoType],
        _indexes: _Indexes | None = None,
    ):
        """Create a new view of needs,

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, use the filter methods to create new views.
        """
        self._needs = _needs
        self._maybe_len: int | None = (
            None  # Cache the length of the needs when first requested
        )
        self._maybe_indexes = _indexes

    def _get_indexes(self) -> _Indexes:
        """Lazily compute the indexes for the needs, when first requested."""
        if self._maybe_indexes is None:
            _idx_is_external: dict[bool, list[str]] = {}
            _idx_types: dict[str, list[str]] = {}
            _idx_type_names: dict[str, list[str]] = {}
            _idx_status: dict[str | None, list[str]] = {}
            _idx_tags: dict[str, list[str]] = {}
            _idx_parts_to_needs: dict[str, list[str]] = {}
            _idx_parts_differ: set[str] = set()
            for id, need in self._needs.items():
                _idx_is_external.setdefault(need["is_external"], []).append(id)
                _idx_types.setdefault(need["type"], []).append(id)
                _idx_type_names.setdefault(need["type_name"], []).append(id)
                _idx_status.setdefault(need["status"], []).append(id)
                for tag in need["tags"]:
                    _idx_tags.setdefault(tag, []).append(id)

                parts = need["parts"]
                parts_different = False
                for part_id, part in parts.items():
                    _idx_parts_to_needs.setdefault(part_id, []).append(id)
                    # Check if parts have different fields to the parent,
                    # i.e. can we filter on the parent fields alone in NeedsAndPartsListView?
                    # In principle, parts should not have these fields,
                    # but there is currently no validation for this, so we need to check.
                    for field in ("is_external", "type", "type_name", "status", "tags"):
                        if field in part and part[field] != need[field]:  # type: ignore[literal-required]
                            parts_different = True
                if parts_different:
                    _idx_parts_differ.add(id)

            self._maybe_indexes = _Indexes(
                is_external=_idx_is_external,
                types=_idx_types,
                type_names=_idx_type_names,
                status=_idx_status,
                tags=_idx_tags,
                parts_to_needs=_idx_parts_to_needs,
                parts_differ=_idx_parts_differ,
            )

        return self._maybe_indexes

    def _copy_filtered(self, ids: Iterable[str]) -> NeedsView:
        """Create a new view with only the needs with the given ids.

        This is a helper method for the filter methods,
        it ensures that the lazy indexing is copied over,
        so that they are not recomputed.
        """
        return NeedsView(
            _needs={id: self._needs[id] for id in ids if id in self._needs},
            _indexes=self._maybe_indexes,
        )

    def __getitem__(self, key: str) -> NeedsInfoType:
        return self._needs[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._needs)

    def __len__(self) -> int:
        if self._maybe_len is None:
            self._maybe_len = len(self._needs)
        return self._maybe_len

    def __bool__(self) -> bool:
        try:
            next(iter(self._needs))
        except StopIteration:
            return False
        return True

    def to_list_with_parts(self) -> NeedsAndPartsListView:
        return NeedsAndPartsListView(_needs=self)

    def filter_ids(self, values: Iterable[str]) -> NeedsView:
        """Create new view with needs filtered by the ``id`` field."""
        return self._copy_filtered(values)

    def filter_is_external(self, value: bool) -> NeedsView:
        """Create new view with only needs where ``is_external`` field is true/false."""
        return self._copy_filtered(self._get_indexes().is_external.get(value, []))

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
                    self._get_indexes().types.get(value, []),
                    self._get_indexes().type_names.get(value, []),
                )
            )
        return self._copy_filtered(
            i for value in values for i in self._get_indexes().types.get(value, [])
        )

    def filter_statuses(self, values: list[str]) -> NeedsView:
        """Create new view with only needs that have certain ``status`` field values."""
        return self._copy_filtered(
            i for value in values for i in self._get_indexes().status.get(value, [])
        )

    def filter_has_tag(self, values: list[str]) -> NeedsView:
        """Create new view with only needs that have at least one of these values in the ``tags`` field list."""
        return self._copy_filtered(
            i for value in values for i in self._get_indexes().tags.get(value, [])
        )


class NeedsAndPartsListView:
    """A read-only view of needs and parts,
    after resolution (e.g. back links have been computed etc)

    The parts are created by creating a copy of the need for each item in ``parts``,
    and then overwriting a subset of fields with the values from the part.
    """

    __slots__ = ("_needs", "_filter_ids")

    def __init__(self, *, _needs: NeedsView, _filter_ids: set[str] | None = None):
        """Initialize a new view of needs.

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, create from a NeedsView instance.
        """
        self._needs = _needs
        self._filter_ids = _filter_ids

    def _copy(self, needs: NeedsView) -> NeedsAndPartsListView:
        """Create a new view with only these needs."""
        return NeedsAndPartsListView(_needs=needs, _filter_ids=self._filter_ids)

    def __iter__(self) -> Iterator[NeedsInfoType]:
        from sphinx_needs.roles.need_part import create_need_from_part

        if self._filter_ids is not None:
            for need in self._needs.values():
                if need["id"] in self._filter_ids:
                    yield need
                for part in need["parts"].values():
                    if part["id"] in self._filter_ids:
                        yield create_need_from_part(need, part)
        else:
            for need in self._needs.values():
                yield need
                for part in need["parts"].values():
                    yield create_need_from_part(need, part)

    def __bool__(self) -> bool:
        try:
            next(iter(self))
        except StopIteration:
            return False
        return True

    def __len__(self) -> int:
        # TODO improve this, since it is not very efficient
        return sum(1 for _ in self)

    def get_need(self, id: str, part_id: str | None = None) -> NeedsInfoType | None:
        """Get a need by id, or return None if it does not exist.

        If ``part_id`` is provided, return the part of the need with that id, or None if it does not exist.
        """
        from sphinx_needs.roles.need_part import create_need_from_part

        if part_id is None:
            if self._filter_ids is None or id in self._filter_ids:
                return self._needs.get(id)
        else:
            if (
                (self._filter_ids is None or part_id in self._filter_ids)
                and (need := self._needs.get(id))
                and (part := need["parts"].get(part_id))
            ):
                return create_need_from_part(need, part)

        return None

    def filter_ids(self, values: Iterable[str]) -> NeedsAndPartsListView:
        """Create new view with needs/parts filtered by the ``id`` field."""
        if self._filter_ids is None:
            self._filter_ids = set(values)
        else:
            self._filter_ids.intersection_update(values)

        # we need to keep not just all needs with these ids,
        # but also needs that have parts with these ids
        ids = self._filter_ids.copy()
        if parts_to_needs := self._needs._get_indexes().parts_to_needs:
            for id in self._filter_ids:
                ids.update(parts_to_needs.get(id, []))

        return self._copy(self._needs.filter_ids(ids))

    def filter_is_external(self, value: bool) -> NeedsAndPartsListView:
        """Create new view with only needs/parts where ``is_external`` field is true/false."""
        if self._needs._get_indexes().parts_differ:
            raise NotImplementedError  # TODO implement this
        return self._copy(self._needs.filter_is_external(value))

    def filter_types(
        self, values: list[str], or_type_names: bool = False
    ) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have certain ``type`` field values.

        :param values: List of types to filter by.
        :param or_type_names: If True, filter by both ``type`` and ``type_name`` field
        """
        if self._needs._get_indexes().parts_differ:
            raise NotImplementedError  # TODO implement this
        return self._copy(self._needs.filter_types(values, or_type_names))

    def filter_statuses(self, values: list[str]) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have certain ``status`` field values."""
        if self._needs._get_indexes().parts_differ:
            raise NotImplementedError  # TODO implement this
        return self._copy(self._needs.filter_statuses(values))

    def filter_has_tag(self, values: list[str]) -> NeedsAndPartsListView:
        """Create new view with only needs/parts that have at least one of these values in the ``tags`` field list."""
        if self._needs._get_indexes().parts_differ:
            raise NotImplementedError  # TODO implement this
        return self._copy(self._needs.filter_has_tag(values))
