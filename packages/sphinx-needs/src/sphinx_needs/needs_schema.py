from __future__ import annotations

import enum
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache, partial
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Generic,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    cast,
    overload,
)

import jsonschema_rs

from sphinx_needs._wording import joined
from sphinx_needs.config import NeedFields
from sphinx_needs.derive import (
    Derive,
    DeriveInvalid,
    DeriveRule,
    is_union,
    typed_empty,
)
from sphinx_needs.exceptions import VariantParsingException
from sphinx_needs.need_item import NeedItem, NeedLink
from sphinx_needs.schema.config import (
    FieldSchemaTypes,
    LinkSchemaType,
    validate_field_schema,
    validate_link_schema_type,
)
from sphinx_needs.schema.core import validate_object_schema_compiles, value_problem
from sphinx_needs.variant_data import VariantDataParsed
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
    schema: FieldSchemaTypes
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
    default: FieldLiteralValue | FieldFunctionArray | None = None
    """ The default value for this field.
    
    Used if the field has not been specifically set, and no predicate matches.
    """
    derive: Derive | None = None
    """The ``derive`` rule computing this field, if it is derived.

    A derived field cannot be set in a need (``directive_option`` is ``False``) or by a
    ``needextend`` (``allow_extend`` is ``False``), and takes no default.
    A :class:`~sphinx_needs.derive.DeriveInvalid` marks a rule that cannot be read:
    the field is closed all the same, and holds its empty value.
    """
    derive_by_type: Mapping[str, Derive] | None = None
    """The rules per need type (``derive_by_type``): need type to rule, each
    overriding ``derive`` on its type, if any.

    The field is derived (closed) on every need type. A need of a type without a rule
    holds :meth:`off_type_value`: with ``derive_by_type`` and no ``derive``, the field
    may carry a literal ``default`` for it (though it allows no other defaults).
    An empty mapping is a field derived on no need type (its ``derive_by_type`` could
    not be read).
    """

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        if self.derive is not None and not isinstance(
            self.derive, DeriveRule | DeriveInvalid
        ):
            raise ValueError("derive must be a DeriveRule or a DeriveInvalid.")
        _check_derive_by_type(self.derive_by_type)
        try:
            validate_field_schema(self.schema)
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
            and isinstance(pair[1], FieldLiteralValue | FieldFunctionArray)
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
        if (
            self.default is not None
            and not self.allow_defaults
            and not self._holds_off_type_default
        ):
            raise ValueError("Defaults are not allowed for this field.")

    @property
    def _holds_off_type_default(self) -> bool:
        """Whether ``default`` is the literal value of the need types without a rule."""
        return (
            self.derive is None
            and self.derive_by_type is not None
            and isinstance(self.default, FieldLiteralValue)
        )

    @property
    def kind(self) -> Literal["field"]:
        """What it declares: a field (a core field or an extra field)."""
        return "field"

    @property
    def derived(self) -> bool:
        """Whether the field is derived: it carries ``derive``, or ``derive_by_type``.

        A derived field is closed on every need type, also on a type without a rule.
        """
        return self.derive is not None or self.derive_by_type is not None

    def rule_for(self, need_type: str) -> Derive | None:
        """The rule computing the field on a need of ``need_type``.

        The type's own ``derive_by_type`` entry, else ``derive``, else ``None``: a need
        of that type holds the field's :meth:`off_type_value`.
        """
        if (
            self.derive_by_type is not None
            and (rule := self.derive_by_type.get(need_type)) is not None
        ):
            return rule
        return self.derive

    def describe_derived(self) -> str:
        """The rules of a derived field, as messages name them: ``kind 'sum'``."""
        return _describe_derived(self.derive, self.derive_by_type)

    def off_type_value(self) -> Any:
        """The value a need holds when its type has no rule (see :meth:`rule_for`).

        The literal ``default``, in the field's type (an integer in a ``number`` field
        is a float); else ``None`` when the field is nullable; else the empty value of
        its type.
        """
        if self._holds_off_type_default:
            assert isinstance(self.default, FieldLiteralValue)
            # imported here, as the functions module imports this one
            from sphinx_needs.functions.functions import _in_field_type

            return _in_field_type(deepcopy(self.default.value), self)
        if self.nullable:
            return None
        return typed_empty(self.type)

    @property
    def type(self) -> Literal["string", "boolean", "integer", "number", "array"]:
        return self.schema["type"]

    @property
    def item_type(self) -> Literal["string", "boolean", "integer", "number"] | None:
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
                        (
                            DynamicFunctionParsed.from_string(
                                value.strip()[2:-2], allow_need=True
                            ),
                        )
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
                elif (
                    self.parse_variants
                    and value.lstrip().startswith("<{")
                    and value.rstrip().endswith("}>")
                ):
                    return FieldFunctionArray(
                        (VariantDataParsed.from_string(value.strip()[2:-2]),)
                    )
                else:
                    return FieldLiteralValue(_from_string_item(value, self.type))
            case "string":
                parsed_items = _split_string(
                    value, self.parse_dynamic_functions, self.parse_variants
                )
                if len(parsed_items) == 1 and parsed_items[0][1] == ListItemType.STD:
                    return FieldLiteralValue(parsed_items[0][0])
                result: list[
                    DynamicFunctionParsed
                    | VariantFunctionParsed
                    | VariantDataParsed
                    | str
                ] = []
                for item, item_type in parsed_items:
                    match item_type:
                        case ListItemType.STD:
                            result.append(item)
                        case ListItemType.DF | ListItemType.DF_U:
                            # TODO warn on unclosed dynamic function
                            result.append(
                                DynamicFunctionParsed.from_string(item, allow_need=True)
                            )
                        case ListItemType.VF | ListItemType.VF_U:
                            # TODO warn on unclosed variant function
                            result.append(VariantFunctionParsed.from_string(item))
                        case ListItemType.VD | ListItemType.VD_U:
                            # TODO warn on unclosed variant data
                            result.append(VariantDataParsed.from_string(item))
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
                    | VariantDataParsed
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
                            array.append(
                                DynamicFunctionParsed.from_string(item, allow_need=True)
                            )
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
                        case ListItemType.VD | ListItemType.VD_U:
                            # TODO warn on unclosed variant data
                            has_df_or_vf = True
                            array.append(VariantDataParsed.from_string(item))

                if has_df_or_vf:
                    return FieldFunctionArray(tuple(array))
                else:
                    return FieldLiteralValue(array)  # ty: ignore[invalid-argument-type]
            case other:
                raise RuntimeError(f"Unknown field type '{other}'.")

    def convert_or_type_check(
        self, value: Any, *, allow_coercion: bool
    ) -> FieldLiteralValue | FieldFunctionArray | None:
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
                    str
                    | DynamicFunctionParsed
                    | VariantFunctionParsed
                    | VariantDataParsed
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
                            DynamicFunctionParsed.from_string(
                                item.strip()[2:-2], allow_need=True
                            )
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
                    elif (
                        self.parse_variants
                        and item.lstrip().startswith("<{")
                        and item.rstrip().endswith("}>")
                    ):
                        has_function = True
                        new_value.append(
                            VariantDataParsed.from_string(item.strip()[2:-2])
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


def _describe_derived(
    derive: Derive | None, derive_by_type: Mapping[str, Derive] | None
) -> str:
    """The rules of a derived field, as messages name them.

    The field's ``derive`` unless the configuration declares a ``derive_by_type``
    entry (an unreadable table declares none, and the markers of a ``derive`` cycling
    on some types are not declared entries), else ``by need type``.
    """
    declared = any(
        not (isinstance(rule, DeriveInvalid) and rule.fallback)
        for rule in (derive_by_type or {}).values()
    )
    if derive is not None and not declared:
        return derive.describe()
    return "by need type"


def _check_derive_by_type(derive_by_type: Mapping[str, Derive] | None) -> None:
    """Check the ``derive_by_type`` of a field or link type: need type to rule.

    :raises ValueError: if it is not a mapping of need type to rule.
    """
    if derive_by_type is None:
        return
    if not isinstance(derive_by_type, Mapping) or not all(
        isinstance(need_type, str) and isinstance(rule, DeriveRule | DeriveInvalid)
        for need_type, rule in derive_by_type.items()
    ):
        raise ValueError(
            "derive_by_type must map need types to a DeriveRule or a DeriveInvalid."
        )


@dataclass(frozen=True, slots=True)
class FieldLiteralValue:
    value: AllowedTypes


@dataclass(frozen=True, slots=True)
class LinksLiteralValue:
    value: list[NeedLink]


@dataclass(frozen=True, slots=True)
class FieldFunctionArray:
    value: tuple[
        DynamicFunctionParsed
        | VariantFunctionParsed
        | VariantDataParsed
        | str
        | bool
        | int
        | float,
        ...,
    ]

    def __iter__(
        self,
    ) -> Iterator[
        DynamicFunctionParsed
        | VariantFunctionParsed
        | VariantDataParsed
        | str
        | bool
        | int
        | float
    ]:
        return iter(self.value)


_ValueType = TypeVar("_ValueType", str, bool, int, float)


@dataclass(frozen=True, slots=True)
class FunctionArrayTyped(Generic[_ValueType]):
    value: tuple[
        DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed | _ValueType,
        ...,
    ]

    def __iter__(
        self,
    ) -> Iterator[
        DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed | _ValueType
    ]:
        return iter(self.value)


@dataclass(frozen=True, slots=True)
class LinksFunctionArray:
    value: tuple[
        NeedLink | DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed,
        ...,
    ]


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
class LinkDisplayConfig:
    """Display/rendering configuration for a link type."""

    incoming: str
    """Title for incoming links (e.g., 'links incoming')."""
    outgoing: str
    """Title for outgoing links (e.g., 'links outgoing')."""
    color: str = "#000000"
    """Color used for needflow diagrams."""
    style: str = ""
    """Line style used for needflow diagrams."""
    style_part: str = "dotted"
    """Line style used for need parts in needflow diagrams."""
    style_start: str = "-"
    """Arrow start style for needflow diagrams."""
    style_end: str = "->"
    """Arrow end style for needflow diagrams."""


@dataclass(frozen=True, kw_only=True, slots=True)
class LinkTargetTypes:
    """The need types the links of a link type may point to: its ``target_types``.

    A link to a need of a listed type, or of a type inheriting from one, transitively,
    is accepted; the check is made where the links are resolved, on the outgoing links
    of the needs of the need type the declaration is for.
    """

    names: tuple[str, ...]
    """The need types as declared, by directive name, each a need type of the project
    (the names that are not are reported and left out where it is declared)."""
    types: frozenset[str]
    """The accepted need types: ``names`` and every type inheriting from one of them,
    expanded once, through the parents ``inherits`` leaves after its checks."""
    declared_by: str | None = None
    """The need type whose ``needs_types`` entry declares them, or ``None`` for a
    ``needs_links`` (or ``needs_extra_links``) entry; a type inheriting the declaration
    keeps its ancestor's, so a message can name where the set comes from."""

    def __post_init__(self) -> None:
        if not self.names or not all(
            isinstance(name, str) and name for name in self.names
        ):
            raise ValueError("names must be a non-empty tuple of need type names.")
        if not set(self.names) <= self.types:
            raise ValueError("types must include every one of names.")


@dataclass(frozen=True, kw_only=True, slots=True)
class LinkSchema:
    """Schema for a single link field."""

    name: str
    description: str = ""
    schema: LinkSchemaType
    directive_option: bool = False
    allow_extend: bool = False
    parse_dynamic_functions: bool = False
    parse_variants: bool = False
    parse_conditions: bool = True
    allow_defaults: bool = False
    predicate_defaults: tuple[
        tuple[str, LinksLiteralValue | LinksFunctionArray],
        ...,
    ] = ()
    """List of (need filter, value) pairs for default predicate values.

    Used if the field has not been specifically set.

    The value from the first matching filter will be used, if any.
    """
    default: LinksLiteralValue | LinksFunctionArray | None = None
    """ The default value for this field.
    
    Used if the field has not been specifically set, and no predicate matches.
    """
    display: LinkDisplayConfig
    """Display/rendering configuration for this link type."""
    copy: bool = False
    """If True, copy links to the common 'links' field (deprecated, removed in 10.0:
    a ``union`` link type replaces it)."""
    allow_dead_links: bool = False
    """If True, add a 'forbidden' class to dead links instead of warning."""
    target_types: LinkTargetTypes | None = None
    """The need types the links may point to (``target_types``); ``None``: any.

    Unlike ``display``, ``copy`` and ``allow_dead_links`` it is no part of the link
    type's shape: a need type may narrow it (:func:`narrowing_problems`), so it is read
    from the declaration for a need's type (:meth:`FieldsSchema.for_type`). A derived
    link type takes none.
    """
    derive: Derive | None = None
    """The ``derive`` rule computing this link type, if it is derived.

    A derived link type cannot be set in a need or by a ``needextend``, and takes no
    default; a :class:`~sphinx_needs.derive.DeriveInvalid` marks a rule that cannot
    be read, and the link type holds no links.
    """
    derive_by_type: Mapping[str, Derive] | None = None
    """The rules per need type (``derive_by_type``): need type to rule, each
    overriding ``derive`` on its type, if any.

    The link type is derived (closed) on every need type. A need of a type without a
    rule holds :meth:`off_type_value`: the literal ``default``, which only
    ``derive_by_type`` without ``derive`` may carry, else no links.
    """

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string.")
        if self.derive is not None and not isinstance(
            self.derive, DeriveRule | DeriveInvalid
        ):
            raise ValueError("derive must be a DeriveRule or a DeriveInvalid.")
        _check_derive_by_type(self.derive_by_type)
        if self.target_types is not None:
            if not isinstance(self.target_types, LinkTargetTypes):
                raise ValueError("target_types must be a LinkTargetTypes.")
            if self.derived:
                raise ValueError("A derived link type takes no target_types.")
        try:
            validate_link_schema_type(self.schema)
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
        if not isinstance(self.parse_conditions, bool):
            raise ValueError("parse_conditions must be a boolean.")
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
    def kind(self) -> Literal["link"]:
        """What it declares: a link type."""
        return "link"

    @property
    def derived(self) -> bool:
        """Whether the link type is derived: it carries ``derive``, or ``derive_by_type``.

        A derived link type is closed on every need type, also on a type without a rule.
        """
        return self.derive is not None or self.derive_by_type is not None

    def rule_for(self, need_type: str) -> Derive | None:
        """The rule computing the link type on a need of ``need_type``.

        The type's own ``derive_by_type`` entry, else ``derive``, else ``None``: a need
        of that type holds the link type's :meth:`off_type_value`.
        """
        if (
            self.derive_by_type is not None
            and (rule := self.derive_by_type.get(need_type)) is not None
        ):
            return rule
        return self.derive

    def describe_derived(self) -> str:
        """The rules of a derived link type, as messages name them: ``kind 'links'``."""
        return _describe_derived(self.derive, self.derive_by_type)

    def union_on(self, need: NeedItem) -> DeriveRule | None:
        """The ``union`` rule that computed this link type on ``need``, if one did.

        There its links are its members' links, so it reports no dead link and no link
        condition of its own, nor does a dead link of it make one forbidden: the
        members do, as they allow dead links. A need from ``needimport`` or
        ``needs_external_needs`` keeps the links its file gives, which no rule
        computed: there the link type is checked as any other. Every check of a
        need's links asks this.
        """
        if need["is_import"] or need["is_external"]:
            return None
        rule = self.rule_for(need["type"])
        return rule if is_union(rule) else None

    def off_type_value(self) -> list[NeedLink]:
        """The links a need holds when its type has no rule (see :meth:`rule_for`).

        The literal ``default`` when ``derive_by_type`` stands without ``derive``, else
        no links.
        """
        if (
            self.derive is None
            and self.derive_by_type is not None
            and isinstance(self.default, LinksLiteralValue)
        ):
            return list(deepcopy(self.default.value))
        return []

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
            schema["default"] = [nl.to_filter_string() for nl in self.default.value]
        return schema

    def type_check(self, value: Any) -> bool:
        """Check if a value is of the correct type for this field."""
        return isinstance(value, list) and all(
            isinstance(i, str | NeedLink) for i in value
        )

    def type_check_item(self, value: Any) -> bool:
        """Check if a value is of the correct item type for this field.

        For 'array' fields, this checks the type of the array items.
        For other fields, this checks the type of the field itself.
        """
        return isinstance(value, str | NeedLink)

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
        array: list[
            NeedLink | DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed
        ] = []
        for item in _split_link_list(
            value,
            self.parse_dynamic_functions,
            self.parse_variants,
            parse_conditions=self.parse_conditions,
        ):
            if isinstance(item, LinkSplitWarning):
                # TODO bubble up as warning?
                raise ValueError(item.message)
            elif isinstance(item, NeedLink):
                array.append(item)
            else:
                has_df_or_vf = True
                array.append(item)

        if has_df_or_vf:
            return LinksFunctionArray(tuple(array))
        else:
            return LinksLiteralValue(array)  # ty: ignore[invalid-argument-type]

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
                    NeedLink
                    | DynamicFunctionParsed
                    | VariantFunctionParsed
                    | VariantDataParsed
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
                            DynamicFunctionParsed.from_string(
                                item.strip()[2:-2], allow_need=True
                            )
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
                    elif (
                        self.parse_variants
                        and item.lstrip().startswith("<{")
                        and item.rstrip().endswith("}>")
                    ):
                        has_function = True
                        new_value.append(
                            VariantDataParsed.from_string(item.strip()[2:-2])
                        )
                    else:
                        new_value.append(
                            NeedLink.from_string(
                                item, parse_conditions=self.parse_conditions
                            )
                        )
                if has_function:
                    return LinksFunctionArray(tuple(new_value))
                else:
                    return LinksLiteralValue(
                        [
                            NeedLink.from_string(
                                v, parse_conditions=self.parse_conditions
                            )
                            for v in value
                        ]
                    )
            else:
                return LinksLiteralValue(
                    [
                        NeedLink.from_string(v, parse_conditions=self.parse_conditions)
                        for v in value
                    ]
                )


class FieldShape(Protocol):
    """The shape of a field: what is the same on every need type.

    Its name, its kind, its ``type`` and ``item_type``, and its derivation (a field
    derived per need type says so in its ``derive_by_type``). The fields schema answers
    a field's shape (:meth:`FieldsSchema.get_any_field` and the other getters); a
    field's declaration in full, which a need type may declare anew, is read through
    :meth:`FieldsSchema.for_type` (:class:`FieldSchema`, :class:`LinkSchema`).
    """

    @property
    def name(self) -> str: ...

    @property
    def kind(self) -> Literal["field", "link"]: ...

    @property
    def type(self) -> Literal["string", "boolean", "integer", "number", "array"]: ...

    @property
    def item_type(self) -> Literal["string", "boolean", "integer", "number"] | None: ...

    @property
    def derived(self) -> bool: ...

    @property
    def derive(self) -> Derive | None: ...

    @property
    def derive_by_type(self) -> Mapping[str, Derive] | None: ...

    def rule_for(self, need_type: str) -> Derive | None: ...

    def describe_derived(self) -> str: ...


class LinkShape(FieldShape, Protocol):
    """The shape of a link type: what is the same on every need type.

    Besides a field's shape, how its links are drawn (``display``), whether they are
    copied into ``links`` (``copy``) and whether a dead link is allowed
    (``allow_dead_links``): every need type declares a link type with the same ones.
    """

    @property
    def type(self) -> Literal["array"]: ...

    @property
    def item_type(self) -> Literal["string"]: ...

    @property
    def display(self) -> LinkDisplayConfig: ...

    @property
    def copy(self) -> bool: ...

    @property
    def allow_dead_links(self) -> bool: ...

    def union_on(self, need: NeedItem) -> DeriveRule | None: ...


class FieldsSchema:
    """A schema for the fields of a single need.

    A field's declaration holds for every need type, unless the need type carries an
    overlay of it (:meth:`add_type_overlay`), or the field is declared on need types
    alone and the type does not declare it: :meth:`for_type` is the schema of the
    needs of one need type, its overlays in place of the declarations they replace.

    The schema answers a field's shape, the same on every need type (its name, kind,
    type and derivation); a need's field is read through :meth:`for_type` of its type,
    and configuration code reads a field's declarations through :meth:`global_declaration`
    and :meth:`type_declarations`. Overlays are registered after every other change to
    the schema, and once it is complete it is frozen (:meth:`freeze`): ``create_schema``
    freezes the schema it builds, and the first :meth:`for_type` one built by hand.
    """

    __slots__ = (
        "_absent",
        "_core_fields",
        "_derived_names",
        "_extra_fields",
        "_frozen",
        "_global_view",
        "_link_fields",
        "_local",
        "_need_types",
        "_project_fields",
        "_type_overlays",
        "_type_views",
        "_view_of",
    )

    def __init__(self) -> None:
        self._core_fields: dict[str, FieldSchema] = {}
        self._extra_fields: dict[str, FieldSchema] = {}
        self._link_fields: dict[str, LinkSchema] = {}
        #: the extra fields the project declares, not an extension or a service
        self._project_fields: set[str] = set()
        #: need type -> field name -> the field's declaration for that need type
        self._type_overlays: dict[str, dict[str, FieldSchema | LinkSchema]] = {}
        #: field name -> its declaration on a need type that does not declare it, one
        #: for every such type
        self._absent: dict[str, FieldSchema | LinkSchema] = {}
        #: field declared on need types alone -> the need types that declare it: it is
        #: absent on every other need type
        self._local: dict[str, frozenset[str]] = {}
        #: need type -> the schema of its needs (each need type with overlays, and
        #: each that does not declare a field declared on need types alone)
        self._type_views: dict[str, TypeFieldsSchema] = {}
        #: the schema of the needs of every need type without overlays
        self._global_view: TypeFieldsSchema | None = None
        #: the schema it is resolved from, and the need type (``None`` for the global
        #: view), for the schema of one need type (:meth:`for_type`)
        self._view_of: tuple[FieldsSchema, str | None] | None = None
        #: whether the schema has been read for a need type (:meth:`freeze`)
        self._frozen = False
        #: the names of the derived fields and link types, once the schema is frozen
        #: (:attr:`derived_names`)
        self._derived_names: frozenset[str] | None = None
        #: the configured need types, if the schema was told (:meth:`set_need_types`)
        self._need_types: frozenset[str] | None = None

    def __repr__(self) -> str:
        return (
            f"Schema(core={list(self._core_fields.values())}, "
            f"extra={list(self._extra_fields.values())}, "
            f"link={list(self._link_fields.values())})"
        )

    def _base(self) -> FieldsSchema:
        """The schema itself, or the one a schema of one need type is resolved from."""
        return self if self._view_of is None else self._view_of[0]

    def _mutating(self) -> None:
        """Refuse to change a frozen schema, or the schema of one need type.

        A schema of one need type exists only once the schema is frozen
        (:meth:`for_type` freezes it before it resolves one), so a change that is
        taken has none to forget.

        :raises TypeError: if this is the schema of one need type, or the schema is
            frozen (:meth:`freeze`)
        """
        if self._view_of is not None:
            if self._view_of[1] is None:
                raise TypeError(
                    "The global view of the fields schema cannot be changed; change "
                    "the schema it is resolved from."
                )
            raise TypeError(
                f"The fields schema of need type {self._view_of[1]!r} cannot be "
                "changed; change the schema it is resolved from."
            )
        if self._frozen:
            raise TypeError(
                "The fields schema cannot be changed once it is complete: "
                "create_schema freezes the schema it builds, and the first read "
                "through for_type freezes one built by hand. Declare fields, link "
                "types and need types in the configuration, before the schema is "
                "built."
            )

    @property
    def frozen(self) -> bool:
        """Whether the schema can no longer be changed (:meth:`freeze`)."""
        return self._frozen

    def freeze(self) -> None:
        """Stop the schema from changing: every later change raises ``TypeError``.

        The schema of each need type with overlays, of each that does not declare a
        field declared on need types alone, and the global view, are resolved now;
        :meth:`for_type` then answers with one of them, so what a need was created with
        is what every later read of its type answers (a schema never told its need
        types resolves the view of a type lacking such a field at its first read).
        ``create_schema`` freezes the schema it builds, as its last step; the first
        :meth:`for_type` freezes a schema built by hand. Freezing again does nothing.
        """
        if self._frozen:
            return
        self._frozen = True
        self._derived_names = self._collect_derived_names()
        for need_type in (*self._type_overlays, *self._lacking()):
            self._resolved(need_type)
        self._resolved(None)

    @property
    def derived_names(self) -> frozenset[str]:
        """The names of the derived extra fields and link types: each one carrying
        ``derive`` or ``derive_by_type``.

        Derivation is a property of the field, the same on every need type (an overlay
        keeps it, :meth:`add_type_overlay`, and a field declared on need types alone is
        derived on the types that do not declare it too), so the set is one for the
        schema: the schema of each need type (:meth:`for_type`) answers the schema's
        own set, the same object. A need refuses a write to any of these names
        (:class:`~sphinx_needs.need_item.NeedItem`). It is computed once the schema is
        frozen (:meth:`freeze`), and at each read before.
        """
        if self._view_of is not None:
            return self._view_of[0].derived_names
        if self._derived_names is not None:
            return self._derived_names
        names = self._collect_derived_names()
        if self._frozen:
            # a schema of one need type made directly: frozen, never changed
            self._derived_names = names
        return names

    def _collect_derived_names(self) -> frozenset[str]:
        """The names of the derived extra fields and link types (:attr:`derived_names`)."""
        # a core field is never derived: a derive on one is refused at load
        return frozenset(
            field.name
            for field in (*self._extra_fields.values(), *self._link_fields.values())
            if field.derived
        )

    def _lacks_local(self, need_type: str) -> bool:
        """Whether a configured need type does not declare a field declared on need
        types alone (:meth:`_localise`)."""
        return bool(self._local) and (
            (self._need_types is None or need_type in self._need_types)
            and any(need_type not in declaring for declaring in self._local.values())
        )

    def _lacking(self) -> list[str]:
        """The configured need types that do not declare a field declared on need
        types alone (:meth:`_localise`)."""
        if not self._local or self._need_types is None:
            return []
        return sorted(t for t in self._need_types if self._lacks_local(t))

    def _localise(self, name: str, declaring: Iterable[str]) -> None:
        """Make ``name`` a field of the need types ``declaring`` alone: in
        :meth:`for_type` of every other configured need type it is absent, its
        declaration one an author (``directive_option``) or a ``needextend``
        (``allow_extend``) cannot set, shared by every such type. A second call
        replaces the first.

        ``create_schema`` calls it for each field a need type's ``fields`` entry
        declares that nothing else declares, once the types' declarations are
        registered.

        :raises ValueError: if the schema has no field of that name
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if self._any_field(name) is None:
            raise ValueError(
                f"Cannot declare field {name!r} on need types alone: there is no field "
                "of that name."
            )
        self._local[name] = frozenset(declaring)

    @property
    def need_types(self) -> frozenset[str] | None:
        """The configured need types (:meth:`set_need_types`), ``None`` if not told."""
        return self._base()._need_types

    def set_need_types(self, names: Iterable[str]) -> None:
        """Tell the schema the configured need types (their directive names).

        Once told, an overlay names one of them (:meth:`add_type_overlay`); a read
        for any need type stays allowed (:meth:`for_type`). It is told once.

        :raises ValueError: if it was told already, or a need type with overlays is
            not among them
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if self._need_types is not None:
            raise ValueError("The need types of the fields schema are already set.")
        need_types = frozenset(names)
        for need_type in self._type_overlays:
            if need_type not in need_types:
                raise ValueError(
                    f"Need type {need_type!r} declares fields anew, but {need_type!r} "
                    "is not a configured need type."
                )
        self._need_types = need_types

    def add_type_overlay(self, need_type: str, field: FieldSchema | LinkSchema) -> None:
        """Declare a field anew for the needs of one need type.

        The overlay is the field's declaration in :meth:`for_type` of that need type;
        a second overlay of the same field for the same need type replaces the first.
        The overlay is a narrowing of the field's declaration
        (:func:`narrowing_problems`): of a field this schema has, of the same kind,
        ``type``, ``item_type`` and derivation, admitting no value the field does not,
        opening nothing the field closes. Once the schema knows the configured need
        types (:meth:`set_need_types`), the need type is one of them. Overlays are
        registered after every other change to the schema.

        :raises ValueError: if the need type is not configured, the schema has no field
            of that name, or the overlay is not a narrowing of it (every reason, joined
            by ``"; "``)
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if not isinstance(need_type, str) or not need_type:
            raise ValueError("need_type must be a non-empty string.")
        if self._need_types is not None and need_type not in self._need_types:
            raise ValueError(
                f"Cannot declare field {field.name!r} for need type {need_type!r}: "
                f"{need_type!r} is not a configured need type."
            )
        base = self._any_field(field.name)
        if base is None:
            raise ValueError(
                f"Cannot declare field {field.name!r} for need type {need_type!r}: "
                "there is no field of that name."
            )
        if problems := narrowing_problems(base, field):
            head = f"Cannot declare field {field.name!r} for need type {need_type!r}"
            # the type and derivation problems read on from the head ("... with type")
            joint = " " if problems[0].startswith("with ") else ": "
            raise ValueError(f"{head}{joint}{'; '.join(problems)}")
        self._type_overlays.setdefault(need_type, {})[field.name] = field

    def for_type(self, need_type: str | None) -> TypeFieldsSchema:
        """The schema of the needs of ``need_type``, every field in full.

        With no need type, or a need type without overlays that declares every field
        declared on need types alone, it is the global view: the fields as every need
        type shares them, one instance. Else it is a schema whose fields are this
        one's, in the same order, with the need type's overlays
        (:meth:`add_type_overlay`) in place of the fields they replace, and each field
        declared on need types alone (by their ``needs_types`` entries) that the type
        does not declare absent. A need type the schema does not know reads the global
        view: an unknown type is reported where a need is created. Neither can be
        changed, and the first call freezes a schema not frozen yet (:meth:`freeze`).
        The schema of one need type answers as the schema it is resolved from.
        """
        if self._view_of is not None:
            return self._view_of[0].for_type(need_type)
        if not self._frozen:
            self.freeze()
        return self._resolved(need_type)

    def _resolved(self, need_type: str | None) -> TypeFieldsSchema:
        """The schema of the needs of ``need_type``, resolved once (by :meth:`freeze`,
        for every need type with overlays, every need type that does not declare a
        field declared on need types alone, and the global view)."""
        if need_type is not None and (
            need_type in self._type_overlays or self._lacks_local(need_type)
        ):
            if (view := self._type_views.get(need_type)) is None:
                view = self._type_views[need_type] = self._resolve_type(need_type)
            return view
        if self._global_view is None:
            self._global_view = self._resolve_type(None)
        return self._global_view

    def _resolve_type(self, need_type: str | None) -> TypeFieldsSchema:
        """The schema of the needs of ``need_type``, its overlays in place."""
        view = TypeFieldsSchema()
        view._core_fields = dict(self._core_fields)
        view._extra_fields = dict(self._extra_fields)
        view._link_fields = dict(self._link_fields)
        view._project_fields = self._project_fields
        overlays = {} if need_type is None else self._type_overlays.get(need_type, {})
        for name, field in overlays.items():
            if isinstance(field, LinkSchema):
                view._link_fields[name] = field
            elif name in view._core_fields:
                view._core_fields[name] = field
            else:
                view._extra_fields[name] = field
        if need_type is not None:
            # a field declared on need types alone is absent on every other type
            view._undeclared = frozenset(
                name
                for name, declaring in self._local.items()
                if need_type not in declaring
            )
            for name in view._undeclared:
                if (field := view._extra_fields.get(name)) is not None:
                    view._extra_fields[name] = self._absent_of(field)
                elif (link := view._link_fields.get(name)) is not None:
                    view._link_fields[name] = self._absent_of(link)
        view._view_of = (self, need_type)
        return view

    @overload
    def _absent_of(self, field: FieldSchema) -> FieldSchema: ...

    @overload
    def _absent_of(self, field: LinkSchema) -> LinkSchema: ...

    def _absent_of(self, field: FieldSchema | LinkSchema) -> FieldSchema | LinkSchema:
        """The declaration of a field on a need type that does not declare it: one for
        every such type. A derived field is closed on every type already.

        It keeps the global ``default`` and ``predicate_defaults``, which no reader
        applies: creation gives an absent field its empty value without defaults, the
        validation's off-type default is a derived field's only, and the readers of a
        default read the global view.
        """
        if field.derived:
            return field
        if (absent := self._absent.get(field.name)) is None:
            absent = self._absent[field.name] = replace(
                field, directive_option=False, allow_extend=False
            )
        return absent

    def add_core_field(self, field: FieldSchema) -> None:
        """Add a core field to the schema.

        :raises ValueError: if a field with the same name already exists
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._core_fields[field.name] = field

    def add_extra_field(self, field: FieldSchema, *, project: bool = False) -> None:
        """Add an extra field to the schema.

        :param project: Whether the project declares it (``needs_fields``,
            ``needs_extra_options``), rather than an extension or a service.
        :raises ValueError: if a field with the same name already exists
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._extra_fields[field.name] = field
        if project:
            self._project_fields.add(field.name)

    def is_project_field(self, name: str) -> bool:
        """Whether the extra field ``name`` is one the project declares."""
        return name in self._project_fields

    def add_link_field(self, field: LinkSchema) -> None:
        """Add a link field to the schema.

        :raises ValueError: if a field with the same name already exists
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        if (
            field.name in self._core_fields
            or field.name in self._extra_fields
            or field.name in self._link_fields
        ):
            raise ValueError(f"Field '{field.name}' already exists.")
        self._link_fields[field.name] = field

    def replace_field(self, field: FieldSchema | LinkSchema) -> None:
        """Replace the core field, extra field or link field of the same name.

        The field keeps its place in the iteration order, and the type, item type and
        derivation of the field a need type declares anew (:meth:`add_type_overlay`);
        each such declaration stays a narrowing of the replacement
        (:func:`narrowing_problems`).

        :raises ValueError: if no field of that name and kind exists, or a need type
            declares it with another ``type``, ``item_type`` or derivation, or not as
            a narrowing of the replacement
        :raises TypeError: if the schema is frozen, or the schema of one need type
        """
        self._mutating()
        for need_type, overlays in self._type_overlays.items():
            if (overlay := overlays.get(field.name)) is None:
                continue
            differs = [
                what
                for what, other in (
                    ("type", overlay.type != field.type),
                    ("item type", overlay.item_type != field.item_type),
                    (
                        "derivation",
                        overlay.derive != field.derive
                        or overlay.derive_by_type != field.derive_by_type,
                    ),
                )
                if other
            ]
            head = (
                f"Cannot replace field {field.name!r} with type {field.type!r} "
                f"(items {field.item_type!r}): need type {need_type!r} declares it"
            )
            if differs:
                kinds = (
                    differs[0]
                    if len(differs) == 1
                    else f"{', '.join(differs[:-1])} and {differs[-1]}"
                )
                raise ValueError(f"{head} with another {kinds}.")
            if problems := narrowing_problems(field, overlay):
                raise ValueError(
                    f"{head}, and not as a narrowing of it: {'; '.join(problems)}"
                )
        if isinstance(field, LinkSchema):
            if field.name not in self._link_fields:
                raise ValueError(f"Link field '{field.name}' does not exist.")
            self._link_fields[field.name] = field
        elif field.name in self._core_fields:
            self._core_fields[field.name] = field
        else:
            if field.name not in self._extra_fields:
                raise ValueError(f"Extra field '{field.name}' does not exist.")
            self._extra_fields[field.name] = field

    def global_declaration(self, name: str) -> FieldSchema | LinkSchema | None:
        """The global declaration of the field ``name``, in full, ``None`` if none.

        The declaration every need type shares unless it declares the field anew
        (:meth:`type_declarations`): for configuration code and audits, which read a
        field before any need, or across needs of every type. A need reads its field
        through :meth:`for_type` of its type. Reading it does not freeze the schema.
        """
        return self._base()._any_field(name)

    def type_declarations(self, name: str) -> Mapping[str, FieldSchema | LinkSchema]:
        """The need types that declare the field ``name`` anew, each with its
        declaration (:meth:`add_type_overlay`), read-only.

        In the order the need types were first given an overlay; empty when no need
        type declares the field anew. Reading it does not freeze the schema.
        """
        return MappingProxyType(
            {
                need_type: overlays[name]
                for need_type, overlays in self._base()._type_overlays.items()
                if name in overlays
            }
        )

    def declares_default(self, name: str) -> bool:
        """Whether a declaration of the field ``name`` carries a default or a
        predicate default: its global declaration, or any need type's.

        Before a need is created it is unknown which declaration, and which predicate,
        will apply: this is the over-approximation for "the field may be given a
        default". Reading it does not freeze the schema.
        """
        return any(
            field.default is not None or bool(field.predicate_defaults)
            for field in (
                self.global_declaration(name),
                *self.type_declarations(name).values(),
            )
            if field is not None
        )

    def _any_field(self, name: str) -> FieldSchema | LinkSchema | None:
        if name in self._core_fields:
            return self._core_fields[name]
        if name in self._extra_fields:
            return self._extra_fields[name]
        if name in self._link_fields:
            return self._link_fields[name]
        return None

    def get_any_field(self, name: str) -> FieldShape | LinkShape | None:
        """Get a field by name: its shape (:meth:`for_type` reads it in full)."""
        return self._any_field(name)

    def get_core_field(self, name: str) -> FieldShape | None:
        """Get a core field by name: its shape (:meth:`for_type` reads it in full)."""
        return self._core_fields.get(name)

    def get_extra_field(self, name: str) -> FieldShape | None:
        """Get an extra field by name: its shape (:meth:`for_type` reads it in full)."""
        return self._extra_fields.get(name)

    def get_link_field(self, name: str) -> LinkShape | None:
        """Get a link field by name: its shape (:meth:`for_type` reads it in full)."""
        return self._link_fields.get(name)

    def iter_all_fields(self) -> Iterable[FieldShape | LinkShape]:
        """Iterate over all fields in the schema."""
        yield from self._core_fields.values()
        yield from self._extra_fields.values()
        yield from self._link_fields.values()

    def iter_core_field_names(self) -> Iterable[str]:
        """Iterate over all core field names in the schema."""
        yield from self._core_fields.keys()

    def iter_core_fields(self) -> Iterable[FieldShape]:
        """Iterate over all core fields in the schema."""
        yield from self._core_fields.values()

    def iter_extra_field_names(self) -> Iterable[str]:
        """Iterate over all extra field names in the schema."""
        yield from self._extra_fields.keys()

    def iter_extra_fields(self) -> Iterable[FieldShape]:
        """Iterate over all extra fields in the schema."""
        yield from self._extra_fields.values()

    def iter_link_field_names(self) -> Iterable[str]:
        """Iterate over all link field names in the schema."""
        yield from self._link_fields.keys()

    def iter_link_fields(self) -> Iterable[LinkShape]:
        """Iterate over all link fields in the schema."""
        yield from self._link_fields.values()

    def copying_link_types(self) -> list[str]:
        """The link types that copy their links into ``links`` (``copy = true``,
        deprecated), as a need's creation copies them: those with ``copy``, but
        ``links`` itself and a derived one (whose ``copy`` is refused), and none where
        ``links`` is derived (nothing is copied into it).

        Read on :meth:`for_type`'s schema, they are those a need of that type copies;
        on the global view, they are why ``links`` takes no ``target_types``: it holds
        links written in it and links copied into it.
        """
        own = self.get_link_field("links")
        if own is None or own.derived:
            return []
        return [
            link.name
            for link in self.iter_link_fields()
            if link.copy and link.name != "links" and not link.derived
        ]


class TypeFieldsSchema(FieldsSchema):
    """The schema of the needs of one need type (:meth:`FieldsSchema.for_type`).

    Its fields are the full declarations its needs read: the need type's overlays in
    place of the fields they replace, or, for the global view, every field as every
    need type shares it. Its getters answer them in full (:class:`FieldSchema`,
    :class:`LinkSchema`), where the schema it is resolved from answers their shapes.
    It cannot be changed.
    """

    __slots__ = ("_undeclared",)

    def __init__(self) -> None:
        super().__init__()
        # resolved by FieldsSchema.for_type, never changed: also one made directly
        self._frozen = True
        #: the fields declared on need types alone that this need type does not
        #: declare (absent here, a derived one too)
        self._undeclared: frozenset[str] = frozenset()

    def declares(self, name: str) -> bool:
        """Whether the need type declares the field or link type ``name``: every one
        but a field declared on need types alone (in their ``needs_types`` entries)
        that this type does not declare. The global view declares every one.

        It answers ``True`` for any other name, a field or not, and a view made
        directly (not by :meth:`FieldsSchema.for_type`) declares every name: ask it
        about the fields of the view.
        """
        return name not in self._undeclared

    def get_any_field(self, name: str) -> FieldSchema | LinkSchema | None:
        """Get a field by name."""
        return self._any_field(name)

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
    VD = "vd"
    VD_U = "vd_unclosed"


def _split_list(
    text: str,
    parse_dynamic_functions: bool,
    parse_variants: bool,
    allow_delimiters: bool = True,
) -> Iterator[list[tuple[str, ListItemType]]]:
    """Split a ``;|,`` delimited string that may contain ``[[...]]`` dynamic functions, ``<<...>>`` variant functions, or ``<{...}>`` variant data.

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
        elif parse_variants and text.startswith("<{"):
            if not _current_elements:
                _current_element = _current_element.lstrip()
            if _current_element:
                _current_elements.append((_current_element, ListItemType.STD))
            _current_element = ""
            text = text[2:]
            while text and not text.startswith("}>"):
                _current_element += text[0]
                text = text[1:]
            if _current_element.endswith("}"):
                _current_element = _current_element[:-1]
            _current_elements.append(
                (
                    _current_element,
                    ListItemType.VD if text.startswith("}>") else ListItemType.VD_U,
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


@dataclass(frozen=True, slots=True)
class LinkSplitWarning:
    """A warning yielded during link list splitting."""

    message: str


def _split_link_list(
    text: str,
    parse_dynamic_functions: bool,
    parse_variants: bool,
    *,
    parse_conditions: bool = True,
) -> Iterator[
    NeedLink
    | DynamicFunctionParsed
    | VariantFunctionParsed
    | VariantDataParsed
    | LinkSplitWarning
]:
    """Split a ``;|,`` delimited link string, directly yielding typed objects.

    Handles ``[[...]]`` dynamic functions, ``<<...>>`` variant functions,
    ``<{...}>`` variant data, and plain link IDs with optional ``[condition]`` syntax.

    Parsing is done left-to-right in a single pass with these priority rules:

    1. ``[[...]]`` → ``DynamicFunctionParsed``
    2. ``<<...>>`` → ``VariantFunctionParsed``
    3. ``<{...}>`` → ``VariantDataParsed``
    4. ``;|,`` → flush accumulated text as a ``NeedLink``
    5. Otherwise → accumulate character

    Plain link items support the format ``ID``, ``ID.part``,
    ``ID[condition]``, or ``ID.part[condition]``.
    The condition uses matched bracket depth,
    so ``ID[[x>1]]`` parses the condition as ``[x>1]``.

    :param text: The string to split.
    :param parse_dynamic_functions: Whether to parse ``[[...]]`` dynamic functions.
    :param parse_variants: Whether to parse ``<<...>>`` variant functions and ``<{...}>`` variant data.
    :param parse_conditions: Whether to parse ``[condition]`` brackets.
    :yields: Parsed link items, or ``LinkSplitWarning`` for non-fatal issues
        (e.g. text adjacent to a dynamic/variant function, unclosed brackets).
    """
    from sphinx_needs.functions.functions import DynamicFunctionParsed

    _current = ""  # text accumulated for the current plain-text item
    _has_special = False  # whether current slot has yielded a DF/VF/VD

    def _flush_current() -> NeedLink | LinkSplitWarning | None:
        """Flush accumulated plain text as a NeedLink, or None if empty."""
        nonlocal _current
        stripped = _current.strip()
        _current = ""
        if not stripped:
            return None
        link, warnings = NeedLink.from_string_with_warnings(
            stripped, parse_conditions=parse_conditions
        )
        if warnings:
            return LinkSplitWarning(warnings[0])
        return link

    while text:
        if parse_dynamic_functions and text.startswith("[[") and not _current.strip():
            # [[ at start of slot (no preceding non-whitespace text) → dynamic function
            _current = ""  # discard any leading whitespace
            _has_special = True
            # Consume until closing ]]
            text = text[2:]
            content = ""
            while text and not text.startswith("]]"):
                content += text[0]
                text = text[1:]
            if content.endswith("]"):
                content = content[:-1]
            yield DynamicFunctionParsed.from_string(content, allow_need=True)
            if text.startswith("]]"):
                text = text[2:]
        elif parse_variants and text.startswith("<<") and not _current.strip():
            # << at start of slot (no preceding non-whitespace text) → variant function
            _current = ""  # discard any leading whitespace
            _has_special = True
            # Consume until closing >>
            text = text[2:]
            content = ""
            while text and not text.startswith(">>"):
                content += text[0]
                text = text[1:]
            if content.endswith(">"):
                content = content[:-1]
            yield VariantFunctionParsed.from_string(content)
            if text.startswith(">>"):
                text = text[2:]
        elif parse_variants and text.startswith("<{") and not _current.strip():
            # <{ at start of slot (no preceding non-whitespace text) → variant data
            _current = ""  # discard any leading whitespace
            _has_special = True
            # Consume until closing }>
            text = text[2:]
            content = ""
            while text and not text.startswith("}>"):
                content += text[0]
                text = text[1:]
            if content.endswith("}"):
                content = content[:-1]
            yield VariantDataParsed.from_string(content)
            if text.startswith("}>"):
                text = text[2:]
        elif text[0] in ";|,":
            # Delimiter: flush current item
            if not _has_special:
                if result := _flush_current():
                    yield result
            else:
                # After a DF/VF, check there's no trailing text
                if _current.strip():
                    yield LinkSplitWarning(
                        "only one string, dynamic function or variant function allowed per array item."
                    )
                _current = ""
            _has_special = False
            text = text[1:]
        else:
            _current += text[0]
            text = text[1:]

    # Flush final item
    if not _has_special:
        if result := _flush_current():
            yield result
    else:
        if _current.strip():
            yield LinkSplitWarning(
                "only one string, dynamic function or variant function allowed per array item."
            )


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
    parent: FieldSchema,
    child: NeedFields,
    *,
    allow_variants: bool,
    allow_dynamic_functions: bool,
) -> FieldSchema:
    """Create a new FieldSchema by inheriting from a parent FieldSchema and applying overrides from a child dictionary.

    :param parent: The parent FieldSchema to inherit from.
    :param child: A dictionary containing the child field overrides.
    :param allow_variants: Whether to allow parse_variants to be set to True in the child.
        This is a bit of a special case for certain core fields, and maybe should be handled differently in the future;
        fields like ``template`` are used before variants are processed, so allowing variants there would not make sense.
    :param allow_dynamic_functions: Whether to allow parse_dynamic_functions to be set to True in the child.
        Core fields that do not support dynamic functions (``allow_df=False``) cannot have this overridden to True.
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

    if "parse_dynamic_functions" in child:
        if not isinstance(child["parse_dynamic_functions"], bool):
            raise ValueError("Child 'parse_dynamic_functions' must be a boolean.")
        if not allow_dynamic_functions and child["parse_dynamic_functions"]:
            raise ValueError(
                "parse_dynamic_functions is not allowed to be True for this field."
            )
        replacements["parse_dynamic_functions"] = child["parse_dynamic_functions"]

    return replace(parent, **replacements)


def inherit_schema(
    parent_schema: FieldSchemaTypes, child_schema: dict[str, Any]
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

    A keyword the child leaves out is taken from the parent (the child dict is changed
    in place); the rules are those of :func:`schema_narrowing_problems`.

    :raises ValueError: with the first rule the child breaks
    """
    if not isinstance(child_schema, dict):
        raise ValueError("Child schema must be a dictionary.")
    _inherit_keywords(parent_schema, child_schema)
    if problems := schema_narrowing_problems(
        parent_schema, child_schema, dropped_is_widening=False
    ):
        raise ValueError(problems[0])


def narrowing_problems(
    base: FieldSchema | LinkSchema, overlay: FieldSchema | LinkSchema
) -> list[str]:
    """Why ``overlay`` is not a narrowing of ``base``: one reason per rule it breaks.

    A need type's declaration of a field (an overlay) is a narrowing of the field's
    declaration when a need of that type is usable wherever a need of any type is
    (Liskov substitution). The rules, in this order:

    1. the same kind, a field or a link type (only this is reported when it differs);
    2. the same ``name``, ``type`` and ``item_type``;
    3. the same ``derive`` and ``derive_by_type``;
    4. every schema keyword at least as strict (``schema_narrowing_problems``);
    5. no schema keyword of ``base`` left out;
    6. ``nullable`` only from true to false;
    7. ``allow_extend``, ``allow_defaults`` and ``directive_option`` only from true
       to false;
    8. the same ``parse_variants`` and ``parse_dynamic_functions``: a needextend
       converts its value once, for the needs of every type;
    9. a literal ``default``, and each literal predicate default, valid against the
       schema of ``overlay``, unless it is the base's own literal, already invalid
       against the schema of ``base`` (that defect is the field's, which validation
       reports on each need); a literal the declaration introduces must be valid
       against its schema; a dynamic function or a variant is not checked;
    10. for a link type, the same ``display``, ``copy``, ``allow_dead_links`` and
        ``parse_conditions``: a link type is drawn and resolved the same on every need
        type;
    11. for a link type whose ``base`` has ``target_types``, ``target_types`` whose
        accepted types (a listed type and the types inheriting from it, the EXPANDED
        sets compared) are among those of ``base``: a link a need of the type may
        hold is one a need of any type may. An overlay without ``target_types`` under
        a base with them drops them: defensive, since a declaration from the
        configuration that gives none (or names no need type) keeps the base's.

    The ``description`` is free. A reason of the rules 1 to 3 reads on from the name
    of the field ("Cannot declare field 'x' for need type 't' ..."), the others are
    sentences. Pure: it changes neither field, and does not raise.

    :return: Every reason, in the order of the rules; empty for a narrowing.
    """
    if base.kind != overlay.kind:
        return ["it is a link type." if base.kind == "link" else "it is a field."]
    problems: list[str] = []
    if overlay.name != base.name:
        problems.append(f"with name {overlay.name!r}: it declares {base.name!r}.")
    same_type = overlay.type == base.type and overlay.item_type == base.item_type
    if not same_type:
        problems.append(
            f"with type {overlay.type!r} (items {overlay.item_type!r}): its type is "
            f"{base.type!r} (items {base.item_type!r}) on every need type."
        )
    if overlay.derive != base.derive or overlay.derive_by_type != base.derive_by_type:
        problems.append(
            "with another derivation: a field is derived per need type by its "
            "derive_by_type."
        )
    if same_type:
        problems.extend(
            schema_narrowing_problems(
                base.schema, overlay.schema, dropped_is_widening=True
            )
        )
    if not base.nullable and overlay.nullable:
        problems.append("Cannot change 'nullable' from False to True in child.")
    for name, base_flag, overlay_flag in (
        ("allow_extend", base.allow_extend, overlay.allow_extend),
        ("allow_defaults", base.allow_defaults, overlay.allow_defaults),
        ("directive_option", base.directive_option, overlay.directive_option),
    ):
        if not base_flag and overlay_flag:
            problems.append(f"Cannot change {name!r} from False to True in child.")
    for name, base_flag, overlay_flag in (
        ("parse_variants", base.parse_variants, overlay.parse_variants),
        (
            "parse_dynamic_functions",
            base.parse_dynamic_functions,
            overlay.parse_dynamic_functions,
        ),
    ):
        if base_flag != overlay_flag:
            problems.append(
                f"Field {base.name!r} declares {name!r} for every need type."
            )
    if same_type:
        problems.extend(_default_problems(overlay, base))
    if isinstance(base, LinkSchema) and isinstance(overlay, LinkSchema):
        for name, same in (
            ("display", overlay.display == base.display),
            ("copy", overlay.copy == base.copy),
            ("allow_dead_links", overlay.allow_dead_links == base.allow_dead_links),
            ("parse_conditions", overlay.parse_conditions == base.parse_conditions),
        ):
            if not same:
                problems.append(
                    f"Link type {base.name!r} declares {name!r} for every need type."
                )
        if (parent := base.target_types) is not None:
            child = overlay.target_types
            if child is None:
                # defensive: a declaration from the configuration keeps the target
                # types before it when it gives none, so only an overlay built by
                # hand (add_type_overlay, replace_field) can drop them
                problems.append(
                    f"Child drops parent 'target_types' {list(parent.names)}."
                )
            elif not child.types <= parent.types:
                # the names whose types the parent does not accept: a listed type's
                # subtypes are accepted with it, so a name the parent accepts adds none
                added = [name for name in child.names if name not in parent.types]
                # never empty: the parent's set holds every subtype of what it holds, so
                # a type the child adds comes from a name outside it; a guard only
                added = added or sorted(child.types - parent.types)
                problems.append(
                    f"Child 'target_types' accept "
                    f"{joined([repr(name) for name in added])}, which "
                    f"parent 'target_types' {list(parent.names)} (or a type "
                    f"inheriting from {'it' if len(parent.names) == 1 else 'them'}) "
                    "do not."
                )
    return problems


def _default_problems(
    field: FieldSchema | LinkSchema, base: FieldSchema | LinkSchema
) -> list[str]:
    """Why a literal default, or a literal predicate default, of ``field`` is not
    valid against its schema: one reason per value, except a literal ``field`` takes
    from ``base`` that is invalid against the schema of ``base`` already, or that is
    the empty value of its type. A link default is checked as a need's links are
    validated: each target once, as its filter string."""
    values: list[tuple[str | None, FieldLiteralValue | LinksLiteralValue]] = []
    if isinstance(field.default, FieldLiteralValue | LinksLiteralValue):
        values.append((None, field.default))
    values.extend(
        (filter_, value)
        for filter_, value in field.predicate_defaults
        if isinstance(value, FieldLiteralValue | LinksLiteralValue)
    )
    #: the base's own literals: an overlay that keeps one keeps the base's defect
    inherited: list[tuple[str | None, object]] = [
        (None, base.default),
        *base.predicate_defaults,
    ]
    empty = typed_empty(field.type)
    problems: list[str] = []
    for filter_, literal in values:
        value = (
            [link.to_filter_string() for link in dict.fromkeys(literal.value)]
            if isinstance(literal, LinksLiteralValue)
            else literal.value
        )
        if value == empty and any(
            filter_ == of and literal is own for of, own in inherited
        ):
            # the empty value the field keeps (a link type's and tags' []) is no
            # default, as None is not one for a nullable field: the need holds none
            continue
        if (message := value_problem(field.name, field.schema, value)) is None:
            continue
        if (filter_, literal) in inherited and (
            value_problem(base.name, base.schema, value) is not None
        ):
            # the field's own defect, inherited, not one the narrowing made
            continue
        of = "" if filter_ is None else f" of the predicate {filter_!r}"
        problems.append(
            f"Default {value!r}{of} is not valid against the narrowed schema: "
            f"{message}."
        )
    return problems


#: the schema keywords a child schema takes from its parent when it leaves them out,
#: in the order they are checked, by type
_KEYWORDS: Final[Mapping[str, tuple[str, ...]]] = {
    "string": ("const", "enum", "pattern", "format", "minLength", "maxLength"),
    "integer": (
        "const",
        "enum",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    ),
    "number": (
        "const",
        "enum",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    ),
    "boolean": ("const",),
    "array": (
        "uniqueItems",
        "minItems",
        "maxItems",
        "minContains",
        "maxContains",
        "contains",
        "items",
    ),
}


def schema_narrowing_problems(
    base_schema: Mapping[str, Any],
    overlay_schema: Mapping[str, Any],
    *,
    dropped_is_widening: bool,
) -> list[str]:
    """Why ``overlay_schema`` admits a value ``base_schema`` does not: one reason per
    schema keyword (the rules of :func:`inherit_schema`).

    :param dropped_is_widening: Whether a keyword of ``base_schema`` that
        ``overlay_schema`` leaves out is a widening, reported after every other reason:
        so for a full declaration, which states every keyword it keeps. A declaration
        through a configuration dict names only what it changes, and takes the rest
        from its parent (:func:`inherit_schema`).
    :return: Every reason, in the order the keywords are checked; empty if none. Pure.
    """
    problems: list[str] = []
    dropped: list[str] = []
    _schema_problems(
        base_schema,
        overlay_schema,
        problems,
        dropped if dropped_is_widening else None,
        allow_array=True,
    )
    return [*problems, *dropped]


def _schema_problems(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    problems: list[str],
    dropped: list[str] | None,
    *,
    allow_array: bool,
) -> None:
    """Add why ``child`` is not a narrowing of ``parent`` to ``problems``, and each
    keyword ``child`` leaves out to ``dropped`` (if given)."""
    parent_type = parent.get("type")
    child_type = child.get("type", parent_type)
    if (
        child_type != parent_type
        or parent_type not in _KEYWORDS
        or (parent_type == "array" and not allow_array)
    ):
        problems.append(
            f"Child 'type' {child_type!r} does not match parent 'type' {parent_type!r}."
        )
        return

    def compare(keyword: str) -> bool:
        """Whether both carry ``keyword``; a keyword the child leaves out is noted."""
        if keyword not in parent:
            return False
        if keyword in child:
            return True
        if dropped is not None:
            dropped.append(f"Child schema drops parent constraint {keyword!r}.")
        return False

    if parent_type == "array":
        _array_problems(parent, child, problems, dropped, compare)
        return
    if compare("const") and child["const"] != parent["const"]:
        problems.append(
            f"Child 'const' value {child['const']!r} does not match parent 'const' "
            f"value {parent['const']!r}."
        )
    if parent_type == "boolean":
        return
    if compare("enum") and not set(child["enum"]).issubset(set(parent["enum"])):
        problems.append(
            f"Child 'enum' values {child['enum']} are not a subset of parent 'enum' "
            f"values {parent['enum']}."
        )
    if "const" in child and "enum" in parent and child["const"] not in parent["enum"]:
        problems.append(
            f"Child 'const' value {child['const']!r} is not in parent 'enum' values "
            f"{parent['enum']}."
        )
    if parent_type == "string":
        _string_problems(parent, child, problems, compare)
    else:
        _number_problems(parent, child, problems, compare)


def _string_problems(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    problems: list[str],
    compare: Callable[[str], bool],
) -> None:
    """The string keywords after ``const`` and ``enum``."""
    if compare("pattern"):
        if child["pattern"] != parent["pattern"]:
            problems.append(
                f"Child 'pattern' {child['pattern']!r} does not match parent 'pattern' "
                f"{parent['pattern']!r}. Pattern constraints cannot be overridden."
            )
    elif (
        "pattern" not in parent
        and "pattern" in child
        and not isinstance(child["pattern"], str)
    ):
        # leave compiling it to jsonschema
        problems.append(f"Child 'pattern' {child['pattern']!r} is not a string.")
    if compare("format") and child["format"] != parent["format"]:
        problems.append(
            f"Child 'format' {child['format']!r} does not match parent 'format' "
            f"{parent['format']!r}. Format constraints cannot be overridden."
        )
    if compare("minLength") and child["minLength"] < parent["minLength"]:
        problems.append(
            f"Child 'minLength' {child['minLength']} is less than parent 'minLength' "
            f"{parent['minLength']}."
        )
    if compare("maxLength") and child["maxLength"] > parent["maxLength"]:
        problems.append(
            f"Child 'maxLength' {child['maxLength']} is greater than parent "
            f"'maxLength' {parent['maxLength']}."
        )


def _number_problems(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    problems: list[str],
    compare: Callable[[str], bool],
) -> None:
    """The number and integer keywords after ``const`` and ``enum``."""
    if compare("minimum") and child["minimum"] < parent["minimum"]:
        problems.append(
            f"Child 'minimum' {child['minimum']} is less than parent 'minimum' "
            f"{parent['minimum']}."
        )
    if compare("maximum") and child["maximum"] > parent["maximum"]:
        problems.append(
            f"Child 'maximum' {child['maximum']} is greater than parent 'maximum' "
            f"{parent['maximum']}."
        )
    if compare("exclusiveMinimum") and (
        child["exclusiveMinimum"] < parent["exclusiveMinimum"]
    ):
        problems.append(
            f"Child 'exclusiveMinimum' {child['exclusiveMinimum']} is less than "
            f"parent 'exclusiveMinimum' {parent['exclusiveMinimum']}."
        )
    if compare("exclusiveMaximum") and (
        child["exclusiveMaximum"] > parent["exclusiveMaximum"]
    ):
        problems.append(
            f"Child 'exclusiveMaximum' {child['exclusiveMaximum']} is greater than "
            f"parent 'exclusiveMaximum' {parent['exclusiveMaximum']}."
        )
    if compare("multipleOf"):
        # the child's multipleOf is a multiple of the parent's (e.g. 4 of 2), with a
        # tolerance for the precision of floats
        parent_multiple = parent["multipleOf"]
        child_multiple = child["multipleOf"]
        remainder = child_multiple % parent_multiple
        if not (abs(remainder) < 1e-9 or abs(remainder - parent_multiple) < 1e-9):
            problems.append(
                f"Child 'multipleOf' {child_multiple} must be a multiple of parent "
                f"'multipleOf' {parent_multiple}."
            )


def _array_problems(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
    problems: list[str],
    dropped: list[str] | None,
    compare: Callable[[str], bool],
) -> None:
    """The array keywords, and the keywords of its items."""
    if (
        compare("uniqueItems")
        and parent["uniqueItems"] is True
        and child["uniqueItems"] is False
    ):
        problems.append(
            "Child 'uniqueItems' constraint cannot be less restrictive than parent."
        )
    if compare("minItems") and child["minItems"] < parent["minItems"]:
        problems.append(
            f"Child 'minItems' {child['minItems']} is less than parent 'minItems' "
            f"{parent['minItems']}."
        )
    if compare("maxItems") and child["maxItems"] > parent["maxItems"]:
        problems.append(
            f"Child 'maxItems' {child['maxItems']} is greater than parent 'maxItems' "
            f"{parent['maxItems']}."
        )
    if compare("minContains") and child["minContains"] < parent["minContains"]:
        problems.append(
            f"Child 'minContains' {child['minContains']} is less than parent "
            f"'minContains' {parent['minContains']}."
        )
    if compare("maxContains") and child["maxContains"] > parent["maxContains"]:
        problems.append(
            f"Child 'maxContains' {child['maxContains']} is greater than parent "
            f"'maxContains' {parent['maxContains']}."
        )
    if compare("contains") and child["contains"] != parent["contains"]:
        problems.append(
            "Child 'contains' constraint does not match parent 'contains' constraint."
        )
    if compare("items"):
        if not isinstance(child["items"], dict):
            problems.append("Child 'items' must be a dictionary.")
            return
        item_problems: list[str] = []
        item_dropped: list[str] | None = None if dropped is None else []
        _schema_problems(
            parent["items"],
            child["items"],
            item_problems,
            item_dropped,
            allow_array=False,
        )
        problems.extend(f"'items' inheritance: {problem}" for problem in item_problems)
        if dropped is not None and item_dropped:
            dropped.extend(
                f"'items' inheritance: {problem}" for problem in item_dropped
            )


def _inherit_keywords(
    parent: Mapping[str, Any], child: dict[str, Any], *, allow_array: bool = True
) -> None:
    """Take every keyword ``child`` leaves out from ``parent``, in place: a declaration
    through a configuration dict names only what it changes."""
    if "type" not in child:
        child["type"] = parent["type"]
    parent_type = parent["type"]
    if (
        child["type"] != parent_type
        or parent_type not in _KEYWORDS
        or (parent_type == "array" and not allow_array)
    ):
        return
    if (
        parent_type == "array"
        and "items" in parent
        and isinstance(child.get("items"), dict)
    ):
        _inherit_keywords(parent["items"], child["items"], allow_array=False)
    for keyword in _KEYWORDS[parent_type]:
        if keyword in parent and keyword not in child:
            child[keyword] = parent[keyword]
