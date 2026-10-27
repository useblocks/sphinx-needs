from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import ExtendType, NeedsExtendType, NeedsMutable, SphinxNeedsData
from sphinx_needs.derive import DeriveRule
from sphinx_needs.exceptions import (
    FunctionParsingException,
    NeedsInvalidFilter,
    VariantParsingException,
)
from sphinx_needs.filter_common import filter_needs_mutable
from sphinx_needs.functions.order import filter_names, placeholder, typed_empty
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedModification
from sphinx_needs.needs_schema import (
    FieldFunctionArray,
    FieldLiteralValue,
    FieldsSchema,
    LinkSchema,
    LinksFunctionArray,
    LinksLiteralValue,
    TypeFieldsSchema,
)
from sphinx_needs.utils import DummyOptionSpec, add_doc, coerce_to_boolean, counted_ids

logger = get_logger(__name__)

DEFAULT_EXTEND_PRIORITY: Final = 500
"""The priority of a ``needextend`` without ``:extend_priority:``.

Lower priorities are applied first, as for Sphinx's event handlers, whose default
priority is 500 too.
"""


class Needextend(nodes.General, nodes.Element):
    pass


class NeedextendDirective(SphinxDirective):
    """
    Directive to modify existing needs
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    option_spec: Final[DummyOptionSpec] = DummyOptionSpec()

    options: dict[str, str | None]

    def _log_warning(
        self, message: str, code: WarningSubTypes = "needextend", /
    ) -> None:
        """Log a warning with the given message and code."""
        log_warning(
            logger,
            message,
            code,
            location=self.get_location(),
        )

    def run(self) -> Sequence[nodes.Node]:
        # throughout this function, we gradually pop values from self.options
        # so that we can warn about unknown options at the end
        options: dict[str, str | None] = self.options

        needs_config = NeedsSphinxConfig(self.env.app.config)
        # the global view: a needextend may match needs of every type, and none is in
        # hand here, so its options are checked and converted against the declarations
        # every need type shares; each matched need is checked against its own type
        # where it is extended (_refused_on_type)
        needs_schema = SphinxNeedsData(self.env).get_schema().for_type(None)

        try:
            # override global needextend_strict if user set it in the directive
            strict = (
                coerce_to_boolean(options.pop("strict"))
                if "strict" in options
                else needs_config.needextend_strict
            )
        except ValueError as err:
            self._log_warning(f"Invalid value for 'strict' option: {err}")
            return []

        try:
            # the order this extend is applied in among all of them: lower first
            extend_priority = (
                directives.nonnegative_int(options.pop("extend_priority") or "")
                if "extend_priority" in options
                else DEFAULT_EXTEND_PRIORITY
            )
        except ValueError as err:
            self._log_warning(f"Invalid value for 'extend_priority' option: {err}")
            return []

        extend_filter = (self.arguments[0] if self.arguments else "").strip()
        if extend_filter.startswith("<") and extend_filter.endswith(">"):
            filter_is_id = True
            extend_filter = extend_filter[1:-1]
        elif extend_filter.startswith('"') and extend_filter.endswith('"'):
            filter_is_id = False
            extend_filter = extend_filter[1:-1]
        elif len(extend_filter.split()) == 1:
            filter_is_id = True
        else:
            filter_is_id = False

        if not extend_filter:
            self._log_warning("Empty ID/filter argument in needextend directive.")
            return []

        modifications: list[
            tuple[str, ExtendType, FieldLiteralValue | FieldFunctionArray | None]
        ] = []
        list_modifications: list[
            tuple[str, ExtendType, LinksLiteralValue | LinksFunctionArray]
        ] = []

        while options:
            key, value = options.popitem()

            if key.startswith("-"):
                key = key[1:]
                etype = ExtendType.DELETE
            elif key.startswith("+"):
                key = key[1:]
                etype = ExtendType.APPEND
            else:
                etype = ExtendType.REPLACE

            if (field_schema := needs_schema.get_any_field(key)) is None:
                self._log_warning(f"Unknown option '{etype.value}{key}'")
                continue
            if field_schema.derived:
                what = "Link type" if isinstance(field_schema, LinkSchema) else "Field"
                self._log_warning(
                    f"{what} {key!r} is derived ({field_schema.describe_derived()}) "
                    f"and cannot be set by a needextend; the option "
                    f"'{etype.value}{key}' is ignored",
                    "derive_authored",
                )
                continue
            if not field_schema.allow_extend:
                self._log_warning(
                    f"Option '{etype.value}{key}' does not support extend operations."
                )
                continue

            if etype == ExtendType.DELETE:
                if value is not None:
                    self._log_warning(
                        f"delete option '{etype.value}{key}' should not have a value."
                    )

                if isinstance(field_schema, LinkSchema):
                    list_modifications.append((key, etype, LinksLiteralValue([])))
                    continue
                # the value is the need's type's: None where it declares the field
                # nullable, else the empty value of its type (extend_needs_data)
                modifications.append((key, etype, None))
            else:
                if etype == ExtendType.APPEND and field_schema.type not in (
                    "string",
                    "array",
                ):
                    self._log_warning(
                        f"Cannot append to option '{etype.value}{key}' with type '{field_schema.type}'."
                    )
                    continue
                if isinstance(field_schema, LinkSchema):
                    try:
                        converted_link_value = field_schema.convert_directive_option(
                            value or ""
                        )
                    except (
                        ValueError,
                        FunctionParsingException,
                        VariantParsingException,
                    ) as err:
                        self._log_warning(
                            f"Invalid value for '{etype.value}{key}' option: {err}"
                        )
                        continue
                    list_modifications.append((key, etype, converted_link_value))
                else:
                    try:
                        converted_field_value = field_schema.convert_directive_option(
                            value or ""
                        )
                    except (
                        ValueError,
                        FunctionParsingException,
                        VariantParsingException,
                    ) as err:
                        self._log_warning(
                            f"Invalid value for '{etype.value}{key}' option: {err}"
                        )
                        continue
                    modifications.append((key, etype, converted_field_value))

        id = self.env.new_serialno("needextend")
        targetid = f"needextend-{self.env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        data = SphinxNeedsData(self.env).get_or_create_extends()
        data[targetid] = {
            "docname": self.env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": extend_filter,
            "filter_is_id": filter_is_id,
            "modifications": modifications,
            "list_modifications": list_modifications,
            "strict": strict,
            "extend_priority": extend_priority,
        }

        add_doc(self.env, self.env.docname)

        node = Needextend("")
        self.set_source_info(node)

        return [targetnode, node]


def extend_needs_data(
    all_needs: NeedsMutable,
    extends: dict[str, NeedsExtendType],
    needs_config: NeedsSphinxConfig,
    *,
    schema: FieldsSchema,
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs.

    The extends are applied in ``(extend_priority, docname, lineno)`` order. Which
    needs each one modifies is decided first, before any extend is applied: an id names
    its need, and a filter matches the needs as written, so no extend changes what
    another one's filter matches. A field an extend sets to a ``[[…]]`` or ``<<…>>``
    holds its empty value until the call is computed, as one written in the need does.

    A filter that names a field a ``[[…]]``, ``<<…>>`` or ``<{…}>`` computes, once
    every extend is applied, saw the value from before it is computed: each such
    extend is reported as ``needs.derive_scope``.
    """

    # Sort by priority, lower first, then by (docname, lineno) to ensure deterministic
    # ordering, regardless of parallel build worker completion order.
    sorted_extends = sorted(
        extends.values(),
        key=lambda x: (x["extend_priority"], x["docname"], x["lineno"]),
    )

    # The needs each extend modifies, taken before any extend is applied, in the order
    # the extends are applied, so the warnings come in that order too. The needs as
    # written are the same for every filter, so one filter string from one document
    # (``c.this_doc()`` reads it) gives one result, and is evaluated once.
    as_written_by_filter: dict[tuple[str, str], frozenset[str] | Exception] = {}
    targets: list[tuple[NeedsExtendType, list[str]]] = []
    for needextend in sorted_extends:
        need_filter = needextend["filter"]
        location = (needextend["docname"], needextend["lineno"])
        if needextend["filter_is_id"]:
            if need_filter not in all_needs:
                error = f"Provided id {need_filter!r} for needextend does not exist."
                if needextend["strict"]:
                    raise NeedsInvalidFilter(error)
                log_warning(logger, error, "needextend", location=location)
                continue
            targets.append((needextend, [need_filter]))
            continue
        key = (need_filter, needextend["docname"])
        if key not in as_written_by_filter:
            as_written_by_filter[key] = _ids_matched_as_written(
                all_needs, needs_config, needextend
            )
        matched = as_written_by_filter[key]
        if isinstance(matched, Exception):
            log_warning(
                logger,
                f"Invalid filter {need_filter!r}: {matched}",
                "needextend",
                location=location,
            )
            continue
        # a fixed order; each need is modified on its own, so nothing depends on it
        targets.append((needextend, sorted(matched)))

    #: (location, need type, option) -> the ids of the needs not extended by it
    refused: dict[tuple[tuple[str, int], str, str], list[str]] = {}
    current_needextend: NeedsExtendType
    for current_needextend, need_ids in targets:
        for need_id in need_ids:
            need = all_needs[need_id]
            need.add_modification(
                NeedModification(
                    docname=current_needextend["docname"],
                    lineno=current_needextend["lineno"],
                )
            )

            location = (
                current_needextend["docname"],
                current_needextend["lineno"],
            )
            # the fields of the need's type: a field it does not allow to extend is
            # not extended on its needs
            type_schema = schema.for_type(need["type"])

            for option_name, etype, link_value in current_needextend[
                "list_modifications"
            ]:
                if _refused_on_type(
                    type_schema, need, option_name, etype, location, refused
                ):
                    continue
                match (etype, link_value):
                    case (ExtendType.APPEND, LinksLiteralValue()):
                        if (df := _computed_links(need, option_name)) is not None:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (*df.value, *link_value.value)
                            )
                            need[option_name] = []
                        else:
                            existing = need.get_links(option_name, as_str=False)
                            need[option_name] = [
                                *existing,
                                *(  # keep unique
                                    v for v in link_value.value if v not in existing
                                ),
                            ]
                    case (ExtendType.APPEND, LinksFunctionArray()):
                        if (df := _computed_links(need, option_name)) is not None:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (  # keep unique
                                    *df.value,
                                    *(v for v in link_value.value if v not in df.value),
                                )
                            )
                            need[option_name] = []
                        else:
                            existing = need.get_links(option_name, as_str=False)
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (
                                    *existing,
                                    *(  # keep unique
                                        v for v in link_value.value if v not in existing
                                    ),
                                )
                            )
                            need[option_name] = []
                    case (ExtendType.REPLACE | ExtendType.DELETE, LinksLiteralValue()):
                        need._dynamic_fields.pop(option_name, None)
                        need[option_name] = link_value.value
                    case (ExtendType.REPLACE | ExtendType.DELETE, LinksFunctionArray()):
                        need._dynamic_fields[option_name] = link_value
                        need[option_name] = []
                    case other_link:
                        raise RuntimeError(
                            f"Unhandled case {other_link} for {option_name!r}"
                        )

            for option_name, etype, field_value in current_needextend["modifications"]:
                if _refused_on_type(
                    type_schema, need, option_name, etype, location, refused
                ):
                    continue
                match (etype, field_value):
                    case (ExtendType.APPEND, FieldLiteralValue()):
                        if (df := _computed_field(need, option_name)) is not None:
                            need._dynamic_fields[option_name] = (
                                FieldFunctionArray((*df.value, *field_value.value))
                                if isinstance(field_value.value, list)
                                else FieldFunctionArray((*df.value, field_value.value))
                            )
                        else:
                            if isinstance(field_value.value, list):
                                # an unset nullable field is None: appending sets it
                                current = need[option_name]
                                need[option_name] = [
                                    *(current if current is not None else []),
                                    *field_value.value,
                                ]
                            elif isinstance(field_value.value, str):
                                need[option_name] = (
                                    need[option_name] + " " + field_value.value
                                    if need[option_name]
                                    else field_value.value
                                )
                            else:
                                raise RuntimeError(
                                    f"Cannot append non-string/array value {field_value.value!r} to field '{option_name}'"
                                )
                    case (ExtendType.APPEND, FieldFunctionArray()):
                        if (df := _computed_field(need, option_name)) is not None:
                            need._dynamic_fields[option_name] = FieldFunctionArray(
                                (*df.value, *field_value.value)
                            )
                        else:
                            if isinstance(need[option_name], list):
                                need._dynamic_fields[option_name] = FieldFunctionArray(
                                    (*need[option_name], *field_value.value)
                                )
                            elif isinstance(need[option_name], str):
                                need._dynamic_fields[option_name] = FieldFunctionArray(
                                    (
                                        need[option_name],
                                        *field_value.value,
                                    )
                                )
                            elif need[option_name] is None:
                                # an unset nullable field: appending sets it
                                need._dynamic_fields[option_name] = field_value
                            else:
                                raise RuntimeError(
                                    f"Cannot append non-string/array value {field_value.value!r} to field '{option_name}'"
                                )
                            # the value written is part of the call's value now
                            _hold_placeholder(need, option_name, type_schema)
                    case (ExtendType.REPLACE | ExtendType.DELETE, None):
                        # a deleted field: the empty value the need's type declares
                        field = type_schema.get_any_field(option_name)
                        if field is None:
                            # an extend kept from an earlier build, of a field this
                            # build's schema does not have: nothing to delete
                            continue
                        need._dynamic_fields.pop(option_name, None)
                        need[option_name] = typed_empty(field)
                    case (ExtendType.REPLACE | ExtendType.DELETE, FieldLiteralValue()):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields.pop(option_name, None)
                        need[option_name] = field_value.value
                    case (ExtendType.REPLACE | ExtendType.DELETE, FieldFunctionArray()):
                        need._dynamic_fields[option_name] = field_value
                        _hold_placeholder(need, option_name, type_schema)
                    case other_field:
                        raise RuntimeError(
                            f"Unhandled case {other_field} for {option_name!r}"
                        )

    for (location, need_type, option), ids in refused.items():
        log_warning(
            logger,
            f"Option '{option}' does not support extend operations on need type "
            f"{need_type!r}; it does not extend "
            f"{counted_ids(ids, ' need' if len(ids) == 1 else ' needs')}.",
            "needextend",
            location=location,
        )
    _report_filters_on_computed_fields(all_needs, targets, needs_config, schema)


def _computed_links(need: NeedItem, name: str) -> LinksFunctionArray | None:
    """The ``[[…]]``, ``<<…>>`` or ``<{…}>`` value a need holds for a link type.

    A need holds its computed values by name, a link type's as a
    :class:`.LinksFunctionArray` and a field's as a :class:`.FieldFunctionArray`, and no
    field has a link type's name.

    :raises RuntimeError: if the need holds a field's computed value under the name.
    """
    computed = need._dynamic_fields.get(name)
    if computed is None or isinstance(computed, LinksFunctionArray):
        return computed
    raise RuntimeError(f"Link type {name!r} holds a field's value {computed!r}")


def _computed_field(need: NeedItem, name: str) -> FieldFunctionArray | None:
    """The ``[[…]]``, ``<<…>>`` or ``<{…}>`` value a need holds for a field.

    The counterpart of :func:`_computed_links`: no link type has a field's name.

    :raises RuntimeError: if the need holds a link type's computed value under the name.
    """
    computed = need._dynamic_fields.get(name)
    if computed is None or isinstance(computed, FieldFunctionArray):
        return computed
    raise RuntimeError(f"Field {name!r} holds a link type's value {computed!r}")


def _refused_on_type(
    type_schema: TypeFieldsSchema,
    need: NeedItem,
    option_name: str,
    etype: ExtendType,
    location: tuple[str, int],
    refused: dict[tuple[tuple[str, int], str, str], list[str]],
) -> bool:
    """Whether the need's type does not allow to extend the field: then the need is
    added to ``refused``, reported once for every needextend, need type and option.

    The directive refuses an option whose field does not allow it on any need type;
    a need type may declare the field anew, or not declare a field declared on need
    types alone, so each need is checked against its type.
    """
    field_schema = type_schema.get_any_field(option_name)
    if field_schema is None or field_schema.allow_extend:
        return False
    refused.setdefault(
        (location, need["type"], f"{etype.value}{option_name}"), []
    ).append(need.id)
    return True


def _hold_placeholder(need: NeedItem, option_name: str, schema: FieldsSchema) -> None:
    """Give a field an extend sets to a call its placeholder value, until it is computed.

    The value it held before the extend is not the call's, and nothing must read it:
    a cycle member, or a read the order cannot place, reads the placeholder whether
    the call was written in the need or set by an extend. An array keeps the items
    written before a call was appended to them; anything else is empty.
    """
    need[option_name] = placeholder(need, option_name, schema)


#: What computes the fields a needextend filter names, keyed by (a declared rule
#: computes one of them on some need, a call or variant does).
_COMPUTED_BY = {
    (True, False): "a derive rule",
    (True, True): "a derive rule, a dynamic function or a variant",
    (False, True): "a dynamic function or variant",
}


def _report_filters_on_computed_fields(
    all_needs: NeedsMutable,
    targets: Sequence[tuple[NeedsExtendType, Sequence[str]]],
    needs_config: NeedsSphinxConfig,
    schema: FieldsSchema,
) -> None:
    """Report each extend whose filter names a field some need computes.

    The filter matched the needs as written, before any ``[[…]]``, ``<<…>>`` or
    ``<{…}>`` is computed, so it saw such a field's value from before. Every need is a
    candidate of a filter, so any need computing the field counts, whether or not the
    filter matched it: a derived field is computed on every need from the project's
    sources, of a type it has a rule for. The needs are looked at only when an extend
    has a filter, once.
    """
    filtered = [
        needextend for needextend, _ in targets if not needextend["filter_is_id"]
    ]
    if not filtered:
        return
    derived = [
        field
        for field in (*schema.iter_extra_fields(), *schema.iter_link_fields())
        if field.derived
    ]
    # each field computed on some need, with the needs computing it: by a declared
    # rule (True) or by a call or variant (False)
    computed: dict[str, dict[str, bool]] = {}
    for need in all_needs.values():
        for field_name in need._dynamic_fields:
            computed.setdefault(field_name, {}).setdefault(need.id, False)
        if derived and not (need["is_import"] or need["is_external"]):
            for field in derived:
                # a need of a type without a rule holds a value that is final
                if isinstance(field.rule_for(need["type"]), DeriveRule):
                    # a rule wins over a call on its (closed) field; defensive, as
                    # no build has been found where the order is observable
                    computed.setdefault(field.name, {})[need.id] = True
    if not computed:
        return
    not_fields = frozenset(needs_config.filter_data)
    for needextend in filtered:
        names = filter_names(needextend["filter"], not_fields)
        read = sorted(
            name
            for name in names.names | names.current
            if name in computed
            or (name == "parent_need" and "parent_needs" in computed)
        )
        if not read:
            continue
        by_need = [
            computed.get("parent_needs" if name == "parent_need" else name, {})
            for name in read
        ]
        ids = {need_id for needs in by_need for need_id in needs}
        by_rule = any(rule for needs in by_need for rule in needs.values())
        by_call = any(not rule for needs in by_need for rule in needs.values())
        quoted = [f"'{name}'" for name in read]
        named = (
            quoted[0]
            if len(quoted) == 1
            else f"{', '.join(quoted[:-1])} and {quoted[-1]}"
        )
        log_warning(
            logger,
            f"needextend filter {needextend['filter']!r} names {named}, which "
            f"{_COMPUTED_BY[by_rule, by_call]} computes on "
            f"{counted_ids(ids, ' need' if len(ids) == 1 else ' needs')}: "
            "the filter sees the value from before it is computed",
            "derive_scope",
            location=(needextend["docname"], needextend["lineno"]),
        )


def _ids_matched_as_written(
    all_needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
    needextend: NeedsExtendType,
) -> frozenset[str] | Exception:
    """Return the ids of the needs a needextend's filter matches as written.

    Called before the first extend is applied, so the needs are as written and need no
    copy; ``id`` cannot be extended, so the ids name the same needs afterwards. It is
    the filter's one evaluation, so a warning the filter logs itself (``needs.filter``,
    for a need it cannot be evaluated on) is logged once, at this extend's location.

    :return: The ids, or the exception if the filter cannot be evaluated at all, which
        each extend carrying the filter reports.
    """
    try:
        found_needs = filter_needs_mutable(
            all_needs,
            needs_config,
            needextend["filter"],
            location=(needextend["docname"], needextend["lineno"]),
            origin_docname=needextend["docname"],
        )
    except Exception as err:
        return err
    return frozenset(need["id"] for need in found_needs)
