from __future__ import annotations

import enum
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache, partial
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeVar

from sphinx_needs.exceptions import VariantParsingException
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
    type: Literal["string", "boolean", "integer", "number", "array"]
    item_type: None | Literal["string", "boolean", "integer", "number"] = None
    nullable: bool = False
    directive_option: bool = False
    allow_dynamic_functions: bool = False
    allow_variant_functions: bool = False
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
                    self.allow_dynamic_functions
                    and value.lstrip().startswith("[[")
                    and value.rstrip().endswith("]]")
                ):
                    return FieldFunctionArray(
                        (DynamicFunctionParsed.from_string(value.strip()[2:-2]),)
                    )
                elif (
                    self.allow_variant_functions
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
                    value, self.allow_dynamic_functions, self.allow_variant_functions
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
                and (self.allow_dynamic_functions or self.allow_variant_functions)
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
                        self.allow_dynamic_functions
                        and item.lstrip().startswith("[[")
                        and item.rstrip().endswith("]]")
                    ):
                        has_function = True
                        new_value.append(
                            DynamicFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    elif (
                        self.allow_variant_functions
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
    directive_option: bool = False
    allow_extend: bool = False
    allow_dynamic_functions: bool = False
    allow_variant_functions: bool = False
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
        if not isinstance(self.allow_dynamic_functions, bool):
            raise ValueError("allow_dynamic_functions must be a boolean.")
        if not isinstance(self.allow_variant_functions, bool):
            raise ValueError("allow_variant_functions must be a boolean.")
        if not isinstance(self.allow_defaults, bool):
            raise ValueError("allow_defaults must be a boolean.")
        if not isinstance(self.allow_extend, bool):
            raise ValueError("allow_extend must be a boolean.")
        if not isinstance(self.directive_option, bool):
            raise ValueError("directive_option must be a boolean.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
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
            value, self.allow_dynamic_functions, self.allow_variant_functions
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
            if allow_coercion and (
                self.allow_dynamic_functions or self.allow_variant_functions
            ):
                from sphinx_needs.functions.functions import DynamicFunctionParsed

                new_value: list[
                    str | DynamicFunctionParsed | VariantFunctionParsed
                ] = []
                has_function = False
                item: str
                for item in value:
                    if (
                        self.allow_dynamic_functions
                        and item.lstrip().startswith("[[")
                        and item.rstrip().endswith("]]")
                    ):
                        has_function = True
                        new_value.append(
                            DynamicFunctionParsed.from_string(item.strip()[2:-2])
                        )
                    elif (
                        self.allow_variant_functions
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

    def iter_core_fields(self) -> Iterable[FieldSchema]:
        """Iterate over all core fields in the schema."""
        yield from self._core_fields.values()

    def iter_extra_fields(self) -> Iterable[FieldSchema]:
        """Iterate over all extra fields in the schema."""
        yield from self._extra_fields.values()

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
