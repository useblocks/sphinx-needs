from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Iterable, Iterator, Mapping

if TYPE_CHECKING:
    from sphinx_needs.data import NeedsInfoType


class _Indexes:
    """Indexes of common fields for fast filtering of needs."""

    __slots__ = ("is_external", "status", "tags", "types", "type_names")

    def __init__(
        self,
        is_external: dict[bool, list[str]],
        types: dict[str, list[str]],
        type_names: dict[str, list[str]],
        status: dict[str | None, list[str]],
        tags: dict[str, list[str]],
    ) -> None:
        self.is_external = is_external
        self.types = types
        self.type_names = type_names
        self.status = status
        self.tags = tags


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
            for id, need in self._needs.items():
                _idx_is_external.setdefault(need["is_external"], []).append(id)
                _idx_types.setdefault(need["type"], []).append(id)
                _idx_type_names.setdefault(need["type_name"], []).append(id)
                _idx_status.setdefault(need["status"], []).append(id)
                for tag in need["tags"]:
                    _idx_tags.setdefault(tag, []).append(id)
            self._maybe_indexes = _Indexes(
                _idx_is_external, _idx_types, _idx_type_names, _idx_status, _idx_tags
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

    def to_list(self) -> NeedsListView:
        return NeedsListView(_needs=self)

    def to_list_with_parts(self) -> NeedsAndPartsListView:
        return NeedsAndPartsListView(_needs=self)

    def filter_ids(self, values: list[str]) -> NeedsView:
        """Create new view with needs filtered by the ``id`` field."""
        return self._copy_filtered(values)

    def filter_is_external(self, value: bool) -> NeedsView:
        """Create new view with needs filtered by the ``is_external`` field."""
        return self._copy_filtered(self._get_indexes().is_external.get(value, []))

    def filter_types(self, values: list[str], or_type_names: bool = False) -> NeedsView:
        """Create new view with needs filtered by the ``type`` field.

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
        """Create new view with needs filtered by the ``status`` field."""
        return self._copy_filtered(
            i for value in values for i in self._get_indexes().status.get(value, [])
        )

    def filter_tags(self, values: list[str]) -> NeedsView:
        """Create new view with needs filtered by the ``tags`` field."""
        return self._copy_filtered(
            i for value in values for i in self._get_indexes().tags.get(value, [])
        )


class NeedsListView:
    """A read-only view of needs,
    after resolution (e.g. back links have been computed etc)
    """

    __slots__ = ("_needs",)

    def __init__(self, *, _needs: NeedsView):
        """ "Initialize a new view of needs.

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, create from a NeedsView instance.
        """
        self._needs = _needs

    def __bool__(self) -> bool:
        return bool(self._needs)

    def __iter__(self) -> Iterator[NeedsInfoType]:
        return iter(self._needs.values())

    def __len__(self) -> int:
        return len(self._needs)

    def to_map_view(self) -> NeedsView:
        return self._needs


class NeedsAndPartsListView:
    """A read-only view of needs and parts,
    after resolution (e.g. back links have been computed etc)

    The parts are created by creating a copy of the need for each item in ``parts``,
    and then overwriting a subset of fields with the values from the part.
    """

    __slots__ = ("_needs", "_maybe_len")

    def __init__(self, *, _needs: NeedsView):
        """Initialize a new view of needs.

        .. important:: This class is not meant to be instantiated by users,
            a singleton instance is managed by sphinx-needs.

            Instead, create from a NeedsView instance.
        """
        self._needs = _needs
        self._maybe_len: int | None = (
            None  # Cache the length of the needs when first requested
        )

    def __bool__(self) -> bool:
        return bool(self._needs)

    def __iter__(self) -> Iterator[NeedsInfoType]:
        from sphinx_needs.roles.need_part import iter_need_parts

        for need in self._needs.values():
            yield need
            yield from iter_need_parts(need)

    def __len__(self) -> int:
        if self._maybe_len is None:
            self._maybe_len = len(self._needs)
        return self._maybe_len

    def to_map_view(self) -> NeedsView:
        return self._needs
