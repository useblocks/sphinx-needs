from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from typing import TYPE_CHECKING, Any, Callable, Dict, Literal, TypedDict

from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_needs.defaults import DEFAULT_DIAGRAM_TEMPLATE, NEEDS_TABLES_CLASSES

if TYPE_CHECKING:
    from sphinx.util.logging import SphinxLoggerAdapter
    from typing_extensions import Required

    from sphinx_needs.data import NeedsInfoType


class Config:
    """
    Stores sphinx-needs specific configuration values.

    This is used to avoid the usage of the sphinx internal config option, as these can be reset or cleaned in
    unspecific order during different events.

    So this Config class somehow collects possible configurations and stores it in a save way.
    """

    def __init__(self) -> None:
        self._extra_options: dict[str, Callable[[str], Any]] = {}
        self._warnings: dict[
            str, str | Callable[[NeedsInfoType, SphinxLoggerAdapter], bool]
        ] = {}

    def clear(self) -> None:
        self._extra_options = {}
        self._warnings = {}

    @property
    def extra_options(self) -> dict[str, Callable[[str], Any]]:
        """Options that are dynamically added to `NeedDirective` & `NeedserviceDirective`,
        after the config is initialized.

        These fields are also added to the each needs data item.

        :returns: Mapping of name to validation function
        """
        return self._extra_options

    @property
    def warnings(
        self,
    ) -> dict[str, str | Callable[[NeedsInfoType, SphinxLoggerAdapter], bool]]:
        """Warning handlers that are added by the user,
        then called at the end of the build.
        """
        return self._warnings


NEEDS_CONFIG = Config()


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


GlobalOptionsType = Dict[str, Any]
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
    """Copy to common links data. Default: True"""
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

    def __init__(self, config: _SphinxConfig) -> None:
        super().__setattr__("_config", config)

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("__"):
            return super().__getattribute__(name)
        return getattr(super().__getattribute__("_config"), f"needs_{name}")

    def __setattr__(self, name: str, value: Any) -> None:
        return setattr(super().__getattribute__("_config"), f"needs_{name}", value)

    types: list[dict[str, Any]] = field(
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
    need_name: str = field(
        default="Need", metadata={"rebuild": "html", "types": (str,)}
    )
    spec_name: str = field(
        default="Specification", metadata={"rebuild": "html", "types": (str,)}
    )
    id_prefix_needs: str = field(
        default="", metadata={"rebuild": "html", "types": (str,)}
    )
    id_prefix_specs: str = field(
        default="", metadata={"rebuild": "html", "types": (str,)}
    )
    id_length: int = field(default=5, metadata={"rebuild": "html", "types": (int,)})
    id_from_title: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    specs_show_needlist: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    id_required: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    id_regex: str = field(
        default="^[A-Z0-9_]{5,}", metadata={"rebuild": "html", "types": ()}
    )
    show_link_type: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    show_link_title: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    show_link_id: bool = field(
        default=True, metadata={"rebuild": "html", "types": (bool,)}
    )
    file: None | str = field(default=None, metadata={"rebuild": "html", "types": ()})
    table_columns: str = field(
        default="ID;TITLE;STATUS;TYPE;OUTGOING;TAGS",
        metadata={"rebuild": "html", "types": (str,)},
    )
    table_style: str = field(
        default="DATATABLES", metadata={"rebuild": "html", "types": (str,)}
    )
    role_need_template: str = field(
        default="{title} ({id})", metadata={"rebuild": "html", "types": (str,)}
    )
    role_need_max_title_length: int = field(
        default=30, metadata={"rebuild": "html", "types": (int,)}
    )
    extra_options: list[str] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    title_optional: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    max_title_length: int = field(
        default=-1, metadata={"rebuild": "html", "types": (int,)}
    )
    title_from_content: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    diagram_template: str = field(
        default=DEFAULT_DIAGRAM_TEMPLATE,
        metadata={"rebuild": "html", "types": (str,)},
    )
    functions: list[Callable[..., Any]] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    global_options: GlobalOptionsType = field(
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
    statuses: list[dict[str, str]] = field(
        default_factory=list, metadata={"rebuild": "html", "types": ()}
    )
    """If given, only the defined status are allowed.
    Values needed for each status:
    * name
    * description
    Example: [{"name": "open", "description": "open status"}, {...}, {...}]
    """
    tags: list[dict[str, str]] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """If given, only the defined tags are allowed.
    Values needed for each tag:
    * name
    * description
    Example: [{"name": "new", "description": "new needs"}, {...}, {...}]
    """
    css: str = field(
        default="modern.css", metadata={"rebuild": "html", "types": (str,)}
    )
    """Path of css file, which shall be used for need style"""
    part_prefix: str = field(
        default="→\xa0", metadata={"rebuild": "html", "types": (str,)}
    )
    """Prefix for need_part output in tables"""
    extra_links: list[LinkOptionsType] = field(
        default_factory=list, metadata={"rebuild": "html", "types": ()}
    )
    """List of additional link types between needs"""
    report_dead_links: bool = field(
        default=True, metadata={"rebuild": "html", "types": (bool,)}
    )
    """DEPRECATED: Use ``suppress_warnings = ["needs.link_outgoing"]`` instead."""
    filter_data: dict[str, Any] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    allow_unsafe_filters: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    flow_show_links: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    flow_link_types: list[str] = field(
        default_factory=lambda: ["links"], metadata={"rebuild": "html", "types": ()}
    )
    """Defines the link_types to show in a needflow diagram."""
    warnings: dict[str, Any] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    warnings_always_warn: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    layouts: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    default_layout: str = field(
        default="clean", metadata={"rebuild": "html", "types": (str,)}
    )
    default_style: None | str = field(
        default=None, metadata={"rebuild": "html", "types": ()}
    )
    flow_configs: dict[str, str] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    template_folder: str = field(
        default="needs_templates/", metadata={"rebuild": "html", "types": (str,)}
    )
    services: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": ()}
    )
    service_all_data: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    debug_no_external_calls: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    external_needs: list[ExternalSource] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )
    """List of external sources to load needs from."""
    builder_filter: str = field(
        default="is_external==False", metadata={"rebuild": "html", "types": (str,)}
    )
    table_classes: list[str] = field(
        default_factory=lambda: NEEDS_TABLES_CLASSES,
        metadata={"rebuild": "html", "types": (list,)},
    )
    """Additional classes to set for needs and needtable."""
    string_links: dict[str, dict[str, Any]] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    build_json: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, the JSON needs file should be built."""
    reproducible_json: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, the JSON needs file should be idempotent for multiple builds fo the same documentation."""
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
    variant_options: list[str] = field(
        default_factory=list, metadata={"rebuild": "html", "types": (list,)}
    )

    # add render context option
    render_context: dict[str, Any] = field(
        default_factory=dict, metadata={"rebuild": "html", "types": (dict,)}
    )
    """Jinja context for rendering templates"""

    debug_measurement: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    # add config for needs_id_builder
    build_json_per_id: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    build_json_per_id_path: str = field(
        default="needs_id", metadata={"rebuild": "html", "types": (str,)}
    )

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
            app.add_config_value(
                f"needs_{item.name}",
                default,
                item.metadata["rebuild"],
                types=item.metadata["types"],
            )
