from __future__ import annotations

from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, Callable, Dict, List, Type

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.environment import BuildEnvironment
from sphinx.errors import SphinxError

import sphinx_needs.debug as debug  # Need to set global var in it for timeing measurements
from sphinx_needs.builder import (
    NeedsBuilder,
    NeedsIdBuilder,
    NeedumlsBuilder,
    build_needs_id_json,
    build_needs_json,
    build_needumls_pumls,
)
from sphinx_needs.config import NEEDS_CONFIG, LinkOptionsType, NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData, merge_data
from sphinx_needs.defaults import (
    LAYOUTS,
    NEED_DEFAULT_OPTIONS,
    NEEDEXTEND_NOT_ALLOWED_OPTIONS,
    NEEDFLOW_CONFIG_DEFAULTS,
)
from sphinx_needs.directives.list2need import List2Need, List2NeedDirective
from sphinx_needs.directives.need import (
    Need,
    NeedDirective,
    analyse_need_locations,
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
from sphinx_needs.functions import NEEDS_COMMON_FUNCTIONS, register_func
from sphinx_needs.logging import get_logger
from sphinx_needs.roles import NeedsXRefRole
from sphinx_needs.roles.need_count import NeedCount, process_need_count
from sphinx_needs.roles.need_func import NeedFunc, process_need_func
from sphinx_needs.roles.need_incoming import NeedIncoming, process_need_incoming
from sphinx_needs.roles.need_outgoing import NeedOutgoing, process_need_outgoing
from sphinx_needs.roles.need_part import NeedPart, process_need_part
from sphinx_needs.roles.need_ref import NeedRef, process_need_ref
from sphinx_needs.services.github import GithubService
from sphinx_needs.services.open_needs import OpenNeedsService
from sphinx_needs.utils import INTERNALS, NEEDS_FUNCTIONS, node_match
from sphinx_needs.warnings import process_warnings

__version__ = VERSION = "2.1.0"
NEEDS_FUNCTIONS.clear()

_NODE_TYPES_T = Dict[
    Type[nodes.Element],
    Callable[[Sphinx, nodes.document, str, List[nodes.Element]], None],
]

NODE_TYPES_PRIO: _NODE_TYPES_T = {  # Node types to be checked before most others
    Needextract: process_needextract,
}

NODE_TYPES: _NODE_TYPES_T = {
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

LOGGER = get_logger(__name__)


def setup(app: Sphinx) -> dict[str, Any]:
    LOGGER.debug("Starting setup of Sphinx-Needs")
    LOGGER.debug("Load Sphinx-Data-Viewer for Sphinx-Needs")
    app.setup_extension("sphinx_data_viewer")
    app.setup_extension("sphinxcontrib.jquery")

    app.add_builder(NeedsBuilder)
    app.add_builder(NeedumlsBuilder)
    app.add_builder(NeedsIdBuilder)

    NeedsSphinxConfig.add_config_values(app)

    # Define nodes
    app.add_node(
        Need, html=(html_visit, html_depart), latex=(latex_visit, latex_depart)
    )
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
    app.add_node(
        NeedPart,
        html=(visitor_dummy, visitor_dummy),
        latex=(visitor_dummy, visitor_dummy),
    )

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
    app.add_role(
        "need",
        NeedsXRefRole(
            nodeclass=NeedRef, innernodeclass=nodes.emphasis, warn_dangling=True
        ),
    )

    app.add_role(
        "need_incoming",
        NeedsXRefRole(
            nodeclass=NeedIncoming, innernodeclass=nodes.emphasis, warn_dangling=True
        ),
    )

    app.add_role(
        "need_outgoing",
        NeedsXRefRole(
            nodeclass=NeedOutgoing, innernodeclass=nodes.emphasis, warn_dangling=True
        ),
    )

    app.add_role(
        "need_part",
        NeedsXRefRole(
            nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True
        ),
    )
    # Shortcut for need_part
    app.add_role(
        "np",
        NeedsXRefRole(
            nodeclass=NeedPart, innernodeclass=nodes.inline, warn_dangling=True
        ),
    )

    app.add_role(
        "need_count",
        NeedsXRefRole(
            nodeclass=NeedCount, innernodeclass=nodes.inline, warn_dangling=True
        ),
    )

    app.add_role(
        "need_func",
        NeedsXRefRole(
            nodeclass=NeedFunc, innernodeclass=nodes.inline, warn_dangling=True
        ),
    )

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect("config-inited", load_config)
    app.connect("config-inited", check_configuration)

    app.connect("env-before-read-docs", prepare_env)
    app.connect("env-before-read-docs", load_external_needs)

    app.connect("env-purge-doc", purge_needs)

    app.connect("doctree-read", analyse_need_locations)

    app.connect("env-merge-info", merge_data)

    app.connect("env-updated", install_lib_static_files)
    app.connect("env-updated", install_permalink_file)
    # This should be called last, so that need-styles can override styles from used libraries
    app.connect("env-updated", install_styles_static_files)

    # There is also the event doctree-read.
    # But it looks like in this event no references are already solved, which
    # makes trouble in our code.
    # However, some sphinx-internal actions (like image collection) are already called during
    # doctree-read. So manipulating the doctree may result in conflicts, as e.g. images get not
    # registered for sphinx. So some sphinx-internal tasks/functions may be called by hand again...
    # See also https://github.com/sphinx-doc/sphinx/issues/7054#issuecomment-578019701 for an example
    app.connect(
        "doctree-resolved",
        process_creator(NODE_TYPES_PRIO, "needextract"),
        priority=100,
    )
    app.connect("doctree-resolved", process_need_nodes)
    app.connect("doctree-resolved", process_creator(NODE_TYPES))

    app.connect("build-finished", process_warnings)
    app.connect("build-finished", build_needs_json)
    app.connect("build-finished", build_needs_id_json)
    app.connect("build-finished", build_needumls_pumls)
    app.connect("build-finished", debug.process_timing)

    # Be sure Sphinx-Needs config gets erased before any events or external API calls get executed.
    # So never but this inside an event.
    NEEDS_CONFIG.clear()

    return {
        "version": VERSION,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def process_creator(
    node_list: _NODE_TYPES_T, doc_category: str = "all"
) -> Callable[[Sphinx, nodes.document, str], None]:
    """
    Create a pre-configured process_caller for given Node types
    """

    def process_caller(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
        """
        A single event_handler for doc-tree-resolved, which cares about the doctree-parsing
        only once and calls the needed sub-handlers (like process_needtables and so).

        Reason: In the past all process-xy handles have parsed the doctree by their own, so the same doctree
        got parsed several times. This is now done at a single place and the related process-xy get a
        list of found docutil node-object for their case.
        """
        # We only need to analyse docs, which have Sphinx-Needs directives in it.
        if (
            fromdocname
            not in SphinxNeedsData(app.env).get_or_create_docs().get(doc_category, [])
            and fromdocname != f"{app.config.root_doc}"
        ):
            return
        current_nodes: dict[type[nodes.Element], list[nodes.Element]] = {}
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
            if (
                check_node in current_nodes
                and check_func is not None
                and current_nodes[check_node]
            ):
                check_func(app, doctree, fromdocname, current_nodes[check_node])

    return process_caller


def load_config(app: Sphinx, *_args: Any) -> None:
    """
    Register extra options and directive based on config from conf.py
    """
    needs_config = NeedsSphinxConfig(app.config)

    if isinstance(needs_config.extra_options, dict):
        LOGGER.info(
            'Config option "needs_extra_options" supports list and dict. However new default type since '
            "Sphinx-Needs 0.7.2 is list. Please see docs for details."
        )

    for option in needs_config.extra_options:
        if option in NEEDS_CONFIG.extra_options:
            LOGGER.warning(
                f'extra_option "{option}" already registered. [needs.config]',
                type="needs",
                subtype="config",
            )
        NEEDS_CONFIG.extra_options[option] = directives.unchanged

    # ensure options for ``needgantt`` functionality are added to the extra options
    for option in (needs_config.duration_option, needs_config.completion_option):
        if option not in NEEDS_CONFIG.extra_options:
            NEEDS_CONFIG.extra_options[option] = directives.unchanged_required

    # Get extra links and create a dictionary of needed options.
    extra_links_raw = needs_config.extra_links
    extra_links = {}
    for extra_link in extra_links_raw:
        extra_links[extra_link["option"]] = directives.unchanged

    title_optional = needs_config.title_optional
    title_from_content = needs_config.title_from_content

    # Update NeedDirective to use customized options
    NeedDirective.option_spec.update(NEEDS_CONFIG.extra_options)
    NeedserviceDirective.option_spec.update(NEEDS_CONFIG.extra_options)

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
    for key, value in NEEDS_CONFIG.extra_options.items():
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

    for t in needs_config.types:
        # Register requested types of needs
        app.add_directive(t["directive"], NeedDirective)

    for name, check in needs_config.warnings.items():
        if name not in NEEDS_CONFIG.warnings:
            NEEDS_CONFIG.warnings[name] = check
        else:
            LOGGER.warning(
                f"{name!r} in 'needs_warnings' is already registered. [needs.config]",
                type="needs",
                subtype="config",
            )

    if needs_config.constraints_failed_color:
        LOGGER.warning(
            'Config option "needs_constraints_failed_color" is deprecated. Please use "needs_constraint_failed_options" styles instead. [needs.config]',
            type="needs",
            subtype="config",
        )

    if needs_config.report_dead_links is not True:
        LOGGER.warning(
            'Config option "needs_constraints_failed_color" is deprecated. Please use `suppress_warnings = ["needs.link_outgoing"]` instead. [needs.config]',
            type="needs",
            subtype="config",
        )


def visitor_dummy(*_args: Any, **_kwargs: Any) -> None:
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def prepare_env(app: Sphinx, env: BuildEnvironment, _docname: str) -> None:
    """
    Prepares the sphinx environment to store sphinx-needs internal data.
    """
    needs_config = NeedsSphinxConfig(app.config)
    data = SphinxNeedsData(env)
    data.get_or_create_needs()
    data.get_or_create_filters()
    data.get_or_create_docs()
    services = data.get_or_create_services()

    # Register embedded services
    services.register("github-issues", GithubService, gh_type="issue")
    services.register("github-prs", GithubService, gh_type="pr")
    services.register("github-commits", GithubService, gh_type="commit")
    services.register("open-needs", OpenNeedsService)

    # Register user defined services
    for name, service in needs_config.services.items():
        if (
            name not in services.services
            and "class" in service
            and "class_init" in service
        ):
            # We found a not yet registered service
            # But only register, if service-config contains class and class_init.
            # Otherwise, the service may get registered later by an external sphinx-needs extension
            services.register(name, service["class"], **service["class_init"])

    # Register built-in functions
    for need_common_func in NEEDS_COMMON_FUNCTIONS:
        register_func(need_common_func)

    # Register functions configured by user
    for needs_func in needs_config.functions:
        register_func(needs_func)

    # The default link name. Must exist in all configurations. Therefore we set it here
    # for the user.
    common_links: list[LinkOptionsType] = []
    link_types = needs_config.extra_links
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

    needs_config.extra_links = common_links + needs_config.extra_links
    needs_config.layouts = {**LAYOUTS, **needs_config.layouts}

    needs_config.flow_configs.update(NEEDFLOW_CONFIG_DEFAULTS)

    # Set time measurement flag
    if needs_config.debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build
        debug.EXECUTE_TIME_MEASUREMENTS = True


def check_configuration(_app: Sphinx, config: Config) -> None:
    """Checks the configuration for invalid options.

    E.g. defined need-option, which is already defined internally
    """
    needs_config = NeedsSphinxConfig(config)
    extra_options = needs_config.extra_options
    link_types = [x["option"] for x in needs_config.extra_links]

    external_filter = needs_config.filter_data
    for extern_filter, value in external_filter.items():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"External filter value: {value} from needs_filter_data {external_filter} is not a string."
            )
        # Check if needs external filter and extra option are using the same name
        if extern_filter in extra_options:
            raise NeedsConfigException(
                f"Same name for external filter and extra option: {extern_filter}."
                " This is not allowed."
            )

    # Check for usage of internal names
    for internal in INTERNALS:
        if internal in extra_options:
            raise NeedsConfigException(
                f'Extra option "{internal}" already used internally. '
                " Please use another name."
            )
        if internal in link_types:
            raise NeedsConfigException(
                f'Link type name "{internal}" already used internally. '
                " Please use another name."
            )

    # Check if option and link are using the same name
    for link in link_types:
        if link in extra_options:
            raise NeedsConfigException(
                f"Same name for link type and extra option: {link}."
                " This is not allowed."
            )
        if link + "_back" in extra_options:
            raise NeedsConfigException(
                "Same name for automatically created link type and extra option: {}."
                " This is not allowed.".format(link + "_back")
            )

    external_variants = needs_config.variants
    external_variant_options = needs_config.variant_options
    for value in external_variants.values():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"Variant filter value: {value} from needs_variants {external_variants} is not a string."
            )

    for option in external_variant_options:
        # Check variant option is added in either extra options or extra links or NEED_DEFAULT_OPTIONS
        if (
            option not in extra_options
            and option not in link_types
            and option not in NEED_DEFAULT_OPTIONS.keys()
        ):
            raise NeedsConfigException(
                f"Variant option `{option}` is not added in either extra options or extra links. "
                "This is not allowed."
            )


class NeedsConfigException(SphinxError):
    pass
