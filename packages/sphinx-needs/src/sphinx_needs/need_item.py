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

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass, replace
from itertools import chain
from operator import attrgetter
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    Protocol,
    overload,
    runtime_checkable,
)

from sphinx_needs._need_source import (
    HopsSource,
    NeedSourceHop,
    NeedSourcePhysical,
    NeedSourceSemantic,
    checked_hops,
    first_line,
    placement_of,
)
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


def _set(source: object, **values: object) -> None:
    """Set the fields of a frozen source from its own ``__init__``."""
    for name, value in values.items():
        object.__setattr__(source, name, value)


def _placed_docname(
    cls: type, hops: tuple[NeedSourceHop, ...], docname: str | None
) -> str:
    """The placement's document, checked against a ``docname`` also given.

    :raises ValueError: if the hops place the need nowhere, or elsewhere.
    """
    placement = placement_of(hops)
    if placement is None or placement.document is None:
        raise ValueError(f"{cls.__name__}: the hops have no placement (no document)")
    if docname is not None and docname != placement.document:
        raise ValueError(
            f"{cls.__name__}: the hops place the need on {placement.document!r}, "
            f"not on {docname!r}"
        )
    return placement.document


def _required(cls: type, name: str, value: object) -> None:
    """Refuse a legacy keyword missing where there are no hops to derive it from."""
    if value is None:
        raise TypeError(
            f"{cls.__name__}.__init__() missing required keyword argument: {name!r} "
            "(it can be omitted only when hops give it)"
        )


@dataclass(slots=True, frozen=True, init=False, repr=False)
class NeedItemSourceUnknown(HopsSource):
    """A class representing the source of a need item, from an unknown source.

    Its keywords are free (an ``external_url`` without ``is_external`` is a valid
    source), so it stores every one of them; ``docname``, where it is given with
    ``hops``, must be the document of their placement.

    ``hops`` is **provisional**: where the need's text came from, innermost first (see
    :mod:`sphinx_needs._need_source`). It may change without a deprecation until it
    reaches ``needs.json``; nothing a filter, a table or ``needs.json`` shows depends
    on it. Without ``hops``, a source with a ``docname`` has one ``page`` hop.
    """

    docname: str | None
    lineno: int | None
    lineno_content: int | None
    external_url: str | None
    is_import: bool
    is_external: bool
    hops: tuple[NeedSourceHop, ...]
    dict_repr: NeedsSourceInfoType = field(init=False)

    def __init__(
        self,
        *,
        docname: str | None = None,
        lineno: int | None = None,
        lineno_content: int | None = None,
        external_url: str | None = None,
        is_import: bool = False,
        is_external: bool = False,
        hops: Iterable[NeedSourceHop] | None = None,
    ) -> None:
        if hops is None:
            hops = (
                (NeedSourceHop(kind="page", document=docname),)
                if docname is not None
                else ()
            )
        else:
            hops = checked_hops(hops)
            placement = placement_of(hops)
            placed = None if placement is None else placement.document
            if docname is None:
                docname = placed
            elif docname != placed:
                raise ValueError(
                    f"NeedItemSourceUnknown: the hops place the need on {placed!r}, "
                    f"not on {docname!r}"
                )
        _set(
            self,
            docname=docname,
            lineno=lineno,
            lineno_content=lineno_content,
            external_url=external_url,
            is_import=is_import,
            is_external=is_external,
            hops=hops,
            dict_repr={
                "docname": docname,
                "lineno": lineno,
                "lineno_content": lineno_content,
                "external_url": external_url,
                "is_import": is_import,
                "is_external": is_external,
            },
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}(docname={self.docname!r}, "
            f"lineno={self.lineno!r}, lineno_content={self.lineno_content!r}, "
            f"external_url={self.external_url!r}, is_import={self.is_import!r}, "
            f"is_external={self.is_external!r})"
        )


@dataclass(slots=True, frozen=True, init=False, repr=False)
class NeedItemSourceDirective(HopsSource):
    """A class representing the source of a need item, from a need directive.

    ``docname`` is the document of the placement hop, and ``lineno`` the start line of
    ``hops[0]`` -- the file the directive is written in, an included file's own line in
    an include. Where ``hops[0]`` has no true line (a docstring read by autodoc, a line
    the state machine cannot map), ``lineno`` is stored beside the hops.

    ``hops`` is **provisional**: where the need's text came from, innermost first (see
    :mod:`sphinx_needs._need_source`). It may change without a deprecation until it
    reaches ``needs.json``; nothing a filter, a table or ``needs.json`` shows depends
    on it. ``docname`` and ``lineno`` can be omitted when ``hops`` give them; given with
    ``hops``, they must agree with them.
    """

    hops: tuple[NeedSourceHop, ...]
    lineno_content: int
    parser_lineno: int | None
    """The directive's line in the *parser's* own line space, where that differs from
    ``lineno``.

    ``lineno`` is the line the directive is written on, resolved back through the state
    machine. The parser counts the lines it was handed instead, and anything that puts
    text into the document -- ``rst_prolog``, ``.. include::``, ``.. list2need::`` --
    shifts that count. Content that exists in no file (a rendered
    ``pre_template``/``post_template``) is parsed at an offset into *that* space, so the
    unresolved number has to survive alongside the resolved one.

    Deliberately not part of ``dict_repr``: it is a parser coordinate rather than need
    data, and never reaches ``needs.json``. ``None`` means the two are the same.
    """
    _lineno: int | None
    """``lineno``, where ``hops[0]`` has no true line to give it."""
    dict_repr: NeedsSourceInfoType = field(init=False)

    def __init__(
        self,
        *,
        docname: str | None = None,
        lineno: int | None = None,
        lineno_content: int,
        parser_lineno: int | None = None,
        hops: Iterable[NeedSourceHop] | None = None,
    ) -> None:
        if hops is None:
            _required(type(self), "docname", docname)
            _required(type(self), "lineno", lineno)
            hops = (NeedSourceHop(kind="page", document=docname),)
        else:
            hops = checked_hops(hops)
        docname = _placed_docname(type(self), hops, docname)
        line = first_line(hops)
        if line is None:
            if lineno is None:
                raise ValueError(
                    "NeedItemSourceDirective: lineno is required, the first hop has "
                    "no line to give it"
                )
            stored, line = lineno, lineno
        elif lineno is not None and lineno != line:
            raise ValueError(
                f"NeedItemSourceDirective: the first hop gives lineno {line!r}, "
                f"not {lineno!r}"
            )
        else:
            stored = None
        _set(
            self,
            hops=hops,
            lineno_content=lineno_content,
            parser_lineno=parser_lineno,
            _lineno=stored,
            dict_repr={
                "docname": docname,
                "lineno": line,
                "lineno_content": lineno_content,
                "external_url": None,
                "is_import": False,
                "is_external": False,
            },
        )

    @property
    def docname(self) -> str:
        """The document of the placement hop."""
        return _placed_docname(type(self), self.hops, None)

    @property
    def lineno(self) -> int:
        """The start line of ``hops[0]``, else the stored line."""
        line = first_line(self.hops)
        if line is None:
            line = self._lineno
        if line is None:  # refused by ``__init__``
            raise ValueError("NeedItemSourceDirective: no lineno")
        return line

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}(docname={self.docname!r}, "
            f"lineno={self.lineno!r}, lineno_content={self.lineno_content!r}, "
            f"parser_lineno={self.parser_lineno!r})"
        )


@dataclass(slots=True, frozen=True, init=False, repr=False)
class NeedItemSourceService(HopsSource):
    """A class representing the source of a need item, from a service directive.

    ``docname`` is the document of the placement hop. ``lineno`` is the directive's
    line in the parser's own line space (shifted by ``rst_prolog`` and includes), so it
    is stored beside the hops, whose lines are the file's.

    ``hops`` is **provisional**: where the need's text came from, innermost first (see
    :mod:`sphinx_needs._need_source`). It may change without a deprecation until it
    reaches ``needs.json``; nothing a filter, a table or ``needs.json`` shows depends
    on it. ``docname`` can be omitted when ``hops`` give it; given with ``hops``, it
    must agree with them.
    """

    hops: tuple[NeedSourceHop, ...]
    _lineno: int
    dict_repr: NeedsSourceInfoType = field(init=False)

    def __init__(
        self,
        *,
        docname: str | None = None,
        lineno: int,
        hops: Iterable[NeedSourceHop] | None = None,
    ) -> None:
        if hops is None:
            _required(type(self), "docname", docname)
            hops = (NeedSourceHop(kind="page", document=docname),)
        else:
            hops = checked_hops(hops)
        docname = _placed_docname(type(self), hops, docname)
        _set(
            self,
            hops=hops,
            _lineno=lineno,
            dict_repr={
                "docname": docname,
                "lineno": lineno,
                "lineno_content": None,
                "external_url": None,
                "is_import": False,
                "is_external": False,
            },
        )

    @property
    def docname(self) -> str:
        """The document of the placement hop."""
        return _placed_docname(type(self), self.hops, None)

    @property
    def lineno(self) -> int:
        """The directive's parser line (a stored legacy fact)."""
        return self._lineno

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}(docname={self.docname!r}, "
            f"lineno={self.lineno!r})"
        )


@dataclass(slots=True, frozen=True, init=False, repr=False)
class NeedItemSourceExternal(HopsSource):
    """A class representing the source of a need item, from an external source.

    ``url`` is the URL of ``hops[0]``, the need's page on the external site.

    ``hops`` is **provisional**: where the need's text came from, innermost first (see
    :mod:`sphinx_needs._need_source`). It may change without a deprecation until it
    reaches ``needs.json``; nothing a filter, a table or ``needs.json`` shows depends
    on it. ``url`` can be omitted when ``hops`` give it; given with ``hops``, it must
    agree with them.
    """

    hops: tuple[NeedSourceHop, ...]
    dict_repr: NeedsSourceInfoType = field(init=False)

    def __init__(
        self,
        *,
        url: str | None = None,
        hops: Iterable[NeedSourceHop] | None = None,
    ) -> None:
        if hops is None:
            _required(type(self), "url", url)
            hops = (
                NeedSourceHop(kind="external", physical=NeedSourcePhysical(url=url)),
            )
        else:
            hops = checked_hops(hops)
        derived = _external_url(hops)
        if url is not None and url != derived:
            raise ValueError(
                f"NeedItemSourceExternal: the hops give url {derived!r}, not {url!r}"
            )
        _set(
            self,
            hops=hops,
            dict_repr={
                "docname": None,
                "lineno": None,
                "lineno_content": None,
                "external_url": derived,
                "is_import": False,
                "is_external": True,
            },
        )

    @property
    def url(self) -> str:
        """The URL of ``hops[0]``."""
        return _external_url(self.hops)

    def __repr__(self) -> str:
        return f"{type(self).__qualname__}(url={self.url!r})"


def _external_url(hops: tuple[NeedSourceHop, ...]) -> str:
    """The URL of an external need's first hop.

    :raises ValueError: if it has none.
    """
    physical = hops[0].physical if hops else None
    if physical is None or physical.url is None:
        raise ValueError("NeedItemSourceExternal: the first hop has no url")
    return physical.url


@dataclass(slots=True, frozen=True, init=False, repr=False)
class NeedItemSourceImport(HopsSource):
    """A class representing the source of a need item, from an import directive.

    ``docname`` is the document of the placement hop. ``lineno`` (the directive's line
    in the parser's own line space) and ``path`` (the argument as written) are stored
    beside the hops; the first hop is the imported file, resolved.

    ``hops`` is **provisional**: where the need's text came from, innermost first (see
    :mod:`sphinx_needs._need_source`). It may change without a deprecation until it
    reaches ``needs.json``; nothing a filter, a table or ``needs.json`` shows depends
    on it. ``docname`` can be omitted when ``hops`` give it; given with ``hops``, it
    must agree with them.
    """

    hops: tuple[NeedSourceHop, ...]
    _lineno: int
    path: str
    dict_repr: NeedsSourceInfoType = field(init=False)

    def __init__(
        self,
        *,
        docname: str | None = None,
        lineno: int,
        path: str,
        hops: Iterable[NeedSourceHop] | None = None,
    ) -> None:
        if hops is None:
            _required(type(self), "docname", docname)
            hops = (
                NeedSourceHop(kind="file"),
                NeedSourceHop(kind="page", document=docname),
            )
        else:
            hops = checked_hops(hops)
        docname = _placed_docname(type(self), hops, docname)
        _set(
            self,
            hops=hops,
            _lineno=lineno,
            path=path,
            dict_repr={
                "docname": docname,
                "lineno": lineno,
                "lineno_content": None,
                "external_url": None,
                "is_import": True,
                "is_external": False,
            },
        )

    @property
    def docname(self) -> str:
        """The document of the placement hop."""
        return _placed_docname(type(self), self.hops, None)

    @property
    def lineno(self) -> int:
        """The directive's parser line (a stored legacy fact)."""
        return self._lineno

    def __repr__(self) -> str:
        return (
            f"{type(self).__qualname__}(docname={self.docname!r}, "
            f"lineno={self.lineno!r}, path={self.path!r})"
        )


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
    )

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
    backlinks: dict[str, list[NeedLink]] = field(default_factory=dict)


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


@dataclass(slots=True, frozen=True, kw_only=True)
class NeedLink:
    """A class representing a link from one need to another.

    .. versionadded:: 8.0.0
    """

    id: str
    part: str | None = None
    condition: str | None = None
    _filter_string: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_filter_string",
            f"{self.id}.{self.part}" if self.part else self.id,
        )

    @staticmethod
    def from_string(link_str: str, *, parse_conditions: bool = True) -> NeedLink:
        """Parse a link from a string (infallible, best-effort).

        Supports formats: ``ID``, ``ID.part``, ``ID[condition]``,
        ``ID.part[condition]``, ``ID[[nested_condition]]``.

        On malformed brackets (unclosed, trailing text), falls back to
        parsing without a condition. Use :meth:`from_string_with_warnings`
        if you need to detect malformed input.

        :param parse_conditions: Whether to parse ``[condition]`` brackets.
        """
        return NeedLink.from_string_with_warnings(
            link_str, parse_conditions=parse_conditions
        )[0]

    @staticmethod
    def from_string_with_warnings(
        link_str: str, *, parse_conditions: bool = True
    ) -> tuple[NeedLink, list[str]]:
        """Parse a link from a string, returning warnings for malformed input.

        Same parsing as :meth:`from_string`, but returns a list of warning
        messages instead of silently ignoring malformed brackets.

        :param parse_conditions: Whether to parse ``[condition]`` brackets.
        :returns: A tuple of ``(NeedLink, warnings)``.
        """
        warnings: list[str] = []

        if not parse_conditions:
            return NeedLink.parse_address(link_str), warnings

        # Find the first '[' that could start a condition
        bracket_start = link_str.find("[")
        if bracket_start <= 0:
            # No condition or no address before '[' — plain ID or ID.part
            return NeedLink.parse_address(link_str), warnings

        address = link_str[:bracket_start]
        rest = link_str[bracket_start:]

        # Count opening bracket depth
        depth = 0
        while depth < len(rest) and rest[depth] == "[":
            depth += 1

        # Find the matching closing brackets
        closing = "]" * depth
        inner = rest[depth:]
        close_pos = inner.find(closing)
        if close_pos < 0:
            warnings.append(
                f"Unclosed condition brackets in link {link_str!r}: "
                f"expected {depth} closing ']' characters."
            )
            return NeedLink.parse_address(link_str), warnings

        trailing = inner[close_pos + depth :]
        if trailing:
            warnings.append(
                f"Unexpected text after closing condition bracket "
                f"in link {link_str!r}: {trailing!r}."
            )
            return NeedLink.parse_address(address), warnings

        condition = inner[:close_pos]
        link = NeedLink.parse_address(
            address, condition=condition if condition else None
        )
        return link, warnings

    @staticmethod
    def parse_address(address: str, /, *, condition: str | None = None) -> NeedLink:
        """Parse an address string into a NeedLink, optionally with a condition."""
        if "." in address:
            id_, part = address.split(".", maxsplit=1)
            return NeedLink(id=id_, part=part, condition=condition)
        return NeedLink(id=address, condition=condition)

    def to_filter_string(self) -> str:
        """Convert the link to a filter string, e.g. 'NEED-1' or 'NEED-1.part'.

        This does **not** include the condition.
        """
        return self._filter_string

    def to_link_string(self) -> str:
        """Serialize the link including the condition, e.g. 'NEED-1[cond]' or 'NEED-1.part[cond]'.

        Uses bracket depth one greater than the longest consecutive run of
        ``]`` in the condition, so the result always round-trips through
        :meth:`from_string`.
        """
        base = f"{self.id}.{self.part}" if self.part else self.id
        if self.condition is None:
            return base
        # Find the longest consecutive run of ']' in the condition
        max_run = 0
        current_run = 0
        for ch in self.condition:
            if ch == "]":
                current_run += 1
                if current_run > max_run:
                    max_run = current_run
            else:
                current_run = 0
        depth = max_run + 1
        open_b = "[" * depth
        close_b = "]" * depth
        return f"{base}{open_b}{self.condition}{close_b}"


_NATURAL_SORT_RE = re.compile(r"(\d+)")


def _natural_sort_key(value: str) -> list[str | int]:
    """Build a sort key for natural ordering: digit runs are compared as ints.

    For example, ``REQ_2`` < ``REQ_9`` < ``REQ_10`` (instead of the default
    lexicographic ``REQ_10`` < ``REQ_2`` < ``REQ_9``). Non-digit runs are
    case-folded so the order is case-insensitive.
    """
    return [
        int(tok) if tok.isdigit() else tok.casefold()
        for tok in _NATURAL_SORT_RE.split(value)
    ]


def _natural_sort_key_total(value: str) -> tuple[list[str | int], str]:
    """A total natural sort key: :func:`_natural_sort_key`, ties broken by the string.

    ``R_02``, ``R_2`` and ``r_2`` share one natural key, so the string itself, compared
    by code point, orders them (``R_02`` < ``R_2`` < ``r_2``) whatever order they came in.
    """
    return _natural_sort_key(value), value


def _link_natural_sort_key(link: NeedLink) -> tuple[list[str | int], str, str]:
    """Natural sort key for a :class:`NeedLink`: its filter string's total natural key
    (see :func:`_natural_sort_key_total`), then the link with its condition, so that
    links to one target under different conditions (``R_2``, ``R_2[status == 'open']``)
    are ordered too, and the order is total."""
    natural, filter_string = _natural_sort_key_total(link.to_filter_string())
    return natural, filter_string, link.to_link_string()


class NeedItem:
    """A class representing a single need item."""

    __slots__ = (
        "_backlinks",
        "_backlinks_keymap",
        "_computed",
        "_constraint_results",
        "_content",
        "_core",
        "_derived",
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
        links: dict[str, list[str]] | dict[str, list[NeedLink]],
        backlinks: dict[str, list[str]] | dict[str, list[NeedLink]] | None = None,
        parts: Sequence[NeedPartData] = (),
        modifications: Sequence[NeedModification] = (),
        constraint_results: NeedConstraintResults | None = None,
        dynamic_fields: dict[str, FieldFunctionArray | LinksFunctionArray]
        | None = None,
        derived: Iterable[str] = (),
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
        :param derived: The keys of the derived fields (extras or links keys), which
            ``need[key] = value`` refuses: they hold what their rules compute
            (:attr:`~sphinx_needs.needs_schema.FieldsSchema.derived_names`).
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
        # one set shared by the needs of a build, per process (a parallel worker
        # unpickles its own): a frozenset is not copied
        self._derived = frozenset(derived)
        self._links: dict[str, list[NeedLink]] = {
            key: [NeedLink.from_string(v) if isinstance(v, str) else v for v in value]
            for key, value in links.items()
        }
        if backlinks is None:
            self._backlinks: dict[str, list[NeedLink]] = {li: [] for li in self._links}
        else:
            self._backlinks = {
                key: [
                    NeedLink.from_string(v) if isinstance(v, str) else v for v in value
                ]
                for key, value in backlinks.items()
            }
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
                isinstance(v, list) and all(isinstance(i, NeedLink) for i in v)
                for v in self._links.values()
            ):
                raise TypeError(
                    "NeedItem links must be a dictionary of lists of NeedLink instances."
                )
            if not all(
                isinstance(v, list) and all(isinstance(i, NeedLink) for i in v)
                for v in self._backlinks.values()
            ):
                raise TypeError(
                    "NeedItem backlinks must be a dictionary of lists of NeedLink instances."
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
            if not_fields := self._derived.difference(self._extras, self._links):
                raise ValueError(
                    f"NeedItem derived keys must be extras or links keys, not: {sorted(not_fields)}"
                )

    def _recompute(self) -> None:
        parts: Mapping[str, NeedsPartType] = {
            p.id: {
                "id": p.id,
                "content": p.content,
                **(
                    {
                        f"{k}_back": [li.to_filter_string() for li in v]
                        for k, v in p.backlinks.items()
                        if v
                    }
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
            "parent_need": parent_needs[0].to_filter_string()
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

    def _set_placement_semantic(self, semantic: tuple[NeedSourceSemantic, ...]) -> None:
        """Replace the source once, its placement hop given ``semantic``.

        Internal: the doctree-read walk (``analyse_need_locations``) is its one caller,
        as the resolver is ``_set_resolved``'s. The source and its hops are immutable,
        so this is the one way a hop changes after the need is created. A source without
        hops (a third party's, which obeys only :class:`NeedItemSourceProtocol`) or
        without a placement (an external need) is left as it is.

        :raises ValueError: if the placement's semantic location is already set.
        """
        source = self._source
        if not isinstance(source, HopsSource) or source.placement is None:
            return
        self._source = source._with_placement_semantic(semantic)

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
    def constraint_results(self) -> NeedConstraintResults | None:
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
            derived=self._derived,
            _validate=False,
        )

    def __eq__(self, other: object) -> bool:
        """Check if two NeedItems are equal."""
        if not isinstance(other, NeedItem):
            return False
        return self._source == other._source and self._equal_but_source(other)

    def moved_only(self, other: NeedItem) -> bool:
        """Whether ``other`` is this need written at other lines: equal to it but for the
        line numbers of its source (``lineno``, ``lineno_content``, the parser's, and
        the lines its hops record).

        That is what an edit above a need in its document changes, and nothing else.
        """
        return (
            self._source != other._source
            and _without_lines(self._source) == _without_lines(other._source)
            and self._equal_but_source(other)
        )

    def _equal_but_source(self, other: NeedItem) -> bool:
        # the derived keys are not compared: they are wiring from the schema, not data
        return (
            self._core == other._core
            and self._extras == other._extras
            and self._links == other._links
            and self._backlinks == other._backlinks
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
            return self._computed[key]  # ty: ignore[invalid-key]
        if key in self._core:
            return self._core[key]  # ty: ignore[invalid-key]
        elif key in self._extras:
            return self._extras[key]
        elif key in self._links:
            return [li.to_filter_string() for li in self._links[key]]
        elif key in self._backlinks_keymap:
            return [
                li.to_filter_string()
                for li in self._backlinks[self._backlinks_keymap[key]]
            ]
        elif key in self._source.dict_repr:
            return self._source.dict_repr[key]  # ty: ignore[invalid-key]
        elif key in self._content.dict_repr:
            return self._content.dict_repr[key]  # ty: ignore[invalid-key]
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
            ([li.to_filter_string() for li in links] for links in self._links.values()),
            (
                [li.to_filter_string() for li in links]
                for links in self._backlinks.values()
            ),
            self._source.dict_repr.values(),
            self._content.dict_repr.values(),
            self._computed.values(),
        )

    def items(self) -> Iterable[tuple[str, Any]]:
        """Return the items of the need item."""
        return chain(
            self._core.items(),
            self._extras.items(),
            ((k, [li.to_filter_string() for li in v]) for k, v in self._links.items()),
            (
                (k1, [li.to_filter_string() for li in self._backlinks[k2]])
                for k1, k2 in self._backlinks_keymap.items()
            ),
            self._source.dict_repr.items(),
            self._content.dict_repr.items(),
            self._computed.items(),
        )

    def iter_core_items(self) -> Iterable[tuple[str, Any]]:
        """Return the core items of the need item."""
        return chain(
            self._core.items(),
            self._source.dict_repr.items(),
            self._content.dict_repr.items(),
            self._computed.items(),
        )

    def __setitem__(self, key: str, value: Any) -> None:
        """Set an item by key.

        A derived field (``derived``) cannot be set: it holds what its rule computes.
        """
        if key in self._derived:
            raise KeyError(
                f"Cannot set derived field {key!r} in NeedItem: its value is computed by its derive rule."
            )
        self._set_resolved(key, value)

    def _set_resolved(self, key: str, value: Any) -> None:
        """Set a field as the resolver computes it, a derived field too.

        The resolver's own write (:mod:`sphinx_needs.functions.functions`), for every
        value it computes: a derived field's, and an authored ``[[…]]``, ``<<…>>`` or
        ``<{…}>`` value's alike, so it is the resolver's write, not the derived write.
        Every other writer sets through ``need[key] = value``, which refuses a derived
        field; every other refusal of ``need[key] = value`` holds here.
        """
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
            self._core[key] = value  # ty: ignore[invalid-key]
        elif key in self._extras:
            self._extras[key] = value
        elif key in self._links:
            if not isinstance(value, list) or not all(
                isinstance(v, str | NeedLink) for v in value
            ):
                raise TypeError(
                    f"Value for link key {key!r} must be a list of strings or NeedLink instances."
                )
            self._links[key] = [
                NeedLink.from_string(v) if isinstance(v, str) else v for v in value
            ]
        elif key in self._backlinks_keymap:
            if not isinstance(value, list) or not all(
                isinstance(v, str | NeedLink) for v in value
            ):
                raise TypeError(
                    f"Value for backlink key {key!r} must be a list of strings."
                )
            self._backlinks[self._backlinks_keymap[key]] = [
                NeedLink.from_string(v) if isinstance(v, str) else v for v in value
            ]
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

    def sort_backlinks(self) -> None:
        """Sort the back links, and the parts' back links, in need-id order.

        Ids are compared as strings (``REQ_10`` before ``REQ_9``), as the dynamic
        functions read the needs of a set. This is the order a dynamic function reads
        a back link list in; :meth:`sort_links` sorts it again for the output.
        """
        for value in self._backlinks.values():
            value.sort(key=attrgetter("id"))
        for part in self._parts.values():
            for value in part.backlinks.values():
                value.sort(key=attrgetter("id"))

    def sort_links(self) -> None:
        """Sort all link and backlink lists in place, removing duplicates.

        Sorts outgoing links, backlinks, and part backlinks by the link's
        string representation, treating embedded digit sequences as integers
        so that e.g. ``REQ_2`` < ``REQ_9`` < ``REQ_10``, ids with one such key
        by the string itself (``R_02`` < ``R_2`` < ``r_2``), and links to one
        target by the link with its condition (``R_2`` < ``R_2[status == 'open']``).
        This makes the order of linked need IDs deterministic, regardless of the
        order in which they were added or the iteration order of the needs collection.
        Duplicate :class:`NeedLink` entries (same id, part, and condition)
        are collapsed.
        """
        for key, value in self._links.items():
            self._links[key] = sorted(set(value), key=_link_natural_sort_key)
        for key, value in self._backlinks.items():
            self._backlinks[key] = sorted(set(value), key=_link_natural_sort_key)
        for part in self._parts.values():
            for key, value in part.backlinks.items():
                part.backlinks[key] = sorted(set(value), key=_link_natural_sort_key)

    def add_backlink(self, link_type: str, backlink: str | NeedLink) -> None:
        """Add a backlink to the need."""
        if link_type not in self._backlinks:
            raise KeyError(f"Link type {link_type!r} does not exist in backlinks.")
        backlink = (
            NeedLink.from_string(backlink) if isinstance(backlink, str) else backlink
        )
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

    @overload
    def get_links(
        self, link_type: str, *, as_str: Literal[True] = True
    ) -> list[str]: ...

    @overload
    def get_links(
        self, link_type: str, *, as_str: Literal[False]
    ) -> list[NeedLink]: ...

    def get_links(
        self, link_type: str, *, as_str: bool = True
    ) -> list[str] | list[NeedLink]:
        """Get link references by link_type key.

        :raises KeyError: If the link_type is not a link type.
        """
        if as_str:
            return [li.to_filter_string() for li in self._links[link_type]]
        return self._links[link_type]

    def iter_links_keys(self) -> Iterable[str]:
        """Yield all link_type keys."""
        yield from self._links.keys()

    @overload
    def iter_links_items(
        self, as_str: Literal[True] = True
    ) -> Iterable[tuple[str, list[str]]]: ...

    @overload
    def iter_links_items(
        self, as_str: Literal[False] = False
    ) -> Iterable[tuple[str, list[NeedLink]]]: ...

    def iter_links_items(
        self, as_str: bool = True
    ) -> Iterable[tuple[str, list[str]]] | Iterable[tuple[str, list[NeedLink]]]:
        """Yield all links as (link_type, references) pairs."""
        if as_str:
            yield from (
                (key, [li.to_filter_string() for li in value])
                for key, value in self._links.items()
            )
        else:
            yield from self._links.items()

    @overload
    def get_backlinks(
        self, link_type: str, *, as_str: Literal[True] = True
    ) -> list[str]: ...

    @overload
    def get_backlinks(
        self, link_type: str, *, as_str: Literal[False]
    ) -> list[NeedLink]: ...

    def get_backlinks(
        self, link_type: str, *, as_str: bool = True
    ) -> list[str] | list[NeedLink]:
        """Get backlink references by link_type key.

        :raises KeyError: If the link_type is not a backlink type.
        """
        if as_str:
            return [li.to_filter_string() for li in self._backlinks[link_type]]
        return self._backlinks[link_type]

    @overload
    def iter_backlinks_items(
        self, as_str: Literal[True] = True
    ) -> Iterable[tuple[str, list[str]]]: ...

    @overload
    def iter_backlinks_items(
        self, as_str: Literal[False] = False
    ) -> Iterable[tuple[str, list[NeedLink]]]: ...

    def iter_backlinks_items(
        self, as_str: bool = True
    ) -> Iterable[tuple[str, list[str]]] | Iterable[tuple[str, list[NeedLink]]]:
        """Yield all backlinks as (link_type, references) pairs."""
        if as_str:
            yield from (
                (key, [li.to_filter_string() for li in value])
                for key, value in self._backlinks.items()
            )
        else:
            yield from self._backlinks.items()

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
            or any(not isinstance(i, NeedLink) for i in v)
            for k, v in part.backlinks.items()
        ):
            raise ValueError(
                f"Part {part.id!r} backlinks must be a dictionary of lists of NeedLink instances."
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
        constraint_results: NeedConstraintResults | None,
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

    def filter_context(self) -> dict[str, Any]:
        """Build a flat dict of all need fields, suitable for use as an eval/template context.

        This is more efficient than ``{**need}`` because it avoids the per-key
        multi-namespace lookup chain and materializes link string lists only once.
        """
        ctx: dict[str, Any] = {}
        ctx.update(self._core)
        ctx.update(self._extras)
        for key, links in self._links.items():
            ctx[key] = [li.to_filter_string() for li in links]
        for exposed_key, link_key in self._backlinks_keymap.items():
            ctx[exposed_key] = [
                li.to_filter_string() for li in self._backlinks[link_key]
            ]
        ctx.update(self._source.dict_repr)
        ctx.update(self._content.dict_repr)
        ctx.update(self._computed)
        return ctx

    def is_in_document(self, docname: str) -> bool:
        """Check if the need is in a given document."""
        return self._source.dict_repr.get("docname") == docname


#: The fields of a source class holding a line number, and nothing else.
_SOURCE_LINE_FIELDS: Final = frozenset(
    {"lineno", "_lineno", "lineno_content", "parser_lineno"}
)


def _without_lines(source: NeedItemSourceProtocol) -> object:
    """A need's source with its line numbers left out, to compare where it is from.

    The line fields of the source class, and the start and end line of each hop's
    file (its hops record the lines too); ``dict_repr`` is computed from the rest.
    """
    if not is_dataclass(source) or isinstance(source, type):
        return source
    kept: list[tuple[str, object]] = []
    for item in fields(source):
        if item.name in _SOURCE_LINE_FIELDS or item.name == "dict_repr":
            continue
        value = getattr(source, item.name)
        if item.name == "hops":
            value = tuple(_hop_without_lines(hop) for hop in value)
        kept.append((item.name, value))
    return type(source), tuple(kept)


def _hop_without_lines(hop: NeedSourceHop) -> NeedSourceHop:
    """A hop with its file's start and end line left out."""
    if hop.physical is None:
        return hop
    return replace(hop, physical=replace(hop.physical, start_line=None, end_line=None))


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

        self._overrides: dict[str, Any] = {
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
                else [li.to_filter_string() for li in blinks]
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

    def filter_context(self) -> dict[str, Any]:
        """Build a flat dict of all need part fields, suitable for use as an eval/template context.

        This is more efficient than ``{**need_part}`` because it avoids
        per-key lookup overhead.
        """
        ctx = self._need.filter_context()
        ctx.update(self._overrides)
        return ctx

    def get_extra(self, key: str) -> str:
        """Get an extra by key.

        :raises KeyError: If the key is not an extra.
        """
        if key not in self._need._extras:
            raise KeyError(key)
        return self[key]

    def iter_extra_keys(self) -> Iterable[str]:
        """Yield all extra keys."""
        yield from self._need._extras.keys()

    def iter_extra_items(self) -> Iterable[tuple[str, str]]:
        """Yield all extras as key-value pairs."""
        for key in self._need._extras:
            yield (key, self[key])

    @overload
    def get_links(
        self, link_type: str, *, as_str: Literal[True] = True
    ) -> list[str]: ...

    @overload
    def get_links(
        self, link_type: str, *, as_str: Literal[False]
    ) -> list[NeedLink]: ...

    def get_links(
        self, link_type: str, *, as_str: bool = True
    ) -> list[str] | list[NeedLink]:
        """Get link references by link_type key.

        :raises KeyError: If the link_type is not a link type.
        """
        if link_type not in self._need._links:
            raise KeyError(link_type)
        # parts cannot link to anything, so return empty list
        return []

    def iter_links_keys(self) -> Iterable[str]:
        """Yield all link_type keys."""
        yield from self._need._links.keys()

    @overload
    def iter_links_items(
        self, as_str: Literal[True] = True
    ) -> Iterable[tuple[str, list[str]]]: ...

    @overload
    def iter_links_items(
        self, as_str: Literal[False] = False
    ) -> Iterable[tuple[str, list[NeedLink]]]: ...

    def iter_links_items(
        self, as_str: bool = True
    ) -> Iterable[tuple[str, list[str]]] | Iterable[tuple[str, list[NeedLink]]]:
        """Yield all links as (link_type, references) pairs."""
        if as_str:
            for key in self._need._links:
                yield (key, self[key])
        else:
            # parts cannot link to anything, so return empty lists
            yield from ((key, []) for key in self._need._links)

    @overload
    def get_backlinks(
        self, link_type: str, *, as_str: Literal[True] = True
    ) -> list[str]: ...

    @overload
    def get_backlinks(
        self, link_type: str, *, as_str: Literal[False]
    ) -> list[NeedLink]: ...

    def get_backlinks(
        self, link_type: str, *, as_str: bool = True
    ) -> list[str] | list[NeedLink]:
        """Get backlink references by link_type key.

        :raises KeyError: If the link_type is not a backlink type.
        """
        if link_type not in self._need._backlinks:
            raise KeyError(link_type)
        if as_str:
            return self[f"{link_type}_back"]
        part = self._need.get_part(self.part_id)
        assert part is not None
        return part.backlinks.get(link_type, [])

    @overload
    def iter_backlinks_items(
        self, as_str: Literal[True] = True
    ) -> Iterable[tuple[str, list[str]]]: ...

    @overload
    def iter_backlinks_items(
        self, as_str: Literal[False] = False
    ) -> Iterable[tuple[str, list[NeedLink]]]: ...

    def iter_backlinks_items(
        self, as_str: bool = True
    ) -> Iterable[tuple[str, list[str]]] | Iterable[tuple[str, list[NeedLink]]]:
        """Yield all backlinks as (link_type, references) pairs."""
        if as_str:
            for key in self._need._backlinks:
                yield (key, self.get_backlinks(key))
        else:
            for key in self._need._backlinks:
                part = self._need.get_part(self.part_id)
                assert part is not None
                yield (
                    key,
                    part.backlinks.get(key, []),
                )

    def is_in_document(self, docname: str) -> bool:
        """Check if the need is in a given document."""
        return self._need.is_in_document(docname)
