from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache, partial
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeVar, cast

import jsonschema_rs

from sphinx_needs.config import NeedFields
from sphinx_needs.exceptions import VariantParsingException
from sphinx_needs.schema.config import (
    ExtraLinkSchemaType,
    ExtraOptionBooleanSchemaType,
    ExtraOptionIntegerSchemaType,
    ExtraOptionMultiValueSchemaType,
    ExtraOptionNumberSchemaType,
    ExtraOptionSchemaTypes,
    ExtraOptionStringSchemaType,
    validate_extra_link_schema_type,
    validate_extra_option_schema,
)
from sphinx_needs.schema.core import validate_object_schema_compiles
from sphinx_needs.variants import VariantFunctionParsed

if TYPE_CHECKING:
    from sphinx_needs.functions.functions import DynamicFunctionParsed


@dataclass(frozen=True, kw_only=True, slots=True)
class FieldSchema:
    """Schema for a single field.

    :raises ValueError: if any of the parameters are invalid
    """

    name: str
    description: str = ""
    schema: ExtraOptionSchemaTypes
    nullable: bool = False
    directive_option: bool = False
    parse_dynamic_functions: bool = False
    parse_variants: bool = False
    allow_defaults: bool = False
    allow_extend: bool = False
    predicate_defaults: tuple[
        tuple[str, FieldLiteralValue | FieldFunctionArray],
        ...,
    ] = ()
    """List of (need filter, value) pairs for default predicate values.

    Used if the field has not been specifically set.

    The value from the first matching filter will be used, if any.
    """
    default: None | FieldLiteralValue | FieldFunctionArray = None
    """ The default value for this field.
    
    Used if the field has not been specifically set, and no predicate matches.
    """

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        try:
            validate_extra_option_schema(self.schema)
        except TypeError as exc:
            raise ValueError(f"Invalid schema: {exc}") from exc
        try:
            validate_object_schema_compiles({"properties": {self.name: self.schema}})
        except jsonschema_rs.ValidationError as exc:
            raise ValueError(f"Invalid schema: {exc}") from exc
        if not isinstance(self.nullable, bool):
            raise ValueError("nullable must be a boolean.")
        if not isinstance(self.parse_dynamic_functions, bool):
            raise ValueError("parse_dynamic_functions must be a boolean.")
        if not isinstance(self.allow_extend, bool):
            raise ValueError("allow_extend must be a boolean.")
        if not isinstance(self.parse_variants, bool):
            raise ValueError("allow_variant must be a boolean.")
        if not isinstance(self.allow_defaults, bool):
            raise ValueError("allow_defaults must be a boolean.")
        if not isinstance(self.directive_option, bool):
            raise ValueError("directive_option must be a boolean.")
        if not isinstance(self.predicate_defaults, tuple) or not all(
            isinstance(pair, tuple)
            and len(pair) == 2
            and isinstance(pair[0], str)
            and (isinstance(pair[1], FieldLiteralValue) | FieldFunctionArray)
            for pair in self.predicate_defaults
        ):
            raise ValueError(
                "predicate_defaults must be a list of (filter, value) pairs."
            )
        if self.default is not None and not isinstance(
            self.default, FieldLiteralValue | FieldFunctionArray
        ):
            raise ValueError(
                "default must be of type FieldLiteralValue or FieldFunctionArray."
            )
        if self.default is not None and not self.allow_defaults:
            raise ValueError("Defaults are not allowed for this field.")

    @property
    def type(self) -> Literal["string", "boolean", "integer", "number", "array"]:
        return self.schema["type"]

    @property
    def item_type(self) -> None | Literal["string", "boolean", "integer", "number"]:
        if self.schema["type"] == "array":
            return self.schema["items"]["type"]
        return None

    def _set_default(self, value: Any, *, allow_coercion: bool) -> None:
        """Set the default value for this field.

        :param value: The default value to set.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :raises ValueError: if defaults are not allowed or value is of the wrong type
        """

        if not self.allow_defaults:
            raise ValueError("Defaults are not allowed for this field.")
        from sphinx_needs.exceptions import FunctionParsingException

        try:
            default = self.convert_or_type_check(value, allow_coercion=allow_coercion)
        except ValueError:
            raise
        except FunctionParsingException as exc:
            raise ValueError(str(exc)) from exc
        except VariantParsingException as exc:
            raise ValueError(str(exc)) from exc

        object.__setattr__(self, "default", default)

    def _set_predicate_defaults(
        self,
        defaults: list[
            tuple[
                str,
                AllowedTypes,
            ]
        ],
        *,
        allow_coercion: bool,
    ) -> None:
        """Set the predicate defaults for this field.

        :param defaults: The list of (need filter, value) pairs to set.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :raises ValueError: if defaults are not allowed or any value is of the wrong type
        """
        if not self.allow_defaults:
            raise ValueError("Defaults are not allowed for this field.")
        if not isinstance(defaults, Sequence):
            raise ValueError("defaults must be a list of (filter, value) pairs.")
        result: list[tuple[str, FieldLiteralValue | FieldFunctionArray]] = []
        for filter_value in defaults:
            if not isinstance(filter_value, Sequence) or len(filter_value) != 2:
                raise ValueError("defaults must be a list of (filter, value) pairs.")
            filter_, value = filter_value
            if not isinstance(filter_, str) or not filter_:
                raise ValueError("Filter must be a non-empty string.")
            from sphinx_needs.exceptions import FunctionParsingException

            try:
                converted_value = self.convert_or_type_check(
                    value, allow_coercion=allow_coercion
                )
            except ValueError:
                raise
            except (FunctionParsingException, VariantParsingException) as exc:
                raise ValueError(str(exc)) from exc
            if converted_value is not None:
                result.append((filter_, converted_value))

        object.__setattr__(self, "predicate_defaults", tuple(result))

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
        if isinstance(self.default, FieldLiteralValue):
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
                if not isinstance(value, list):
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

    def type_check_item(self, value: Any) -> bool:
        """Check if a value is of the correct item type for this field.

        For 'array' field types, this checks against the item_type.
        For other fields, returns False.
        """
        if self.type != "array" or self.item_type is None:
            return False
        match self.item_type:
            case "string":
                return isinstance(value, str)
            case "boolean":
                return isinstance(value, bool)
            case "integer":
                return isinstance(value, int)
            case "number":
                return isinstance(value, int | float)
            case other:
                raise RuntimeError(f"Unknown item type '{other}'.")

    def convert_directive_option(
        self, value: str
    ) -> FieldLiteralValue | FieldFunctionArray:
        """Convert a string to the correct type for this field.

        :raises TypeError: if value is not a string
        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        :raises VariantParsingException: if a variant function is malformed
        """
        from sphinx_needs.functions.functions import DynamicFunctionParsed

        if not isinstance(value, str):
            raise TypeError(f"Value '{value}' is not a string.")
        match self.type:
            case "boolean" | "integer" | "number":
                if (
                    self.parse_dynamic_functions
                    and value.lstrip().startswith("[[")
                    and value.rstrip().endswith("]]")
                ):
                    return FieldFunctionArray(
                        (DynamicFunctionParsed.from_string(value.strip()[2:-2]),)
                    )
                elif (
                    self.parse_variants
                    and value.lstrip().startswith("<<")
                    and value.rstrip().endswith(">>")
                ):
                    return FieldFunctionArray(
                        (
                            VariantFunctionParsed.from_string(
                                value.strip()[2:-2],
                                partial(_from_string_item, item_type=self.type),
                            ),
                        )
                    )
                else:
                    return FieldLiteralValue(_from_string_item(value, self.type))
            case "string":
                parsed_items = _split_string(
                    value, self.parse_dynamic_functions, self.parse_variants
                )
                if len(parsed_items) == 1 and parsed_items[0][1] == ListItemType.STD:
                    return FieldLiteralValue(parsed_items[0][0])
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
                return FieldFunctionArray(tuple(result))
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
                    value, self.parse_dynamic_functions, self.parse_variants
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
                            array.append(
                                VariantFunctionParsed.from_string(
                                    item,
                                    partial(
                                        _from_string_item, item_type=self.item_type
                                    ),
                                )
                            )

                if has_df_or_vf:
                    return FieldFunctionArray(tuple(array))  # type: ignore[arg-type]
                else:
                    return FieldLiteralValue(array)  # type: ignore[arg-type]
            case other:
                raise RuntimeError(f"Unknown field type '{other}'.")

    def convert_or_type_check(
        self, value: Any, *, allow_coercion: bool
    ) -> None | FieldLiteralValue | FieldFunctionArray:
        """Convert a value to the correct type for this field, or check if it is of the correct type.

        :param value: The value to convert or check.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :returns: True if the value is of the correct type, False otherwise.

        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        :raises VariantParsingException: if a variant function is malformed
        """
        if allow_coercion and isinstance(value, str):
            return self.convert_directive_option(value)
        else:
            if not self.type_check(value):
                raise ValueError(f"Invalid value for field {self.name!r}: {value!r}")
            if value is None:
                return None
            if (
                allow_coercion
                and (self.parse_dynamic_functions or self.parse_variants)
                and self.type == "array"
                and self.item_type == "string"
            ):
                # TODO perhaps should also allow for other item types? (would need to do before type checking)
                from sphinx_needs.functions.functions import DynamicFunctionParsed

                new_value: list[
                    str | DynamicFunctionParsed | VariantFunctionParsed
                ] = []
                has_function = False
                item: str
                for item in value:
                    if (
                        self.parse_dynamic_functions
                        and item.lstrip().startswith("[[")
                        and item.rstrip().endswith("]]")
                    ):
                        has_function = True
                        new_value.append(
                            DynamicFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    elif (
                        self.parse_variants
                        and item.lstrip().startswith("<<")
                        and item.rstrip().endswith(">>")
                    ):
                        has_function = True
                        new_value.append(
                            VariantFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    else:
                        new_value.append(item)
                if has_function:
                    return FieldFunctionArray(tuple(new_value))
                else:
                    return FieldLiteralValue(value)

            return FieldLiteralValue(value)


AllowedTypes: TypeAlias = (
    str | bool | int | float | list[str] | list[bool] | list[int] | list[float]
)
"""
Type alias for all allowed types in need fields.

This includes scalar types (str, bool, int, float) and their corresponding list types.
"""


@dataclass(frozen=True, slots=True)
class FieldLiteralValue:
    value: AllowedTypes


@dataclass(frozen=True, slots=True)
class LinksLiteralValue:
    value: list[str]


@dataclass(frozen=True, slots=True)
class FieldFunctionArray:
    value: (
        tuple[DynamicFunctionParsed | VariantFunctionParsed | str, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | bool, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | int, ...]
        | tuple[DynamicFunctionParsed | VariantFunctionParsed | float, ...]
    )

    def __iter__(
        self,
    ) -> Iterator[
        DynamicFunctionParsed | VariantFunctionParsed | str | bool | int | float
    ]:
        return iter(self.value)


_ValueType = TypeVar("_ValueType", str, bool, int, float)


@dataclass(frozen=True, slots=True)
class FunctionArrayTyped(Generic[_ValueType]):
    value: tuple[DynamicFunctionParsed | VariantFunctionParsed | _ValueType, ...]

    def __iter__(
        self,
    ) -> Iterator[DynamicFunctionParsed | VariantFunctionParsed | _ValueType]:
        return iter(self.value)


@dataclass(frozen=True, slots=True)
class LinksFunctionArray:
    value: tuple[str | DynamicFunctionParsed | VariantFunctionParsed, ...]


@lru_cache(maxsize=128)
def _from_string_item(
    value: str,
    item_type: Literal["string", "boolean", "integer", "number"],
    prefix: str = "",
) -> str | bool | int | float:
    """Convert a string to the given type.

    :raises ValueError: if value cannot be converted to the correct type
    """
    # TODO(mh) no caller passes prefix - it is not used as a prefix below
    match item_type:
        case "string":
            return value
        case "boolean":
            if value.lower() in ("", "true", "yes", "y", "on", "1"):
                return True
            if value.lower() in ("false", "no", "n", "off", "0"):
                return False
            raise ValueError(f"Cannot convert {value!r} to boolean{prefix}")
        case "integer":
            if value == "":
                return 0
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(
                    f"Cannot convert {value!r} to integer{prefix}"
                ) from exc
        case "number":
            if value == "":
                return 0.0
            try:
                return float(value)
            except ValueError as exc:
                raise ValueError(f"Cannot convert {value!r} to float{prefix}") from exc
        case _:
            raise RuntimeError(f"Unknown item type {item_type!r}{prefix}")


@dataclass(frozen=True, kw_only=True, slots=True)
class LinkSchema:
    """Schema for a single link field."""

    name: str
    description: str = ""
    schema: ExtraLinkSchemaType
    directive_option: bool = False
    allow_extend: bool = False
    parse_dynamic_functions: bool = False
    parse_variants: bool = False
    allow_defaults: bool = False
    predicate_defaults: tuple[
        tuple[str, LinksLiteralValue | LinksFunctionArray],
        ...,
    ] = ()
    """List of (need filter, value) pairs for default predicate values.

    Used if the field has not been specifically set.

    The value from the first matching filter will be used, if any.
    """
    default: None | LinksLiteralValue | LinksFunctionArray = None
    """ The default value for this field.
    
    Used if the field has not been specifically set, and no predicate matches.
    """

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        try:
            validate_extra_link_schema_type(self.schema)
        except TypeError as exc:
            raise ValueError(f"Invalid schema: {exc}") from exc
        try:
            validate_object_schema_compiles({"properties": {self.name: self.schema}})
        except jsonschema_rs.ValidationError as exc:
            raise ValueError(f"Invalid schema: {exc}") from exc
        if not isinstance(self.parse_dynamic_functions, bool):
            raise ValueError("parse_dynamic_functions must be a boolean.")
        if not isinstance(self.parse_variants, bool):
            raise ValueError("parse_variants must be a boolean.")
        if not isinstance(self.allow_defaults, bool):
            raise ValueError("allow_defaults must be a boolean.")
        if not isinstance(self.allow_extend, bool):
            raise ValueError("allow_extend must be a boolean.")
        if not isinstance(self.directive_option, bool):
            raise ValueError("directive_option must be a boolean.")
        if not isinstance(self.predicate_defaults, tuple) or not all(
            isinstance(pair, tuple) and len(pair) == 2
            for pair in self.predicate_defaults
        ):
            raise ValueError(
                "predicate_defaults must be a list of (filter, value) pairs."
            )
        if self.default is not None and not isinstance(
            self.default, LinksLiteralValue | LinksFunctionArray
        ):
            raise ValueError(
                "default must be of type LinksLiteralValue or LinksFunctionArray."
            )

    @property
    def type(self) -> Literal["array"]:
        return "array"

    @property
    def item_type(self) -> Literal["string"]:
        return "string"

    @property
    def nullable(self) -> Literal[False]:
        return False

    def _set_default(self, value: Any, *, allow_coercion: bool) -> None:
        """Set the default value for this field.

        :param value: The default value to set.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :raises ValueError: if defaults are not allowed or value is of the wrong type
        """
        if not self.allow_defaults:
            raise ValueError("Defaults are not allowed for this field.")
        from sphinx_needs.exceptions import FunctionParsingException

        try:
            default = self.convert_or_type_check(value, allow_coercion=allow_coercion)
        except ValueError:
            raise
        except (FunctionParsingException, VariantParsingException) as exc:
            raise ValueError(str(exc)) from exc

        object.__setattr__(self, "default", default)

    def _set_predicate_defaults(
        self,
        defaults: list[tuple[str, str | list[str]]],
        *,
        allow_coercion: bool,
    ) -> None:
        """Set the predicate defaults for this field.

        :param defaults: The list of (need filter, value) pairs to set.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :raises ValueError: if defaults are not allowed or any value is of the wrong type
        """
        if not self.allow_defaults:
            raise ValueError("Defaults are not allowed for this field.")
        if not isinstance(defaults, Sequence):
            raise ValueError("defaults must be a list of (filter, value) pairs.")
        result: list[tuple[str, LinksLiteralValue | LinksFunctionArray]] = []
        for filter_value in defaults:
            if not isinstance(filter_value, Sequence) or len(filter_value) != 2:
                raise ValueError("defaults must be a list of (filter, value) pairs.")
            filter_, value = filter_value
            if not isinstance(filter_, str) or not filter_:
                raise ValueError("Filter must be a non-empty string.")

            from sphinx_needs.exceptions import FunctionParsingException

            try:
                converted_value = self.convert_or_type_check(
                    value, allow_coercion=allow_coercion
                )
            except ValueError:
                raise
            except (FunctionParsingException, VariantParsingException) as exc:
                raise ValueError(str(exc)) from exc
            result.append((filter_, converted_value))

        object.__setattr__(self, "predicate_defaults", tuple(result))

    def json_schema(self) -> dict[str, Any]:
        """Return a JSON schema representation of this field."""
        schema: dict[str, Any] = {
            "type": "array",
            "items": {"type": "string"},
            "description": f"Link field '{self.name}'",
        }
        if self.description:
            schema["description"] = self.description
        if isinstance(self.default, LinksLiteralValue):
            schema["default"] = self.default.value
        return schema

    def type_check(self, value: Any) -> bool:
        """Check if a value is of the correct type for this field."""
        return isinstance(value, list) and all(isinstance(i, str) for i in value)

    def type_check_item(self, value: Any) -> bool:
        """Check if a value is of the correct item type for this field.

        For 'array' fields, this checks the type of the array items.
        For other fields, this checks the type of the field itself.
        """
        return isinstance(value, str)

    def convert_directive_option(
        self, value: str
    ) -> LinksLiteralValue | LinksFunctionArray:
        """Convert a string to the correct type for this field.

        :raises TypeError: if value is not a string
        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        :raises VariantParsingException: if a variant function is malformed
        """

        if not isinstance(value, str):
            raise TypeError(f"Value '{value}' is not a string.")

        has_df_or_vf = False
        array: list[str | DynamicFunctionParsed | VariantFunctionParsed] = []
        for parsed in _split_list(
            value, self.parse_dynamic_functions, self.parse_variants
        ):
            if len(parsed) != 1:
                raise ValueError(
                    "only one string, dynamic function or variant function allowed per array item."
                )
            item, item_type = parsed[0]
            match item_type:
                case ListItemType.STD:
                    array.append(item)
                case ListItemType.DF | ListItemType.DF_U:
                    from sphinx_needs.functions.functions import DynamicFunctionParsed

                    # TODO warn on unclosed dynamic function
                    has_df_or_vf = True
                    array.append(DynamicFunctionParsed.from_string(item))
                case ListItemType.VF | ListItemType.VF_U:
                    # TODO warn on unclosed variant function
                    has_df_or_vf = True
                    array.append(VariantFunctionParsed.from_string(item))

        if has_df_or_vf:
            return LinksFunctionArray(tuple(array))
        else:
            return LinksLiteralValue(array)  # type: ignore[arg-type]

    def convert_or_type_check(
        self, value: Any, *, allow_coercion: bool
    ) -> LinksLiteralValue | LinksFunctionArray:
        """Convert a value to the correct type for this field, or check if it is of the correct type.

        :param value: The value to convert or check.
        :param allow_coercion: Whether to allow coercion of string values to the correct type.
            This will also allow dynamic and variant functions if the field allows them.

        :returns: True if the value is of the correct type, False otherwise.

        :raises ValueError: if value cannot be converted to the correct type
        :raises FunctionParsingException: if a dynamic function is malformed
        :raises VariantParsingException: if a variant function is malformed
        """
        if allow_coercion and isinstance(value, str):
            return self.convert_directive_option(value)
        else:
            if not self.type_check(value):
                raise ValueError(f"Invalid value for field {self.name!r}: {value!r}")
            if allow_coercion and (self.parse_dynamic_functions or self.parse_variants):
                from sphinx_needs.functions.functions import DynamicFunctionParsed

                new_value: list[
                    str | DynamicFunctionParsed | VariantFunctionParsed
                ] = []
                has_function = False
                item: str
                for item in value:
                    if (
                        self.parse_dynamic_functions
                        and item.lstrip().startswith("[[")
                        and item.rstrip().endswith("]]")
                    ):
                        has_function = True
                        new_value.append(
                            DynamicFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    elif (
                        self.parse_variants
                        and item.lstrip().startswith("<<")
                        and item.rstrip().endswith(">>")
                    ):
                        has_function = True
                        new_value.append(
                            VariantFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    else:
                        new_value.append(item)
                if has_function:
                    return LinksFunctionArray(tuple(new_value))
                else:
                    return LinksLiteralValue(value)
            else:
                return LinksLiteralValue(value)


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

    def add_core_field(self, field: FieldSchema) -> None:
        """Add a core field to the schema.

        :raises ValueError: if a field with the same name already exists
        """
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._core_fields[field.name] = field

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

    def add_link_field(self, field: LinkSchema) -> None:
        """Add a link field to the schema.

        :raises ValueError: if a field with the same name already exists
        """
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._link_fields[field.name] = field

    def get_any_field(self, name: str) -> FieldSchema | LinkSchema | None:
        """Get a field by name."""
        if name in self._core_fields:
            return self._core_fields[name]
        if name in self._extra_fields:
            return self._extra_fields[name]
        if name in self._link_fields:
            return self._link_fields[name]
        return None

    def get_core_field(self, name: str) -> FieldSchema | None:
        """Get a core field by name."""
        return self._core_fields.get(name)

    def get_extra_field(self, name: str) -> FieldSchema | None:
        """Get an extra field by name."""
        return self._extra_fields.get(name)

    def get_link_field(self, name: str) -> LinkSchema | None:
        """Get a link field by name."""
        return self._link_fields.get(name)

    def iter_all_fields(self) -> Iterable[FieldSchema | LinkSchema]:
        """Iterate over all fields in the schema."""
        yield from self._core_fields.values()
        yield from self._extra_fields.values()
        yield from self._link_fields.values()

    def iter_core_field_names(self) -> Iterable[str]:
        """Iterate over all core field names in the schema."""
        yield from self._core_fields.keys()

    def iter_core_fields(self) -> Iterable[FieldSchema]:
        """Iterate over all core fields in the schema."""
        yield from self._core_fields.values()

    def iter_extra_field_names(self) -> Iterable[str]:
        """Iterate over all extra field names in the schema."""
        yield from self._extra_fields.keys()

    def iter_extra_fields(self) -> Iterable[FieldSchema]:
        """Iterate over all extra fields in the schema."""
        yield from self._extra_fields.values()

    def iter_link_field_names(self) -> Iterable[str]:
        """Iterate over all link field names in the schema."""
        yield from self._link_fields.keys()

    def iter_link_fields(self) -> Iterable[LinkSchema]:
        """Iterate over all link fields in the schema."""
        yield from self._link_fields.values()


class ListItemType(enum.Enum):
    STD = "std"
    DF = "df"
    DF_U = "df_unclosed"
    VF = "vf"
    VF_U = "vf_unclosed"


def _split_list(
    text: str,
    parse_dynamic_functions: bool,
    parse_variants: bool,
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
        if parse_dynamic_functions and text.startswith("[["):
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
        elif parse_variants and text.startswith("<<"):
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
    text: str, parse_dynamic_functions: bool, parse_variants: bool
) -> list[tuple[str, ListItemType]]:
    """Split a string that may contain ``[[...]]`` dynamic functions or ``<<...>>`` variant functions.

    :param text: The string to split.

    :returns: A list of tuples.
        Each tuple contains the string (unparsed), an enum of the type.
        and only yielded if it is not empty.
    """
    if not (stripped := text.strip()) or not (
        parse_dynamic_functions or parse_variants
    ):
        return [(stripped, ListItemType.STD)]
    return next(
        iter(
            _split_list(
                text,
                parse_dynamic_functions,
                parse_variants,
                allow_delimiters=False,
            )
        )
    )


def create_inherited_field(
    parent: FieldSchema, child: NeedFields, *, allow_variants: bool
) -> FieldSchema:
    """Create a new FieldSchema by inheriting from a parent FieldSchema and applying overrides from a child dictionary.

    :param parent: The parent FieldSchema to inherit from.
    :param child: A dictionary containing the child field overrides.
    :param allow_variants: Whether to allow parse_variants to be set to True in the child.
        This is a bit of a special case for certain core fields, and maybe should be handled differently in the future;
        fields like ``template`` are used before variants are processed, so allowing variants there would not make sense.
    """
    replacements: dict[str, Any] = {}

    if "description" in child:
        if not isinstance(child["description"], str):
            raise ValueError("Child 'description' must be a string.")
        replacements["description"] = child["description"]

    if "schema" in child:
        child_schema = child["schema"]
        inherit_schema(parent.schema, cast(dict[str, Any], child_schema))
        replacements["schema"] = child_schema

    if "nullable" in child:
        if not isinstance(child["nullable"], bool):
            raise ValueError("Child 'nullable' must be a boolean.")
        if parent.nullable is False and child["nullable"] is True:
            raise ValueError("Cannot change 'nullable' from False to True in child.")
        replacements["nullable"] = child["nullable"]

    if "parse_variants" in child:
        if not isinstance(child["parse_variants"], bool):
            raise ValueError("Child 'parse_variants' must be a boolean.")
        if not allow_variants and child["parse_variants"]:
            raise ValueError("parse_variants is not allowed to be True for this field.")
        replacements["parse_variants"] = child["parse_variants"]

    return replace(parent, **replacements)


def inherit_schema(
    parent_schema: ExtraOptionSchemaTypes, child_schema: dict[str, Any]
) -> None:
    """Inherit and validate constraints from parent schema to child schema.

    Inheritance follows the SysML2 concept of specialization, whereby
    subtypes must be usable wherever the supertype is expected (Liskov substitutability principle).
    Changing the type would violate substitutability (Liskov principle).

    The following override rules apply:

    **General (all types):**

    - The ``type`` of the child must be the same as the parent.
    - For ``array`` type fields, the ``item_type`` of the child must be the same as the parent.

    **String type constraints:**

    - ``const``: Child cannot change the constant value.
    - ``enum``: Child's enum values must be a subset of the parent's enum values.
    - ``pattern``: Child must have the same pattern (cannot be overridden).
    - ``format``: Child must have the same format (cannot be overridden).
    - ``minLength``: Child's minimum length must be ≥ the parent's.
    - ``maxLength``: Child's maximum length must be ≤ the parent's.

    **Boolean type constraints:**

    - ``const``: Child must have the same constant value as the parent.

    **Number and Integer type constraints:**

    - ``const``: Child must have the same constant value as the parent.
    - ``enum``: Child's enum values must be a subset of the parent's enum values.
    - ``minimum``: Child's minimum must be ≥ the parent's.
    - ``maximum``: Child's maximum must be ≤ the parent's.
    - ``exclusiveMinimum``: Child's exclusive minimum must be ≥ the parent's.
    - ``exclusiveMaximum``: Child's exclusive maximum must be ≤ the parent's.
    - ``multipleOf``: Child's multipleOf must be a multiple of the parent's.

    **Array type constraints:**

    - ``minItems``: Child's minimum must be ≥ the parent's.
    - ``maxItems``: Child's maximum must be ≤ the parent's.
    - ``minContains``: Child's minimum must be ≥ the parent's.
    - ``maxContains``: Child's maximum must be ≤ the parent's.
    - ``contains``: Child must match the parent's constraint (cannot be overridden).
    - ``items``: The above rules are applied also to the item schema.

    """
    if not isinstance(child_schema, dict):
        raise ValueError("Child schema must be a dictionary.")

    if "type" not in child_schema:
        child_schema["type"] = parent_schema["type"]

    if parent_schema["type"] == "string" and child_schema["type"] == "string":
        _validate_string_constraints(parent_schema, child_schema)

    elif parent_schema["type"] == "integer" and child_schema["type"] == "integer":  # noqa: SIM114
        _validate_number_or_integer_constraints(parent_schema, child_schema)

    elif parent_schema["type"] == "number" and child_schema["type"] == "number":
        _validate_number_or_integer_constraints(parent_schema, child_schema)

    elif parent_schema["type"] == "boolean" and child_schema["type"] == "boolean":
        _validate_boolean_constraints(parent_schema, child_schema)

    elif parent_schema["type"] == "array" and child_schema["type"] == "array":
        _validate_array_constraints(parent_schema, child_schema)

    else:
        raise ValueError(
            f"Child 'type' {child_schema.get('type')!r} does not match parent 'type' {parent_schema.get('type')!r}."
        )


def _validate_boolean_constraints(
    parent_schema: ExtraOptionBooleanSchemaType, child_schema: dict[str, Any]
) -> None:
    """Validate and merge boolean-specific constraints from parent to child schema.

    :param parent_schema: The parent field's schema dictionary
    :param child_schema: The child field's schema dictionary (will be modified in-place)
    :raises ValueError: if child constraints are invalid relative to parent constraints
    """
    if "const" in parent_schema:
        if "const" in child_schema:
            if child_schema["const"] != parent_schema["const"]:
                raise ValueError(
                    f"Child 'const' value {child_schema['const']!r} does not match parent 'const' value {parent_schema['const']!r}."
                )
        else:
            child_schema["const"] = parent_schema["const"]


def _validate_string_constraints(
    parent_schema: ExtraOptionStringSchemaType, child_schema: dict[str, Any]
) -> None:
    """Validate and merge string-specific constraints from parent to child schema.

    :param parent_schema: The parent field's schema dictionary
    :param child_schema: The child field's schema dictionary (will be modified in-place)
    :raises ValueError: if child constraints are invalid relative to parent constraints
    """
    # Validate const constraint - must be identical
    if "const" in parent_schema:
        if "const" in child_schema:
            if child_schema["const"] != parent_schema["const"]:
                raise ValueError(
                    f"Child 'const' value {child_schema['const']!r} does not match parent 'const' value {parent_schema['const']!r}."
                )
        else:
            child_schema["const"] = parent_schema["const"]

    # Validate enum constraints
    if "enum" in parent_schema:
        if "enum" in child_schema:
            parent_str_enum_set = set(parent_schema["enum"])
            child_str_enum_set = set(child_schema["enum"])
            if not child_str_enum_set.issubset(parent_str_enum_set):
                raise ValueError(
                    f"Child 'enum' values {child_schema['enum']} are not a subset of parent 'enum' values {parent_schema['enum']}."
                )
        else:
            child_schema["enum"] = parent_schema["enum"]

    # Inherit pattern constraint - child cannot override
    if "pattern" in parent_schema:
        if (
            "pattern" in child_schema
            and child_schema["pattern"] != parent_schema["pattern"]
        ):
            raise ValueError(
                f"Child 'pattern' {child_schema['pattern']!r} does not match parent 'pattern' {parent_schema['pattern']!r}. Pattern constraints cannot be overridden."
            )
        child_schema["pattern"] = parent_schema["pattern"]

    # Inherit format constraint - child cannot override
    if "format" in parent_schema:
        if (
            "format" in child_schema
            and child_schema["format"] != parent_schema["format"]
        ):
            raise ValueError(
                f"Child 'format' {child_schema['format']!r} does not match parent 'format' {parent_schema['format']!r}. Format constraints cannot be overridden."
            )
        child_schema["format"] = parent_schema["format"]

    # Validate minLength constraint
    if "minLength" in parent_schema:
        if "minLength" in child_schema:
            if child_schema["minLength"] < parent_schema["minLength"]:
                raise ValueError(
                    f"Child 'minLength' {child_schema['minLength']} is less than parent 'minLength' {parent_schema['minLength']}."
                )
        else:
            child_schema["minLength"] = parent_schema["minLength"]

    # Validate maxLength constraint
    if "maxLength" in parent_schema:
        if "maxLength" in child_schema:
            if child_schema["maxLength"] > parent_schema["maxLength"]:
                raise ValueError(
                    f"Child 'maxLength' {child_schema['maxLength']} is greater than parent 'maxLength' {parent_schema['maxLength']}."
                )
        else:
            child_schema["maxLength"] = parent_schema["maxLength"]


_T = TypeVar("_T", ExtraOptionNumberSchemaType, ExtraOptionIntegerSchemaType)


def _validate_number_or_integer_constraints(
    parent_schema: _T, child_schema: dict[str, Any]
) -> None:
    """Validate and merge number/integer-specific constraints from parent to child schema.

    :param parent_schema: The parent field's schema dictionary
    :param child_schema: The child field's schema dictionary (will be modified in-place)
    :raises ValueError: if child constraints are invalid relative to parent constraints
    """
    # Validate const constraint - must be identical
    if "const" in parent_schema:
        if "const" in child_schema:
            if child_schema["const"] != parent_schema["const"]:
                raise ValueError(
                    f"Child 'const' value {child_schema['const']!r} does not match parent 'const' value {parent_schema['const']!r}."
                )
        else:
            child_schema["const"] = parent_schema["const"]

    # Validate enum constraints
    if "enum" in parent_schema:
        if "enum" in child_schema:
            parent_enum_set = set(parent_schema["enum"])
            child_enum_set = set(child_schema["enum"])
            if not child_enum_set.issubset(parent_enum_set):
                raise ValueError(
                    f"Child 'enum' values {child_schema['enum']} are not a subset of parent 'enum' values {parent_schema['enum']}."
                )
        else:
            child_schema["enum"] = parent_schema["enum"]

    # Validate minimum constraint
    if "minimum" in parent_schema:
        if "minimum" in child_schema:
            if child_schema["minimum"] < parent_schema["minimum"]:
                raise ValueError(
                    f"Child 'minimum' {child_schema['minimum']} is less than parent 'minimum' {parent_schema['minimum']}."
                )
        else:
            child_schema["minimum"] = parent_schema["minimum"]

    # Validate maximum constraint
    if "maximum" in parent_schema:
        if "maximum" in child_schema:
            if child_schema["maximum"] > parent_schema["maximum"]:
                raise ValueError(
                    f"Child 'maximum' {child_schema['maximum']} is greater than parent 'maximum' {parent_schema['maximum']}."
                )
        else:
            child_schema["maximum"] = parent_schema["maximum"]

    # Validate exclusiveMinimum constraint
    if "exclusiveMinimum" in parent_schema:
        if "exclusiveMinimum" in child_schema:
            if child_schema["exclusiveMinimum"] < parent_schema["exclusiveMinimum"]:
                raise ValueError(
                    f"Child 'exclusiveMinimum' {child_schema['exclusiveMinimum']} is less than parent 'exclusiveMinimum' {parent_schema['exclusiveMinimum']}."
                )
        else:
            child_schema["exclusiveMinimum"] = parent_schema["exclusiveMinimum"]

    # Validate exclusiveMaximum constraint
    if "exclusiveMaximum" in parent_schema:
        if "exclusiveMaximum" in child_schema:
            if child_schema["exclusiveMaximum"] > parent_schema["exclusiveMaximum"]:
                raise ValueError(
                    f"Child 'exclusiveMaximum' {child_schema['exclusiveMaximum']} is greater than parent 'exclusiveMaximum' {parent_schema['exclusiveMaximum']}."
                )
        else:
            child_schema["exclusiveMaximum"] = parent_schema["exclusiveMaximum"]

    # Validate multipleOf constraint
    # The child value must be a multiple of the parent's multipleOf
    if "multipleOf" in parent_schema:
        if "multipleOf" in child_schema:
            # Check if child's multipleOf is a multiple of parent's multipleOf
            parent_multiple = parent_schema["multipleOf"]
            child_multiple = child_schema["multipleOf"]
            # For proper constraint narrowing, child should be a multiple of parent
            # e.g., if parent requires multipleOf 2, child can require multipleOf 4, 6, 8, etc.
            if child_multiple % parent_multiple != 0:
                raise ValueError(
                    f"Child 'multipleOf' {child_multiple} must be a multiple of parent 'multipleOf' {parent_multiple}."
                )
        else:
            child_schema["multipleOf"] = parent_schema["multipleOf"]


def _validate_array_constraints(
    parent_schema: ExtraOptionMultiValueSchemaType, child_schema: dict[str, Any]
) -> None:
    """Validate and merge array-specific constraints from parent to child schema.

    :param parent_schema: The parent field's schema dictionary
    :param child_schema: The child field's schema dictionary (will be modified in-place)
    :raises ValueError: if child constraints are invalid relative to parent constraints
    """
    # Validate uniqueItems constraint
    if "uniqueItems" in parent_schema:
        if "uniqueItems" in child_schema:
            if (
                parent_schema["uniqueItems"] is True
                and child_schema["uniqueItems"] is False
            ):
                raise ValueError(
                    "Child 'uniqueItems' constraint cannot be less restrictive than parent."
                )
        else:
            child_schema["uniqueItems"] = parent_schema["uniqueItems"]

    # Validate minItems constraint
    if "minItems" in parent_schema:
        if "minItems" in child_schema:
            if child_schema["minItems"] < parent_schema["minItems"]:
                raise ValueError(
                    f"Child 'minItems' {child_schema['minItems']} is less than parent 'minItems' {parent_schema['minItems']}."
                )
        else:
            child_schema["minItems"] = parent_schema["minItems"]

    # Validate maxItems constraint
    if "maxItems" in parent_schema:
        if "maxItems" in child_schema:
            if child_schema["maxItems"] > parent_schema["maxItems"]:
                raise ValueError(
                    f"Child 'maxItems' {child_schema['maxItems']} is greater than parent 'maxItems' {parent_schema['maxItems']}."
                )
        else:
            child_schema["maxItems"] = parent_schema["maxItems"]

    # Validate minContains constraint
    if "minContains" in parent_schema:
        if "minContains" in child_schema:
            if child_schema["minContains"] < parent_schema["minContains"]:
                raise ValueError(
                    f"Child 'minContains' {child_schema['minContains']} is less than parent 'minContains' {parent_schema['minContains']}."
                )
        else:
            child_schema["minContains"] = parent_schema["minContains"]

    # Validate maxContains constraint
    if "maxContains" in parent_schema:
        if "maxContains" in child_schema:
            if child_schema["maxContains"] > parent_schema["maxContains"]:
                raise ValueError(
                    f"Child 'maxContains' {child_schema['maxContains']} is greater than parent 'maxContains' {parent_schema['maxContains']}."
                )
        else:
            child_schema["maxContains"] = parent_schema["maxContains"]

    # Inherit contains constraint - child cannot override
    if "contains" in parent_schema:
        if (
            "contains" in child_schema
            and child_schema["contains"] != parent_schema["contains"]
        ):
            raise ValueError(
                "Child 'contains' constraint does not match parent 'contains' constraint."
            )
        child_schema["contains"] = parent_schema["contains"]

    if "items" in parent_schema:
        if "items" not in child_schema:
            child_schema["items"] = parent_schema["items"]
        else:
            parent_items = parent_schema["items"]
            child_items = child_schema["items"]

            if not isinstance(child_items, dict):
                raise ValueError("Child 'items' must be a dictionary.")

            if "type" not in child_items:
                child_items["type"] = parent_items["type"]

            try:
                if parent_items["type"] == "string" and child_items["type"] == "string":
                    _validate_string_constraints(parent_items, child_items)

                elif (
                    parent_items["type"] == "integer"
                    and child_items["type"] == "integer"
                ):
                    # type restricted to ExtraOptionIntegerSchemaType
                    _validate_number_or_integer_constraints(parent_items, child_items)

                elif (
                    parent_items["type"] == "number" and child_items["type"] == "number"
                ):
                    # type restricted to ExtraOptionNumberSchemaType
                    _validate_number_or_integer_constraints(parent_items, child_items)

                elif (
                    parent_items["type"] == "boolean"
                    and child_items["type"] == "boolean"
                ):
                    _validate_boolean_constraints(parent_items, child_items)

                else:
                    raise ValueError(
                        f"Child 'type' {child_items.get('type')!r} does not match parent 'type' {parent_items.get('type')!r}."
                    )
            except ValueError as e:
                raise ValueError(f"'items' inheritance: {e}")
