from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, TypedDict, cast

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.config import Config
from sphinx.config import Config as _SphinxConfig
from sphinx.environment import BuildEnvironment

import sphinx_needs.debug as debug  # Need to set global var in it for timeing measurements
from sphinx_needs import __version__
from sphinx_needs.api import get_needs_view
from sphinx_needs.builder import (
    NeedsBuilder,
    NeedsIdBuilder,
    NeedumlsBuilder,
    SchemaBuilder,
    build_needs_id_json,
    build_needs_json,
    build_needumls_pumls,
)
from sphinx_needs.config import (
    _NEEDS_CONFIG,
    LinkOptionsType,
    NeedsSphinxConfig,
)
from sphinx_needs.data import (
    ENV_DATA_VERSION,
    CoreFieldParameters,
    NeedsCoreFields,
    SphinxNeedsData,
    merge_data,
)
from sphinx_needs.defaults import (
    GRAPHVIZ_STYLE_DEFAULTS,
    LAYOUTS,
    NEEDFLOW_CONFIG_DEFAULTS,
)
from sphinx_needs.directives.list2need import List2Need, List2NeedDirective
from sphinx_needs.directives.need import (
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
from sphinx_needs.directives.needflow import (
    NeedflowDirective,
    NeedflowGraphiz,
    NeedflowPlantuml,
    html_visit_needflow_graphviz,
    process_needflow_graphviz,
    process_needflow_plantuml,
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
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.external_needs import load_external_needs
from sphinx_needs.functions import NEEDS_COMMON_FUNCTIONS
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkSchema,
    LinksLiteralValue,
    create_inherited_field,
)
from sphinx_needs.nodes import Need
from sphinx_needs.roles import NeedsXRefRole
from sphinx_needs.roles.need_count import NeedCount, process_need_count
from sphinx_needs.roles.need_func import NeedFunc, NeedFuncRole, process_need_func
from sphinx_needs.roles.need_incoming import NeedIncoming, process_need_incoming
from sphinx_needs.roles.need_outgoing import NeedOutgoing, process_need_outgoing
from sphinx_needs.roles.need_part import NeedPart, NeedPartRole, process_need_part
from sphinx_needs.roles.need_ref import NeedRef, process_need_ref
from sphinx_needs.schema.config import (
    ExtraOptionIntegerSchemaType,
    SchemasFileRootType,
)
from sphinx_needs.schema.config_utils import (
    resolve_schemas_config,
    validate_schemas_config,
)
from sphinx_needs.schema.process import process_schemas
from sphinx_needs.services.github import GithubService
from sphinx_needs.services.open_needs import OpenNeedsService
from sphinx_needs.utils import node_match
from sphinx_needs.warnings import process_warnings

try:
    import tomllib  # added in python 3.11
except ImportError:
    import tomli as tomllib


VERSION = __version__

_NODE_TYPES_T = dict[
    type[nodes.Element],
    Callable[[Sphinx, nodes.document, str, list[nodes.Element]], None],
]

NODE_TYPES_PRIO: _NODE_TYPES_T = {  # Node types to be checked before most others
    Needextract: process_needextract,
}

NODE_TYPES: _NODE_TYPES_T = {
    Needbar: process_needbar,
    # Needextract: process_needextract,
    Needlist: process_needlist,
    Needtable: process_needtables,
    NeedflowPlantuml: process_needflow_plantuml,
    NeedflowGraphiz: process_needflow_graphviz,
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


def load_schemas_config_from_json(app: Sphinx, config: _SphinxConfig) -> None:
    """Merge the configuration from the JSON file into the Sphinx config."""
    needs_config = NeedsSphinxConfig(config)
    if needs_config.schema_definitions_from_json is None:
        return
    if needs_config.schema_definitions:
        raise NeedsConfigException(
            "You cannot use both 'needs_schema_definitions' and 'needs_schema_definitions_from_json' at the same time."
        )
    json_file = Path(app.confdir, needs_config.schema_definitions_from_json).resolve()

    if not json_file.exists():
        raise NeedsConfigException(
            f"'needs_schema_definitions_from_json' file does not exist: {json_file}"
        )

    try:
        with Path(json_file).open("rb") as fp:
            json_data = json.load(fp)
        assert isinstance(json_data, dict), "Data must be a dict"
    except Exception as exc:
        raise NeedsConfigException(f"Could not load JSON file: {exc}") from exc

    # schema_definitions are checked later in validate_schemas_config()
    needs_config.schema_definitions = cast(SchemasFileRootType, json_data)


def setup(app: Sphinx) -> dict[str, Any]:
    LOGGER.debug("Starting setup of Sphinx-Needs")
    LOGGER.debug("Load Sphinx-Data-Viewer for Sphinx-Needs")
    app.setup_extension("sphinx_data_viewer")
    app.setup_extension("sphinxcontrib.jquery")
    app.setup_extension("sphinx.ext.graphviz")

    app.add_builder(NeedsBuilder)
    app.add_builder(NeedumlsBuilder)
    app.add_builder(NeedsIdBuilder)
    app.add_builder(SchemaBuilder)

    NeedsSphinxConfig.add_config_values(app)

    # Define nodes
    app.add_node(
        Need, html=(html_visit, html_depart), latex=(latex_visit, latex_depart)
    )
    app.add_node(Needbar)
    app.add_node(Needimport)
    app.add_node(Needlist)
    app.add_node(Needtable)
    app.add_node(NeedflowPlantuml)
    app.add_node(NeedflowGraphiz, html=(html_visit_needflow_graphviz, None))
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

    app.add_role("need_part", NeedPartRole())
    app.add_role("np", NeedPartRole())  # Shortcut for need_part

    app.add_role(
        "need_count",
        NeedsXRefRole(
            nodeclass=NeedCount, innernodeclass=nodes.inline, warn_dangling=True
        ),
    )

    app.add_role("need_func", NeedFuncRole(with_brackets=True))  # deprecrated
    app.add_role("ndf", NeedFuncRole(with_brackets=False))

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect("config-inited", load_config_from_toml, priority=10)  # runs early
    app.connect("config-inited", load_config)
    app.connect("config-inited", merge_default_configs)
    app.connect("config-inited", check_configuration, priority=600)  # runs late

    app.connect("env-before-read-docs", prepare_env)
    # note we have to place create_schema after prepare_env, as that can add extra options,
    # but before load_external_needs, where we start to add needs.
    app.connect("env-before-read-docs", create_schema)
    # schemas type injection uses information from create_schema
    app.connect("env-before-read-docs", resolve_schemas_config)

    app.connect("env-before-read-docs", load_external_needs)

    app.connect("env-purge-doc", purge_needs)

    app.connect("doctree-read", analyse_need_locations)

    app.connect("env-merge-info", merge_data)

    app.connect("env-updated", install_lib_static_files)
    app.connect("env-updated", install_permalink_file)
    # This should be called last, so that need-styles can override styles from used libraries
    app.connect("env-updated", install_styles_static_files)

    # emitted during post_process_needs_data, both are passed the mutable needs dict
    app.add_event("needs-before-post-processing")
    app.add_event("needs-before-sealing")

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

    app.connect("write-started", process_schemas)
    app.connect("write-started", ensure_post_process_needs_data)

    app.connect("build-finished", process_warnings)
    app.connect("build-finished", build_needs_json)
    app.connect("build-finished", build_needs_id_json)
    app.connect("build-finished", build_needumls_pumls)
    app.connect("build-finished", debug.process_timing)
    app.connect("build-finished", release_data_locks, priority=9999)

    # Be sure Sphinx-Needs config gets erased before any events or external API calls get executed.
    # So never but this inside an event.
    _NEEDS_CONFIG.clear()

    return {
        "version": VERSION,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
        "env_version": ENV_DATA_VERSION,
    }


def ensure_post_process_needs_data(app: Sphinx, builder: Builder) -> None:
    """
    Make sure post_process_needs_data is called at least once.

    Warnings are emitted in that step, even when no docs are updated.
    """
    get_needs_view(app)


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


def load_config_from_toml(app: Sphinx, config: Config) -> None:
    """
    Load config from toml file, if defined in conf.py

    All configs starting with "schema_" are loaded from a dedicated
    "schema" table in the toml file.
    """
    needs_config = NeedsSphinxConfig(config)
    if needs_config.from_toml is None:
        return

    # resolve relative to confdir
    toml_file = Path(app.confdir, needs_config.from_toml).resolve()
    toml_path = needs_config.from_toml_table

    if not toml_file.exists():
        log_warning(
            LOGGER,
            f"'needs_from_toml' file does not exist: {toml_file}",
            "config",
            None,
        )
        return
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)
        for key in (*toml_path, "needs"):
            toml_data = toml_data[key]
        assert isinstance(toml_data, dict), "Data must be a dict"
        if "schema" in toml_data:
            assert isinstance(toml_data["schema"], dict), (
                "'schema' table must be a dict"
            )

    except Exception as e:
        log_warning(
            LOGGER,
            f"Error loading 'needs_from_toml' file: {e}",
            "config",
            None,
        )
        return

    allowed_keys = NeedsSphinxConfig.field_names()

    for key, value in toml_data.items():
        if key not in allowed_keys:
            continue
        config["needs_" + key] = NeedsSphinxConfig.convert_field_value(
            key, value, toml_file.parent
        )

    for key, value in toml_data.get("schema", {}).items():
        if key not in allowed_keys:
            continue
        config["needs_schema_"][key] = NeedsSphinxConfig.convert_field_value(
            key, value, toml_file.parent, "schema_"
        )


def load_config(app: Sphinx, *_args: Any) -> None:
    """
    Register extra options and directive based on config from conf.py
    """
    needs_config = NeedsSphinxConfig(app.config)

    if not isinstance(needs_config._extra_options, list):
        raise NeedsConfigException(
            "Config option 'needs_extra_options' must be a list."
        )

    if needs_config._extra_options:
        log_warning(
            LOGGER,
            'Config option "needs_extra_options" is deprecated. Please use "needs_fields" instead.',
            "deprecated",
            None,
        )

    for option in needs_config._extra_options:
        description = "Added by needs_extra_options config"
        schema = None
        if isinstance(option, str):
            name = option
        elif isinstance(option, dict):
            try:
                name = option["name"]
            except KeyError:
                log_warning(
                    LOGGER,
                    f"extra_option is a dict, but does not contain a 'name' key: {option}",
                    "config",
                    None,
                )
                continue
            description = option.get("description", description)
            schema = option.get("schema")
        else:
            log_warning(
                LOGGER,
                f"extra_option is not a string or dict: {option}",
                "config",
                None,
            )
            continue

        _NEEDS_CONFIG.add_extra_option(name, description, schema=schema, override=True)

    if not isinstance(needs_config._fields, dict):
        raise NeedsConfigException("Config option 'needs_fields' must be a dict.")

    for option_name, option_params in needs_config._fields.items():
        if not isinstance(option_name, str):
            log_warning(
                LOGGER,
                f"needs_fields key is not a string: {option_name}",
                "config",
                None,
            )
            continue
        if not isinstance(option_params, dict):
            log_warning(
                LOGGER,
                f"needs_fields entry for '{option_name}' is not a dict: {option_params}",
                "config",
                None,
            )
            continue
        if option_name in NeedsCoreFields:
            continue
        description = option_params.get("description", "Added by needs_fields config")
        schema = option_params.get("schema")
        nullable = option_params.get("nullable")
        parse_variants = option_params.get("parse_variants")
        _NEEDS_CONFIG.add_extra_option(
            option_name,
            description,
            schema=schema,
            nullable=nullable,
            parse_variants=parse_variants,
            override=True,
        )

    # ensure options for `needgantt` functionality are added to the extra options
    for option in (needs_config.duration_option, needs_config.completion_option):
        default_schema: ExtraOptionIntegerSchemaType = {"type": "integer"}
        if option not in _NEEDS_CONFIG.extra_options:
            _NEEDS_CONFIG.add_extra_option(
                option, "Added for needgantt functionality", schema=default_schema
            )
        else:
            # ensure schema is correct
            existing = _NEEDS_CONFIG.extra_options[option]
            if existing.schema is None:
                existing.schema = default_schema
            else:
                if existing.schema.get("type") not in {"integer", "number"}:
                    raise NeedsConfigException(
                        f"Schema type for option '{option}' is not 'integer' or 'number' as required by needgantt."
                    )

    for t in needs_config.types:
        # Register requested types of needs
        app.add_directive(t["directive"], NeedDirective)

    for name, check in needs_config._warnings.items():
        if name not in _NEEDS_CONFIG.warnings:
            _NEEDS_CONFIG.add_warning(name, check)
        else:
            log_warning(
                LOGGER,
                f"{name!r} in 'needs_warnings' is already registered.",
                "config",
                None,
            )

    if needs_config.constraints_failed_color:
        log_warning(
            LOGGER,
            'Config option "needs_constraints_failed_color" is deprecated. Please use "needs_constraint_failed_options" styles instead.',
            "config",
            None,
        )

    if needs_config.report_dead_links is not True:
        log_warning(
            LOGGER,
            'Config option "needs_report_dead_links" is deprecated. Please use `suppress_warnings = ["needs.link_outgoing"]` instead.',
            "config",
            None,
        )

    load_schemas_config_from_json(app, app.config)


def visitor_dummy(*_args: Any, **_kwargs: Any) -> None:
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def prepare_env(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:
    """
    Prepares the sphinx environment to store sphinx-needs internal data.
    """
    needs_config = NeedsSphinxConfig(app.config)
    data = SphinxNeedsData(env)

    # Register embedded services
    services = data.get_or_create_services()
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

    # Set time measurement flag
    if needs_config.debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build
        debug.EXECUTE_TIME_MEASUREMENTS = True

    if needs_config.debug_filters:
        with contextlib.suppress(FileNotFoundError):
            Path(str(app.outdir), "debug_filters.jsonl").unlink()


def merge_default_configs(_app: Sphinx, config: Config) -> None:
    """Merge built-in defaults with user configuration."""
    needs_config = NeedsSphinxConfig(config)

    needs_config.layouts = {**LAYOUTS, **needs_config.layouts}

    needs_config.flow_configs = {
        **NEEDFLOW_CONFIG_DEFAULTS,
        **needs_config.flow_configs,
    }
    needs_config.graphviz_styles = {
        **GRAPHVIZ_STYLE_DEFAULTS,
        **needs_config.graphviz_styles,
    }

    # Register built-in functions
    for need_common_func in NEEDS_COMMON_FUNCTIONS:
        _NEEDS_CONFIG.add_function(need_common_func)

    # Register functions configured by user
    for needs_func in needs_config._functions:
        _NEEDS_CONFIG.add_function(needs_func)

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

    for link in needs_config.extra_links:
        if "outgoing" not in link:
            link["outgoing"] = link["option"]
        if "incoming" not in link:
            link["incoming"] = f"{link['option']} incoming"


def check_configuration(app: Sphinx, config: Config) -> None:
    """Checks the configuration for invalid options.

    E.g. defined need-option, which is already defined internally
    """
    needs_config = NeedsSphinxConfig(config)
    extra_options = _NEEDS_CONFIG.extra_options
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
    for internal in NeedsCoreFields:
        if internal in extra_options:
            raise NeedsConfigException(
                f'Extra option "{internal}" already used internally. '
                " Please use another name in your config (needs_extra_options)."
            )
        if internal in link_types:
            raise NeedsConfigException(
                f'Link type name "{internal}" already used internally. '
                " Please use another name in your config (needs_extra_links)."
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
    for value in external_variants.values():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"Variant filter value: {value} from needs_variants {external_variants} is not a string."
            )

    if needs_config._variant_options:
        log_warning(
            LOGGER,
            'Config option "needs_variant_options" is deprecated. Please use "needs_fields" with "parse_variants" instead.',
            "deprecated",
            None,
        )
        allowed_internal_variants = {
            k for k, v in NeedsCoreFields.items() if v.get("allow_variants")
        }
        for option in needs_config._variant_options:
            # Check variant option is added to an allowed field
            if option in link_types:
                raise NeedsConfigException(
                    f"Variant option `{option}` is a link type. This is not allowed."
                )
            if option not in extra_options and option not in allowed_internal_variants:
                raise NeedsConfigException(
                    f"Variant option `{option}` is not added in needs_extra_options or needs_fields. "
                    "This is not allowed."
                )

    validate_schemas_config(app, needs_config)


def _get_core_schema(data: CoreFieldParameters) -> tuple[dict[str, Any], bool]:
    type_ = data["schema"]["type"]
    nullable = False
    if isinstance(type_, list):
        assert type_[1] == "null", "Only nullable types supported as list"
        type_ = type_[0]
        nullable = True
    schema = {"type": type_}
    if type_ == "array":
        schema["items"] = data["schema"].get("items", {"type": "string"})
    return schema, nullable


def create_schema(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:
    needs_config = NeedsSphinxConfig(app.config)
    schema = FieldsSchema()
    for name, data in NeedsCoreFields.items():
        if not data.get("add_to_field_schema", False):
            continue
        description = data["description"]
        _schema, nullable = _get_core_schema(data)

        # merge in additional schema from needs_statuses and needs_tags config
        if name == "status" and needs_config.statuses:
            log_warning(
                LOGGER,
                'Config option "needs_statuses" is deprecated. Please use "needs_fields.status.schema.enum" to define custom status field enum constraints.',
                "deprecated",
                None,
            )
            _schema["enum"] = [status["name"] for status in needs_config.statuses]
        if name == "tags" and needs_config.tags:
            log_warning(
                LOGGER,
                'Config option "needs_tags" is deprecated. Please use "needs_fields.tags.schema.items.enum" to define custom tags field enum constraints.',
                "deprecated",
                None,
            )
            _schema["items"] = {
                "type": "string",
                "enum": [tag["name"] for tag in needs_config.tags],
            }

        default = data["schema"].get("default", None)
        field = FieldSchema(
            name=name,
            description=description,
            nullable=nullable,
            schema=_schema,  # type: ignore[arg-type]
            default=None if default is None else FieldLiteralValue(default),
            allow_defaults=data.get("allow_default", False),
            allow_extend=data.get("allow_extend", False),
            parse_dynamic_functions=data.get("allow_df", False),
            parse_variants=name in needs_config._variant_options
            if data.get("allow_variants", False)
            else False,
            directive_option=name != "title",
        )

        if (core_override := needs_config._fields.get(name)) is not None:
            try:
                field = create_inherited_field(
                    field,
                    core_override,
                    allow_variants=data.get("allow_variants", False),
                )
            except Exception as exc:
                raise NeedsConfigException(
                    f"Invalid `needs_fields` core option override for {name!r}: {exc}"
                ) from exc

        try:
            schema.add_core_field(field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid core option {name!r}: {exc}") from exc

    for name, extra in _NEEDS_CONFIG.extra_options.items():
        try:
            _schema = (
                deepcopy(extra.schema)  # type: ignore[arg-type]
                if extra.schema is not None
                else {"type": "string"}
            )
            if extra.nullable is not None:
                nullable = extra.nullable
            else:
                # follows that of legacy (pre-schema) extra option,
                # i.e. nullable if schema is defined
                nullable = extra.schema is not None
            parse_variants = (
                False if extra.parse_variants is None else extra.parse_variants
            )
            if name in needs_config._variant_options:
                # for backward compatibility with deprecated config option
                parse_variants = True
            field = FieldSchema(
                name=name,
                description=extra.description,
                schema=_schema,  # type: ignore[arg-type]
                nullable=nullable,
                # note, default follows that of legacy (pre-schema) extra option,
                # i.e. default to "" only if no schema is defined
                default=None if extra.schema is not None else FieldLiteralValue(""),
                allow_defaults=True,
                allow_extend=True,
                parse_dynamic_functions=True,
                parse_variants=parse_variants,
                directive_option=True,
            )
            schema.add_extra_field(field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid extra option {name!r}: {exc}") from exc

    for link in needs_config.extra_links:
        name = link["option"]
        try:
            # create link schema, with defaults if not defined
            _schema = (
                deepcopy(link["schema"])  # type: ignore[arg-type]
                if "schema" in link
                else {"type": "array", "items": {"type": "string"}}
            )
            if "type" not in _schema:
                _schema["type"] = "array"
            if "items" not in _schema:
                _schema["items"] = {"type": "string"}
            if "type" not in _schema["items"]:
                _schema["items"]["type"] = "string"
            if "contains" in _schema and "type" not in _schema["contains"]:
                _schema["contains"]["type"] = "string"
            link_field = LinkSchema(
                name=name,
                description="Link field",
                schema=_schema,  # type: ignore[arg-type]
                default=LinksLiteralValue([]),
                allow_defaults=True,
                allow_extend=True,
                parse_dynamic_functions=True,
                parse_variants=link.get("parse_variants", False),
                directive_option=True,
            )
            schema.add_link_field(link_field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid extra link {name!r}: {exc}") from exc

    for field_name, field_config in needs_config._fields.items():
        _set_default(schema, "needs_fields", field_name, field_config)

    for link_config in needs_config.extra_links:
        _set_default(schema, "needs_extra_links", link_config["option"], link_config)

    if needs_config._global_options:
        log_warning(
            LOGGER,
            'Config option "needs_global_options" is deprecated. Please use needs_fields and needs_extra_links instead.',
            "deprecated",
            None,
        )
    for name, default_config in needs_config._global_options.items():
        if unknown := set(default_config).difference({"predicates", "default"}):
            log_warning(
                LOGGER,
                f"needs_global_options {name!r} value contains unknown keys: {unknown}",
                "config",
                None,
            )
        _set_default(
            schema, "needs_global_options", name, default_config, warn_not_dict=True
        )

    SphinxNeedsData(env)._set_schema(schema)


class _DefaultsDictType(TypedDict, total=False):
    predicates: list[tuple[str, Any]]
    default: Any


def _set_default(
    schema: FieldsSchema,
    config_name: str,
    name: str,
    values: _DefaultsDictType,
    *,
    warn_not_dict: bool = False,
    allow_coercion: bool = True,
) -> None:
    if not isinstance(values, dict):
        if warn_not_dict:
            log_warning(
                LOGGER,
                f"{config_name}[{name!r}] value is not a dict",
                "config",
                None,
            )
        return
    if "default" not in values and "predicates" not in values:
        return

    if (field_for_default := schema.get_any_field(name)) is None:
        log_warning(
            LOGGER,
            f"{config_name}[{name!r}] does not correspond to any defined field",
            "config",
            None,
        )
        return
    if not field_for_default.allow_defaults:
        log_warning(
            LOGGER,
            f"{config_name}[{name!r}]['default'] cannot be set, as field does not allow defaults",
            "config",
            None,
        )
        return
    if "default" in values:
        try:
            field_for_default._set_default(
                values["default"], allow_coercion=allow_coercion
            )
        except Exception as exc:
            log_warning(
                LOGGER,
                f"{config_name}[{name!r}]['default'] value is incorrect: {exc}",
                "config",
                None,
            )
    if "predicates" in values:
        try:
            field_for_default._set_predicate_defaults(
                values["predicates"], allow_coercion=allow_coercion
            )
        except Exception as exc:
            log_warning(
                LOGGER,
                f"{config_name}[{name!r}]['predicates'] value is incorrect: {exc}",
                "config",
                None,
            )


def release_data_locks(app: Sphinx, _exception: Exception) -> None:
    """Release the lock on needs data mutations.

    This should ONLY be used at the very end of the sphinx processing.
    The only reason is it is included is because esbonio does not properly re-start sphinx builds,
    such that this would be re-set.
    """
    SphinxNeedsData(app.env).needs_is_post_processed = False
    app.env._needs_warnings_executed = False  # type: ignore[attr-defined]
