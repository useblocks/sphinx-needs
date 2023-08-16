from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, Dict, List

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.environment import BuildEnvironment
from sphinx.errors import SphinxError

import sphinx_needs.debug as debug  # Need to set global var in it for timeing measurements
from sphinx_needs.api.configuration import add_extra_option
from sphinx_needs.builder import (
    NeedsBuilder,
    NeedumlsBuilder,
    build_needs_json,
    build_needumls_pumls,
)
from sphinx_needs.config import NEEDS_CONFIG
from sphinx_needs.defaults import (
    DEFAULT_DIAGRAM_TEMPLATE,
    LAYOUTS,
    NEED_DEFAULT_OPTIONS,
    NEEDEXTEND_NOT_ALLOWED_OPTIONS,
    NEEDFLOW_CONFIG_DEFAULTS,
    NEEDS_TABLES_CLASSES,
)
from sphinx_needs.directives.list2need import List2Need, List2NeedDirective
from sphinx_needs.directives.need import (
    Need,
    NeedDirective,
    add_sections,
    html_depart,
    html_visit,
    latex_depart,
    latex_visit,
    process_need_nodes,
    purge_needs,
)
from sphinx_needs.directives.needbar import Needbar, NeedbarDirective, process_needbar
from sphinx_needs.directives.needextend import Needextend, NeedextendDirective
from sphinx_needs.directives.needextract import (
    Needextract,
    NeedextractDirective,
    process_needextract,
)
from sphinx_needs.directives.needfilter import (
    Needfilter,
    NeedfilterDirective,
    process_needfilters,
)
from sphinx_needs.directives.needflow import (
    Needflow,
    NeedflowDirective,
    process_needflow,
)
from sphinx_needs.directives.needgantt import (
    Needgantt,
    NeedganttDirective,
    process_needgantt,
)
from sphinx_needs.directives.needimport import Needimport, NeedimportDirective
from sphinx_needs.directives.needlist import (
    Needlist,
    NeedlistDirective,
    process_needlist,
)
from sphinx_needs.directives.needpie import Needpie, NeedpieDirective, process_needpie
from sphinx_needs.directives.needreport import NeedReportDirective
from sphinx_needs.directives.needsequence import (
    Needsequence,
    NeedsequenceDirective,
    process_needsequence,
)
from sphinx_needs.directives.needservice import Needservice, NeedserviceDirective
from sphinx_needs.directives.needtable import (
    Needtable,
    NeedtableDirective,
    process_needtables,
)
from sphinx_needs.directives.needuml import (
    NeedarchDirective,
    Needuml,
    NeedumlDirective,
    process_needuml,
)
from sphinx_needs.environment import (
    install_lib_static_files,
    install_permalink_file,
    install_styles_static_files,
)
from sphinx_needs.external_needs import load_external_needs
from sphinx_needs.functions import needs_common_functions, register_func
from sphinx_needs.logging import get_logger
from sphinx_needs.roles import NeedsXRefRole
from sphinx_needs.roles.need_count import NeedCount, process_need_count
from sphinx_needs.roles.need_func import NeedFunc, process_need_func
from sphinx_needs.roles.need_incoming import NeedIncoming, process_need_incoming
from sphinx_needs.roles.need_outgoing import NeedOutgoing, process_need_outgoing
from sphinx_needs.roles.need_part import NeedPart, process_need_part
from sphinx_needs.roles.need_ref import NeedRef, process_need_ref
from sphinx_needs.services.github import GithubService
from sphinx_needs.services.manager import ServiceManager
from sphinx_needs.services.open_needs import OpenNeedsService
from sphinx_needs.utils import INTERNALS, NEEDS_FUNCTIONS, node_match
from sphinx_needs.warnings import process_warnings

VERSION = "1.3.0"
NEEDS_FUNCTIONS.clear()


NODE_TYPES_PRIO = {  # Node types to be checked before most others
    Needextract: process_needextract,
}

NODE_TYPES = {
    Needbar: process_needbar,
    # Needextract: process_needextract,
    Needfilter: process_needfilters,
    Needlist: process_needlist,
    Needtable: process_needtables,
    Needflow: process_needflow,
    Needpie: process_needpie,
    Needsequence: process_needsequence,
    Needgantt: process_needgantt,
    Needuml: process_needuml,
    NeedPart: process_need_part,
    NeedRef: process_need_ref,
    NeedIncoming: process_need_incoming,
    NeedOutgoing: process_need_outgoing,
    NeedCount: process_need_count,
    NeedFunc: process_need_func,
}


def setup(app: Sphinx) -> Dict[str, Any]:
    log = get_logger(__name__)
    log.debug("Starting setup of Sphinx-Needs")
    log.debug("Load Sphinx-Data-Viewer for Sphinx-Needs")
    app.setup_extension("sphinx_data_viewer")

    app.add_builder(NeedsBuilder)
    app.add_builder(NeedumlsBuilder)
    app.add_config_value(
        "needs_types",
        [
            {"directive": "req", "title": "Requirement", "prefix": "R_", "color": "#BFD8D2", "style": "node"},
            {"directive": "spec", "title": "Specification", "prefix": "S_", "color": "#FEDCD2", "style": "node"},
            {"directive": "impl", "title": "Implementation", "prefix": "I_", "color": "#DF744A", "style": "node"},
            {"directive": "test", "title": "Test Case", "prefix": "T_", "color": "#DCB239", "style": "node"},
            # Kept for backwards compatibility
            {"directive": "need", "title": "Need", "prefix": "N_", "color": "#9856a5", "style": "node"},
        ],
        "html",
    )
    app.add_config_value("needs_include_needs", True, "html", types=[bool])
    app.add_config_value("needs_need_name", "Need", "html", types=[str])
    app.add_config_value("needs_spec_name", "Specification", "html", types=[str])
    app.add_config_value("needs_id_prefix_needs", "", "html", types=[str])
    app.add_config_value("needs_id_prefix_specs", "", "html", types=[str])
    app.add_config_value("needs_id_length", 5, "html", types=[int])
    app.add_config_value("needs_id_from_title", False, "html", types=[bool])
    app.add_config_value("needs_specs_show_needlist", False, "html", types=[bool])
    app.add_config_value("needs_id_required", False, "html", types=[bool])
    app.add_config_value(
        "needs_id_regex",
        f"^[A-Z0-9_]{{{app.config.needs_id_length},}}",
        "html",
    )
    app.add_config_value("needs_show_link_type", False, "html", types=[bool])
    app.add_config_value("needs_show_link_title", False, "html", types=[bool])
    app.add_config_value("needs_show_link_id", True, "html", types=[bool])
    app.add_config_value("needs_file", None, "html")
    app.add_config_value("needs_table_columns", "ID;TITLE;STATUS;TYPE;OUTGOING;TAGS", "html")
    app.add_config_value("needs_table_style", "DATATABLES", "html")

    app.add_config_value("needs_role_need_template", "{title} ({id})", "html")
    app.add_config_value("needs_role_need_max_title_length", 30, "html", types=[int])

    app.add_config_value("needs_extra_options", [], "html")
    app.add_config_value("needs_title_optional", False, "html", types=[bool])
    app.add_config_value("needs_max_title_length", -1, "html", types=[int])
    app.add_config_value("needs_title_from_content", False, "html", types=[bool])

    app.add_config_value("needs_diagram_template", DEFAULT_DIAGRAM_TEMPLATE, "html")

    app.add_config_value("needs_functions", [], "html", types=[list])
    app.add_config_value("needs_global_options", {}, "html", types=[dict])

    app.add_config_value("needs_duration_option", "duration", "html")
    app.add_config_value("needs_completion_option", "completion", "html")

    app.add_config_value("needs_needextend_strict", True, "html", types=[bool])

    # If given, only the defined status are allowed.
    # Values needed for each status:
    # * name
    # * description
    # Example: [{"name": "open", "description": "open status"}, {...}, {...}]
    app.add_config_value("needs_statuses", [], "html")

    # If given, only the defined tags are allowed.
    # Values needed for each tag:
    # * name
    # * description
    # Example: [{"name": "new", "description": "new needs"}, {...}, {...}]
    app.add_config_value("needs_tags", [], "html", types=[list])

    # Path of css file, which shall be used for need style
    app.add_config_value("needs_css", "modern.css", "html")

    # Prefix for need_part output in tables
    app.add_config_value("needs_part_prefix", "\u2192\u00a0", "html")

    # List of additional links, which can be used by setting related option
    # Values needed for each new link:
    # * name (will also be the option name)
    # * incoming
    # * copy_link (copy to common links data. Default: True)
    # * color (used for needflow. Default: #000000)
    # Example: [{"name": "blocks, "incoming": "is blocked by", "copy_link": True, "color": "#ffcc00"}]
    app.add_config_value("needs_extra_links", [], "html")

    # Deactivate log msgs of dead links if set to False, default is True
    app.add_config_value("needs_report_dead_links", True, "html", types=[bool])

    app.add_config_value("needs_filter_data", {}, "html")
    app.add_config_value("needs_allow_unsafe_filters", False, "html")

    app.add_config_value("needs_flow_show_links", False, "html")
    app.add_config_value("needs_flow_link_types", ["links"], "html")

    app.add_config_value("needs_warnings", {}, "html")
    app.add_config_value("needs_warnings_always_warn", False, "html", types=[bool])
    app.add_config_value("needs_layouts", {}, "html")
    app.add_config_value("needs_default_layout", "clean", "html")
    app.add_config_value("needs_default_style", None, "html")

    app.add_config_value("needs_flow_configs", {}, "html")

    app.add_config_value("needs_template_folder", "needs_templates/", "html")

    app.add_config_value("needs_services", {}, "html")
    app.add_config_value("needs_service_all_data", False, "html", types=[bool])

    app.add_config_value("needs_debug_no_external_calls", False, "html", types=[bool])

    app.add_config_value("needs_external_needs", [], "html")

    app.add_config_value("needs_builder_filter", "is_external==False", "html", types=[str])

    # Additional classes to set for needs and needtable.
    app.add_config_value("needs_table_classes", NEEDS_TABLES_CLASSES, "html", types=[list])

    app.add_config_value("needs_string_links", {}, "html", types=[dict])

    app.add_config_value("needs_build_json", False, "html", types=[bool])

    app.add_config_value("needs_build_needumls", "", "html", types=[str])

    # Permalink related config values.
    # path to permalink.html; absolute path from web-root
    app.add_config_value("needs_permalink_file", "permalink.html", "html")
    # path to needs.json relative to permalink.html
    app.add_config_value("needs_permalink_data", "needs.json", "html")
    # path to needs_report_template file which is based on the conf.py directory.
    app.add_config_value("needs_report_template", "", "html", types=[str])

    # add constraints option
    app.add_config_value("needs_constraints", {}, "html", types=[dict])
    app.add_config_value("needs_constraint_failed_options", {}, "html", types=[dict])
    app.add_config_value("needs_constraints_failed_color", "", "html")

    # add variants option
    app.add_config_value("needs_variants", {}, "html", types=[dict])
    app.add_config_value("needs_variant_options", [], "html", types=[list])

    # add jinja context option
    app.add_config_value("needs_render_context", {}, "html", types=[dict])

    #
    app.add_config_value("needs_debug_measurement", False, "html", types=[dict])

    # Define nodes
    app.add_node(Need, html=(html_visit, html_depart), latex=(latex_visit, latex_depart))
    app.add_node(
        Needfilter,
    )
    app.add_node(Needbar)
    app.add_node(Needimport)
    app.add_node(Needlist)
    app.add_node(Needtable)
    app.add_node(Needflow)
    app.add_node(Needpie)
    app.add_node(Needsequence)
    app.add_node(Needgantt)
    app.add_node(Needextract)
    app.add_node(Needservice)
    app.add_node(Needextend)
    app.add_node(Needuml)
    app.add_node(List2Need)
    app.add_node(NeedPart, html=(visitor_dummy, visitor_dummy), latex=(visitor_dummy, visitor_dummy))

    ########################################################################
    # DIRECTIVES
    ########################################################################

    # Define directives
    app.add_directive("needbar", NeedbarDirective)
    app.add_directive("needfilter", NeedfilterDirective)
    app.add_directive("needlist", NeedlistDirective)
    app.add_directive("needtable", NeedtableDirective)
    app.add_directive("needflow", NeedflowDirective)
    app.add_directive("needpie", NeedpieDirective)
    app.add_directive("needsequence", NeedsequenceDirective)
    app.add_directive("needgantt", NeedganttDirective)
    app.add_directive("needimport", NeedimportDirective)
    app.add_directive("needextract", NeedextractDirective)
    app.add_directive("needservice", NeedserviceDirective)
    app.add_directive("needextend", NeedextendDirective)
    app.add_directive("needreport", NeedReportDirective)
    app.add_directive("needuml", NeedumlDirective)
    app.add_directive("needarch", NeedarchDirective)
    app.add_directive("list2need", List2NeedDirective)

    ########################################################################
    # ROLES
    ########################################################################
    # Provides :need:`ABC_123` for inline links.
    app.add_role("need", NeedsXRefRole(nodeclass=NeedRef, innernodeclass=nodes.emphasis, warn_dangling=True))

    app.add_role(
        "need_incoming", NeedsXRefRole(nodeclass=NeedIncoming, innernodeclass=nodes.emphasis, warn_dangling=True)
    )

    app.add_role(
        "need_outgoing", NeedsXRefRole(nodeclass=NeedOutgoing, innernodeclass=nodes.emphasis, warn_dangling=True)
    )

    app.add_role("need_part", NeedsXRefRole(nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True))
    # Shortcut for need_part
    app.add_role("np", NeedsXRefRole(nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True))

    app.add_role("need_count", NeedsXRefRole(nodeclass=NeedCount, innernodeclass=nodes.inline, warn_dangling=True))

    app.add_role("need_func", NeedsXRefRole(nodeclass=NeedFunc, innernodeclass=nodes.inline, warn_dangling=True))

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect("env-purge-doc", purge_needs)
    app.connect("config-inited", load_config)
    app.connect("env-before-read-docs", prepare_env)
    app.connect("env-before-read-docs", load_external_needs)
    app.connect("config-inited", check_configuration)
    # app.connect("doctree-resolved", add_sections)
    app.connect("doctree-read", add_sections)
    app.connect("env-merge-info", merge_data)

    # There is also the event doctree-read.
    # But it looks like in this event no references are already solved, which
    # makes trouble in our code.
    # However, some sphinx-internal actions (like image collection) are already called during
    # doctree-read. So manipulating the doctree may result in conflicts, as e.g. images get not
    # registered for sphinx. So some sphinx-internal tasks/functions may be called by hand again...
    # See also https://github.com/sphinx-doc/sphinx/issues/7054#issuecomment-578019701 for an example
    app.connect("doctree-resolved", process_need_nodes)
    app.connect("doctree-resolved", process_creator(NODE_TYPES_PRIO, "needextract"), priority=100)
    app.connect("doctree-resolved", process_creator(NODE_TYPES))

    app.connect("build-finished", process_warnings)
    app.connect("build-finished", build_needs_json)
    app.connect("build-finished", build_needumls_pumls)
    app.connect("build-finished", debug.process_timing)
    app.connect("env-updated", install_lib_static_files)
    app.connect("env-updated", install_permalink_file)

    # This should be called last, so that need-styles can override styles from used libraries
    app.connect("env-updated", install_styles_static_files)

    # Be sure Sphinx-Needs config gets erased before any events or external API calls get executed.
    # So never but this inside an event.
    NEEDS_CONFIG.create("extra_options", dict, overwrite=True)
    NEEDS_CONFIG.create("warnings", dict, overwrite=True)

    return {
        "version": VERSION,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def process_creator(node_list, doc_category="all"):
    """
    Create a pre-configured process_caller for given Node types
    """

    def process_caller(app: Sphinx, doctree: nodes.document, fromdocname: str):
        """
        A single event_handler for doc-tree-resolved, which cares about the doctree-parsing
        only once and calls the needed sub-handlers (like process_needtables and so).

        Reason: In the past all process-xy handles have parsed the doctree by their own, so the same doctree
        got parsed several times. This is now done at a single place and the related process-xy get a
        list of found docutil node-object for their case.
        """
        # We only need to analyse docs, which have Sphinx-Needs directives in it.
        if (
            fromdocname not in app.builder.env.needs_all_docs.get(doc_category, [])
            and fromdocname != f"{app.config.root_doc}"
        ):
            return
        current_nodes = {}
        check_nodes = list(node_list.keys())
        for node_need in doctree.findall(node_match(check_nodes)):
            for check_node in node_list:
                if isinstance(node_need, check_node):
                    if check_node not in current_nodes:
                        current_nodes[check_node] = []
                    current_nodes[check_node].append(node_need)
                    break  # We found the related type for the need

        # Let's call the handlers
        for check_node, check_func in node_list.items():
            # Call the handler only, if it defined, and we found some nodes for it
            if check_node in current_nodes and check_func is not None and current_nodes[check_node]:
                check_func(app, doctree, fromdocname, current_nodes[check_node])

    return process_caller


def load_config(app: Sphinx, *_args) -> None:
    """
    Register extra options and directive based on config from conf.py
    """
    log = get_logger(__name__)
    types = app.config.needs_types

    if isinstance(app.config.needs_extra_options, dict):
        log.info(
            'Config option "needs_extra_options" supports list and dict. However new default type since '
            "Sphinx-Needs 0.7.2 is list. Please see docs for details."
        )

    existing_extra_options = NEEDS_CONFIG.get("extra_options")
    for option in app.config.needs_extra_options:
        if option in existing_extra_options:
            log.warning(f'extra_option "{option}" already registered.')
        NEEDS_CONFIG.add("extra_options", {option: directives.unchanged}, dict, True)
    extra_options = NEEDS_CONFIG.get("extra_options")

    # Get extra links and create a dictionary of needed options.
    extra_links_raw = app.config.needs_extra_links
    extra_links = {}
    for extra_link in extra_links_raw:
        extra_links[extra_link["option"]] = directives.unchanged

    title_optional = app.config.needs_title_optional
    title_from_content = app.config.needs_title_from_content

    # Update NeedDirective to use customized options
    NeedDirective.option_spec.update(extra_options)
    NeedserviceDirective.option_spec.update(extra_options)

    # Update NeedDirective to use customized links
    NeedDirective.option_spec.update(extra_links)
    NeedserviceDirective.option_spec.update(extra_links)

    # Update NeedextendDirective with option modifiers.
    for key, value in NEED_DEFAULT_OPTIONS.items():
        # Ignore options like "id"
        if key in NEEDEXTEND_NOT_ALLOWED_OPTIONS:
            continue

        NeedextendDirective.option_spec.update(
            {
                key: value,
                f"+{key}": value,
                f"-{key}": directives.flag,
            }
        )

    for key, value in extra_links.items():
        NeedextendDirective.option_spec.update(
            {
                key: value,
                f"+{key}": value,
                f"-{key}": directives.flag,
                f"{key}_back": value,
                f"+{key}_back": value,
                f"-{key}_back": directives.flag,
            }
        )

    # "links" is not part of the extra_links-dict, so we need
    # to set the links_back values by hand
    NeedextendDirective.option_spec.update(
        {
            "links_back": NEED_DEFAULT_OPTIONS["links"],
            "+links_back": NEED_DEFAULT_OPTIONS["links"],
            "-links_back": directives.flag,
        }
    )
    for key, value in extra_options.items():
        NeedextendDirective.option_spec.update(
            {
                key: value,
                f"+{key}": value,
                f"-{key}": directives.flag,
            }
        )

    if title_optional or title_from_content:
        NeedDirective.required_arguments = 0
        NeedDirective.optional_arguments = 1

    for t in types:
        # Register requested types of needs
        app.add_directive(t["directive"], NeedDirective)

    existing_warnings = NEEDS_CONFIG.get("warnings")
    for name, check in app.config.needs_warnings.items():
        if name not in existing_warnings:
            NEEDS_CONFIG.add("warnings", {name: check}, dict, append=True)
        else:
            log.warning(f'{name} for "warnings" is already registered.')


def visitor_dummy(*_args, **_kwargs) -> None:
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def prepare_env(app: Sphinx, env: BuildEnvironment, _docname: str) -> None:
    """
    Prepares the sphinx environment to store sphinx-needs internal data.
    """
    if not hasattr(env, "needs_all_needs"):
        # Used to store all needed information about all needs in document
        env.needs_all_needs = {}

    if not hasattr(env, "needs_all_filters"):
        # Used to store all needed information about all filters in document
        env.needs_all_filters = {}

    if not hasattr(env, "needs_services"):
        # Used to store all needed information about all services
        app.needs_services = ServiceManager(app)

    if not hasattr(env, "needs_all_docs"):
        # Used to store all docnames, which have need-function in it and therefor
        # need to be handled later
        env.needs_all_docs = {"all": []}

    # Register embedded services
    app.needs_services.register("github-issues", GithubService, gh_type="issue")
    app.needs_services.register("github-prs", GithubService, gh_type="pr")
    app.needs_services.register("github-commits", GithubService, gh_type="commit")
    app.needs_services.register("open-needs", OpenNeedsService)

    # Register user defined services
    for name, service in app.config.needs_services.items():
        if name not in app.needs_services.services and "class" in service and "class_init" in service:
            # We found a not yet registered service
            # But only register, if service-config contains class and class_init.
            # Otherwise, the service may get registered later by an external sphinx-needs extension
            app.needs_services.register(name, service["class"], **service["class_init"])

    needs_functions = app.config.needs_functions

    # Register built-in functions
    for need_common_func in needs_common_functions:
        register_func(need_common_func)

    # Register functions configured by user
    for needs_func in needs_functions:
        register_func(needs_func)

    # Own extra options
    for option in ["hidden", "duration", "completion", "has_dead_links", "has_forbidden_dead_links", "constraints"]:
        # Check if not already set by user
        if option not in NEEDS_CONFIG.get("extra_options"):
            add_extra_option(app, option)

    # The default link name. Must exist in all configurations. Therefore we set it here
    # for the user.
    common_links = []
    link_types = app.config.needs_extra_links
    basic_link_type_found = False
    parent_needs_link_type_found = False
    for link_type in link_types:
        if link_type["option"] == "links":
            basic_link_type_found = True
        elif link_type["option"] == "parent_needs":
            parent_needs_link_type_found = True

    if not basic_link_type_found:
        common_links.append(
            {
                "option": "links",
                "outgoing": "links outgoing",
                "incoming": "links incoming",
                "copy": False,
                "color": "#000000",
            }
        )

    if not parent_needs_link_type_found:
        common_links.append(
            {
                "option": "parent_needs",
                "outgoing": "parent needs",
                "incoming": "child needs",
                "copy": False,
                "color": "#333333",
            }
        )

    app.config.needs_extra_links = common_links + app.config.needs_extra_links

    app.config.needs_layouts = {**LAYOUTS, **app.config.needs_layouts}

    app.config.needs_flow_configs.update(NEEDFLOW_CONFIG_DEFAULTS)

    if not hasattr(env, "needs_workflow"):
        # Used to store workflow status information for already executed tasks.
        # Some tasks like backlink_creation need be performed only once.
        # But most sphinx-events get called several times (for each single document
        # file), which would also execute our code several times...
        env.needs_workflow = {
            "backlink_creation_links": False,
            "dynamic_values_resolved": False,
            "links_checked": False,
            "add_sections": False,
            "variant_option_resolved": False,
            "needs_extended": False,
        }
        for link_type in app.config.needs_extra_links:
            env.needs_workflow["backlink_creation_{}".format(link_type["option"])] = False

    # Set time measurement flag
    if app.config.needs_debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build
        debug.EXECUTE_TIME_MEASUREMENTS = True


def check_configuration(_app: Sphinx, config: Config) -> None:
    """
    Checks the configuration for invalid options.

    E.g. defined need-option, which is already defined internally

    :param app:
    :param config:
    :return:
    """
    extra_options = config["needs_extra_options"]
    link_types = [x["option"] for x in config["needs_extra_links"]]

    external_filter = getattr(config, "needs_filter_data", {})
    for extern_filter, value in external_filter.items():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"External filter value: {value} from needs_filter_data {external_filter} is not a string."
            )
        # Check if needs external filter and extra option are using the same name
        if extern_filter in extra_options:
            raise NeedsConfigException(
                "Same name for external filter and extra option: {}." " This is not allowed.".format(extern_filter)
            )

    # Check for usage of internal names
    for internal in INTERNALS:
        if internal in extra_options:
            raise NeedsConfigException(
                'Extra option "{}" already used internally. ' " Please use another name.".format(internal)
            )
        if internal in link_types:
            raise NeedsConfigException(
                'Link type name "{}" already used internally. ' " Please use another name.".format(internal)
            )

    # Check if option and link are using the same name
    for link in link_types:
        if link in extra_options:
            raise NeedsConfigException(
                "Same name for link type and extra option: {}." " This is not allowed.".format(link)
            )
        if link + "_back" in extra_options:
            raise NeedsConfigException(
                "Same name for automatically created link type and extra option: {}."
                " This is not allowed.".format(link + "_back")
            )

    external_variants = getattr(config, "needs_variants", {})
    external_variant_options = getattr(config, "needs_variant_options", [])
    for value in external_variants.values():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"Variant filter value: {value} from needs_variants {external_variants} is not a string."
            )

    for option in external_variant_options:
        # Check variant option is added in either extra options or extra links or NEED_DEFAULT_OPTIONS
        if option not in extra_options and option not in link_types and option not in NEED_DEFAULT_OPTIONS.keys():
            raise NeedsConfigException(
                "Variant option `{}` is not added in either extra options or extra links. "
                "This is not allowed.".format(option)
            )


def merge_data(_app: Sphinx, env: BuildEnvironment, _docnames: List[str], other: BuildEnvironment):
    """
    Performs data merge of parallel executed workers.
    Used only for parallel builds.

    Needs to update env manually for all data Sphinx-Needs collect during read phase
    """

    # Update global needs dict
    needs = env.needs_all_needs
    other_needs = other.needs_all_needs
    needs.update(other_needs)

    def merge(name: str, is_complex_dict: bool = False) -> None:
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

    merge("need_all_needbar")
    merge("need_all_needtables")
    merge("need_all_needextend")
    merge("need_all_needextracts")
    merge("need_all_needfilters")
    merge("need_all_needflows")
    merge("need_all_needgantts")
    merge("need_all_needlists")
    merge("need_all_needpie")
    merge("need_all_needsequences")
    merge("needs_all_needumls")
    merge("needs_all_docs", is_complex_dict=True)  # list type


class NeedsConfigException(SphinxError):
    pass
