"""Module to control access to sphinx-needs data,
which is stored in the Sphinx environment.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    NewType,
    TypedDict,
)

from sphinx.util.logging import getLogger

from sphinx_needs.logging import log_warning
from sphinx_needs.views import NeedsView

if TYPE_CHECKING:
    from docutils.nodes import Text
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment
    from typing_extensions import NotRequired, Required

    from sphinx_needs.nodes import Need
    from sphinx_needs.services.manager import ServiceManager


LOGGER = getLogger(__name__)

ENV_DATA_VERSION: Final = 2
"""Version of the data stored in the environment.

See https://www.sphinx-doc.org/en/master/extdev/index.html#extension-metadata
"""


class NeedsPartType(TypedDict):
    """Data for a single need part."""

    id: str
    """ID of the part"""
    content: str
    """Content of the part."""
    links: list[str]
    """List of need IDs, which are referenced by this part."""
    links_back: list[str]
    """List of need IDs, which are referencing this part."""

    # note back links for each type are also set dynamically in post_process_needs_data (-> create_back_links)


class CoreFieldParameters(TypedDict):
    """Parameters for core fields."""

    description: str
    """Description of the field."""
    schema: dict[str, Any]
    """JSON schema for the field."""
    allow_default: NotRequired[Literal["str", "str_list"]]
    """Whether the field allows custom default values to be set, and their type,
    via needs_global_options (False if not present).
    """
    allow_extend: NotRequired[bool]
    """Whether field can be modified by needextend (False if not present)."""
    allow_df: NotRequired[bool]
    """Whether dynamic functions are allowed for this field (False if not present)."""
    deprecate_df: NotRequired[bool]
    """Whether dynamic functions are deprecated for this field (False if not present)."""
    show_in_layout: NotRequired[bool]
    """Whether to show the field in the rendered layout of the need by default (False if not present)."""
    exclude_external: NotRequired[bool]
    """Whether field should be excluded when loading external needs (False if not present)."""
    exclude_import: NotRequired[bool]
    """Whether field should be excluded when importing needs (False if not present)."""
    exclude_json: NotRequired[bool]
    """Whether field should be part of the default exclusions from the JSON representation (False if not present)."""


NeedsCoreFields: Final[Mapping[str, CoreFieldParameters]] = {
    "id": {"description": "ID of the data.", "schema": {"type": "string"}},
    "docname": {
        "description": "Name of the document where the need is defined (None if external).",
        "schema": {"type": ["string", "null"], "default": None},
        "exclude_external": True,
        "exclude_import": True,
    },
    "lineno": {
        "description": "Line number where the need is defined (None if external).",
        "schema": {"type": ["integer", "null"], "default": None},
        "exclude_external": True,
        "exclude_import": True,
    },
    "lineno_content": {
        "description": "Line number on which the need content starts (None if external).",
        "schema": {"type": ["integer", "null"], "default": None},
        "exclude_json": True,
        "exclude_external": True,
        "exclude_import": True,
    },
    "title": {
        "description": "Title of the need.",
        "schema": {"type": "string"},
        "allow_df": True,
    },
    "status": {
        "description": "Status of the need.",
        "schema": {"type": ["string", "null"], "default": None},
        "show_in_layout": True,
        "allow_default": "str",
        "allow_df": True,
        "allow_extend": True,
    },
    "tags": {
        "description": "List of tags.",
        "schema": {"type": "array", "items": {"type": "string"}, "default": []},
        "show_in_layout": True,
        "allow_default": "str_list",
        "allow_df": True,
        "allow_extend": True,
    },
    "collapse": {
        "description": "Hide the meta-data information of the need.",
        "schema": {"type": "boolean", "default": False},
        "exclude_json": True,
        "exclude_external": True,
        "allow_extend": True,
    },
    "hide": {
        "description": "If true, the need is not rendered.",
        "schema": {"type": "boolean", "default": False},
        "exclude_json": True,
        "exclude_external": True,
        "allow_extend": True,
    },
    "layout": {
        "description": "Key of the layout, which is used to render the need.",
        "schema": {"type": ["string", "null"], "default": None},
        "show_in_layout": True,
        "allow_default": "str",
        "exclude_external": True,
    },
    "style": {
        "description": "Comma-separated list of CSS classes (all appended by `needs_style_`).",
        "schema": {"type": ["string", "null"], "default": None},
        "show_in_layout": True,
        "exclude_external": True,
        "allow_default": "str",
        "allow_df": True,
        "allow_extend": True,
    },
    "arch": {
        "description": "Mapping of uml key to uml content.",
        "schema": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "default": {},
        },
    },
    "is_external": {
        "description": "If true, no node is created and need is referencing external url.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
        "exclude_import": True,
    },
    "external_url": {
        "description": "URL of the need, if it is an external need.",
        "schema": {"type": ["string", "null"], "default": None},
        "show_in_layout": True,
        "exclude_import": True,
    },
    "external_css": {
        "description": "CSS class name, added to the external reference.",
        "schema": {"type": "string", "default": ""},
        "exclude_import": True,
    },
    "type": {
        "description": "Type of the need.",
        "schema": {"type": "string", "default": ""},
        "deprecate_df": True,
    },
    "type_name": {
        "description": "Name of the type.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
        "deprecate_df": True,
    },
    "type_prefix": {
        "description": "Prefix of the type.",
        "schema": {"type": "string", "default": ""},
        "exclude_json": True,
        "exclude_external": True,
        "exclude_import": True,
        "deprecate_df": True,
    },
    "type_color": {
        "description": "Hexadecimal color code of the type.",
        "schema": {"type": "string", "default": ""},
        "exclude_json": True,
        "exclude_external": True,
        "exclude_import": True,
        "deprecate_df": True,
    },
    "type_style": {
        "description": "Style of the type.",
        "schema": {"type": "string", "default": ""},
        "exclude_json": True,
        "exclude_external": True,
        "exclude_import": True,
        "deprecate_df": True,
    },
    "is_modified": {
        "description": "Whether the need was modified by needextend.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
        "exclude_import": True,
    },
    "modifications": {
        "description": "Number of modifications by needextend.",
        "schema": {"type": "integer", "default": 0},
        "exclude_external": True,
        "exclude_import": True,
    },
    "is_need": {
        "description": "Whether the need is a need.",
        "schema": {"type": "boolean", "default": True},
        "exclude_external": True,
        "exclude_import": True,
    },
    "is_part": {
        "description": "Whether the need is a part.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
        "exclude_import": True,
    },
    "parts": {
        "description": "Mapping of parts, a.k.a. sub-needs, IDs to data that overrides the need's data",
        "schema": {
            "type": "object",
            "additionalProperties": {"type": "object"},
            "default": {},
        },
    },
    "id_parent": {
        "description": "<parent ID>, or <self ID> if not a part.",
        "exclude_json": True,
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "id_complete": {
        "description": "<parent ID>.<self ID>, or <self ID> if not a part.",
        "exclude_json": True,
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "jinja_content": {
        "description": "Whether the content should be pre-processed by jinja.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
    },
    "template": {
        "description": "Template of the need.",
        "schema": {"type": ["string", "null"], "default": None},
        "exclude_external": True,
    },
    "pre_template": {
        "description": "Pre-template of the need.",
        "schema": {"type": ["string", "null"], "default": None},
        "exclude_external": True,
    },
    "post_template": {
        "description": "Post-template of the need.",
        "schema": {"type": ["string", "null"], "default": None},
        "exclude_external": True,
    },
    "content": {
        "description": "Content of the need.",
        "schema": {"type": "string", "default": ""},
    },
    "pre_content": {
        "description": "Pre-content of the need.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "post_content": {
        "description": "Post-content of the need.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "has_dead_links": {
        "description": "True if any links reference need ids that are not found in the need list.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
        "exclude_import": True,
    },
    "has_forbidden_dead_links": {
        "description": "True if any links reference need ids that are not found in the need list, and the link type does not allow dead links.",
        "schema": {"type": "boolean", "default": False},
        "exclude_external": True,
        "exclude_import": True,
    },
    "constraints": {
        "description": "List of constraint names, which are defined for this need.",
        "schema": {"type": "array", "items": {"type": "string"}, "default": []},
        "allow_default": "str_list",
        "allow_df": True,
        "allow_extend": True,
    },
    "constraints_results": {
        "description": "Mapping of constraint name, to check name, to result.",
        "schema": {
            "type": "object",
            "additionalProperties": {"type": "object"},
            "default": {},
        },
        "exclude_external": True,
        "exclude_import": True,
    },
    "constraints_passed": {
        "description": "True if all constraints passed, False if any failed, None if not yet checked.",
        "schema": {"type": "boolean", "default": True},
        "exclude_external": True,
        "exclude_import": True,
    },
    "constraints_error": {
        "description": "An error message set if any constraint failed, and `error_message` field is set in config.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "doctype": {
        "description": "Type of the document where the need is defined, e.g. '.rst'.",
        "schema": {"type": "string", "default": ".rst"},
    },
    "sections": {
        "description": "Sections of the need.",
        "schema": {"type": "array", "items": {"type": "string"}, "default": []},
        "exclude_import": True,
    },
    "section_name": {
        "description": "Simply the first section.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
    "signature": {
        "description": "Derived from a docutils desc_name node.",
        "schema": {"type": "string", "default": ""},
        "show_in_layout": True,
        "exclude_import": True,
    },
    "parent_need": {
        "description": "Simply the first parent id.",
        "schema": {"type": "string", "default": ""},
        "exclude_external": True,
        "exclude_import": True,
    },
}


class NeedsInfoType(TypedDict, total=False):
    """Data for a single need."""

    id: Required[str]
    """ID of the data."""

    docname: Required[str | None]
    """Name of the document where the need is defined (None if external)."""
    lineno: Required[int | None]
    """Line number where the need is defined (None if external)."""
    lineno_content: Required[int | None]
    """Line number on which the need content starts (None if external)."""

    # meta information
    title: Required[str]
    """Title of the need."""
    status: Required[None | str]
    tags: Required[list[str]]

    # rendering information
    collapse: Required[bool]
    """Hide the meta-data information of the need."""
    hide: Required[bool]
    """If true, the need is not rendered."""
    layout: Required[None | str]
    """Key of the layout, which is used to render the need."""
    style: Required[None | str]
    """Comma-separated list of CSS classes (all appended by `needs_style_`)."""

    # TODO why is it called arch?
    arch: Required[dict[str, str]]
    """Mapping of uml key to uml content."""

    # external reference information
    is_external: Required[bool]
    """If true, no node is created and need is referencing external url."""
    external_url: Required[None | str]
    """URL of the need, if it is an external need."""
    external_css: Required[str]
    """CSS class name, added to the external reference."""

    # type information (based on needs_types config)
    type: Required[str]
    type_name: Required[str]
    type_prefix: Required[str]
    type_color: Required[str]
    """Hexadecimal color code of the type."""
    type_style: Required[str]

    is_modified: Required[bool]
    """Whether the need was modified by needextend."""
    modifications: Required[int]
    """Number of modifications by needextend."""

    # used to distinguish a part from a need
    is_need: Required[bool]
    is_part: Required[bool]
    # Mapping of parts, a.k.a. sub-needs, IDs to data that overrides the need's data
    parts: Required[dict[str, NeedsPartType]]
    # additional information required for compatibility with parts
    id_parent: Required[str]
    """<parent ID>, or <self ID> if not a part."""
    id_complete: Required[str]
    """<parent ID>.<self ID>, or <self ID> if not a part."""

    # content creation information
    jinja_content: Required[bool]
    template: Required[None | str]
    pre_template: Required[None | str]
    post_template: Required[None | str]
    content: Required[str]
    pre_content: str
    post_content: str

    # these default to False and are updated in check_links post-process
    has_dead_links: Required[bool]
    """True if any links reference need ids that are not found in the need list."""
    has_forbidden_dead_links: Required[bool]
    """True if any links reference need ids that are not found in the need list,
    and the link type does not allow dead links.
    """

    # constraints information
    constraints: Required[list[str]]
    """List of constraint names, which are defined for this need."""
    # set in process_need_nodes (-> process_constraints) transform
    constraints_results: Required[dict[str, dict[str, bool]]]
    """Mapping of constraint name, to check name, to result."""
    constraints_passed: Required[bool]
    """True if all constraints passed, False if any failed, None if not yet checked."""
    constraints_error: str
    """An error message set if any constraint failed, and `error_message` field is set in config."""

    # additional source information
    doctype: Required[str]
    """Type of the document where the need is defined, e.g. '.rst'."""
    # set in analyse_need_locations transform
    sections: Required[list[str]]
    section_name: Required[str]
    """Simply the first section."""
    signature: Required[str | Text]
    """Derived from a docutils desc_name node."""
    parent_need: Required[str]
    """Simply the first parent id."""

    # link information
    # Note, there is more dynamically added link information;
    # for each item in needs_extra_links config
    # (and in prepare_env 'links' and 'parent_needs' are added if not present),
    # you end up with a key named by the "option" field,
    # and then another key named by the "option" field + "_back"
    # these all have value type `list[str]`
    # back links are all set in process_need_nodes (-> create_back_links) transform
    links: list[str]
    """List of need IDs, which are referenced by this need."""
    links_back: list[str]
    """List of need IDs, which are referencing this need."""
    parent_needs: list[str]
    """List of parents of the this need (by id),
    i.e. if this need is nested in another
    """
    parent_needs_back: list[str]
    """List of children of this need (by id),
    i.e. if needs are nested within this one
    """

    # Fields added dynamically by services:
    # options from ``BaseService.options`` get added to ``extra_options``,
    # via `ServiceManager.register`,
    # which in turn means they are added to every need via ``add_need``
    # ``GithubService.options``
    avatar: str
    closed_at: str
    created_at: str
    max_amount: str
    service: str
    specific: str
    ## type: str  # although this is already an internal field
    updated_at: str
    user: str
    # ``OpenNeedsService.options``
    params: str
    prefix: str
    url_postfix: str
    # shared ``GithubService.options`` and ``OpenNeedsService.options``
    max_content_lines: str
    id_prefix: str
    query: str
    url: str

    # Note there are also these dynamic keys:
    # - items in ``needs_extra_options`` + ``needs_duration_option`` + ``needs_completion_option``,
    #   which get added to ``extra_options``,
    #   and in turn means they are added to every need via ``add_need`` (as strings)


class NeedsBaseDataType(TypedDict):
    """A base type for data items collected from directives."""

    docname: str
    """Name of the document where the need is defined."""
    lineno: int
    """Line number where the need is defined."""
    target_id: str
    """ID of the data."""


class NeedsBarType(NeedsBaseDataType):
    """Data for a single (matplotlib) bar diagram."""

    error_id: str
    title: None | str
    content: str
    legend: bool
    x_axis_title: str
    xlabels: list[str]
    xlabels_rotation: str
    y_axis_title: str
    ylabels: list[str]
    ylabels_rotation: str
    separator: str
    stacked: bool
    show_sum: None | bool
    show_top_sum: None | bool
    sum_rotation: None | str
    transpose: bool
    horizontal: bool
    style: str
    colors: list[str]
    text_color: str


class NeedsExtendType(NeedsBaseDataType):
    """Data to modify existing need(s)."""

    filter: str
    """Filter string to select needs to extend."""
    filter_is_id: bool
    """Whether the filter is a single need ID."""
    modifications: dict[str, Any]
    """Mapping of field name to new value.
    If the field name starts with a ``+``, the new value is appended to the existing value.
    If the field name starts with a ``-``, the existing value is cleared (new value is ignored).
    """
    strict: bool
    """If ``filter`` conforms to ``needs_id_regex``,
    and is not an existing need ID,
    whether to except the build (otherwise log-info message is written).
    """


class NeedsFilteredBaseType(NeedsBaseDataType):
    """A base type for all filtered data."""

    status: list[str]
    tags: list[str]
    types: list[str]
    filter: None | str
    sort_by: None | str
    filter_code: list[str]
    filter_func: None | str
    filter_warning: str | None
    """If set, the filter is exported with this ID in the needs.json file."""


class NeedsFilteredDiagramBaseType(NeedsFilteredBaseType):
    """A base type for all filtered diagram data."""

    show_legend: bool
    show_filters: bool
    show_link_names: bool
    link_types: list[str]
    config: str
    config_names: str
    scale: str
    highlight: str
    align: None | str
    debug: bool
    caption: None | str


class NeedsExtractType(NeedsFilteredBaseType):
    """Data to extract needs from a document."""

    layout: str
    style: str
    show_filters: bool
    filter_arg: None | str


class GraphvizStyleType(TypedDict, total=False):
    """Defines a graphviz style"""

    root: dict[str, str]
    """Root attributes"""
    graph: dict[str, str]
    """Graph attributes"""
    node: dict[str, str]
    """Node attributes"""
    edge: dict[str, str]
    """Edge attributes"""


class NeedsFlowType(NeedsFilteredDiagramBaseType):
    """Data for a single (filtered) flow chart."""

    classes: list[str]
    """List of CSS classes."""

    alt: str
    """Alternative text for the diagram in HTML output."""

    root_id: str | None
    """need ID to use as a root node."""

    root_direction: Literal["both", "incoming", "outgoing"]
    """Which link directions to include from the root node (if set)."""

    root_depth: int | None
    """How many levels to include from the root node (if set)."""

    border_color: str | None
    """Color of the outline of the needs, specified using the variant syntax."""

    graphviz_style: GraphvizStyleType
    """Graphviz style configuration."""


class NeedsGanttType(NeedsFilteredDiagramBaseType):
    """Data for a single (filtered) gantt chart."""

    starts_with_links: list[str]
    starts_after_links: list[str]
    ends_with_links: list[str]
    milestone_filter: str
    start_date: None | str
    timeline: Literal[None, "daily", "weekly", "monthly"]
    no_color: bool
    duration_option: str
    completion_option: str


class NeedsListType(NeedsFilteredBaseType):
    """Data for a single (filtered) needs list."""

    show_tags: bool
    show_status: bool
    show_filters: bool


class NeedsPieType(NeedsBaseDataType):
    """Data for a single (matplotlib) pie chart."""

    title: str
    content: str
    legend: bool
    explode: None | list[float]
    style: None | str
    labels: None | list[str]
    colors: None | list[str]
    text_color: None | str
    shadow: bool
    filter_func: None | str
    filter_warning: str | None


class NeedsSequenceType(NeedsFilteredDiagramBaseType):
    """Data for a single (filtered) sequence diagram."""

    start: str


class NeedsTableType(NeedsFilteredBaseType):
    """Data for a single (filtered) needs table."""

    caption: None | str
    classes: list[str]
    columns: list[tuple[str, str]]
    """List of (name, title)"""
    colwidths: list[int]
    style: str
    style_row: str
    style_col: str
    sort: str
    show_filters: bool
    show_parts: bool


class NeedsUmlType(NeedsBaseDataType):
    """Data for a single (filtered) uml diagram."""

    caption: None | str
    content: str
    scale: str
    align: str
    config_names: None | str
    config: str
    debug: bool
    extra: dict[str, str]
    key: None | str
    save: None | str
    is_arch: bool
    # set in process_needuml
    content_calculated: str
    process_time: float
    """Time taken to process the diagram."""


NeedsMutable = NewType("NeedsMutable", dict[str, NeedsInfoType])
"""A mutable view of the needs, before resolution
"""


class SphinxNeedsData:
    """Centralised access to sphinx-needs data, stored within the Sphinx environment."""

    def __init__(self, env: BuildEnvironment) -> None:
        self.env = env

    @property
    def _env_needs(self) -> dict[str, NeedsInfoType]:
        try:
            return self.env._needs_all_needs
        except AttributeError:
            self.env._needs_all_needs = {}
        return self.env._needs_all_needs

    def has_need(self, need_id: str) -> bool:
        """Check if a need with the given ID exists."""
        return need_id in self._env_needs

    def add_need(self, need: NeedsInfoType) -> None:
        """Add an unprocessed need to the cache.

        This will overwrite any existing need with the same ID.

        .. important:: this should only be called within the read phase,
            before the needs have been fully collected and resolved.
        """
        if self.needs_is_post_processed:
            raise RuntimeError("Needs have already been post-processed and frozen.")
        self._env_needs[need["id"]] = need

    def remove_need(self, need_id: str) -> None:
        """Remove a single need from the cache, if it exists.

        .. important:: this should only be called within the read phase,
            before the needs have been fully collected and resolved.
        """
        if self.needs_is_post_processed:
            raise RuntimeError("Needs have already been post-processed and frozen.")
        if need_id in self._env_needs:
            del self._env_needs[need_id]
        self.remove_need_node(need_id)

    def remove_doc(self, docname: str) -> None:
        """Remove all data related to a document from the cache.

        .. important:: this should only be called within the read phase,
            before the needs have been fully collected and resolved.
        """
        if self.needs_is_post_processed:
            raise RuntimeError("Needs have already been post-processed and frozen.")
        for need_id in list(self._env_needs):
            if self._env_needs[need_id]["docname"] == docname:
                del self._env_needs[need_id]
                self.remove_need_node(need_id)
        docs = self.get_or_create_docs()
        for key, value in docs.items():
            docs[key] = [doc for doc in value if doc != docname]

    def get_needs_mutable(self) -> NeedsMutable:
        """Get all needs, mapped by ID.

        .. important:: this should only be called within the read phase,
            before the needs have been fully collected and resolved.
        """
        if self.needs_is_post_processed:
            raise RuntimeError("Needs have already been post-processed and frozen.")
        return self._env_needs  # type: ignore[return-value]

    def get_needs_view(self) -> NeedsView:
        """Return a read-only view of all resolved needs.

        .. important:: this should only be called within the write phase,
            after the needs have been fully collected.
            If not already done, this will ensure all needs are resolved
            (e.g. back links have been computed etc),
            and then lock the data to prevent further modification.
        """
        if not self.needs_is_post_processed:
            from sphinx_needs.directives.need import post_process_needs_data

            # TODO the following code may be good to make access stricter, however,
            # it fails on rebuilds, where e.g. `build-finished` events can be called without the phase having been updated
            # from sphinx.util.build_phase import BuildPhase
            # if self.env.app.phase in (BuildPhase.INITIALIZATION, BuildPhase.READING):
            #     raise RuntimeError(
            #         "Trying to retrieve needs view incorrectly in init/read phase."
            #     )

            post_process_needs_data(self.env.app)

        try:
            return self.env._needs_view
        except AttributeError:
            self.env._needs_view = NeedsView._from_needs(self._env_needs)
        return self.env._needs_view

    def get_or_create_docs(self) -> dict[str, list[str]]:
        """Get mapping of need category to docnames containing the need.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env._needs_all_docs
        except AttributeError:
            self.env._needs_all_docs = {"all": []}
        return self.env._needs_all_docs

    @property
    def needs_is_post_processed(self) -> bool:
        """Whether needs have been post-processed."""
        try:
            return self.env._needs_is_post_processed
        except AttributeError:
            self.env._needs_is_post_processed = False
        return self.env._needs_is_post_processed

    @needs_is_post_processed.setter
    def needs_is_post_processed(self, value: bool) -> None:
        self.env._needs_is_post_processed = value

    def get_or_create_services(self) -> ServiceManager:
        """Get information about services.

        This is lazily created and cached in the environment.
        """
        from sphinx_needs.services.manager import ServiceManager

        try:
            return self.env.app._needs_services
        except AttributeError:
            self.env.app._needs_services = ServiceManager(self.env.app)
        return self.env.app._needs_services

    def get_or_create_extends(self) -> dict[str, NeedsExtendType]:
        """Get all need modifications, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env._need_all_needextend
        except AttributeError:
            self.env._need_all_needextend = {}
        return self.env._need_all_needextend

    def get_or_create_umls(self) -> dict[str, NeedsUmlType]:
        """Get all need uml diagrams, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env._needs_all_needumls
        except AttributeError:
            self.env._needs_all_needumls = {}
        return self.env._needs_all_needumls

    @property
    def _needs_all_nodes(self) -> dict[str, Need]:
        try:
            return self.env._needs_all_nodes
        except AttributeError:
            self.env._needs_all_nodes = {}
        return self.env._needs_all_nodes

    def set_need_node(self, need_id: str, node: Need) -> None:
        """Set a need node in the cache."""
        self._needs_all_nodes[need_id] = node.deepcopy()

    def remove_need_node(self, need_id: str) -> None:
        """Remove a need node from the cache, if it exists."""
        if need_id in self._needs_all_nodes:
            del self._needs_all_nodes[need_id]

    def get_need_node(self, need_id: str) -> Need | None:
        """Get a copy of a need node from the cache, if it exists."""
        if need_id in self._needs_all_nodes:
            # We must create a copy of the node, as it may be reused several time
            # (multiple needextract for the same need) and the Sphinx ImageTransformator add location specific
            # uri to some nodes, which are not valid for all locations.
            return self._needs_all_nodes[need_id].deepcopy()
        return None


def merge_data(
    _app: Sphinx, env: BuildEnvironment, docnames: list[str], other: BuildEnvironment
) -> None:
    """
    Performs data merge of parallel executed workers.
    Used only for parallel builds.

    Needs to update env manually for all data Sphinx-Needs collect during read phase
    """
    this_data = SphinxNeedsData(env)
    other_data = SphinxNeedsData(other)

    # Update needs
    needs = this_data._env_needs
    other_needs = other_data._env_needs
    for other_id, other_need in other_needs.items():
        if other_id in needs:
            # we only want to warn if the need comes from one of the docs parsed in this worker
            _docname = other_need["docname"]
            if _docname in docnames:
                message = (
                    f"A need with ID {other_id} already exists, "
                    f"title: {other_need['title']!r}."
                )
                log_warning(
                    LOGGER,
                    message,
                    "duplicate_id",
                    location=(_docname, other_need["lineno"]) if _docname else None,
                )
        else:
            needs[other_id] = other_need

    # update other data

    def _merge(name: str, is_complex_dict: bool = False) -> None:
        # Update global needs dict
        if not hasattr(env, name):
            setattr(env, name, {})
        objects = getattr(env, name)
        if hasattr(other, name):
            other_objects = getattr(other, name)
            if isinstance(other_objects, dict) and isinstance(objects, dict):
                if not is_complex_dict:
                    objects.update(other_objects)
                else:
                    for other_key, other_value in other_objects.items():
                        # other_value is a list from here on!
                        if other_key in objects:
                            objects[other_key] = list(
                                set(objects[other_key]) | set(other_value)
                            )
                        else:
                            objects[other_key] = other_value
            elif isinstance(other_objects, list) and isinstance(objects, list):
                objects = list(set(objects) | set(other_objects))
            else:
                raise TypeError(
                    f'Objects to "merge" must be dict or list, '
                    f"not {type(other_objects)} and {type(objects)}"
                )

    _merge("_needs_all_docs", is_complex_dict=True)
    _merge("_needs_all_nodes")
    _merge("_need_all_needextend")
    _merge("_needs_all_needumls")
