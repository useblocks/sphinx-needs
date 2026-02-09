from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_needs.data import GraphvizStyleType, NeedsCoreFields
from sphinx_needs.defaults import DEFAULT_DIAGRAM_TEMPLATE
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.schema.config import (
    ExtraLinkSchemaType,
    FieldBooleanSchemaType,
    FieldIntegerSchemaType,
    FieldMultiValueSchemaType,
    FieldNumberSchemaType,
    FieldSchemaTypes,
    FieldStringSchemaType,
    SchemasFileRootType,
)

if TYPE_CHECKING:
    from sphinx.util.logging import SphinxLoggerAdapter
    from typing_extensions import NotRequired, Required

    from sphinx_needs.functions.functions import DynamicFunction
    from sphinx_needs.need_item import NeedItem


LOGGER = get_logger(__name__)


@dataclass(kw_only=True, slots=True)
class NewFieldParams:
    """Defines a single new field for needs"""

    source: Literal[
        "needs_extra_options",
        "needs_fields",
        "add_extra_option",
        "add_field",
        "service",
    ]
    """Where the field was added from."""
    description: str
    """A description of the field."""
    nullable: bool | None = None
    """Whether the field allows unset values."""
    schema: (
        FieldStringSchemaType
        | FieldBooleanSchemaType
        | FieldIntegerSchemaType
        | FieldNumberSchemaType
        | FieldMultiValueSchemaType
        | None
    )
    """A JSON schema for the option."""
    parse_variants: bool | None = None
    """Whether variants are parsed in this field."""
    predicates: None | list[tuple[str, Any]] = None
    """List of (need filter, value) pairs for default predicate values.

    Used if the field has not been specifically set.

    The value from the first matching filter will be used, if any.
    """
    default: None | Any = None
    """Default value for the field.
    
    Used if the field has not been specifically set, and no predicate matches.
    """


class NeedFunctionsType(TypedDict):
    name: str
    function: DynamicFunction


class _Config:
    """Stores sphinx-needs configuration values that can be set both via the sphinx configuration,
    and also via the API functions.
    """

    def __init__(self) -> None:
        self._fields: dict[str, NewFieldParams] = {}
        self._functions: dict[str, NeedFunctionsType] = {}
        self._warnings: dict[
            str, str | Callable[[NeedItem, SphinxLoggerAdapter], bool]
        ] = {}

    def clear(self) -> None:
        self._fields = {}
        self._functions = {}
        self._warnings = {}

    @property
    def fields(self) -> Mapping[str, NewFieldParams]:
        """Custom need fields.

        These fields can be added via sphinx configuration,
        and also via the `add_field` API function.

        They are added to the each needs data item,
        and as directive options on `NeedDirective` and `NeedserviceDirective`.
        """
        return self._fields

    def add_field(
        self,
        name: str,
        description: str,
        source: Literal[
            "needs_extra_options",
            "needs_fields",
            "add_extra_option",
            "add_field",
            "service",
        ],
        *,
        schema: FieldStringSchemaType
        | FieldBooleanSchemaType
        | FieldIntegerSchemaType
        | FieldNumberSchemaType
        | FieldMultiValueSchemaType
        | None = None,
        nullable: None | bool = None,
        default: None | Any = None,
        predicates: None | list[tuple[str, Any]] = None,
        parse_variants: None | bool = None,
        override: bool = False,
    ) -> None:
        """Adds a need field to the configuration."""
        if name in NeedsCoreFields:
            from sphinx_needs.exceptions import (
                NeedsApiConfigWarning,  # avoid circular import
            )

            raise NeedsApiConfigWarning(
                f"Cannot add need field with name {name!r}"
                + (f" ({description!r})" if description else "")
                + ", as it is already used as a core field name."
            )
        if (existing := self._fields.get(name)) is not None:
            message = f"Duplicate need field {name!r}, registered via {existing.source}({existing.description!r}) and {source}({description!r})."
            if override:
                log_warning(LOGGER, message, "config", None)
            else:
                from sphinx_needs.exceptions import (
                    NeedsApiConfigWarning,  # avoid circular import
                )

                raise NeedsApiConfigWarning(message)
        self._fields[name] = NewFieldParams(
            source=source,
            description=description,
            schema=schema,
            nullable=nullable,
            default=default,
            predicates=predicates,
            parse_variants=parse_variants,
        )

    @property
    def functions(self) -> Mapping[str, NeedFunctionsType]:
        """Dynamic functions that are added by the user."""
        return self._functions

    def add_function(self, function: DynamicFunction, name: str | None = None) -> None:
        """Adds a dynamic function to the configuration."""
        func_name = function.__name__ if name is None else name
        if func_name in self._functions:
            log_warning(
                LOGGER,
                f"Dynamic function {func_name} already registered.",
                "config",
                None,
            )
        self._functions[func_name] = {"name": func_name, "function": function}

    @property
    def warnings(
        self,
    ) -> Mapping[str, str | Callable[[NeedItem, SphinxLoggerAdapter], bool]]:
        """Warning handlers that are added by the user,
        then called at the end of the build.
        """
        return self._warnings

    def add_warning(
        self,
        name: str,
        filter: str | Callable[[NeedItem, SphinxLoggerAdapter], bool],
    ) -> None:
        """Adds a warning handler to the configuration."""
        self._warnings[name] = filter


_NEEDS_CONFIG = _Config()


class ConstraintFailedType(TypedDict):
    """Defines what to do if a constraint is not fulfilled"""

    on_fail: list[Literal["warn", "break"]]
    """warn: log a warning, break: raise a ``NeedsConstraintFailed`` exception"""
    style: list[str]
    """How to style the rendered need."""
    force_style: bool
    """If True, append styles to existing styles, else replace existing styles."""


class ExternalSource(TypedDict, total=False):
    """Defines an external source to import needs from.

    External source will be a JSON with the key path::

        versions -> <local project version> -> needs -> <list of needs>

    """

    # either
    json_path: str
    """A local path to a JSON file"""
    # or
    json_url: str
    """A remote URL to a JSON object"""

    version: str
    """Override `current_version` from loaded JSON (optional)"""

    base_url: str
    """Used to create the `external_url` field for each need item (required)"""

    target_url: str
    """Used to create the `external_url` field for each need item (optional)"""

    id_prefix: str
    """Prefix all IDs from the external source with this string (optional, uppercased)"""

    css_class: str
    """Added as the `external_css` field for each need item (optional)"""

    allow_type_coercion: bool
    """If true, values will be coerced to the expected type where possible (optional, default: True)."""


GlobalOptionsType = dict[str, Any]
"""Default values given to specified fields of needs

Values can be:

- a tuple: ``(value, filter_string)``, where the default is only applied if the filter_string is fulfilled
- a tuple: ``(value, filter_string, alternative default)``, 
    where the default is applied if the filter_string is fulfilled, 
    otherwise the alternative default is used
- a list of the tuples above
- otherwise, always set as the given value
"""


class LinkOptionsType(TypedDict, total=False):
    """Options for links between needs"""

    option: Required[str]
    """The name of the link option"""
    incoming: str
    """The incoming link title"""
    outgoing: str
    """The outgoing link title"""
    copy: bool
    """Copy to common links data. Default: False"""
    color: str
    """Used for needflow. Default: #000000"""
    style: str
    """Used for needflow. Default: solid"""
    style_part: str
    """Used for needflow. Default: '[dotted]'"""
    style_start: str
    """Used for needflow. Default: '-'"""
    style_end: str
    """Used for needflow. Default: '->'"""
    allow_dead_links: bool
    """If True, add a 'forbidden' class to dead links"""
    schema: NotRequired[ExtraLinkSchemaType]
    """
    A JSON schema for the link option.
    
    If given, the schema will apply to all needs that use this link option.
    The schema is applied locally on unresolved links, i.e. on the list of string ids.
    For more granular control and graph traversal, use the `needs_schema_definitions` configuration.
    """
    default: NotRequired[Any]
    """Default value for the link option."""
    predicates: NotRequired[list[tuple[str, Any]]]
    """List of (need filter, value) pairs for predicate default values."""
    parse_variants: NotRequired[bool]
    """Whether variants are parsed in this field."""


class NeedType(TypedDict):
    """Defines a need type"""

    directive: str
    """The directive name."""
    title: str
    """A human readable title."""
    prefix: str
    """The prefix to use for the need ID."""
    color: NotRequired[str]
    """The default color to use in diagrams (default: "#000000")."""
    style: NotRequired[str]
    """The default node style to use in diagrams (default: "node")."""


class NeedFields(TypedDict):
    """Defines a field for needs"""

    description: NotRequired[str]
    """A description of the field."""
    schema: NotRequired[FieldSchemaTypes]
    """
    A JSON schema definition for the field.
    
    If given, the schema will apply to all needs that use this option.
    For more granular control, use the `needs_schema_definitions` configuration.
    """
    nullable: NotRequired[bool]
    """Whether the field allows unset values."""
    default: NotRequired[Any]
    """Default value for the field."""
    predicates: NotRequired[list[tuple[str, Any]]]
    """List of (need filter, value) pairs for predicate default values."""
    parse_variants: NotRequired[bool]
    """Whether variants are parsed in this field."""


class NeedField(NeedFields):
    """Defines an extra option for needs"""

    name: str
    """The name of the option."""


class NeedStatusesOption(TypedDict):
    name: str
    description: NotRequired[str]


class NeedTagsOption(TypedDict):
    name: str
    description: NotRequired[str]


def _abs_path(value: Any, base: Path) -> Any:
    """Convert a possibly relative path to an absolute path,
    based on the given base path.
    """
    if isinstance(value, str | Path):
        path = Path(value)
        if not path.is_absolute():
            path = base / path
            return str(path.resolve())
    return value


def _abs_path_external_sources(
    value: list[ExternalSource], base: Path
) -> list[ExternalSource]:
    """Convert possibly relative paths in external sources to absolute paths,
    based on the given base path.
    """
    new_sources: list[ExternalSource] = []
    for source in value:
        new_source = source.copy()
        if "json_path" in source:
            new_source["json_path"] = _abs_path(source["json_path"], base)
        new_sources.append(new_source)
    return new_sources


@dataclass
class NeedsSphinxConfig:
    """A wrapper around the Sphinx configuration,
    to access the needs specific configuration values,
    with working type annotations.
    """

    # This is a modification of the normal dataclass pattern,
    # such that we simply redirect all attribute access to the
    # Sphinx config object, but in a manner where type annotations will work
    # for static type analysis.
    # Note also that we treat `functions` and `warnings` as special-cases,
    # since these configurations can also be added to dynamically via the API

    def __init__(self, config: _SphinxConfig) -> None:
        super().__setattr__("_config", config)

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("__") or name in ("_config", "functions", "warnings"):
            return super().__getattribute__(name)
        if name.startswith("_"):
            name = name[1:]
        return getattr(super().__getattribute__("_config"), f"needs_{name}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("__") or name in ("_config", "functions", "warnings"):
            return super().__setattr__(name, value)
        if name.startswith("_"):
            name = name[1:]
        return setattr(super().__getattribute__("_config"), f"needs_{name}", value)

    @classmethod
    def add_config_values(cls, app: Sphinx) -> None:
        """Add all config values to the Sphinx application."""
        for item in fields(cls):
            if item.default_factory is not MISSING:
                default = item.default_factory()
            elif item.default is not MISSING:
                default = item.default
            else:
                raise Exception(
                    f"Config item {item.name} has no default value or factory."
                )
            name = item.name
            if name.startswith("_"):
                name = name[1:]
            app.add_config_value(
                f"needs_{name}",
                default,
                item.metadata["rebuild"],
                types=item.metadata["types"],
            )

    @classmethod
    def field_names(cls) -> set[str]:
        """Get all config fields (without ``needs_`` prefix)"""
        names = [field.name for field in fields(cls)]
        return {name[1:] if name.startswith("_") else name for name in names}

    @classmethod
    def convert_field_value(
        cls, name: str, value: Any, base_path: Path, prefix: str = ""
    ) -> Any:
        """Convert a config field value from toml, if a converter is defined."""
        try:
            _field = next(
                field
                for field in fields(cls)
                if field.name in (f"{prefix}{name}", f"_{prefix}{name}")
            )
        except StopIteration:
            raise ValueError(f"Unknown config field: {name!r}")
        converter = _field.metadata.get("toml_convert")
        if converter:
            return converter(value, base_path)
        return value

    @classmethod
    def get_default(cls, name: str) -> Any:
        """Get the default value for a config item."""
        _field = next(
            field for field in fields(cls) if field.name in (name, f"_{name}")
        )
        if _field.default_factory is not MISSING:
            return _field.default_factory()
        return _field.default

    from_toml: str | None = field(
        default=None, metadata={"rebuild": "env", "types": (str, type(None))}
    )
    """Path to a TOML file to load configuration from."""

    from_toml_table: list[str] = field(
        default_factory=list, metadata={"rebuild": "env", "types": (list,)}
    )
    """Path to the root table in the toml file to load configuration from."""

    schema_validation_enabled: bool = field(
        default=True,
        metadata={"rebuild": "env", "types": (bool,)},
    )
    """Enable schema validation for needs."""
    schema_definitions: SchemasFileRootType = field(
        default_factory=lambda: cast(SchemasFileRootType, {}),
        metadata={"rebuild": "env", "types": (dict,)},
    )
    """Schema definitions to write complex validations based on selectors."""

    schema_definitions_from_json: str | None = field(
        default=None,
        metadata={
            "rebuild": "env",
            "types": (str, type(None)),
            "toml_convert": _abs_path,
        },
    )
    """Path to a JSON file to load the schemas from."""

    schema_debug_active: bool = field(
        default=False,
        metadata={"rebuild": "env", "types": (bool,)},
    )
    """Activate the debug mode for schema validation to dump JSON/schema files and messages."""

    schema_debug_path: str = field(
        default="schema_debug",
        metadata={"rebuild": "env", "types": (str,), "toml_convert": _abs_path},
    )
    """
    Path to the directory where the debug files are stored.

    If the path is relative, the caller needs to make sure
    it gets converted to a use case specific absolute path, e.g.
    with confdir for Sphinx.
    """

    schema_debug_ignore: list[str] = field(
        default_factory=lambda: [
            "field_success",
            "extra_link_success",
            "select_success",
            "select_fail",
            "local_success",
            "network_local_success",
        ],
        metadata={
            "rebuild": "env",
            "types": (list,),
        },
    )
    """List of scenarios that are ignored for dumping debug information."""

    types: list[NeedType] = field(
        default_factory=lambda: [
            {
                "directive": "req",
                "title": "Requirement",
                "prefix": "R_",
                "color": "#BFD8D2",
                "style": "node",
            },
            {
                "directive": "spec",
                "title": "Specification",
                "prefix": "S_",
                "color": "#FEDCD2",
                "style": "node",
            },
            {
                "directive": "impl",
                "title": "Implementation",
                "prefix": "I_",
                "color": "#DF744A",
                "style": "node",
            },
            {
                "directive": "test",
                "title": "Test Case",
                "prefix": "T_",
                "color": "#DCB239",
                "style": "node",
            },
            # Kept for backwards compatibility
            {
                "directive": "need",
                "title": "Need",
                "prefix": "N_",
                "color": "#9856a5",
                "style": "node",
            },
        ],
        metadata={"rebuild": "html", "types": ()},
    )
    """Custom user need types"""
    include_needs: bool = field(
        default=True, metadata={"rebuild": "html", "types": (bool,)}
    )
    id_length: int = field(default=5, metadata={"rebuild": "html", "types": (int,)})
    """Length of auto-generated IDs (without prefix)"""
    id_from_title: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Base auto-generated IDs on the title."""
    id_required: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Require an ID for each need."""
    id_regex: str = field(
        default="^[A-Z0-9_]{5,}", metadata={"rebuild": "html", "types": ()}
    )
    """Regex to validate need IDs."""
    show_link_type: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Show the link type in the need incoming/outgoing roles."""
    show_link_title: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Show the link title in the need incoming/outgoing roles."""
    show_link_id: bool = field(
        default=True, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Show the link ID in the need incoming/outgoing roles."""
    file: None | str = field(
        default=None,
        metadata={"rebuild": "html", "types": (), "toml_convert": _abs_path},
    )
    """Path to the needs builder input file."""
    table_columns: str = field(
        default="ID;TITLE;STATUS;TYPE;OUTGOING;TAGS",
        metadata={"rebuild": "html", "types": (str,)},
    )
    """Default columns to show in the needtable."""
    table_style: str = field(
        default="DATATABLES", metadata={"rebuild": "html", "types": (str,)}
    )
    """Default style for the needtable."""
    role_need_template: str = field(
        default="{title} ({id})", metadata={"rebuild": "html", "types": (str,)}
    )
    """Template for the need role output."""
    role_need_max_title_length: int = field(
        default=30, metadata={"rebuild": "html", "types": (int,)}
    )
    """Maximum length of the title in the need role output."""
    _fields: dict[str, NeedFields] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    _extra_options: list[str | NeedField] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """List of extra options for needs, that get added as directive options and need fields."""

    title_optional: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, the title of a need directive is optional."""
    max_title_length: int = field(
        default=-1, metadata={"rebuild": "html", "types": (int,)}
    )
    """Maximum length of an auto-generated need title."""
    title_from_content: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Create auto-generated titles from the first sentence of content."""
    diagram_template: str = field(
        default=DEFAULT_DIAGRAM_TEMPLATE,
        metadata={"rebuild": "html", "types": (str,)},
    )
    """Template for node content in needflow diagrams (with plantuml engine)."""
    _functions: list[DynamicFunction] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """List of dynamic functions."""

    @property
    def functions(self) -> Mapping[str, NeedFunctionsType]:
        """Dynamic functions that are added by the user.

        These functions can be added via sphinx configuration,
        but also via the `add_dynamic_function` API function.
        """
        return _NEEDS_CONFIG.functions

    _global_options: GlobalOptionsType = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Default values given to specified fields of needs"""

    duration_option: str = field(
        default="duration", metadata={"rebuild": "html", "types": (str,)}
    )
    """Added to options on need directives, and key on need data items, for use by ``needgantt``"""
    completion_option: str = field(
        default="completion", metadata={"rebuild": "html", "types": (str,)}
    )
    """Added to options on need directives, and key on need data items, for use by ``needgantt``"""
    needextend_strict: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Raise exceptions if a needextend filter does not match any needs."""
    statuses: list[NeedStatusesOption] = field(
        default_factory=list, metadata={"rebuild": "html", "types": ()}
    )
    """If given, only the defined statuses are allowed."""
    tags: list[NeedTagsOption] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """If given, only the defined tags are allowed."""
    css: str = field(
        default="modern.css",
        metadata={"rebuild": "html", "types": (str,), "toml_convert": _abs_path},
    )
    """Path of css file, which shall be used for need style"""
    part_prefix: str = field(
        default="→\xa0", metadata={"rebuild": "html", "types": (str,)}
    )
    """Prefix for need_part output in tables"""
    _extra_links: list[LinkOptionsType] = field(
        default_factory=list, metadata={"rebuild": "html", "types": ()}
    )
    """List of additional link types between needs (internal config, use schema for access after config resolution)"""
    report_dead_links: bool = field(
        default=True, metadata={"rebuild": "html", "types": (bool,)}
    )
    """DEPRECATED: Use ``suppress_warnings = ["needs.link_outgoing"]`` instead."""
    filter_data: dict[str, str] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Additional context data for filters."""
    allow_unsafe_filters: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """Allow filters to change the need data."""
    filter_max_time: int | float | None = field(
        default=None, metadata={"rebuild": "html", "types": (type(None), int, float)}
    )
    """Warn if process_filter runs for longer than this time (in seconds)."""
    uml_process_max_time: int | float | None = field(
        default=None, metadata={"rebuild": "html", "types": (type(None), int, float)}
    )
    """Warn if process_needuml runs for longer than this time (in seconds)."""
    flow_engine: Literal["plantuml", "graphviz"] = field(
        default="plantuml", metadata={"rebuild": "env", "types": (str,)}
    )
    """The rendering engine to use for needflow diagrams."""
    flow_show_links: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, show links in needflow diagrams by default."""
    flow_link_types: list[str] = field(
        default_factory=lambda: ["links"], metadata={"rebuild": "html", "types": ()}
    )
    """Defines the link_types to show in a needflow diagram."""
    _warnings: dict[str, Any] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Defines warnings to be checked at the end of the build (name -> string filter / filter function)."""

    @property
    def warnings(
        self,
    ) -> Mapping[str, str | Callable[[NeedItem, SphinxLoggerAdapter], bool]]:
        """Defines warnings to be checked at the end of the build (name -> string filter / filter function).

        These handlers can be added via sphinx configuration,
        but also via the `add_warning` API function.
        """
        return _NEEDS_CONFIG.warnings

    warnings_always_warn: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, log individual warnings per warning check failed."""
    layouts: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Defines custom layouts for needs rendering."""
    default_layout: str = field(
        default="clean", metadata={"rebuild": "html", "types": (str,)}
    )
    """The default layout to use for needs rendering."""
    default_style: None | str = field(
        default=None, metadata={"rebuild": "html", "types": ()}
    )
    """The default style to use for needs rendering."""
    flow_configs: dict[str, str] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Additional configuration for needflow diagrams (plantuml engine)."""
    graphviz_styles: dict[str, GraphvizStyleType] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Additional configuration for needflow diagrams (graphviz engine)."""
    template_folder: str = field(
        default="needs_templates/",
        metadata={"rebuild": "html", "types": (str,), "toml_convert": _abs_path},
    )
    """Path to the template folder for needs rendering templates."""
    services: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    """Extra configuration options for services."""
    service_all_data: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, unknown sevice option data is shown in the need content."""
    import_keys: dict[str, str] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Mapping of keys that can be used as needimport arguments and replaced by the value."""
    external_needs: list[ExternalSource] = field(
        default_factory=list,
        metadata={
            "rebuild": "html",
            "types": (list,),
            "toml_convert": _abs_path_external_sources,
        },
    )
    """List of external sources to load needs from."""
    builder_filter: str = field(
        default="is_external==False", metadata={"rebuild": "html", "types": (str,)}
    )
    """Filter string to use for the needs builder."""
    table_classes: list[str] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """Additional classes to set for needs and needtable."""
    string_links: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """In the need representation, find and render links in field values."""
    build_json: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, the JSON needs file should be built."""
    reproducible_json: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, the JSON needs file should be idempotent for multiple builds fo the same documentation."""
    json_exclude_fields: list[str] = field(
        default_factory=lambda: [
            name
            for name, params in NeedsCoreFields.items()
            if params.get("exclude_json")
        ],
        metadata={"rebuild": "html", "types": (list,)},
    )
    """List of keys to exclude from the JSON needs file."""
    json_remove_defaults: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, remove need fields with default values from the JSON needs file."""
    build_needumls: str = field(
        default="", metadata={"rebuild": "html", "types": (str,)}
    )
    permalink_file: str = field(
        default="permalink.html", metadata={"rebuild": "html", "types": (str,)}
    )
    """Permalink related config values.
    path to permalink.html; absolute path from web-root
    """
    permalink_data: str = field(
        default="needs.json", metadata={"rebuild": "html", "types": (str,)}
    )
    """path to needs.json relative to permalink.html"""
    report_template: str = field(
        default="", metadata={"rebuild": "html", "types": (str,)}
    )
    """path to needs_report_template file which is based on the conf.py directory."""

    constraints: dict[str, dict[str, str]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Mapping of constraint name, to check name, to filter string.
    There are also some special keys for a constraint:

    - severity: The severity of the constraint. This is used to determine what to do if the constraint is not fulfilled.
    - error_message: A help text for the constraint, can include Jinja2 variables.
    """
    constraint_failed_options: dict[str, ConstraintFailedType] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Mapping of constraint severity to what to do if a constraint is not fulfilled."""
    constraints_failed_color: str = field(
        default="", metadata={"rebuild": "html", "types": (str,)}
    )
    """DEPRECATED: Use constraint_failed_options instead."""

    # add variants option
    variants: dict[str, str] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Mapping of variant name to filter string."""
    _variant_options: list[str] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """List of need fields that may contain variants."""

    # add render context option
    render_context: dict[str, Any] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Jinja context for rendering templates"""

    # add config for needs_id_builder
    build_json_per_id: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    build_json_per_id_path: str = field(
        default="needs_id", metadata={"rebuild": "html", "types": (str,)}
    )

    debug_measurement: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, log runtime information for various functions."""
    debug_filters: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, log filter processing runtime information."""
