from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Final

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import suppress_logging

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import ExtendType, NeedsExtendType, NeedsMutable, SphinxNeedsData
from sphinx_needs.exceptions import (
    FunctionParsingException,
    NeedsInvalidFilter,
    VariantParsingException,
)
from sphinx_needs.filter_common import filter_needs_mutable
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.need_item import NeedModification
from sphinx_needs.needs_schema import (
    FieldFunctionArray,
    FieldLiteralValue,
    LinkSchema,
    LinksFunctionArray,
    LinksLiteralValue,
)
from sphinx_needs.utils import (
    DummyOptionSpec,
    add_doc,
    coerce_to_boolean,
    counted_ids,
)

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
        needs_schema = SphinxNeedsData(self.env).get_schema()

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
                if field_schema.nullable:
                    modifications.append((key, etype, None))
                    continue
                match field_schema.type:
                    case "string":
                        modifications.append((key, etype, FieldLiteralValue("")))
                    case "boolean":
                        modifications.append((key, etype, FieldLiteralValue(False)))
                    case "number":
                        modifications.append((key, etype, FieldLiteralValue(0.0)))
                    case "integer":
                        modifications.append((key, etype, FieldLiteralValue(0)))
                    case "array":
                        modifications.append((key, etype, FieldLiteralValue([])))
                    case other:
                        self._log_warning(
                            f"Unknown field type '{other}' for option '{key}'"
                        )
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
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs.

    The extends are applied in ``(extend_priority, docname, lineno)`` order, and each
    filter is evaluated against the needs as the extends applied before it left them.
    A filter that matches other needs against the needs as written, before any extend
    is applied, is reported as ``needs.needextend_match_order``.
    """

    # Sort by priority, lower first, then by (docname, lineno) to ensure deterministic
    # ordering, regardless of parallel build worker completion order.
    sorted_extends = sorted(
        extends.values(),
        key=lambda x: (x["extend_priority"], x["docname"], x["lineno"]),
    )

    # What each filter matches against the needs as written, taken before any extend
    # is applied; an id-targeted extend's target is fixed, so it needs none. The needs
    # as written are the same for every filter, so one filter string from one document
    # (``c.this_doc()`` reads it) gives one set, and is evaluated once.
    as_written_by_filter: dict[tuple[str, str], frozenset[str] | None] = {}
    matched_as_written: list[frozenset[str] | None] = []
    for needextend in sorted_extends:
        if needextend["filter_is_id"]:
            matched_as_written.append(None)
            continue
        key = (needextend["filter"], needextend["docname"])
        if key not in as_written_by_filter:
            as_written_by_filter[key] = _ids_matched_as_written(
                all_needs, needs_config, needextend
            )
        matched_as_written.append(as_written_by_filter[key])

    current_needextend: NeedsExtendType
    for current_needextend, as_written in zip(
        sorted_extends, matched_as_written, strict=True
    ):
        need_filter = current_needextend["filter"]
        location = (current_needextend["docname"], current_needextend["lineno"])
        if current_needextend["filter_is_id"]:
            try:
                found_needs = [all_needs[need_filter]]
            except KeyError:
                error = f"Provided id {need_filter!r} for needextend does not exist."
                if current_needextend["strict"]:
                    raise NeedsInvalidFilter(error)
                else:
                    log_warning(logger, error, "needextend", location=location)
                continue
        else:
            try:
                found_needs = filter_needs_mutable(
                    all_needs,
                    needs_config,
                    need_filter,
                    location=location,
                    origin_docname=current_needextend["docname"],
                )
            except Exception as e:
                log_warning(
                    logger,
                    f"Invalid filter {need_filter!r}: {e}",
                    "needextend",
                    location=location,
                )
                continue
            if as_written is not None:
                matched_now = frozenset(need["id"] for need in found_needs)
                if matched_now != as_written:
                    log_warning(
                        logger,
                        _match_order_message(matched_now, as_written),
                        "needextend_match_order",
                        location=location,
                    )

        for found_need in found_needs:
            # Work in the stored needs, not on the search result
            need = all_needs[found_need["id"]]
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

            for option_name, etype, link_value in current_needextend[
                "list_modifications"
            ]:
                match (etype, link_value):
                    case (ExtendType.APPEND, LinksLiteralValue()):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (*df.value, *link_value.value)  # ty: ignore[invalid-argument-type]
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
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (  # keep unique
                                    *df.value,
                                    *(v for v in link_value.value if v not in df.value),
                                )  # ty: ignore[invalid-argument-type]
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
                match (etype, field_value):
                    case (ExtendType.APPEND, FieldLiteralValue()):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields[option_name] = (
                                FieldFunctionArray((*df.value, *field_value.value))  # ty: ignore[invalid-argument-type]
                                if isinstance(field_value.value, list)
                                else FieldFunctionArray((*df.value, field_value.value))  # ty: ignore[invalid-argument-type]
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
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields[option_name] = FieldFunctionArray(
                                (*df.value, *field_value.value)  # ty: ignore[invalid-argument-type]
                            )
                        else:
                            if isinstance(need[option_name], list):
                                need._dynamic_fields[option_name] = FieldFunctionArray(
                                    (*need[option_name], *field_value.value)  # ty: ignore[invalid-argument-type]
                                )
                            elif isinstance(need[option_name], str):
                                need._dynamic_fields[option_name] = FieldFunctionArray(
                                    (
                                        need[option_name],
                                        *field_value.value,
                                    )  # ty: ignore[invalid-argument-type]
                                )
                            elif need[option_name] is None:
                                # an unset nullable field: appending sets it
                                need._dynamic_fields[option_name] = field_value
                            else:
                                raise RuntimeError(
                                    f"Cannot append non-string/array value {field_value.value!r} to field '{option_name}'"
                                )
                    case (ExtendType.REPLACE | ExtendType.DELETE, None):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields.pop(option_name, None)
                        need[option_name] = None
                    case (ExtendType.REPLACE | ExtendType.DELETE, FieldLiteralValue()):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields.pop(option_name, None)
                        need[option_name] = field_value.value
                    case (ExtendType.REPLACE | ExtendType.DELETE, FieldFunctionArray()):
                        need._dynamic_fields[option_name] = field_value
                        # TODO reset need[option_name] to something sensible?
                    case other_field:
                        raise RuntimeError(
                            f"Unhandled case {other_field} for {option_name!r}"
                        )


def _ids_matched_as_written(
    all_needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
    needextend: NeedsExtendType,
) -> frozenset[str] | None:
    """Return the ids of the needs a needextend's filter matches before any extend.

    Called before the first extend is applied, so the needs are as written and need no
    copy; ``id`` cannot be extended, so the ids name the same needs afterwards. Nothing
    is logged (the location only feeds that logging): the filter is evaluated again
    when the extend is applied, and reports its errors there, once.

    :return: The ids, or ``None`` if the filter cannot be evaluated.
    """
    with suppress_logging():
        try:
            found_needs = filter_needs_mutable(
                all_needs,
                needs_config,
                needextend["filter"],
                location=(needextend["docname"], needextend["lineno"]),
                origin_docname=needextend["docname"],
            )
        except Exception:
            return None
    return frozenset(need["id"] for need in found_needs)


def _match_order_message(now: Collection[str], as_written: Collection[str]) -> str:
    """Return the ``needs.needextend_match_order`` message for one extend.

    :param now: The ids the filter matches after the earlier extends.
    :param as_written: The ids it matches against the needs as written.
    """
    return (
        "the needs matched by this needextend depend on modifications applied by "
        "earlier needextend directives: it matches "
        f"{counted_ids(now, ' need' if len(now) == 1 else ' needs')} now and "
        f"{counted_ids(as_written)} against the needs as written; from the next "
        "release filters are evaluated against the needs as written, before any "
        "needextend is applied"
    )
