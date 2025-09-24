from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from docutils import nodes
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import ExtendType, NeedsExtendType, NeedsMutable, SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
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
from sphinx_needs.utils import DummyOptionSpec, add_doc, coerce_to_boolean

logger = get_logger(__name__)


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
                    except ValueError as err:
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
                    except ValueError as err:
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
    """Use data gathered from needextend directives to modify fields of existing needs."""

    current_needextend: NeedsExtendType
    for current_needextend in extends.values():
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
                                (*df.value, *link_value.value)
                            )
                            need[option_name] = []
                        else:
                            need[option_name] = [
                                *need[option_name],
                                *(  # keep unique
                                    v
                                    for v in link_value.value
                                    if v not in need[option_name]
                                ),
                            ]
                    case (ExtendType.APPEND, LinksFunctionArray()):
                        if (df := need._dynamic_fields.get(option_name)) is not None:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (  # keep unique
                                    *df.value,
                                    *(v for v in link_value.value if v not in df.value),
                                )
                            )
                            need[option_name] = []
                        else:
                            need._dynamic_fields[option_name] = LinksFunctionArray(
                                (
                                    *need[option_name],
                                    *(  # keep unique
                                        v
                                        for v in link_value.value
                                        if v not in need[option_name]
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
                                FieldFunctionArray((*df.value, *field_value.value))
                                if isinstance(field_value.value, list)
                                else FieldFunctionArray((*df.value, field_value.value))
                            )
                        else:
                            if isinstance(field_value.value, list):
                                need[option_name] = [
                                    *need[option_name],
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
