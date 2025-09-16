from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.variants import VariantFunctionParsed


@dataclass(frozen=True, kw_only=True, slots=True)
class FieldSchema:
    """Schema for a single field.

    :raises ValueError: if any of the parameters are invalid
    """

    name: str
    description: str = ""
    type: Literal["string", "boolean", "integer", "number", "array"]
    item_type: None | Literal["string", "boolean", "integer", "number"]
    nullable: bool = False
    allow_dynamic_functions: bool = False
    allow_extend: bool = False
    allow_variant_functions: bool = False
    allow_defaults: bool = True
    default: (
        None
        | FieldValue
        | DynamicFunctionParsed
        | VariantFunctionParsed
        | FunctionArray
    ) = None
    # TODO predicate defaults (and check against allow_defaults)
    directive_option: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        if self.type not in ("string", "boolean", "integer", "number", "array"):
            raise ValueError(
                "type must be one of 'string', 'boolean', 'integer', 'number', 'array'."
            )
        if self.item_type is not None and self.item_type not in (
            "string",
            "boolean",
            "integer",
            "number",
        ):
            raise ValueError(
                "item_type must be one of 'string', 'boolean', 'integer', 'number'."
            )
        if not isinstance(self.nullable, bool):
            raise ValueError("nullable must be a boolean.")
        if not isinstance(self.allow_dynamic_functions, bool):
            raise ValueError("allow_dynamic_functions must be a boolean.")
        if not isinstance(self.allow_extend, bool):
            raise ValueError("allow_extend must be a boolean.")
        if not isinstance(self.allow_variant_functions, bool):
            raise ValueError("allow_variant must be a boolean.")
        if not isinstance(self.allow_defaults, bool):
            raise ValueError("allow_defaults must be a boolean.")
        if self.type != "array" and self.item_type is not None:
            raise ValueError("item_type can only be set for array fields.")
        if self.type == "array" and self.item_type is None:
            raise ValueError("item_type must be set for array fields.")
        if not self.allow_defaults and self.default is not None:
            raise ValueError("default cannot be set if allow_defaults is False.")
        if not isinstance(
            self.default,
            None
            | FieldValue
            | DynamicFunctionParsed
            | VariantFunctionParsed
            | FunctionArray,
        ):
            raise ValueError("default value is not of the correct type.")
            # TODO also check FieldValue contents?

    def json_schema(self) -> dict[str, Any]:
        """Return a JSON schema representation of this field."""
        schema: dict[str, Any] = {}
        if self.nullable:
            schema["type"] = [self.type, "null"]
        else:
            schema["type"] = self.type
        if self.type == "array" and self.item_type is not None:
            schema["items"] = {"type": self.item_type}
        if self.description:
            schema["description"] = self.description
        if isinstance(self.default, FieldValue):
            schema["default"] = self.default.value
        elif self.nullable:
            schema["default"] = None
        return schema

    def type_check(self, value: Any) -> bool:
        """Check if a value is of the correct type for this field."""
        if self.nullable and value is None:
            return True
        match self.type:
            case "string":
                return isinstance(value, str)
            case "boolean":
                return isinstance(value, bool)
            case "integer":
                return isinstance(value, int)
            case "number":
                return isinstance(value, int | float)
            case "array":
                if not isinstance(value, list | tuple):
                    return False
                if self.item_type is None:
                    return False
                match self.item_type:
                    case "string":
                        return all(isinstance(item, str) for item in value)
                    case "boolean":
                        return all(isinstance(item, bool) for item in value)
                    case "integer":
                        return all(isinstance(item, int) for item in value)
                    case "number":
                        return all(isinstance(item, int | float) for item in value)
                    case other:
                        raise RuntimeError(f"Unknown item type '{other}'.")
            case other:
                raise RuntimeError(f"Unknown field type '{other}'.")

    def convert_directive_option(
        self, value: str
    ) -> FieldValue | DynamicFunctionParsed | VariantFunctionParsed | FunctionArray:
        """Convert a string to the correct type for this field.

        :raises TypeError: if value is not a string
        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        :raises VariantParsingException: if a variant function is malformed
        """
        if not isinstance(value, str):
            raise TypeError(f"Value '{value}' is not a string.")
        match self.type:
            case "boolean" | "integer" | "number":
                if (
                    self.allow_dynamic_functions
                    and value.lstrip().startswith("[[")
                    and value.rstrip().endswith("]]")
                ):
                    return DynamicFunctionParsed.from_string(value.strip()[2:-2])
                elif (
                    self.allow_variant_functions
                    and value.lstrip().startswith("<<")
                    and value.rstrip().endswith(">>")
                ):
                    return VariantFunctionParsed.from_string(value.strip()[2:-2])
                else:
                    return FieldValue(_from_string_item(value, self.type))
            case "string":
                parsed_items = _split_string(
                    value, self.allow_dynamic_functions, self.allow_variant_functions
                )
                if len(parsed_items) == 1 and parsed_items[0][1] == ListItemType.STD:
                    return FieldValue(parsed_items[0][0])
                result: list[DynamicFunctionParsed | VariantFunctionParsed | str] = []
                for item, item_type in parsed_items:
                    match item_type:
                        case ListItemType.STD:
                            result.append(item)
                        case ListItemType.DF | ListItemType.DF_U:
                            # TODO warn on unclosed dynamic function
                            result.append(DynamicFunctionParsed.from_string(item))
                        case ListItemType.VF | ListItemType.VF_U:
                            # TODO warn on unclosed variant function
                            result.append(VariantFunctionParsed.from_string(item))
                return FunctionArray(tuple(result))
            case "array":
                if self.item_type is None:
                    raise RuntimeError("Array field has no item type defined.")

                has_df_or_vf = False
                array: list[
                    str
                    | bool
                    | int
                    | float
                    | DynamicFunctionParsed
                    | VariantFunctionParsed
                ] = []
                for parsed in _split_list(
                    value, self.allow_dynamic_functions, self.allow_variant_functions
                ):
                    if len(parsed) != 1:
                        raise ValueError(
                            "only one string, dynamic function or variant function allowed per array item."
                        )
                    item, item_type = parsed[0]
                    match item_type:
                        case ListItemType.STD:
                            array.append(_from_string_item(item, self.item_type))
                        case ListItemType.DF | ListItemType.DF_U:
                            # TODO warn on unclosed dynamic function
                            has_df_or_vf = True
                            array.append(DynamicFunctionParsed.from_string(item))
                        case ListItemType.VF | ListItemType.VF_U:
                            # TODO warn on unclosed variant function
                            has_df_or_vf = True
                            array.append(VariantFunctionParsed.from_string(item))

                if has_df_or_vf:
                    return FunctionArray(tuple(array))  # type: ignore[arg-type]
                else:
                    return FieldValue(array)  # type: ignore[arg-type]
            case other:
                raise RuntimeError(f"Unknown field type '{other}'.")


@dataclass(frozen=True, slots=True)
class FieldValue:
    value: str | bool | int | float | list[str] | list[bool] | list[int] | list[float]


@dataclass(frozen=True, slots=True)
class FunctionArray:
    value: (
        tuple[DynamicFunctionParsed | VariantFunctionParsed | str, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | bool, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | int, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | float, ...]
    )


@lru_cache(maxsize=128)
def _from_string_item(
    value: str,
    item_type: Literal["string", "boolean", "integer", "number"],
    prefix: str = "",
) -> str | bool | int | float:
    """Convert a string to the given type.

    :raises ValueError: if value cannot be converted to the correct type
    """
    match item_type:
        case "string":
            return value
        case "boolean":
            if value.lower() in ("", "true", "yes"):
                return True
            if value.lower() in ("false", "no"):
                return False
            raise ValueError(f"Cannot convert {value!r} to boolean{prefix}")
        case "integer":
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(
                    f"Cannot convert {value!r}  to integer{prefix}"
                ) from exc
        case "number":
            try:
                return float(value)
            except ValueError as exc:
                raise ValueError(f"Cannot convert {value!r}  to float{prefix}") from exc
        case _:
            raise RuntimeError(f"Unknown item type {item_type!r}{prefix}")


@dataclass(frozen=True, kw_only=True, slots=True)
class LinkSchema:
    """Schema for a single link field."""


class FieldsSchema:
    """A schema for the fields of a single need."""

    __slots__ = ("_core_fields", "_extra_fields", "_link_fields")

    def __init__(self) -> None:
        self._core_fields: dict[str, FieldSchema] = {}
        self._extra_fields: dict[str, FieldSchema] = {}
        self._link_fields: dict[str, LinkSchema] = {}

    def __repr__(self) -> str:
        return (
            f"Schema(core={list(self._core_fields.values())}, "
            f"extra={list(self._extra_fields.values())}, "
            f"link={list(self._link_fields.values())})"
        )

    def add_extra_field(self, field: FieldSchema) -> None:
        """Add an extra field to the schema.

        :raises ValueError: if a field with the same name already exists
        """
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._extra_fields[field.name] = field


class ListItemType(enum.Enum):
    STD = "std"
    DF = "df"
    DF_U = "df_unclosed"
    VF = "vf"
    VF_U = "vf_unclosed"


def _split_list(
    text: str,
    allow_dynamic_functions: bool,
    allow_variant_functions: bool,
    allow_delimiters: bool = True,
) -> Iterator[list[tuple[str, ListItemType]]]:
    """Split a ``;|,`` delimited string that may contain ``[[...]]`` dynamic functions or ``<<...>>`` variant functions.

    :param text: The string to split.

    :yields: A list of tuples.
        Each tuple contains the string (unparsed), an enum of the type.
        Each string is stripped of leading (if at start of item) and trailing (if at end of item) whitespace,
        and only yielded if it is not empty.

    """
    _current_element = ""
    _current_elements: list[tuple[str, ListItemType]] = []
    while text:
        if allow_dynamic_functions and text.startswith("[["):
            if not _current_elements:
                _current_element = _current_element.lstrip()
            if _current_element:
                _current_elements.append((_current_element, ListItemType.STD))
            _current_element = ""
            text = text[2:]
            while text and not text.startswith("]]"):
                _current_element += text[0]
                text = text[1:]
            if _current_element.endswith("]"):
                _current_element = _current_element[:-1]
            _current_elements.append(
                (
                    _current_element,
                    ListItemType.DF if text.startswith("]]") else ListItemType.DF_U,
                )
            )
            _current_element = ""
            text = text[2:]
        elif allow_variant_functions and text.startswith("<<"):
            if not _current_elements:
                _current_element = _current_element.lstrip()
            if _current_element:
                _current_elements.append((_current_element, ListItemType.STD))
            _current_element = ""
            text = text[2:]
            while text and not text.startswith(">>"):
                _current_element += text[0]
                text = text[1:]
            if _current_element.endswith(">"):
                _current_element = _current_element[:-1]
            _current_elements.append(
                (
                    _current_element,
                    ListItemType.VF if text.startswith(">>") else ListItemType.VF_U,
                )
            )
            _current_element = ""
            text = text[2:]
        elif allow_delimiters and text[0] in ";|,":
            if not _current_elements:
                _current_element = _current_element.lstrip()
            if el := _current_element.rstrip():
                _current_elements.append((el, ListItemType.STD))
            if _current_elements:
                yield _current_elements
            _current_element = ""
            _current_elements = []
            text = text[1:]
        else:
            _current_element += text[0]
            text = text[1:]

    if not _current_elements:
        _current_element = _current_element.lstrip()
    if el := _current_element.rstrip():
        _current_elements.append((el, ListItemType.STD))
    if _current_elements:
        yield _current_elements


def _split_string(
    text: str, allow_dynamic_functions: bool, allow_variant_functions: bool
) -> list[tuple[str, ListItemType]]:
    """Split a string that may contain ``[[...]]`` dynamic functions or ``<<...>>`` variant functions.

    :param text: The string to split.

    :returns: A list of tuples.
        Each tuple contains the string (unparsed), an enum of the type.
        and only yielded if it is not empty.
    """
    if not (stripped := text.strip()) or not (
        allow_dynamic_functions or allow_variant_functions
    ):
        return [(stripped, ListItemType.STD)]
    return next(
        iter(
            _split_list(
                text,
                allow_dynamic_functions,
                allow_variant_functions,
                allow_delimiters=False,
            )
        )
    )
