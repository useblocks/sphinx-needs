from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from sphinx_needs.functions.functions import DynamicFunctionParsed


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
    allow_variant: bool = False
    default: None | DynamicFunctionParsed | Any = None
    # TODO predicate defaults
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
        if not isinstance(self.allow_variant, bool):
            raise ValueError("allow_variant must be a boolean.")
        if self.type != "array" and self.item_type is not None:
            raise ValueError("item_type can only be set for array fields.")
        if self.type == "array" and self.item_type is None:
            raise ValueError("item_type must be set for array fields.")
        if self.type == "array" and self.allow_variant:
            raise ValueError("array fields cannot be variant.")
        if not isinstance(
            self.default, None | DynamicFunctionParsed
        ) and not self.type_check(self.default):
            raise ValueError("default value is not of the correct type.")

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
        if not isinstance(self.default, None | DynamicFunctionParsed):
            schema["default"] = self.default
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
    ) -> FieldValue | DynamicFunctionParsed | DynamicFunctionArray:
        """Convert a string to the correct type for this field.

        :raises TypeError: if value is not a string
        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        """
        if not isinstance(value, str):
            raise TypeError(f"Value '{value}' is not a string.")
        match self.type:
            case "string":
                if self.allow_dynamic_functions and "[[" in value:
                    lst: list[str | DynamicFunctionParsed] = []
                    while value:
                        start = value.find("[[")
                        if start == -1:
                            if value:
                                lst.append(value)
                            break
                        if value[:start]:
                            lst.append(value[:start])
                        end = value.find("]]", start + 2)
                        if end == -1:
                            # TODO warn about unclosed dynamic function
                            df = DynamicFunctionParsed.from_string(value[start + 2 :])
                            value = ""
                        else:
                            df = DynamicFunctionParsed.from_string(
                                value[start + 2 : end]
                            )
                            value = value[end + 2 :]
                        lst.append(df)
                    if len(lst) == 1 and isinstance(lst[0], DynamicFunctionParsed):
                        return lst[0]
                    else:
                        return DynamicFunctionArray(tuple(lst))
                # TODO handle variant options
                return FieldValue(_from_string_item(value, self.type))
            case "boolean" | "integer" | "number":
                if (
                    self.allow_dynamic_functions
                    and value.lstrip().startswith("[[")
                    and value.rstrip().endswith("]]")
                ):
                    return DynamicFunctionParsed.from_string(value.strip()[2:-2])
                # TODO handle variant options
                return FieldValue(_from_string_item(value, self.type))
            case "array":
                if self.item_type is None:
                    raise RuntimeError("Array field has no item type defined.")
                if self.allow_dynamic_functions:
                    dynamic_funcs = False
                    array: list[str | bool | int | float | DynamicFunctionParsed] = []
                    for parsed in _split_list_with_dyn_funcs(value):
                        if len(parsed) != 1:
                            raise ValueError(
                                "only one dynamic function allowed per array item."
                            )
                        # TODO warn on unclosed dynamic function
                        item, is_df, _unclosed = parsed[0]
                        if is_df:
                            dynamic_funcs = True
                            array.append(DynamicFunctionParsed.from_string(item))
                        else:
                            array.append(_from_string_item(item, self.item_type))
                    if dynamic_funcs:
                        return DynamicFunctionArray(tuple(array))  # type: ignore[arg-type]
                    else:
                        return FieldValue(array)  # type: ignore[arg-type]
                else:
                    return FieldValue(
                        [  # type: ignore[arg-type]
                            _from_string_item(
                                item.strip(), self.item_type, f" (item {i})"
                            )
                            for i, item in enumerate(re.split(";|,", value))
                            if item.strip()
                        ]
                    )
            case other:
                raise RuntimeError(f"Unknown field type '{other}'.")


@dataclass(frozen=True, slots=True)
class FieldValue:
    value: str | bool | int | float | list[str] | list[bool] | list[int] | list[float]


@dataclass(frozen=True, slots=True)
class DynamicFunctionArray:
    value: (
        tuple[DynamicFunctionParsed | str, ...]
        | tuple[DynamicFunctionParsed | bool, ...]
        | tuple[DynamicFunctionParsed | int, ...]
        | tuple[DynamicFunctionParsed | float, ...]
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


def _split_list_with_dyn_funcs(
    text: str,
) -> Iterator[list[tuple[str, bool, bool]]]:
    """Split a ``;|,`` delimited string that may contain ``[[...]]`` dynamic functions.

    :param text: The string to split.

    :yields: A tuple of the string and a boolean indicating if the string contains one or more dynamic functions, and if there is an unclosed dynamic function.
        Each string is stripped of leading and trailing whitespace,
        and only yielded if it is not empty.

    """
    _current_element = ""
    _current_elements = []
    while text:
        if text.startswith("[["):
            if el := _current_element.strip():
                _current_elements.append((el, False, False))
            _current_element = ""
            text = text[2:]
            while text and not text.startswith("]]"):
                _current_element += text[0]
                text = text[1:]
            if _current_element.endswith("]"):
                _current_element = _current_element[:-1]
            _current_elements.append(
                (_current_element, True, not text.startswith("]]"))
            )
            _current_element = ""
            text = text[2:]
        elif text[0] in ";|,":
            if el := _current_element.strip():
                _current_elements.append((el, False, False))
            if _current_elements:
                yield _current_elements
            _current_element = ""
            _current_elements = []
            text = text[1:]
        else:
            _current_element += text[0]
            text = text[1:]

    if el := _current_element.strip():
        _current_elements.append((el, False, False))
    if _current_elements:
        yield _current_elements
