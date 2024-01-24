"""Module to control access to sphinx-needs data,
which is stored in the Sphinx environment.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from docutils.nodes import Element, Text
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

    from sphinx_needs.services.manager import ServiceManager


class NeedsFilterType(TypedDict):
    filter: str
    """Filter string."""
    status: list[str]
    tags: list[str]
    types: list[str]
    result: list[str]
    amount: int
    export_id: str
    """If set, the filter is exported with this ID in the needs.json file."""


class NeedsBaseDataType(TypedDict):
    """A base type for all data."""

    docname: str
    """Name of the document where the need is defined."""
    lineno: int
    """Line number where the need is defined."""
    target_id: str
    """ID of the data."""


class NeedsPartType(TypedDict):
    """Data for a single need part."""

    id: str
    """ID of the part"""

    is_part: bool
    is_need: bool

    content: str
    """Content of the part."""
    document: str
    """docname where the part is defined."""
    links: list[str]
    """List of need IDs, which are referenced by this part."""
    links_back: list[str]
    """List of need IDs, which are referencing this part."""


class NeedsInfoType(NeedsBaseDataType):
    """Data for a single need."""

    id: str
    """ID of the data (same as target_id)"""

    # meta information
    full_title: str
    """Title of the need, of unlimited length."""
    title: str
    """Title of the need, trimmed to a maximum length."""
    status: None | str
    tags: list[str]

    # rendering information
    collapse: bool
    """hide the meta-data information of the need."""
    hide: bool
    """If true, the need is not rendered."""
    delete: bool
    """If true, the need is deleted entirely."""
    layout: None | str
    """Key of the layout, which is used to render the need."""
    style: None | str
    """Comma-separated list of CSS classes (all appended by `needs_style_`)."""

    # TODO why is it called arch?
    arch: dict[str, str]
    """Mapping of uml key to uml content."""

    # external reference information
    is_external: bool
    """If true, no node is created and need is referencing external url"""
    external_url: None | str
    """URL of the need, if it is an external need."""
    external_css: str
    """CSS class name, added to the external reference."""

    # type information (based on needs_types config)
    type: str
    type_name: str
    type_prefix: str
    type_color: str
    """Hexadecimal color code of the type."""
    type_style: str

    is_modified: bool
    """Whether the need was modified by needextend."""
    modifications: int
    """Number of modifications by needextend."""

    # parts information
    parts: dict[str, NeedsPartType]
    is_need: bool
    is_part: bool

    # content creation information
    jinja_content: bool
    template: None | str
    pre_template: None | str
    post_template: None | str
    content: str
    pre_content: str
    post_content: str
    content_id: None | str
    """ID of the content node."""
    content_node: None | Element
    """deep copy of the content node."""

    # link information
    links: list[str]
    """List of need IDs, which are referenced by this need."""
    links_back: list[str]
    """List of need IDs, which are referencing this need."""
    # TODO there is more dynamically added link information;
    # for each item in needs_extra_links config
    # (and in prepare_env 'links' and 'parent_needs' are added if not present),
    # you end up with a key named by the "option" field,
    # and then another key named by the "option" field + "_back"
    # these all have value type `list[str]`
    # back links are all set in process_need_nodes (-> create_back_links) transform

    # constraints information
    constraints: list[str]
    """List of constraint names, which are defined for this need."""
    # set in process_need_nodes (-> process_constraints) transform
    constraints_results: dict[str, dict[str, bool]]
    """Mapping of constraint name, to check name, to result."""
    constraints_passed: None | bool
    """True if all constraints passed, False if any failed, None if not yet checked."""
    constraints_error: str
    """An error message set if any constraint failed, and `error_message` field is set in config."""

    # additional source information
    doctype: str
    """Type of the document where the need is defined, e.g. '.rst'"""
    # set in analyse_need_locations transform
    sections: list[str]
    section_name: str
    """Simply the first section"""
    signature: str | Text
    """Derived from a docutils desc_name node"""
    parent_needs: list[str]
    """List of parents of the this need (by id),
    i.e. if this need is nested in another
    """
    parent_needs_back: list[str]
    """List of children of this need (by id),
    i.e. if needs are nested within this one
    """
    parent_need: str
    """Simply the first parent id"""

    # default extra options
    # TODO these all default to "" which I don't think is good
    hidden: str
    duration: str
    completion: str
    # constraints: str  # this is already set in create_need
    # these are updated in process_need_nodes (-> check_links) transform
    has_dead_links: str | bool
    has_forbidden_dead_links: str | bool
    # options from `BaseService.options` get added to every need,
    # via `ServiceManager.register`, which adds them to `extra_options``
    # GithubService
    avatar: str
    closed_at: str
    created_at: str
    max_amount: str
    service: str
    specific: str
    # _type: str  # type is already set in create_need
    updated_at: str
    user: str
    # OpenNeedsService
    params: str
    prefix: str
    url_postfix: str
    # shared GithubService and OpenNeedsService
    max_content_lines: str
    id_prefix: str
    query: str
    url: str

    # Note there are also:
    # - dynamic default options that can be set by needs_extra_options config
    # - dynamic global options that can be set by needs_global_options config


class NeedsPartsInfoType(NeedsInfoType):
    """Generated by prepare_need_list"""

    document: str
    """docname where the part is defined."""
    id_parent: str
    id_complete: str


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

    filter: None | str
    """Single need ID or filter string to select multiple needs."""
    modifications: dict[str, str]
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
    export_id: str
    filter_warning: str
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


class _NeedsFilterType(NeedsFilteredBaseType):
    """Data to present (filtered) needs inside a list, table or diagram

    .. deprecated:: 0.2.0
    """

    show_tags: bool
    show_status: bool
    show_filters: bool
    show_legend: bool
    layout: Literal["list", "table", "diagram"]


class NeedsFlowType(NeedsFilteredDiagramBaseType):
    """Data for a single (filtered) flow chart."""


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
    filter_warning: str


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


class SphinxNeedsData:
    """Centralised access to sphinx-needs data, stored within the Sphinx environment."""

    def __init__(self, env: BuildEnvironment) -> None:
        self.env = env

    def get_or_create_needs(self) -> dict[str, NeedsInfoType]:
        """Get all needs, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.needs_all_needs
        except AttributeError:
            self.env.needs_all_needs = {}
        return self.env.needs_all_needs

    @property
    def has_export_filters(self) -> bool:
        """Whether any filters have export IDs."""
        try:
            return self.env.needs_filters_export_id
        except AttributeError:
            return False

    @has_export_filters.setter
    def has_export_filters(self, value: bool) -> None:
        self.env.needs_filters_export_id = value

    def get_or_create_filters(self) -> dict[str, NeedsFilterType]:
        """Get all filters, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.needs_all_filters
        except AttributeError:
            self.env.needs_all_filters = {}
        return self.env.needs_all_filters

    def get_or_create_docs(self) -> dict[str, list[str]]:
        """Get mapping of need category to docnames containing the need.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.needs_all_docs
        except AttributeError:
            self.env.needs_all_docs = {"all": []}
        return self.env.needs_all_docs

    @property
    def needs_is_post_processed(self) -> bool:
        """Whether needs have been post-processed."""
        try:
            return self.env.needs_is_post_processed
        except AttributeError:
            self.env.needs_is_post_processed = False
        return self.env.needs_is_post_processed

    @needs_is_post_processed.setter
    def needs_is_post_processed(self, value: bool) -> None:
        self.env.needs_is_post_processed = value

    def get_or_create_services(self) -> ServiceManager:
        """Get information about services.

        This is lazily created and cached in the environment.
        """
        from sphinx_needs.services.manager import ServiceManager

        try:
            return self.env.app.needs_services
        except AttributeError:
            self.env.app.needs_services = ServiceManager(self.env.app)
        return self.env.app.needs_services

    def get_or_create_bars(self) -> dict[str, NeedsBarType]:
        """Get all bar charts, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needbar
        except AttributeError:
            self.env.need_all_needbar = {}
        return self.env.need_all_needbar

    def get_or_create_extends(self) -> dict[str, NeedsExtendType]:
        """Get all need modifications, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needextend
        except AttributeError:
            self.env.need_all_needextend = {}
        return self.env.need_all_needextend

    def get_or_create_extracts(self) -> dict[str, NeedsExtractType]:
        """Get all need extractions, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needextracts
        except AttributeError:
            self.env.need_all_needextracts = {}
        return self.env.need_all_needextracts

    def _get_or_create_filters(self) -> dict[str, _NeedsFilterType]:
        """Get all need filters, mapped by ID.

        .. deprecated:: 0.2.0

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needfilters
        except AttributeError:
            self.env.need_all_needfilters = {}
        return self.env.need_all_needfilters

    def get_or_create_flows(self) -> dict[str, NeedsFlowType]:
        """Get all need flow charts, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needflows
        except AttributeError:
            self.env.need_all_needflows = {}
        return self.env.need_all_needflows

    def get_or_create_gantts(self) -> dict[str, NeedsGanttType]:
        """Get all need gantt charts, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needgantts
        except AttributeError:
            self.env.need_all_needgantts = {}
        return self.env.need_all_needgantts

    def get_or_create_lists(self) -> dict[str, NeedsListType]:
        """Get all need gantt charts, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needlists
        except AttributeError:
            self.env.need_all_needlists = {}
        return self.env.need_all_needlists

    def get_or_create_pies(self) -> dict[str, NeedsPieType]:
        """Get all need gantt charts, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needpie
        except AttributeError:
            self.env.need_all_needpie = {}
        return self.env.need_all_needpie

    def get_or_create_sequences(self) -> dict[str, NeedsSequenceType]:
        """Get all need sequence diagrams, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needsequences
        except AttributeError:
            self.env.need_all_needsequences = {}
        return self.env.need_all_needsequences

    def get_or_create_tables(self) -> dict[str, NeedsTableType]:
        """Get all need tables, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.need_all_needtables
        except AttributeError:
            self.env.need_all_needtables = {}
        return self.env.need_all_needtables

    def get_or_create_umls(self) -> dict[str, NeedsUmlType]:
        """Get all need uml diagrams, mapped by ID.

        This is lazily created and cached in the environment.
        """
        try:
            return self.env.needs_all_needumls
        except AttributeError:
            self.env.needs_all_needumls = {}
        return self.env.needs_all_needumls


def merge_data(_app: Sphinx, env: BuildEnvironment, _docnames: list[str], other: BuildEnvironment) -> None:
    """
    Performs data merge of parallel executed workers.
    Used only for parallel builds.

    Needs to update env manually for all data Sphinx-Needs collect during read phase
    """

    # Update global needs dict
    needs = SphinxNeedsData(env).get_or_create_needs()
    other_needs = SphinxNeedsData(other).get_or_create_needs()
    needs.update(other_needs)
    if SphinxNeedsData(other).has_export_filters:
        SphinxNeedsData(env).has_export_filters = True

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
                            objects[other_key] = list(set(objects[other_key]) | set(other_value))
                        else:
                            objects[other_key] = other_value
            elif isinstance(other_objects, list) and isinstance(objects, list):
                objects = list(set(objects) | set(other_objects))
            else:
                raise TypeError(
                    f'Objects to "merge" must be dict or list, ' f"not {type(other_objects)} and {type(objects)}"
                )

    _merge("needs_all_docs", is_complex_dict=True)
    _merge("need_all_needbar")
    _merge("need_all_needextend")
    _merge("need_all_needextracts")
    _merge("need_all_needfilters")
    _merge("need_all_needflows")
    _merge("need_all_needgantts")
    _merge("need_all_needlists")
    _merge("need_all_needpie")
    _merge("need_all_needsequences")
    _merge("need_all_needtables")
    _merge("needs_all_needumls")
