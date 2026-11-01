"""Declared derived fields: the ``derive`` rule of a ``needs_fields`` or ``needs_links`` entry.

A field (or link type) whose entry carries a ``derive`` table is *derived*: its value is
computed by the rule, for every need the project creates from its sources, and an author
cannot set it -- not in a need, not by a ``needextend``. The table names a ``kind`` and
the kind's operands, each under a fixed *role* name::

    [needs.fields.total]
    schema = { type = "number" }
    derive = { kind = "sum", field = "hours", over = "links" }

Beside it, or instead of it, a ``derive_by_type`` table gives a rule per need type,
overriding ``derive`` on that type; a need of a type without a rule holds the field's
default (else ``None``, or the empty value of its type). The field is derived, and
closed, on every need type::

    [needs.fields.total]
    schema = { type = "number" }
    default = 0
    derive_by_type.epic = { kind = "sum", field = "hours", over = "links" }

This module reads the tables (``parse_derive``, ``parse_derive_by_type``) and checks the
rules against the declared fields and link types (``check_derive_rules``). A rule that
cannot be read is kept as a :class:`DeriveInvalid` marker rather than dropped, so the
field stays closed to authors and holds its empty value, as the rule promised it would
not be authored.

Nothing here touches Sphinx: the checks return the problems, and the caller reports them
(as ``needs.derive_invalid``).
"""

from __future__ import annotations

import ast
import enum
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias, TypeGuard

from sphinx_needs._source_facets import READERS as FACET_READERS
from sphinx_needs._wording import title_hint

if TYPE_CHECKING:
    from sphinx_needs.needs_schema import FieldSchema, FieldsSchema, LinkSchema

DeriveKind: TypeAlias = Literal[
    "copy",
    "sum",
    "count",
    "min",
    "max",
    "any",
    "all",
    "collect",
    "hash",
    "fingerprint",
    "links",
    "content_links",
    "union",
]

#: The kinds, in the order the documentation lists them.
KINDS: Final[tuple[DeriveKind, ...]] = (
    "copy",
    "sum",
    "count",
    "min",
    "max",
    "any",
    "all",
    "collect",
    "hash",
    "fingerprint",
    "links",
    "content_links",
    "union",
)

#: The kinds that compute a link list, declared on a link type; every other kind
#: computes a value, declared on a field, but :data:`PATH_KINDS`.
LINK_KINDS: Final = frozenset({"links", "content_links", "union"})

#: The kinds declared on a field or on a link type. On a link type they compute a path
#: through other links (``copy`` of ``id``, ``collect`` of a link type, over a link
#: type), and the link type is a summary.
PATH_KINDS: Final = frozenset({"copy", "collect"})

#: The roles, in the order a rule's problems are looked for.
ROLES: Final = (
    "field",
    "fields",
    "exclude",
    "over",
    "from",
    "join",
    "where",
    "test",
    "empty",
    "select",
    "transitive",
    "include_self",
    "include_parts",
    "after",
)

#: Roles that are reserved for a later release: a rule naming one cannot be read.
#: None is today (the ``expr`` kind of a later release is refused as an unknown kind).
RESERVED_ROLES: Final = frozenset[str]()

#: The core fields, besides every ``NeedsCoreFields`` entry, that cannot carry a rule.
CORE_LINK_TYPES: Final = frozenset({"parent_needs"})

#: Per kind, the roles it requires and the roles it may take besides.
_ROLES_OF: Final[Mapping[str, tuple[frozenset[str], frozenset[str]]]] = {
    "copy": (
        frozenset({"field"}),
        frozenset({"from", "over", "join", "where", "select", "include_self", "after"}),
    ),
    "sum": (frozenset({"field", "over"}), frozenset({"where", "after"})),
    "count": (frozenset({"over"}), frozenset({"field", "where", "after"})),
    "min": (
        frozenset({"field", "over"}),
        frozenset({"where", "transitive", "include_self", "after"}),
    ),
    "max": (
        frozenset({"field", "over"}),
        frozenset({"where", "transitive", "include_self", "after"}),
    ),
    "any": (
        frozenset({"over"}),
        frozenset({"field", "test", "where", "empty", "after"}),
    ),
    "all": (
        frozenset({"over"}),
        frozenset({"field", "test", "where", "empty", "after"}),
    ),
    "collect": (frozenset({"field", "over"}), frozenset({"where", "after"})),
    "hash": (frozenset({"fields"}), frozenset({"after"})),
    "fingerprint": (frozenset(), frozenset({"exclude"})),
    # ``where`` or ``join``: required as one, see parse_derive
    "links": (
        frozenset(),
        frozenset({"where", "join", "include_self", "include_parts"}),
    ),
    "content_links": (frozenset(), frozenset({"from", "where"})),
    "union": (frozenset({"fields"}), frozenset()),
}

#: Per kind of :data:`PATH_KINDS`, the roles it requires and may take besides on a
#: link type: it is computed with the link types, from the links written in them.
_PATH_ROLES_OF: Final[Mapping[str, tuple[frozenset[str], frozenset[str]]]] = {
    "copy": (frozenset({"field", "over"}), frozenset({"where", "select"})),
    "collect": (frozenset({"field", "over"}), frozenset({"where"})),
}

_STRING_ROLES: Final = frozenset({"field", "over", "from", "where", "test"})
_BOOLEAN_ROLES: Final = frozenset(
    {"empty", "transitive", "include_self", "include_parts"}
)
_SELECT: Final = ("first", "unique", "list")
#: The keys of the ``join`` role.
_JOIN_KEYS: Final = ("field", "equals")


@dataclass(frozen=True, slots=True)
class DeriveJoin:
    """The ``join`` role: the needs whose ``field`` equals one of this need's ``equals``.

    Both are text fields: a string is split on ``,``, an array taken by item, each
    value stripped, and a need matches when the two share a value.

    :ivar field: The field read on every need, the candidates.
    :ivar equals: The field read on the need holding the rule.
    """

    field: str
    equals: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DeriveRule:
    """A ``derive`` rule that can be read: the kind and its roles.

    :ivar kind: The kind.
    :ivar field: The ``field`` role: the field read on each candidate, or on this need.
    :ivar fields: The ``fields`` role: the own fields hashed, in order (``hash``), or
        the link types whose links are united, in order (``union``).
    :ivar exclude: The ``exclude`` role (``fingerprint``): what it leaves out.
    :ivar over: The ``over`` role: a link type, or ``<link type>_back``.
    :ivar from_need: The ``from`` role: the id of the one need read.
    :ivar join: The ``join`` role (``links``, ``copy``): the needs whose field equals
        one of this need's values.
    :ivar where: The ``where`` role: the predicate narrowing the candidates (on
        ``copy``, with ``over`` or ``join`` only).
    :ivar test: The ``test`` role: the predicate asserted of each candidate.
    :ivar empty: The ``empty`` role (``any``, ``all``): the value over no candidate,
        once ``where`` has dropped the candidates it does not hold on; ``None``, unset,
        is the kind's own value there, ``False`` for ``any`` and ``True`` for ``all``.
    :ivar select: The ``select`` role of a ``copy`` over several targets.
    :ivar transitive: The ``transitive`` role of ``min`` / ``max``.
    :ivar include_self: The ``include_self`` role.
    :ivar include_parts: The ``include_parts`` role (``links``).
    :ivar after_derived: The ``after = "derived"`` role.
    :ivar on_link: Whether a ``copy`` or ``collect`` is declared on a link type: it
        computes a path (:attr:`path`), a link list.
    """

    kind: DeriveKind
    field: str | None = None
    fields: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    over: str | None = None
    from_need: str | None = None
    join: DeriveJoin | None = None
    where: str | None = None
    test: str | None = None
    empty: bool | None = None
    select: Literal["first", "unique", "list"] = "first"
    transitive: bool = False
    include_self: bool = False
    include_parts: bool = False
    after_derived: bool = False
    on_link: bool = False

    @property
    def late(self) -> bool:
        """Whether the rule runs in the late stage, after every other derivation."""
        return self.kind in {"hash", "fingerprint"} or self.after_derived

    @property
    def link_valued(self) -> bool:
        """Whether the rule computes a link list."""
        return self.kind in LINK_KINDS or self.on_link

    @property
    def path(self) -> bool:
        """Whether the rule computes a path through other links: a ``copy`` or a
        ``collect`` on a link type, which makes the link type a summary."""
        return self.on_link and self.kind in PATH_KINDS

    def describe(self) -> str:
        """The rule as messages name it: ``kind 'sum'``."""
        return f"kind {self.kind!r}"


@dataclass(frozen=True, slots=True)
class DeriveInvalid:
    """A ``derive`` rule that cannot be read.

    The field (or link type) stays derived: an author cannot set it, nor can a
    ``needextend``, and it holds its empty value.

    :ivar kind: The kind as written, if it is a string.
    :ivar reason: Why the rule cannot be read.
    :ivar fallback: Whether the marker stands, in ``derive_by_type``, for the field's
        ``derive`` on a need type where it cycles, rather than for an entry the
        configuration declares.
    """

    kind: str | None
    reason: str
    fallback: bool = False

    def describe(self) -> str:
        """The rule as messages name it."""
        return "an invalid rule" if self.kind is None else f"kind {self.kind!r}"


Derive: TypeAlias = DeriveRule | DeriveInvalid
"""What a derived field or link type holds: its rule, or the marker of one that cannot be read."""


@dataclass(frozen=True, slots=True)
class DeriveCall:
    """A derived field's rule, as the value the pass computes for one need.

    The pass gives every need from the project's sources one per derived field, from
    the current schema, as the field's one dynamic item: a structured value, ordered
    and computed like a ``[[…]]`` of the kind's stratum.

    :ivar rule: The rule.
    """

    rule: DeriveRule

    def describe(self) -> str:
        """The rule as messages name it: ``derive rule 'sum'``."""
        return f"derive rule {self.rule.kind!r}"


def parse_derive(raw: Any, *, on_link: bool) -> Derive:
    """Read a ``derive`` table: the kind, and that its roles fit the kind.

    What the roles name (a field, a link type, a filter) is checked against the rest of
    the configuration by :func:`check_derive_rules`.

    :param raw: The ``derive`` value, as configured.
    :param on_link: Whether it is declared on a link type (``needs_links``),
        rather than on a field (``needs_fields``).
    :return: The rule, or the marker of a rule that cannot be read, with why.
    """
    if not isinstance(raw, Mapping):
        return DeriveInvalid(None, "it is not a table naming a 'kind'")
    if "kind" not in raw:
        return DeriveInvalid(None, "it has no 'kind'")
    kind = raw["kind"]
    if not isinstance(kind, str) or kind not in _ROLES_OF:
        return DeriveInvalid(
            kind if isinstance(kind, str) else None,
            f"the kind {kind!r} is unknown; the kinds are {', '.join(KINDS)}",
        )
    prefix = f"kind {kind!r}"
    if reserved := sorted(RESERVED_ROLES & set(raw)):
        return DeriveInvalid(
            kind,
            f"{prefix}: the {reserved[0]!r} role is reserved and not available yet",
        )
    if unknown := sorted(str(k) for k in raw if k != "kind" and k not in ROLES):
        if unknown[0] == "types":
            # the role this key replaced: say where a rule for some types goes
            return DeriveInvalid(
                kind,
                f"{prefix}: 'types' is not a role; a rule for some need types is "
                "declared in those need types' own entries (a derive under the type's "
                "fields or links), or under derive_by_type for a type an extension "
                "adds",
            )
        if unknown[0] == "summary":
            # the stance is the link type's, the same under every rule of it
            return DeriveInvalid(
                kind,
                f"{prefix}: 'summary' is not a role; whether a link type is a summary "
                "is given on its needs_links entry, beside derive",
            )
        return DeriveInvalid(kind, f"{prefix}: {unknown[0]!r} is not a role")
    if on_link and kind not in LINK_KINDS | PATH_KINDS:
        return DeriveInvalid(
            kind,
            f"{prefix} computes a value, so it is declared on a field (needs_fields), "
            "not on a link type",
        )
    if not on_link and kind in LINK_KINDS:
        return DeriveInvalid(
            kind,
            f"{prefix} computes a link list, so it is declared on a link type "
            "(needs_links), not on a field",
        )
    path = on_link and kind in PATH_KINDS
    required, optional = (_PATH_ROLES_OF if path else _ROLES_OF)[kind]
    # a path's refusals name where the kind is declared: on a field it takes more
    where = f"{prefix} on a link type" if path else prefix
    for role in ROLES:
        if role in raw and role not in required and role not in optional:
            return DeriveInvalid(kind, f"{where} does not take the role {role!r}")
    for role in ROLES:
        if role in required and role not in raw:
            return DeriveInvalid(kind, f"{where} requires the role {role!r}")
    if kind == "links" and "where" not in raw and "join" not in raw:
        return DeriveInvalid(kind, f"{prefix} requires the role 'where' or 'join'")
    for role in ROLES:
        if role in raw and (problem := _value_problem(role, raw[role])) is not None:
            return DeriveInvalid(kind, f"{prefix}: the role {role!r} {problem}")
    if (twice := _named_twice(raw.get("exclude", ()))) is not None:
        return DeriveInvalid(
            kind, f"{prefix}: the role 'exclude' names {twice!r} twice"
        )
    if kind == "union" and (twice := _named_twice(raw["fields"])) is not None:
        return DeriveInvalid(kind, f"{prefix}: the role 'fields' names {twice!r} twice")
    if path and (problem := _path_problem(kind, raw)) is not None:
        return DeriveInvalid(kind, f"{where}: {problem}")
    if not path and (problem := _combination_problem(kind, raw)) is not None:
        return DeriveInvalid(kind, f"{prefix} {problem}")
    return DeriveRule(
        kind=kind,
        field=raw.get("field"),
        fields=tuple(raw.get("fields", ())),
        exclude=tuple(raw.get("exclude", ())),
        over=raw.get("over"),
        from_need=raw.get("from"),
        join=DeriveJoin(raw["join"]["field"], raw["join"]["equals"])
        if "join" in raw
        else None,
        where=raw.get("where"),
        test=raw.get("test"),
        empty=raw.get("empty"),
        # a path is a list of links: every target
        select=raw.get("select", "list" if path else "first"),
        transitive=raw.get("transitive", False),
        include_self=raw.get("include_self", False),
        include_parts=raw.get("include_parts", False),
        after_derived="after" in raw,
        on_link=path,
    )


def parse_derive_by_type(
    raw: Any, *, on_link: bool, need_types: Mapping[str, str]
) -> tuple[dict[str, Derive], list[tuple[str, str]]]:
    """Read a ``derive_by_type`` table: need type to rule, each read by :func:`parse_derive`.

    A key naming no declared need type is ignored; a rule that cannot be read is kept as
    its :class:`DeriveInvalid` marker, so the needs of that type hold their empty value.
    A ``derive_by_type`` that is not a table, or an empty one, gives no rule on any type.

    :param raw: The ``derive_by_type`` value, as configured.
    :param on_link: Whether it is declared on a link type.
    :param need_types: The declared need types: each directive name, with its title.
    :return: The rules by need type, and the problems found reading them, each as
        ``(part, reason)``: the part is ``derive_by_type`` for the table, else
        ``derive_by_type.<key>``.
    """
    if not isinstance(raw, Mapping):
        return {}, [("derive_by_type", "it is not a table of need types")]
    if not raw:
        return {}, [("derive_by_type", "it names no need type")]
    rules: dict[str, Derive] = {}
    problems: list[tuple[str, str]] = []
    for key in sorted(raw, key=str):
        name = str(key)
        if not isinstance(key, str) or key not in need_types:
            hint = title_hint(name, need_types)
            problems.append(
                (
                    f"derive_by_type.{name}",
                    f"{name!r} is not a need type{hint}; the entry is ignored",
                )
            )
            continue
        rule = parse_derive(raw[key], on_link=on_link)
        rules[key] = rule
        if isinstance(rule, DeriveInvalid):
            problems.append((f"derive_by_type.{key}", rule.reason))
    return rules, problems


def _value_problem(role: str, value: Any) -> str | None:
    """What is wrong with the value of one role, if anything."""
    if role in _STRING_ROLES:
        if not isinstance(value, str):
            return "must be a string"
        if role in {"field", "over", "from"} and not value.strip():
            return "must not be empty"
    elif role in _BOOLEAN_ROLES:
        if not isinstance(value, bool):
            return "must be a boolean"
    elif role == "fields":
        if (
            not isinstance(value, list | tuple)
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            return "must be a non-empty list of field names"
    elif role == "exclude":
        # an empty list leaves nothing out
        if not isinstance(value, list | tuple) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            return "must be a list of field names"
    elif role == "select":
        if value not in _SELECT:
            return 'must be "first", "unique" or "list"'
    elif role == "after" and value != "derived":
        return 'must be "derived"'
    elif role == "join":
        return _join_shape_problem(value)
    return None


def _join_shape_problem(value: Any) -> str | None:
    """What is wrong with the value of the ``join`` role, if anything: it is a table of
    exactly ``field`` and ``equals``, each a field's name."""
    if not isinstance(value, Mapping):
        return "must be a table with 'field' and 'equals'"
    if extra := sorted(str(key) for key in value if key not in _JOIN_KEYS):
        return f"has the key {extra[0]!r}; it takes 'field' and 'equals'"
    for key in _JOIN_KEYS:
        if key not in value:
            return f"has no {key!r}"
    for key in _JOIN_KEYS:
        if not isinstance(value[key], str) or not value[key].strip():
            return f"must name a field in {key!r}"
    return None


def _named_twice(names: Iterable[str]) -> str | None:
    """The first name a list names a second time, if any."""
    seen: set[str] = set()
    for name in names:
        if name in seen:
            return name
        seen.add(name)
    return None


def _path_problem(kind: str, raw: Mapping[str, Any]) -> str | None:
    """What is wrong with a ``copy`` or ``collect`` on a link type, of its shape."""
    if kind == "copy" and raw["field"] != "id":
        return (
            f"the role 'field' names {raw['field']!r}; a copy on a link type copies "
            "'id', linking each need 'over' names"
        )
    if "select" in raw and raw["select"] != "list":
        return (
            f"the role 'select' is {raw['select']!r}; a link list holds every target, "
            'so it is "list"'
        )
    return None


def _combination_problem(kind: str, raw: Mapping[str, Any]) -> str | None:
    """What is wrong with how the roles of a rule go together, if anything."""
    if kind == "copy":
        if sum(role in raw for role in ("from", "over", "join")) > 1:
            return "takes one of the roles 'from', 'over' and 'join', not more"
        if "select" in raw and "over" not in raw and "join" not in raw:
            return "takes the role 'select' only with 'over' or 'join'"
        # a where narrows the candidates, and a copy of one need has none
        if "where" in raw and "over" not in raw and "join" not in raw:
            return "takes the role 'where' only with 'over' or 'join'"
        # ``false``, the default, says nothing, as on min and max without transitive
        if raw.get("include_self") and "join" not in raw:
            return "takes the role 'include_self' only with 'join'"
    if kind == "links" and "join" in raw and raw.get("include_parts"):
        # a join's candidates are needs only
        return "takes the role 'include_parts' only without 'join'"
    if kind in {"any", "all"} and ("field" in raw) == ("test" in raw):
        return "takes exactly one of the roles 'field' and 'test'"
    if kind in {"min", "max"} and raw.get("include_self") and not raw.get("transitive"):
        return "takes the role 'include_self' only with 'transitive = true'"
    if kind == "links" and "where" in raw and not str(raw["where"]).strip():
        return "has an empty 'where', which would link every need"
    return None


# -- what a fingerprint includes ------------------------------------------------------


class NoDefault(enum.Enum):
    """The marker of a name a fingerprint always includes: it has no default to omit."""

    NO_DEFAULT = "no default"


#: A name without a default: it enters every fingerprint.
NO_DEFAULT: Final = NoDefault.NO_DEFAULT

#: The core fields a fingerprint includes, besides the project's fields and link types.
FINGERPRINT_CORE: Final = ("id", "type", "title", "status", "tags", "content")


def fingerprint_names(schema: FieldsSchema) -> dict[str, Any]:
    """Every name a ``fingerprint`` includes, with the default it is compared against.

    The names: ``id``, ``type``, ``title``, ``status``, ``tags`` and ``content``; every
    field the project declares (``needs_fields``, ``needs_extra_options``) that is not
    derived; every link type that is not derived, ``parent_needs`` aside. Never a field
    an extension or a service registers, nor any other core field.

    A name enters a need's fingerprint only when its value differs from its default:
    the field's literal default, else ``None`` when it is nullable, else
    :data:`NO_DEFAULT` (it always enters). A default that is a dynamic function or a
    variant is no literal default. ``id``, ``type`` and ``title`` have none,
    ``content`` has ``""``; a link type's default is its list of links, and a link
    type or ``tags`` without a literal default has ``[]``, its empty value.

    The default is the field's global declaration
    (:meth:`~sphinx_needs.needs_schema.FieldsSchema.global_declaration`), the same for the
    needs of every type: a value equal to a default a need type declares anew enters
    the fingerprint of its needs, unless it equals the global default too.

    :param schema: The schema, every field and link type added.
    :return: Each name, in the order above, with its default.
    """
    # imported here, as the schema module imports this one
    from sphinx_needs.needs_schema import FieldLiteralValue, LinksLiteralValue

    def declared(name: str) -> FieldSchema | LinkSchema:
        field = schema.global_declaration(name)
        assert field is not None, "a name of the schema"
        return field

    def default_of(name: str) -> Any:
        field = declared(name)
        if isinstance(field.default, FieldLiteralValue):
            return field.default.value
        return None if field.nullable else NO_DEFAULT

    names: dict[str, Any] = {}
    for name in FINGERPRINT_CORE:
        if name == "content":
            names[name] = ""
        elif name in {"status", "tags"} and schema.get_core_field(name):
            names[name] = default_of(name)
            if name == "tags" and names[name] is NO_DEFAULT:
                names[name] = []
        else:
            names[name] = NO_DEFAULT
    for field in schema.iter_extra_fields():
        if not field.derived and schema.is_project_field(field.name):
            names[field.name] = default_of(field.name)
    # Every link type is the project's today: only needs_links and needs_extra_links
    # declare one, and there is no API for an extension to add one. The set of names
    # is frozen to what the project declares, so when such an API lands, its link
    # types must be marked as the extension's (as add_extra_field's project flag
    # marks a field) and left out here.
    for link in schema.iter_link_fields():
        if not link.derived and link.name not in CORE_LINK_TYPES:
            default = declared(link.name).default
            names[link.name] = (
                list(default.value) if isinstance(default, LinksLiteralValue) else []
            )
    return names


# -- the checks against the configuration ---------------------------------------------


@dataclass(frozen=True, slots=True)
class _ValueType:
    """The type of a value a rule reads: a scalar type, or an array of one."""

    type: str
    item: str | None = None
    enum: bool = False

    def describe(self) -> str:
        if self.type == "array":
            return f"an array of {self.item}"
        return f"{self.type} with an enum" if self.enum else self.type


_LINK_LIST: Final = _ValueType("array", "string")


@dataclass(frozen=True, slots=True)
class DeriveProblem:
    """A ``needs.derive_invalid`` finding: a rule that cannot be read, or a key beside it.

    :ivar name: The field or link type the rule is declared on.
    :ivar on_link: Whether it is a link type.
    :ivar message: The warning.
    :ivar reason: Why the rule cannot be read, as its marker records it.
    :ivar core: Whether the rule is on a core field, which cannot carry one: the rule
        is ignored, and the field is not derived.
    :ivar part: What of the field's configuration it is about: ``derive`` (the rule,
        or a key beside it), ``derive_by_type`` (the table), ``derive_by_type.<type>``
        (one entry, or a key beside the rule a need type's entry gives), or ``beside``
        (a key beside ``derive_by_type`` alone).
    :ivar on_types: For a ``derive`` rule in a cycle on some need types only (through
        their ``derive_by_type`` entries): those types. The rule cannot be read there,
        and applies on every other type.
    :ivar type_reasons: For such a rule: each of those types with why it cannot be
        read there (the cycle closes along its own path on each).
    :ivar beside: The keys refused beside ``derive`` (``copy`` among them) with the
        rule as read: a finding replacing this one says them.
    """

    name: str
    on_link: bool
    message: str
    reason: str = ""
    core: bool = False
    part: str = "derive"
    on_types: tuple[str, ...] = ()
    type_reasons: tuple[tuple[str, str], ...] = ()
    beside: tuple[str, ...] = ()

    @property
    def order(self) -> tuple[bool, str, int, str]:
        """Where the finding is reported among the others: the fields, then the link
        types, each by name; within a name ``derive``, the ``derive_by_type`` table,
        its entries by need type, then the key beside ``derive_by_type``."""
        if self.part.startswith("derive_by_type."):
            rank, entry = 2, self.part.removeprefix("derive_by_type.")
        else:
            rank, entry = (
                {"derive": 0, "derive_by_type": 1, "beside": 3}[self.part],
                "",
            )
        return (self.on_link, self.name, rank, entry)


def _what(on_link: bool) -> str:
    return "link type" if on_link else "field"


def invalid_message(name: str, *, on_link: bool, reason: str) -> str:
    """The ``needs.derive_invalid`` warning for a rule that cannot be read."""
    what = _what(on_link)
    holds = "holds no links" if on_link else "holds its empty value"
    return (
        f"Invalid derive of {what} {name!r}: {reason}; "
        f"the {what} cannot be set in a need or by a needextend, and {holds}"
    )


def invalid_entry_message(
    name: str,
    *,
    on_link: bool,
    need_type: str,
    reason: str,
    spelling: str | None = None,
) -> str:
    """The ``needs.derive_invalid`` warning for a ``derive_by_type`` entry that cannot
    be read.

    :param spelling: The configuration the rule came from, if not ``derive_by_type``:
        a need type's entry (``needs_types['task'].fields['p'].derive``).
    """
    what = _what(on_link)
    holds = "holds no links" if on_link else "holds its empty value"
    entry = spelling or f"derive_by_type.{need_type}"
    return (
        f"Invalid derive of {what} {name!r}: {entry}: {reason}; "
        f"the {what} cannot be set in a need or by a needextend, and on need type "
        f"{need_type!r} {holds}"
    )


def _named_types(need_types: list[str]) -> str:
    quoted = [repr(need_type) for need_type in need_types]
    if len(quoted) == 1:
        return f"need type {quoted[0]}"
    return f"need types {', '.join(quoted[:-1])} and {quoted[-1]}"


def invalid_on_types_message(
    name: str,
    *,
    on_link: bool,
    type_reasons: Iterable[tuple[str, str]],
    everywhere: bool = False,
) -> str:
    """The ``needs.derive_invalid`` warning for a ``derive`` rule in a cycle of
    own-field reads on some need types: one clause per distinct cycle, naming the
    types it closes on.

    :param type_reasons: Each need type the rule cycles on, with why.
    :param everywhere: Whether those are every need type, so it applies on none.
    """
    what = _what(on_link)
    holds = "holds no links" if on_link else "holds its empty value"
    by_reason: dict[str, list[str]] = {}
    for need_type, reason in sorted(type_reasons):
        by_reason.setdefault(reason, []).append(need_type)
    clauses = "; ".join(
        f"on {_named_types(types)}: {reason}" for reason, types in by_reason.items()
    )
    count = sum(len(types) for types in by_reason.values())
    there = "that need type" if count == 1 else "those need types"
    rest = "" if everywhere else "; on every other need type the rule applies"
    return (
        f"Invalid derive of {what} {name!r}: {clauses}; the {what} cannot be set in a "
        f"need or by a needextend, and on {there} {holds}{rest}"
    )


def by_type_message(
    name: str,
    *,
    on_link: bool,
    part: str,
    reason: str,
    uses_derive: Literal["every", "uncycled", "none"] = "none",
) -> str:
    """The ``needs.derive_invalid`` warning for a ``derive_by_type`` table, or a key of
    it, that cannot be read (see :func:`parse_derive_by_type`).

    :param uses_derive: For the table (which adds no rule): which need types use the
        ``derive`` beside it -- every one, those it does not cycle on (its own
        finding names them), or none (there is none, or it cannot be read).
    """
    what = _what(on_link)
    if part == "derive_by_type":
        rules = {
            "every": "every need type uses its derive",
            "uncycled": "every need type uses its derive, but those it cycles on",
            "none": "no need type has a rule",
        }[uses_derive]
        return (
            f"Invalid derive_by_type of {what} {name!r}: {reason}; the {what} cannot "
            f"be set in a need or by a needextend, and {rules}"
        )
    return f"Invalid derive_by_type of {what} {name!r}: {reason}"


#: Why ``allow_dead_links`` cannot be given beside a link type whose rules are unions.
_UNION_DEAD_LINKS: Final = " (a union's dead links are its members')"

#: Why ``allow_dead_links`` cannot be given beside a link type whose rules are each a
#: union or a path, a path among them.
_PATH_DEAD_LINKS: Final = (
    " (the dead links a copy or collect carries are those of the link type it collects)"
)

#: Why ``summary = false`` cannot be given beside a ``copy`` or ``collect`` of a link
#: type.
_PATH_SUMMARY: Final = " (a link a copy or collect computes is a path, not an edge)"


def carries_links(rule: Derive | None) -> TypeGuard[DeriveRule]:
    """Whether a rule's links are other link types' links: a ``union`` (its members',
    on the need) or a path (``copy`` or ``collect`` on a link type, on other needs).
    Their dead links and conditions are those link types', where they are written."""
    return is_union(rule) or (isinstance(rule, DeriveRule) and rule.path)


def _why_beside(keys: Sequence[str], *, path: bool = False) -> str:
    """Why the keys refused beside a rule are, for those whose reason is not plain.

    :param path: Whether a path is among the rules, which ``allow_dead_links`` is
        refused beside.
    """
    dead = _PATH_DEAD_LINKS if path else _UNION_DEAD_LINKS
    return (dead if "allow_dead_links" in keys else "") + (
        _PATH_SUMMARY if "summary" in keys else ""
    )


def beside_clause(keys: Sequence[str], *, path: bool = False) -> str:
    """What a finding of a ``derive`` adds for the keys refused beside it, when the
    finding is another's: a cycle on some need types only, which leaves the rule
    applying on the others, so the keys beside it are still refused."""
    named = " and ".join(repr(key) for key in keys)
    verb = "are" if len(keys) > 1 else "is"
    why = _why_beside(keys, path=path)
    return f"; {named} cannot be given beside derive, and {verb} ignored{why}"


def beside_by_type_message(
    name: str,
    *,
    on_link: bool,
    keys: list[str],
    spelling: str | None = None,
    entries: Sequence[str] = (),
    path: bool = False,
) -> str:
    """The ``needs.derive_invalid`` warning for a key beside ``derive_by_type`` alone:
    ``predicates``, a ``default`` that is not a literal, or an ``allow_dead_links``
    where every rule is a ``union``.

    :param spelling: The need type's entry the key came from, if it did (a link type
        need types alone declare, whose rules are folded into ``derive_by_type``): the
        entry is named, and the key is beside its ``derive``.
    :param entries: The need types' entries the rules come from, when no
        ``derive_by_type`` is written (their rules are folded into it): the key is
        beside their rules, which are named.
    """
    named = " and ".join(repr(key) for key in keys)
    verb = "are" if len(keys) > 1 else "is"
    union = _why_beside(keys, path=path)
    if spelling is not None:
        return (
            f"Invalid derive of {_what(on_link)} {name!r}: {spelling}: {named} cannot "
            f"be given beside derive, and {verb} ignored{union}; the rule applies"
        )
    why = (
        "; the default of the need types without a rule must be a literal value"
        if "default" in keys
        else ""
    )
    beside = (
        f"the rules of need types' entries ({', '.join(entries)})"
        if entries
        else "derive_by_type"
    )
    return (
        f"Invalid derive of {_what(on_link)} {name!r}: {named} cannot be given beside "
        f"{beside}, and {verb} ignored{union}{why}; the rules apply"
    )


def core_message(name: str, *, on_link: bool, spelling: str | None = None) -> str:
    """The ``needs.derive_invalid`` warning for a rule on a core field or link type.

    :param spelling: The need type's entry the rule came from, if it did.
    """
    what = _what(on_link)
    entry = "" if spelling is None else f"{spelling}: "
    return (
        f"Invalid derive of {what} {name!r}: {entry}a core {what} cannot carry a "
        "derive rule in this release; the rule is ignored"
    )


def copy_on_derived_message(name: str, *, described: str) -> str:
    """The ``needs.derive_invalid`` warning for ``copy = true`` on a derived link type.

    :param described: The link type's rules, as messages name them.
    """
    return (
        f"Invalid derive of link type {name!r}: {described}: 'copy' is not "
        "available on a derived link type in this release, and is ignored; "
        "the rule applies"
    )


def beside_message(name: str, *, on_link: bool, rule: Derive, keys: list[str]) -> str:
    """The ``needs.derive_invalid`` warning for a default beside a rule."""
    named = " and ".join(repr(key) for key in keys)
    verb = "are" if len(keys) > 1 else "is"
    union = _why_beside(keys, path=isinstance(rule, DeriveRule) and rule.path)
    return (
        f"Invalid derive of {_what(on_link)} {name!r}: {rule.describe()}: {named} "
        f"cannot be given beside derive, and {verb} ignored{union}; the rule applies"
    )


def typed_empty(type_: str) -> Any:
    """The empty value of a field type: ``""``, ``False``, ``0``, ``0.0`` or ``[]``.

    It is what a derived field that is not nullable holds until its rule computes
    it (its placeholder), and ``None`` for a type that is not one of these.
    """
    match type_:
        case "string":
            return ""
        case "boolean":
            return False
        case "integer":
            return 0
        case "number":
            return 0.0
        case "array":
            return []
    return None


def copy_problem(schema: FieldsSchema) -> DeriveProblem | None:
    """The finding of a derived ``links`` that link types are declared to copy into.

    A link type with ``copy = true`` copies its links into ``links``; when ``links``
    holds what a rule computes, nothing is copied, and that is reported at the rule,
    naming every copying link type. The rule applies.
    """
    # imported here, as the schema module imports this one
    from sphinx_needs.needs_schema import LinkSchema

    links = schema.get_link_field("links")
    if links is None or not links.derived:
        return None
    # a derived link type copies nothing, and is reported at its own rule; the
    # schema is still built, so each link type is read in its global declaration
    copying = sorted(
        name
        for name in schema.iter_link_field_names()
        if (link := schema.global_declaration(name)) is not None
        and isinstance(link, LinkSchema)
        and link.copy
        and name != "links"
        and not link.derived
    )
    if not copying:
        return None
    named = " and ".join(repr(name) for name in copying)
    what = "link types" if len(copying) > 1 else "link type"
    return DeriveProblem(
        "links",
        True,
        f"Invalid derive of link type 'links': {links.describe_derived()}: 'links' is "
        f"derived; the copy of the {what} {named} into it is ignored; the rule applies",
        # reported with the rule, else as a key beside derive_by_type
        part="derive" if links.derive is not None else "beside",
    )


def check_derive_rules(
    schema: FieldsSchema, need_types: Iterable[str] | None = None
) -> list[DeriveProblem]:
    """Check every rule of the schema against the declared fields and link types.

    Each rule (``derive``, and each ``derive_by_type`` entry) is checked on its own
    (what its roles name, the predicates, the type of its result against the field's
    ``schema``), then the rules that read one another's own fields are checked for a
    cycle, which no need could compute. A cycle is on one need, so it is looked for per
    need type, among the rules that apply to that type: a type's own entry in a cycle
    cannot be read; a ``derive`` in a cycle on some types only cannot be read on those
    types (:attr:`DeriveProblem.on_types`), and applies on the others.

    :param schema: The schema, every field and link type added.
    :param need_types: The declared need types (directive names); if not given, the
        types the ``derive_by_type`` entries name, and every other type as one.
    :return: One problem per rule that cannot be read, in :attr:`DeriveProblem.order`.
    """
    problems: dict[tuple[bool, str, str], DeriveProblem] = {}
    # the global declarations: the rules are checked before any need is created
    targets = [
        target
        for name in (*schema.iter_extra_field_names(), *schema.iter_link_field_names())
        if (target := schema.global_declaration(name)) is not None
    ]
    #: the rules that can be read, by field and by entry ("" for ``derive``)
    valid: dict[tuple[str, str], tuple[DeriveRule, FieldSchema | LinkSchema]] = {}
    for target in targets:
        entries = [("", target.derive), *sorted((target.derive_by_type or {}).items())]
        for entry, rule in entries:
            if not isinstance(rule, DeriveRule):
                continue
            on_link = rule.link_valued
            if (reason := _rule_problem(rule, target, schema)) is not None:
                part = f"derive_by_type.{entry}" if entry else "derive"
                problems[(on_link, target.name, part)] = DeriveProblem(
                    target.name,
                    on_link,
                    invalid_entry_message(
                        target.name, on_link=on_link, need_type=entry, reason=reason
                    )
                    if entry
                    else invalid_message(target.name, on_link=on_link, reason=reason),
                    reason=reason,
                    part=part,
                )
            else:
                valid[(target.name, entry)] = (rule, target)
    for key, problem in _per_type_cycle_problems(targets, valid, need_types).items():
        problems.setdefault(key, problem)
    return sorted(problems.values(), key=lambda problem: problem.order)


def _per_type_cycle_problems(
    targets: list[FieldSchema | LinkSchema],
    valid: Mapping[tuple[str, str], tuple[DeriveRule, FieldSchema | LinkSchema]],
    need_types: Iterable[str] | None,
) -> dict[tuple[bool, str, str], DeriveProblem]:
    """The rules in a cycle of own-field reads, looked for per need type.

    The need types without a ``derive_by_type`` entry anywhere share their rules (every
    ``derive``), so they are looked at once, together.
    """
    listed = sorted({t for target in targets for t in target.derive_by_type or {}})
    #: each type an entry names, alone ("" for the others, together), with its types
    groups: list[tuple[str, tuple[str, ...]]]
    if need_types is None:
        # every type the entries do not name, as one group
        groups = [(t, (t,)) for t in listed]
        groups.append(("", ("",)))
        every_type: frozenset[str] = frozenset({*listed, ""})
    else:
        declared = sorted(set(need_types))
        groups = [(t, (t,)) for t in listed if t in declared]
        if others := tuple(t for t in declared if t not in listed):
            groups.append(("", others))
        every_type = frozenset(declared)
    problems: dict[tuple[bool, str, str], DeriveProblem] = {}
    #: a ``derive`` in a cycle: each type it cycles on, with why there
    fallbacks: dict[str, dict[str, str]] = {}
    for need_type, types in groups:
        rules: dict[str, tuple[DeriveRule, FieldSchema | LinkSchema]] = {}
        own: set[str] = set()
        for target in targets:
            entry = need_type if need_type in (target.derive_by_type or {}) else ""
            if (rule := valid.get((target.name, entry))) is not None:
                rules[target.name] = rule
                if entry:
                    own.add(target.name)
        for name, reason in _cycle_problems(rules).items():
            on_link = rules[name][0].link_valued
            if name in own:
                problems[(on_link, name, f"derive_by_type.{need_type}")] = (
                    DeriveProblem(
                        name,
                        on_link,
                        invalid_entry_message(
                            name, on_link=on_link, need_type=need_type, reason=reason
                        ),
                        reason=reason,
                        part=f"derive_by_type.{need_type}",
                    )
                )
            else:
                for cycling in types:
                    fallbacks.setdefault(name, {})[cycling] = reason
    for name, reasons in fallbacks.items():
        on_link = valid[(name, "")][0].link_valued
        type_reasons = tuple(sorted(reasons.items()))
        reason = type_reasons[0][1]
        everywhere = set(reasons) >= every_type
        if everywhere and len(set(reasons.values())) == 1:
            # the rule cycles on every need type, along one path: it cannot be read
            # anywhere, reported as a project without derive_by_type reports it
            problem = DeriveProblem(
                name,
                on_link,
                invalid_message(name, on_link=on_link, reason=reason),
                reason=reason,
            )
        else:
            problem = DeriveProblem(
                name,
                on_link,
                invalid_on_types_message(
                    name,
                    on_link=on_link,
                    type_reasons=type_reasons,
                    everywhere=everywhere,
                ),
                reason=reason,
                # a rule cycling on every type cannot be read on any
                on_types=() if everywhere else tuple(t for t, _ in type_reasons),
                type_reasons=() if everywhere else type_reasons,
            )
        problems[(on_link, name, "derive")] = problem
    return problems


def _rule_problem(
    rule: DeriveRule, target: FieldSchema | LinkSchema, schema: FieldsSchema
) -> str | None:
    """Why one rule cannot be read against the configuration, if it cannot."""
    prefix = rule.describe()
    links = set(schema.iter_link_field_names())
    if rule.over is not None and not _is_link_name(rule.over, links):
        return (
            f"{prefix}: the role 'over' names {rule.over!r}, "
            "which is not a link type or the back links of one"
        )
    source: _ValueType | None = None
    if rule.field is not None:
        source = _value_type(rule.field, schema, links)
        if source is None:
            return (
                f"{prefix}: the role 'field' names {rule.field!r}, "
                "which is not a field, a link type or the back links of one"
            )
    if rule.path and (problem := _path_names_problem(rule, target, schema, links)):
        return problem
    if rule.kind == "union":
        return _union_problem(rule, links, schema)
    for name in rule.fields:
        if name.endswith("_back") and name[:-5] in links:
            return (
                f"{prefix}: the role 'fields' names the back links {name!r}, "
                "which cannot be hashed"
            )
        if _value_type(name, schema, links) is None:
            return (
                f"{prefix}: the role 'fields' names {name!r}, "
                "which is not a field or a link type"
            )
    included = fingerprint_names(schema) if rule.kind == "fingerprint" else {}
    for name in rule.exclude:
        if _value_type(name, schema, links) is None:
            return (
                f"{prefix}: the role 'exclude' names {name!r}, "
                "which is not a field or a link type"
            )
        if name not in included:
            return (
                f"{prefix}: the role 'exclude' names {name!r}, "
                "which a fingerprint never includes"
            )
    if rule.join is not None:
        for key, name in (("field", rule.join.field), ("equals", rule.join.equals)):
            if (problem := join_name_problem(name, schema, links)) is not None:
                return f"{prefix}: the role 'join' names {name!r} in {key!r}{problem}"
    for role, text in (("where", rule.where), ("test", rule.test)):
        if text is not None and (problem := filter_problem(text)) is not None:
            return f"{prefix}: the role {role!r} {problem}"
    if rule.link_valued:
        return None
    return _result_problem(rule, source, target)


def _path_names_problem(
    rule: DeriveRule,
    target: FieldSchema | LinkSchema,
    schema: FieldsSchema,
    links: set[str],
) -> str | None:
    """Why a ``copy`` or ``collect`` on a link type cannot be read against the
    configuration, if it cannot.

    It is computed with the link types, before the back links are built and before any
    value field is computed: its ``over`` names no back links, and a ``collect``'s
    ``field`` a link type, derived or not. Its ``over`` may name a derived link type: a
    ``union`` is read through its members, so the needs it names are known when the
    link types are ordered; another rule's links are known only once computed, so the
    rule reads its ``field`` on every need computing it, and a ``collect`` of its own
    link type there would read itself: refused. Each is known at load, so it is
    refused there rather than reported on every need.
    """
    prefix = rule.describe()
    assert rule.over is not None and rule.field is not None, "a path has both"
    if rule.over not in links:
        return (
            f"{prefix}: the role 'over' names the back links {rule.over!r}, which a "
            "link type's rule cannot read: they are built after the link types"
        )
    if (
        rule.kind == "collect"
        and rule.field == target.name
        and (computing := _computed_over(schema, rule.over, frozenset())) is not None
    ):
        return (
            f"{prefix}: the role 'field' names {rule.field!r}, the link type it "
            f"computes, and the role 'over' names {rule.over!r}, which a "
            f"{computing!r} rule computes: which needs it names is known only once "
            "it is computed, so the collect would read itself on every need (over a "
            "union, which is read through its members, it is computed need by need)"
        )
    if rule.kind == "collect":
        if rule.field not in links and _is_link_name(rule.field, links):
            return (
                f"{prefix}: the role 'field' names the back links {rule.field!r}, "
                "which a link type's rule cannot read: they are built after the link "
                "types"
            )
        if rule.field not in links:
            return (
                f"{prefix}: the role 'field' names {rule.field!r}, which is not a "
                "link type; a collect on a link type gathers the links of a link type "
                "(a copy of 'id' links the needs themselves)"
            )
    return None


def _computed_over(schema: FieldsSchema, name: str, seen: frozenset[str]) -> str | None:
    """The kind of a rule other than a ``union`` computing the link type ``name``, or a
    member of a union computing it (through unions of unions), if one does: its links
    are known only once it is computed. ``None`` when every rule is a union of link
    types no other rule computes, or there is none."""
    # imported here, as the schema module imports this one
    from sphinx_needs.needs_schema import LinkSchema

    link = schema.global_declaration(name)
    if not isinstance(link, LinkSchema) or name in seen:
        return None
    for rule in (link.derive, *(link.derive_by_type or {}).values()):
        if not isinstance(rule, DeriveRule):
            continue  # a rule that cannot be read holds no links
        if rule.kind != "union":
            return rule.kind
        for member in rule.fields:
            if (kind := _computed_over(schema, member, seen | {name})) is not None:
                return kind
    return None


def _union_problem(
    rule: DeriveRule, links: set[str], schema: FieldsSchema
) -> str | None:
    """Why a ``union`` cannot be read against the configuration, if it cannot: each
    member must be a link type, other than ``parent_needs``, and no summary link type
    (a union is read as one set of edges, and a summary link materialises a path).

    The union itself, or a union naming it back, is the cycle check's to refuse.
    """
    prefix = rule.describe()
    for name in rule.fields:
        if name in CORE_LINK_TYPES:
            return (
                f"{prefix}: the role 'fields' names {name!r}, which a union cannot "
                "read in this release"
            )
        if _is_link_name(name, links) and name not in links:
            return (
                f"{prefix}: the role 'fields' names the back links {name!r}, which a "
                "union cannot read: they are built after the link types"
            )
        if name not in links:
            return (
                f"{prefix}: the role 'fields' names {name!r}, which is not a link type"
            )
        if is_summary(schema, name):
            return (
                f"{prefix}: the role 'fields' names {name!r}, a summary link type, "
                "which a union cannot read: a union is read as one set of edges, and a "
                "summary link is a shortcut, not an edge"
            )
    return None


def is_summary(schema: FieldsSchema, name: str) -> bool:
    """Whether the link type ``name`` is a summary, as its global declaration says."""
    # imported here, as the schema module imports this one
    from sphinx_needs.needs_schema import LinkSchema

    link = schema.global_declaration(name)
    return isinstance(link, LinkSchema) and link.summary


def is_union(rule: Derive | None) -> TypeGuard[DeriveRule]:
    """Whether a rule is a ``union``: its links are those of its members, which report
    their own dead links and link conditions, so the union reports none of its own.

    A ``union`` that cannot be read is no union: it holds no links.
    """
    return isinstance(rule, DeriveRule) and rule.kind == "union"


def _result_problem(
    rule: DeriveRule, source: _ValueType | None, target: FieldSchema | LinkSchema
) -> str | None:
    """Why the result of a value-valued rule cannot be held by its field, if it cannot."""
    prefix = rule.describe()
    result = _ValueType(
        target.type,
        target.item_type,
        bool(target.schema.get("enum")) if target.type != "array" else False,
    )
    match rule.kind:
        case "copy":
            assert source is not None, "copy requires a field"
            if rule.select == "list":
                if result.type != "array":
                    return (
                        f"{prefix}: the role 'select' is \"list\", which needs an array "
                        f"field, and the field's schema is {result.describe()}"
                    )
                expected = _ValueType("array", source.item or source.type)
                if not _holds(result, expected):
                    return (
                        f"{prefix}: the role 'select' is \"list\", so the rule gives "
                        f"{expected.describe()}, which the field's schema "
                        f"({result.describe()}) cannot hold"
                    )
            elif not _holds(result, source):
                return (
                    f"{prefix}: the role 'field' names {rule.field!r} "
                    f"({source.describe()}), which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "sum":
            assert source is not None, "sum requires a field"
            if source.type not in {"number", "integer"}:
                return (
                    f"{prefix}: the role 'field' names {rule.field!r} "
                    f"({source.describe()}), which is not a number"
                )
            if not _holds(result, source):
                return (
                    f"{prefix} gives {_a(source.type)}, which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "count":
            if not _holds(result, _ValueType("integer")):
                return (
                    f"{prefix} gives an integer, which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "min" | "max":
            assert source is not None, "min and max require a field"
            if source.type not in {"number", "integer"} and not (
                source.type == "string" and source.enum
            ):
                return (
                    f"{prefix}: the role 'field' names {rule.field!r} "
                    f"({source.describe()}), which has no order; "
                    "min and max read a number or a string with an enum"
                )
            if not _holds(result, source):
                return (
                    f"{prefix}: the role 'field' names {rule.field!r} "
                    f"({source.describe()}), which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "any" | "all":
            if source is not None and source.type != "boolean":
                return (
                    f"{prefix}: the role 'field' names {rule.field!r} "
                    f"({source.describe()}), which is not a boolean"
                )
            if result.type != "boolean":
                return (
                    f"{prefix} gives a boolean, which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "collect":
            assert source is not None, "collect requires a field"
            expected = _ValueType("array", source.item or source.type)
            if not _holds(result, expected):
                return (
                    f"{prefix} gives {expected.describe()}, which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
        case "hash" | "fingerprint":
            if result.type != "string":
                return (
                    f"{prefix} gives a string, which the field's schema "
                    f"({result.describe()}) cannot hold"
                )
    return None


def _a(type_: str) -> str:
    """A type's name with its article: ``a number``, ``an integer``."""
    return f"{'an' if type_[0] in 'aeiou' else 'a'} {type_}"


def _holds(result: _ValueType, value: _ValueType) -> bool:
    """Whether a field of type ``result`` can hold a value of type ``value``."""

    def scalar(result_type: str | None, value_type: str | None) -> bool:
        return result_type == value_type or (
            result_type == "number" and value_type == "integer"
        )

    if value.type == "array":
        return result.type == "array" and scalar(result.item, value.item)
    return result.type != "array" and scalar(result.type, value.type)


def join_name_problem(
    name: str, schema: FieldsSchema, links: Iterable[str]
) -> str | None:
    """Why a join cannot compare ``name``, if it cannot: it must be a value field
    holding a string (an enum included) or an array of strings.

    :return: The rest of a sentence naming ``name``: a link type (or its back links),
        a name that is no field, or a field of another type.
    """
    links = set(links)
    if _is_link_name(name, links):
        return ", a link type; a join compares text fields"
    joined = _value_type(name, schema, links)
    if joined is None:
        return ", which is not a field"
    if joined.type != "string" and joined != _LINK_LIST:
        return (
            f" ({joined.describe()}); a join compares a string or an array of strings"
        )
    return None


def _is_link_name(name: str, links: Iterable[str]) -> bool:
    """Whether ``name`` is a link type, or the back links of one."""
    links = set(links)
    return name in links or (name.endswith("_back") and name[:-5] in links)


def _value_type(name: str, schema: FieldsSchema, links: set[str]) -> _ValueType | None:
    """The type of the value ``name`` reads on a need, ``None`` if it names nothing."""
    if _is_link_name(name, links):
        return _LINK_LIST
    # the global declaration: a need type's enum is a subset of it
    field = schema.global_declaration(name)
    if field is not None:
        return _ValueType(
            field.type,
            field.item_type,
            field.type != "array" and bool(field.schema.get("enum")),
        )
    # imported here, as the data module imports the schema module, which imports this
    from sphinx_needs.data import NeedsCoreFields

    if (core := NeedsCoreFields.get(name)) is None:
        return None
    core_schema: Mapping[str, Any] = core["schema"]
    type_ = core_schema.get("type")
    if isinstance(type_, list):
        type_ = next((t for t in type_ if t != "null"), None)
    if not isinstance(type_, str):
        return None
    item = core_schema.get("items", {}).get("type") if type_ == "array" else None
    return _ValueType(type_, item if isinstance(item, str) else None)


def filter_problem(text: str) -> str | None:
    """Why a ``where`` / ``test`` predicate cannot be read by a declared rule, if it cannot.

    It must parse as a filter, and read the candidate alone: a predicate naming
    ``needs`` (every need), ``current_need`` (the reader) or a ``c.`` check (such as
    ``c.this_doc()``) is not portable, as ubCode cannot evaluate it -- but
    ``c.is_a("<type>")``, which reads the candidate's type alone, against the need
    types the project declares, and a facet of its source, ``c.source.<facet>``, which
    reads the candidate's source alone.

    :param text: The predicate.
    """
    try:
        compile(text, "<derive>", "eval")
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError) as exc:
        detail = exc.msg if isinstance(exc, SyntaxError) else str(exc)
        return f"does not parse as a filter ({detail})"
    #: the ``c.is_a("<type>")`` checks, which read the candidate alone
    is_a = {
        id(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "is_a"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "c"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    #: the ``c.source`` of each ``c.source.<facet>``, which reads the candidate alone
    facets = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in FACET_READERS
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "source"
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {"needs", "current_need"}:
            return f"names {node.id!r}, which a declared rule cannot read"
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "c"
            and id(node) not in is_a
            and id(node) not in facets
        ):
            return f"calls 'c.{node.attr}', which a declared rule cannot read"
    return None


def _own_reads(rule: DeriveRule) -> tuple[str, list[str]]:
    """The fields of its own need a rule reads (its S-edges), with the role naming them.

    A ``join`` reads ``equals`` on its own need, and its ``field`` on every need: only
    the first is an S-edge (a ``links`` rule's names are text fields, which no link
    rule computes, so only ``copy`` can close a cycle through them).
    """
    if rule.kind == "copy" and rule.join is not None:
        return "join", [rule.join.equals]
    if rule.kind == "copy" and rule.over is None and rule.from_need is None:
        return "field", [rule.field] if rule.field is not None else []
    if rule.kind in {"hash", "union"}:
        return "fields", list(rule.fields)
    return "", []


def _cycle_problems(
    rules: Mapping[str, tuple[DeriveRule, FieldSchema | LinkSchema]],
) -> dict[str, str]:
    """The rules that read one another's own fields in a cycle, with why.

    A rule reading a field of its own need that a rule reads back, directly or
    through other rules, can be computed on no need: it is known at load, unlike a
    cycle through ``over`` or ``from``, which depends on the needs.
    """
    edges: dict[str, list[str]] = {}
    roles: dict[str, str] = {}
    for name, (rule, _) in rules.items():
        role, reads = _own_reads(rule)
        roles[name] = role
        edges[name] = [read for read in reads if read in rules]
    problems: dict[str, str] = {}
    for component in _components(edges):
        if len(component) == 1 and component[0] not in edges[component[0]]:
            continue
        inside = set(component)
        for name in sorted(component):
            rule = rules[name][0]
            path = _cycle_path(name, edges, inside)
            problems[name] = (
                f"{rule.describe()}: the role {roles[name]!r} reads {path[1]!r}, "
                f"whose rule reads this field back ({' -> '.join(path)}), "
                "so no need can compute it"
            )
    return problems


def _cycle_path(
    name: str, edges: Mapping[str, list[str]], inside: set[str]
) -> list[str]:
    """The shortest path of reads from a rule's field back to it, within its cycle.

    Each step is a read: the path starts and ends at ``name``.
    """
    parents: dict[str, str] = {}
    queue = [name]
    for vertex in queue:
        for target in edges[vertex]:
            if target == name:
                path = [vertex]
                while path[-1] != name:
                    path.append(parents[path[-1]])
                return [*reversed(path), name]
            if target in inside and target not in parents:
                parents[target] = vertex
                queue.append(target)
    raise AssertionError("a member of a cycle reads its way back to itself")


def _components(edges: Mapping[str, list[str]]) -> list[list[str]]:
    """The strongly connected components of a small graph (Tarjan, recursive)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(vertex: str) -> None:
        index[vertex] = low[vertex] = len(index)
        stack.append(vertex)
        on_stack.add(vertex)
        for target in edges.get(vertex, ()):
            if target not in index:
                visit(target)
                low[vertex] = min(low[vertex], low[target])
            elif target in on_stack:
                low[vertex] = min(low[vertex], index[target])
        if low[vertex] == index[vertex]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == vertex:
                    break
            components.append(component)

    for vertex in sorted(edges):
        if vertex not in index:
            visit(vertex)
    return components
