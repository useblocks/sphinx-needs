# -*- coding: utf-8 -*-

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.errors import SphinxError
from sphinx.roles import XRefRole

from sphinxcontrib.needs.builder import NeedsBuilder
from sphinxcontrib.needs.defaults import (
    DEFAULT_DIAGRAM_TEMPLATE,
    LAYOUTS,
    NEED_DEFAULT_OPTIONS,
    NEEDEXTEND_NOT_ALLOWED_OPTIONS,
    NEEDFLOW_CONFIG_DEFAULTS,
)
from sphinxcontrib.needs.directives.need import (
    Need,
    NeedDirective,
    add_sections,
    html_depart,
    html_visit,
    latex_depart,
    latex_visit,
    print_need_nodes,
    process_need_nodes,
    purge_needs,
)
from sphinxcontrib.needs.directives.needextend import (
    Needextend,
    NeedextendDirective,
    process_needextend,
)
from sphinxcontrib.needs.directives.needextract import (
    Needextract,
    NeedextractDirective,
    process_needextract,
)
from sphinxcontrib.needs.directives.needfilter import (
    Needfilter,
    NeedfilterDirective,
    process_needfilters,
)
from sphinxcontrib.needs.directives.needflow import (
    Needflow,
    NeedflowDirective,
    process_needflow,
)
from sphinxcontrib.needs.directives.needgantt import (
    Needgantt,
    NeedganttDirective,
    process_needgantt,
)
from sphinxcontrib.needs.directives.needimport import Needimport, NeedimportDirective
from sphinxcontrib.needs.directives.needlist import (
    Needlist,
    NeedlistDirective,
    process_needlist,
)
from sphinxcontrib.needs.directives.needpie import (
    Needpie,
    NeedpieDirective,
    process_needpie,
)
from sphinxcontrib.needs.directives.needsequence import (
    Needsequence,
    NeedsequenceDirective,
    process_needsequence,
)
from sphinxcontrib.needs.directives.needservice import Needservice, NeedserviceDirective
from sphinxcontrib.needs.directives.needtable import (
    Needtable,
    NeedtableDirective,
    process_needtables,
)
from sphinxcontrib.needs.environment import (
    install_lib_static_files,
    install_styles_static_files,
)
from sphinxcontrib.needs.external_needs import load_external_needs
from sphinxcontrib.needs.functions import needs_common_functions, register_func
from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.roles.need_count import NeedCount, process_need_count
from sphinxcontrib.needs.roles.need_func import NeedFunc, process_need_func
from sphinxcontrib.needs.roles.need_incoming import NeedIncoming, process_need_incoming
from sphinxcontrib.needs.roles.need_outgoing import NeedOutgoing, process_need_outgoing
from sphinxcontrib.needs.roles.need_part import NeedPart, process_need_part
from sphinxcontrib.needs.roles.need_ref import NeedRef, process_need_ref
from sphinxcontrib.needs.services.github import GithubService
from sphinxcontrib.needs.services.manager import ServiceManager
from sphinxcontrib.needs.utils import INTERNALS, NEEDS_FUNCTIONS
from sphinxcontrib.needs.warnings import process_warnings

VERSION = "0.7.0"
NEEDS_FUNCTIONS.clear()


class TagsDummy:
    """
    Dummy class for faking tags.has() feature during own import of conf.py
    """

    @staticmethod
    def has(*_args):
        return True


def setup(app):
    log = get_logger(__name__)
    log.debug("Starting setup of sphinx-Needs")
    app.add_builder(NeedsBuilder)
    app.add_config_value(
        "needs_types",
        [
            dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
            dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
            dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
            dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
            # Kept for backwards compatibility
            dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node"),
        ],
        "html",
    )
    app.add_config_value("needs_include_needs", True, "html", types=[bool])
    app.add_config_value("needs_need_name", "Need", "html", types=[str])
    app.add_config_value("needs_spec_name", "Specification", "html", types=[str])
    app.add_config_value("needs_id_prefix_needs", "", "html", types=[str])
    app.add_config_value("needs_id_prefix_specs", "", "html", types=[str])
    app.add_config_value("needs_id_length", 5, "html", types=[int])
    app.add_config_value("needs_specs_show_needlist", False, "html", types=[bool])
    app.add_config_value("needs_id_required", False, "html", types=[bool])
    app.add_config_value(
        "needs_id_regex",
        "^[A-Z0-9_]{{{id_length},}}".format(id_length=app.config.needs_id_length),
        "html",
    )
    app.add_config_value("needs_show_link_type", False, "html", types=[bool])
    app.add_config_value("needs_show_link_title", False, "html", types=[bool])
    app.add_config_value("needs_file", "needs.json", "html")
    app.add_config_value("needs_table_columns", "ID;TITLE;STATUS;TYPE;OUTGOING;TAGS", "html")
    app.add_config_value("needs_table_style", "DATATABLES", "html")

    app.add_config_value("needs_role_need_template", "{title} ({id})", "html")
    app.add_config_value("needs_role_need_max_title_length", 30, "html", types=[int])

    app.add_config_value("needs_extra_options", {}, "html")
    app.add_config_value("needs_title_optional", False, "html", types=[bool])
    app.add_config_value("needs_max_title_length", -1, "html", types=[int])
    app.add_config_value("needs_title_from_content", False, "html", types=[bool])

    app.add_config_value("needs_diagram_template", DEFAULT_DIAGRAM_TEMPLATE, "html")

    app.add_config_value("needs_functions", [], "html", types=[list])
    app.add_config_value("needs_global_options", {}, "html", types=[dict])

    app.add_config_value("needs_duration_option", "duration", "html")
    app.add_config_value("needs_completion_option", "completion", "html")

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
    app.add_config_value("needs_tags", False, "html", types=[bool])

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

    app.add_config_value("needs_flow_show_links", False, "html")
    app.add_config_value("needs_flow_link_types", ["links"], "html")

    app.add_config_value("needs_warnings", {}, "html")
    app.add_config_value("needs_layouts", {}, "html")
    app.add_config_value("needs_default_layout", "clean", "html")
    app.add_config_value("needs_default_style", None, "html")

    app.add_config_value("needs_flow_configs", {}, "html")

    app.add_config_value("needs_template_folder", "needs_templates/", "html")

    app.add_config_value("needs_services", {}, "html")
    app.add_config_value("needs_service_all_data", False, "html", types=[bool])

    app.add_config_value("needs_debug_no_external_calls", False, "html", types=[bool])

    app.add_config_value("needs_external_needs", [], "html")

    # Define nodes
    app.add_node(Need, html=(html_visit, html_depart), latex=(latex_visit, latex_depart))
    app.add_node(
        Needfilter,
    )
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
    app.add_node(NeedPart, html=(visitor_dummy, visitor_dummy), latex=(visitor_dummy, visitor_dummy))

    ########################################################################
    # DIRECTIVES
    ########################################################################

    # Define directives
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

    ########################################################################
    # ROLES
    ########################################################################
    # Provides :need:`ABC_123` for inline links.
    app.add_role("need", XRefRole(nodeclass=NeedRef, innernodeclass=nodes.emphasis, warn_dangling=True))

    app.add_role("need_incoming", XRefRole(nodeclass=NeedIncoming, innernodeclass=nodes.emphasis, warn_dangling=True))

    app.add_role("need_outgoing", XRefRole(nodeclass=NeedOutgoing, innernodeclass=nodes.emphasis, warn_dangling=True))

    app.add_role("need_part", XRefRole(nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True))
    # Shortcut for need_part
    app.add_role("np", XRefRole(nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True))

    app.add_role("need_count", XRefRole(nodeclass=NeedCount, innernodeclass=nodes.inline, warn_dangling=True))

    app.add_role("need_func", XRefRole(nodeclass=NeedFunc, innernodeclass=nodes.inline, warn_dangling=True))

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect("env-purge-doc", purge_needs)
    app.connect("config-inited", load_config)
    app.connect("env-before-read-docs", prepare_env)
    app.connect("env-before-read-docs", load_external_needs)
    app.connect("config-inited", check_configuration)

    # There is also the event doctree-read.
    # But it looks like in this event no references are already solved, which
    # makes trouble in our code.
    # However, some sphinx-internal actions (like image collection) are already called during
    # doctree-read. So manipulating the doctree may result in conflicts, as e.g. images get not
    # registered for sphinx. So some sphinx-internal tasks/functions may be called by hand again...
    # See also https://github.com/sphinx-doc/sphinx/issues/7054#issuecomment-578019701 for an example
    app.connect("doctree-resolved", add_sections)
    app.connect("doctree-resolved", process_need_nodes)
    app.connect("doctree-resolved", process_needextend)  # Must be done very early, as it modifies need data
    app.connect("doctree-resolved", print_need_nodes)
    app.connect("doctree-resolved", process_needextract)
    app.connect("doctree-resolved", process_needfilters)
    app.connect("doctree-resolved", process_needlist)
    app.connect("doctree-resolved", process_needtables)
    app.connect("doctree-resolved", process_needflow)
    app.connect("doctree-resolved", process_needpie)
    app.connect("doctree-resolved", process_needsequence)
    app.connect("doctree-resolved", process_needgantt)
    app.connect("doctree-resolved", process_need_part)
    app.connect("doctree-resolved", process_need_ref)
    app.connect("doctree-resolved", process_need_incoming)
    app.connect("doctree-resolved", process_need_outgoing)
    app.connect("doctree-resolved", process_need_count)
    app.connect("doctree-resolved", process_need_func)
    app.connect("build-finished", process_warnings)
    app.connect("env-updated", install_lib_static_files)

    # Called during consistency check, which if after everything got read in.
    # app.connect('env-check-consistency', process_warnings)

    # This should be called last, so that need-styles can override styles from used libraries
    app.connect("env-updated", install_styles_static_files)

    return {
        "version": VERSION,
        "parallel_read_safe": False,  # Must be False, otherwise IDs are not found exceptions are raised.
        "parallel_write_safe": True,
    }


def load_config(app: Sphinx, *_args):
    """
    Register extra options and directive based on config from conf.py
    """
    types = app.config.needs_types
    extra_options = app.config.needs_extra_options

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


def visitor_dummy(*_args, **_kwargs):
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def prepare_env(app, env, _docname):
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

    # Register embedded services
    app.needs_services.register("github-issues", GithubService, gh_type="issue")
    app.needs_services.register("github-prs", GithubService, gh_type="pr")
    app.needs_services.register("github-commits", GithubService, gh_type="commit")

    # Register user defined services
    for name, service in app.config.needs_services.items():
        if name not in app.needs_services.services.keys():
            # We found a not yet registered service
            app.needs_services.register(name, service["class"], **service["class_init"])

    needs_functions = app.config.needs_functions

    # Register built-in functions
    for need_common_func in needs_common_functions:
        register_func(need_common_func)

    # Register functions configured by user
    for needs_func in needs_functions:
        register_func(needs_func)

    # Own extra options
    for option in ["hidden", "duration", "completion", "has_dead_links", "has_forbidden_dead_links"]:
        # Check if not already set by user
        if option not in app.config.needs_extra_options.keys():
            app.config.needs_extra_options[option] = directives.unchanged

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
        # Some tasks like backlink_creation need be be performed only once.
        # But most sphinx-events get called several times (for each single document
        # file), which would also execute our code several times...
        env.needs_workflow = {
            "backlink_creation_links": False,
            "dynamic_values_resolved": False,
            "needs_extended": False,
        }
        for link_type in app.config.needs_extra_links:
            env.needs_workflow["backlink_creation_{}".format(link_type["option"])] = False


def check_configuration(_app: Sphinx, config: Config):
    """
    Checks the configuration for invalid options.

    E.g. defined need-option, which is already defined internally

    :param app:
    :param config:
    :return:
    """
    extra_options = config["needs_extra_options"]
    link_types = [x["option"] for x in config["needs_extra_links"]]

    # Check for usage of internal names
    for internal in INTERNALS:
        if internal in extra_options.keys():
            raise NeedsConfigException(
                'Extra option "{}" already used internally. ' " Please use another name.".format(internal)
            )
        if internal in link_types:
            raise NeedsConfigException(
                'Link type name "{}" already used internally. ' " Please use another name.".format(internal)
            )

    # Check if option and link are using the same name
    for link in link_types:
        if link in extra_options.keys():
            raise NeedsConfigException(
                "Same name for link type and extra option: {}." " This is not allowed.".format(link)
            )
        if link + "_back" in extra_options.keys():
            raise NeedsConfigException(
                "Same name for automatically created link type and extra option: {}."
                " This is not allowed.".format(link + "_back")
            )


class NeedsConfigException(SphinxError):
    pass
