"""Declared derived fields: the ``derive`` rule of a ``needs_fields`` or ``needs_links`` entry.

A field (or link type) whose entry carries a ``derive`` table is *derived*: its value is
computed by the rule, for every need the project creates from its sources, and an author
cannot set it -- not in a need, not by a ``needextend``. The table names a ``kind`` and
the kind's operands, each under a fixed *role* name::

    [needs.fields.total]
    schema = { type = "number" }
    derive = { kind = "sum", field = "hours", over = "links" }

This module reads the table (``parse_derive``) and checks the rule against the
declared fields and link types (``check_derive_rules``). A rule that cannot be read is
kept as a :class:`DeriveInvalid` marker rather than dropped, so the field stays closed to
authors and holds its empty value, as the rule promised it would not be authored.

Nothing here touches Sphinx: the checks return the problems, and the caller reports them
(as ``needs.derive_invalid``).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias

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
    "links",
    "content_links",
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
    "links",
    "content_links",
)

#: The kinds that compute a link list, declared on a link type; every other kind
#: computes a value, declared on a field.
LINK_KINDS: Final = frozenset({"links", "content_links"})

#: The roles, in the order a rule's problems are looked for.
ROLES: Final = (
    "field",
    "fields",
    "over",
    "from",
    "where",
    "test",
    "select",
    "transitive",
    "include_self",
    "include_parts",
    "after",
)

#: Roles that are reserved for a later release: a rule naming one cannot be read.
RESERVED_ROLES: Final = frozenset({"join"})

#: The core fields, besides every ``NeedsCoreFields`` entry, that cannot carry a rule.
CORE_LINK_TYPES: Final = frozenset({"parent_needs"})

#: Per kind, the roles it requires and the roles it may take besides.
_ROLES_OF: Final[Mapping[str, tuple[frozenset[str], frozenset[str]]]] = {
    "copy": (frozenset({"field"}), frozenset({"from", "over", "select", "after"})),
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
    "any": (frozenset({"over"}), frozenset({"field", "test", "where", "after"})),
    "all": (frozenset({"over"}), frozenset({"field", "test", "where", "after"})),
    "collect": (frozenset({"field", "over"}), frozenset({"where", "after"})),
    "hash": (frozenset({"fields"}), frozenset({"after"})),
    "links": (frozenset({"where"}), frozenset({"include_self", "include_parts"})),
    "content_links": (frozenset(), frozenset({"from", "where"})),
}

_STRING_ROLES: Final = frozenset({"field", "over", "from", "where", "test"})
_BOOLEAN_ROLES: Final = frozenset({"transitive", "include_self", "include_parts"})
_SELECT: Final = ("first", "unique", "list")


@dataclass(frozen=True, slots=True, kw_only=True)
class DeriveRule:
    """A ``derive`` rule that can be read: the kind and its roles.

    :ivar kind: The kind.
    :ivar field: The ``field`` role: the field read on each candidate, or on this need.
    :ivar fields: The ``fields`` role (``hash``): the own fields hashed, in order.
    :ivar over: The ``over`` role: a link type, or ``<link type>_back``.
    :ivar from_need: The ``from`` role: the id of the one need read.
    :ivar where: The ``where`` role: the predicate narrowing the candidates.
    :ivar test: The ``test`` role: the predicate asserted of each candidate.
    :ivar select: The ``select`` role of a ``copy`` over several targets.
    :ivar transitive: The ``transitive`` role of ``min`` / ``max``.
    :ivar include_self: The ``include_self`` role.
    :ivar include_parts: The ``include_parts`` role (``links``).
    :ivar after_derived: The ``after = "derived"`` role.
    """

    kind: DeriveKind
    field: str | None = None
    fields: tuple[str, ...] = ()
    over: str | None = None
    from_need: str | None = None
    where: str | None = None
    test: str | None = None
    select: Literal["first", "unique", "list"] = "first"
    transitive: bool = False
    include_self: bool = False
    include_parts: bool = False
    after_derived: bool = False

    @property
    def late(self) -> bool:
        """Whether the rule runs in the late stage, after every other derivation."""
        return self.kind == "hash" or self.after_derived

    @property
    def link_valued(self) -> bool:
        """Whether the rule computes a link list."""
        return self.kind in LINK_KINDS

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
    """

    kind: str | None
    reason: str

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
        return DeriveInvalid(kind, f"{prefix}: {unknown[0]!r} is not a role")
    if on_link and kind not in LINK_KINDS:
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
    required, optional = _ROLES_OF[kind]
    for role in ROLES:
        if role in raw and role not in required and role not in optional:
            return DeriveInvalid(kind, f"{prefix} does not take the role {role!r}")
    for role in ROLES:
        if role in required and role not in raw:
            return DeriveInvalid(kind, f"{prefix} requires the role {role!r}")
    for role in ROLES:
        if role in raw and (problem := _value_problem(role, raw[role])) is not None:
            return DeriveInvalid(kind, f"{prefix}: the role {role!r} {problem}")
    if (problem := _combination_problem(kind, raw)) is not None:
        return DeriveInvalid(kind, f"{prefix} {problem}")
    return DeriveRule(
        kind=kind,
        field=raw.get("field"),
        fields=tuple(raw.get("fields", ())),
        over=raw.get("over"),
        from_need=raw.get("from"),
        where=raw.get("where"),
        test=raw.get("test"),
        select=raw.get("select", "first"),
        transitive=raw.get("transitive", False),
        include_self=raw.get("include_self", False),
        include_parts=raw.get("include_parts", False),
        after_derived="after" in raw,
    )


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
    elif role == "select":
        if value not in _SELECT:
            return 'must be "first", "unique" or "list"'
    elif role == "after" and value != "derived":
        return 'must be "derived"'
    return None


def _combination_problem(kind: str, raw: Mapping[str, Any]) -> str | None:
    """What is wrong with how the roles of a rule go together, if anything."""
    if kind == "copy":
        if "from" in raw and "over" in raw:
            return "takes one of the roles 'from' and 'over', not both"
        if "select" in raw and "over" not in raw:
            return "takes the role 'select' only with 'over'"
    if kind in {"any", "all"} and ("field" in raw) == ("test" in raw):
        return "takes exactly one of the roles 'field' and 'test'"
    if kind in {"min", "max"} and raw.get("include_self") and not raw.get("transitive"):
        return "takes the role 'include_self' only with 'transitive = true'"
    if kind == "links" and not str(raw.get("where", "")).strip():
        return "has an empty 'where', which would link every need"
    return None


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
    """

    name: str
    on_link: bool
    message: str
    reason: str = ""
    core: bool = False


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


def core_message(name: str, *, on_link: bool) -> str:
    """The ``needs.derive_invalid`` warning for a rule on a core field or link type."""
    what = _what(on_link)
    return (
        f"Invalid derive of {what} {name!r}: a core {what} cannot carry a derive rule "
        "in this release; the rule is ignored"
    )


def copy_on_derived_message(name: str, *, rule: Derive) -> str:
    """The ``needs.derive_invalid`` warning for ``copy = true`` on a derived link type."""
    return (
        f"Invalid derive of link type {name!r}: {rule.describe()}: 'copy' is not "
        "available on a derived link type in this release, and is ignored; "
        "the rule applies"
    )


def beside_message(name: str, *, on_link: bool, rule: Derive, keys: list[str]) -> str:
    """The ``needs.derive_invalid`` warning for a default beside a rule."""
    named = " and ".join(repr(key) for key in keys)
    verb = "are" if len(keys) > 1 else "is"
    return (
        f"Invalid derive of {_what(on_link)} {name!r}: {rule.describe()}: {named} "
        f"cannot be given beside derive, and {verb} ignored; the rule applies"
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
    links = schema.get_link_field("links")
    if links is None or links.derive is None:
        return None
    # a derived link type copies nothing, and is reported at its own rule
    copying = sorted(
        link.name
        for link in schema.iter_link_fields()
        if link.copy and link.name != "links" and link.derive is None
    )
    if not copying:
        return None
    named = " and ".join(repr(name) for name in copying)
    what = "link types" if len(copying) > 1 else "link type"
    return DeriveProblem(
        "links",
        True,
        f"Invalid derive of link type 'links': {links.derive.describe()}: 'links' is "
        f"derived; the copy of the {what} {named} into it is ignored; the rule applies",
    )


def check_derive_rules(schema: FieldsSchema) -> list[DeriveProblem]:
    """Check every rule of the schema against the declared fields and link types.

    Each rule is checked on its own (what its roles name, the predicates, the type of
    its result against the field's ``schema``), then the rules that read one another's
    own fields are checked for a cycle, which no need could compute.

    :param schema: The schema, every field and link type added.
    :return: One problem per rule that cannot be read, fields first, each by name.
    """
    problems: dict[tuple[bool, str], DeriveProblem] = {}
    rules: dict[str, tuple[DeriveRule, FieldSchema | LinkSchema]] = {}
    for target in (*schema.iter_extra_fields(), *schema.iter_link_fields()):
        rule = target.derive
        if not isinstance(rule, DeriveRule):
            continue
        on_link = rule.link_valued
        if (reason := _rule_problem(rule, target, schema)) is not None:
            problems[(on_link, target.name)] = DeriveProblem(
                target.name,
                on_link,
                invalid_message(target.name, on_link=on_link, reason=reason),
                reason=reason,
            )
        else:
            rules[target.name] = (rule, target)
    for name, reason in _cycle_problems(rules).items():
        on_link = rules[name][0].link_valued
        problems[(on_link, name)] = DeriveProblem(
            name,
            on_link,
            invalid_message(name, on_link=on_link, reason=reason),
            reason=reason,
        )
    return [problems[key] for key in sorted(problems)]


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
    for role, text in (("where", rule.where), ("test", rule.test)):
        if text is not None and (problem := filter_problem(text)) is not None:
            return f"{prefix}: the role {role!r} {problem}"
    if rule.link_valued:
        return None
    return _result_problem(rule, source, target)


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
        case "hash":
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


def _is_link_name(name: str, links: Iterable[str]) -> bool:
    """Whether ``name`` is a link type, or the back links of one."""
    links = set(links)
    return name in links or (name.endswith("_back") and name[:-5] in links)


def _value_type(name: str, schema: FieldsSchema, links: set[str]) -> _ValueType | None:
    """The type of the value ``name`` reads on a need, ``None`` if it names nothing."""
    if _is_link_name(name, links):
        return _LINK_LIST
    field = schema.get_extra_field(name) or schema.get_core_field(name)
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
    ``c.this_doc()``) is not portable, as ubCode cannot evaluate it.

    :param text: The predicate.
    """
    try:
        compile(text, "<derive>", "eval")
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError) as exc:
        detail = exc.msg if isinstance(exc, SyntaxError) else str(exc)
        return f"does not parse as a filter ({detail})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {"needs", "current_need"}:
            return f"names {node.id!r}, which a declared rule cannot read"
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "c"
        ):
            return f"calls 'c.{node.attr}', which a declared rule cannot read"
    return None


def _own_reads(rule: DeriveRule) -> tuple[str, list[str]]:
    """The fields of its own need a rule reads (its S-edges), with the role naming them."""
    if rule.kind == "copy" and rule.over is None and rule.from_need is None:
        return "field", [rule.field] if rule.field is not None else []
    if rule.kind == "hash":
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
