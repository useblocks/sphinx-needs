from __future__ import annotations

import contextlib
import dataclasses
import difflib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from functools import partial
from itertools import chain
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, Final, Literal, TypedDict, TypeVar, cast

from docutils import nodes
from docutils.parsers.rst import directives as rst_directives
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.config import Config
from sphinx.config import Config as _SphinxConfig
from sphinx.environment import BuildEnvironment

import sphinx_needs.debug as debug  # Need to set global var in it for timeing measurements
import sphinx_needs.logging as needs_logging
from sphinx_needs import __version__
from sphinx_needs._wording import joined, title_hint
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
from sphinx_needs.card_layouts import compile_card_layouts
from sphinx_needs.config import (
    _NEEDS_CONFIG,
    DEFAULT_NEED_TYPES,
    LinkOptionsType,
    NeedField,
    NeedFields,
    NeedLinksConfig,
    NeedsSphinxConfig,
    NeedType,
    NewFieldParams,
    type_field_names,
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
from sphinx_needs.derive import (
    CORE_LINK_TYPES,
    DeriveInvalid,
    DeriveProblem,
    DeriveRule,
    beside_by_type_message,
    beside_clause,
    beside_message,
    by_type_message,
    check_derive_rules,
    copy_on_derived_message,
    copy_problem,
    core_message,
    invalid_entry_message,
    invalid_message,
    is_union,
    parse_derive,
    parse_derive_by_type,
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
from sphinx_needs.directives.needchoose import (
    ChooseDirective,
    OtherwiseDirective,
    WhenDirective,
)
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
from sphinx_needs.directives.needflow._options import validate_flow_config
from sphinx_needs.directives.needgantt import (
    Needgantt,
    NeedganttDirective,
    process_needgantt,
)
from sphinx_needs.directives.needif import IfDirective
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
    DEFAULT_PAGE_SIZE,
    DEFAULT_PAGE_SIZES,
    Needtable,
    NeedtableDirective,
    NeedtableHeader,
    NeedtableRow,
    NeedtableTable,
    html_depart_needtable_header,
    html_depart_needtable_row,
    html_depart_needtable_table,
    html_visit_needtable_header,
    html_visit_needtable_row,
    html_visit_needtable_table,
    process_needtables,
    validate_page_size,
    validate_page_sizes,
)
from sphinx_needs.directives.needuml import (
    NeedarchDirective,
    Needuml,
    NeedumlDirective,
    process_needuml,
)
from sphinx_needs.environment import (
    install_lib_static_files,
    install_needtable_assets,
    install_permalink_file,
    install_styles_static_files,
)
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.external_needs import load_external_needs
from sphinx_needs.functions import NEEDS_COMMON_FUNCTIONS
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.needs_schema import (
    BACK_LINKS_KEYWORDS,
    BackLinksSchema,
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
    LinksLiteralValue,
    LinkTargetTypes,
    _inherit_keywords,
    create_inherited_field,
    narrowing_problems,
    schema_narrowing_problems,
    severity_problems,
)
from sphinx_needs.nodes import Need
from sphinx_needs.roles import NeedsXRefRole
from sphinx_needs.roles.need_count import NeedCount, process_need_count
from sphinx_needs.roles.need_func import NeedFunc, NeedFuncRole, process_need_func
from sphinx_needs.roles.need_incoming import NeedIncoming, process_need_incoming
from sphinx_needs.roles.need_outgoing import NeedOutgoing, process_need_outgoing
from sphinx_needs.roles.need_part import NeedPart, NeedPartRole, process_need_part
from sphinx_needs.roles.need_ref import NeedRef, process_need_ref
from sphinx_needs.roles.variant import VariantRole
from sphinx_needs.schema.config import (
    FieldIntegerSchemaType,
    SchemasFileRootType,
    UnknownKeyword,
    drop_unknown_keywords,
    validate_field_schema,
)
from sphinx_needs.schema.config_utils import (
    resolve_schemas_config,
    validate_schemas_config,
)
from sphinx_needs.schema.process import process_schemas
from sphinx_needs.services.config.github import GITHUB_SERVICES
from sphinx_needs.services.github import (
    GithubService,
    add_configured_github_services,
)
from sphinx_needs.string_links import compile_string_links
from sphinx_needs.utils import node_match
from sphinx_needs.variant_data import VariantDataProxy
from sphinx_needs.warnings import process_warnings
from ub_project import (
    NO_DATA_FILE,
    VARIANT_DATA_LOCATION,
    VARIANTS_UNKNOWN_KEY,
    NoDataFile,
    ProjectConfigError,
    load_toml,
    read_variants,
    resolve_variant_data,
    select_table,
)

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
    # Sphinx 7 only: show_warning_types now, and after any later setup() changed it
    needs_logging.configure_warning_types(app, app.config)
    app.connect("config-inited", needs_logging.configure_warning_types, priority=0)
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
    # The three docutils sub-classes a needtable's HTML is built from. They exist only so
    # that the HTML writers can emit attributes docutils has no other channel for (the
    # markup contract in `design/needstable-contract.md`); NO other builder gets a
    # visitor, so `SphinxTranslator.dispatch_visit` walks the MRO and latex, text,
    # texinfo and man render them as the plain `table`/`row`/`entry` they subclass.
    app.add_node(
        NeedtableTable,
        html=(html_visit_needtable_table, html_depart_needtable_table),
    )
    app.add_node(
        NeedtableRow,
        html=(html_visit_needtable_row, html_depart_needtable_row),
    )
    app.add_node(
        NeedtableHeader,
        html=(html_visit_needtable_header, html_depart_needtable_header),
    )
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
    app.add_node(
        NeedRef,
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
    app.add_directive("if", IfDirective)
    app.add_directive("choose", ChooseDirective)
    app.add_directive("when", WhenDirective)
    app.add_directive("otherwise", OtherwiseDirective)
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

    app.add_role("ndf", NeedFuncRole())

    # Resolves :variant:`a.b` immediately to the value from needs_variant_data.
    app.add_role("variant", VariantRole())

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect("config-inited", load_config_from_toml, priority=10)  # runs early
    # runs directly after the toml config is loaded, which can set the variant data,
    # and before anything that may want to read the merged map,
    # up to and including configuration that decides which documents are read
    app.connect("config-inited", resolve_variant_data_config, priority=11)
    # after the toml config is loaded, which can set the need types, and before every
    # reader of them: load_config and the add_need_type calls of other extensions (500).
    # sphinx-codelinks' register_string_links is at 12 too and reads no need types, so
    # the order between the two does not matter
    app.connect("config-inited", resolve_need_types, priority=12)
    # the configured built-in GitHub services, their need types and their layout:
    # after the toml config, which can configure them, and at 12 rather than later, so
    # every documented reader of the need types (above 12) sees them (#2265)
    app.connect("config-inited", add_configured_github_services, priority=12)
    app.connect("config-inited", load_config)
    app.connect("config-inited", merge_default_configs)
    # runs after the built-in layouts are merged in, and before the config is checked
    app.connect("config-inited", compile_card_layouts, priority=550)
    app.connect("config-inited", compile_string_links, priority=551)
    app.connect("config-inited", check_configuration, priority=600)  # runs late

    app.connect("env-before-read-docs", prepare_env)
    # after prepare_env, which registers the services, so that the list compared is the
    # complete one, the need types added from code included, on every build
    app.connect("env-before-read-docs", reread_on_need_types_change)
    # note we have to place create_schema after prepare_env, as that can add extra fields,
    # but before load_external_needs, where we start to add needs.
    app.connect("env-before-read-docs", create_schema)
    # schemas type injection uses information from create_schema
    app.connect("env-before-read-docs", resolve_schemas_config)

    app.connect("env-before-read-docs", load_external_needs)

    app.connect("env-purge-doc", purge_needs)

    app.connect("doctree-read", analyse_need_locations)

    app.connect("env-merge-info", merge_data)

    # the needtable client assets go only on the pages that have a needtable (#462)
    app.connect("html-page-context", install_needtable_assets)

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
    # The registry is one per process, not per application: applications set up in one
    # process and built interleaved share it, and a later setup clears what an earlier
    # application's extensions added -- fields, functions, need types and layouts alike.
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

    The variant data is read by ``ub_project`` (:func:`_load_variants_from_toml`), from
    the ``[variants]`` table or its legacy location, the ``variant_data*`` keys of the
    ``[needs]`` table.
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
        toml_doc = load_toml(toml_file)
    except Exception as e:
        # not only ProjectConfigError: tomllib can also fail with a RecursionError, for
        # example, which ``load_toml`` does not wrap; either way the file only warns
        log_warning(
            LOGGER,
            f"Error loading 'needs_from_toml' file: {e}",
            "config",
            None,
        )
        return
    try:
        toml_data: Any = toml_doc
        for key in (*toml_path, "needs"):
            toml_data = toml_data[key]
        assert isinstance(toml_data, dict), "Data must be a dict"
        if "schema" in toml_data:
            assert isinstance(toml_data["schema"], dict), (
                "'schema' table must be a dict"
            )

    except Exception as e:
        # a file holding a variants table and no needs table is read: the variant data
        # may be all it configures
        if isinstance(e, KeyError) and _is_present(toml_doc, (*toml_path, "variants")):
            toml_data = {}
        else:
            log_warning(
                LOGGER,
                f"Error loading 'needs_from_toml' file: {e}",
                "config",
                None,
            )
            return

    allowed_keys = NeedsSphinxConfig.field_names()
    overridden_keys: set[str] = set()
    config_overrides = getattr(config, "overrides", None)
    if isinstance(config_overrides, dict):
        overridden_keys = {str(key) for key in config_overrides}

    for key, value in toml_data.items():
        if key not in allowed_keys:
            continue
        if key in _LEGACY_VARIANT_KEYS:
            # read with [variants] by _load_variants_from_toml, which decides the location
            continue
        config_key = "needs_" + key
        # Keep values passed via sphinx-build -D (confoverrides) untouched.
        if key in overridden_keys or config_key in overridden_keys:
            continue
        if (reason := NeedsSphinxConfig.toml_ignored_reason(key)) is not None:
            # never read, so every occurrence is reported, an empty one included
            log_warning(
                LOGGER,
                f"'needs_from_toml' file sets {key!r}, which is ignored: {reason}",
                "config",
                None,
            )
            continue
        config[config_key] = NeedsSphinxConfig.convert_field_value(
            key, value, toml_file.parent
        )

    schema_config_overridden = "needs_schema_" in overridden_keys
    for key, value in toml_data.get("schema", {}).items():
        if key not in allowed_keys:
            continue
        if schema_config_overridden or f"needs_schema_{key}" in overridden_keys:
            continue
        config["needs_schema_"][key] = NeedsSphinxConfig.convert_field_value(
            key, value, toml_file.parent, "schema_"
        )

    _load_variants_from_toml(
        config,
        toml_doc,
        toml_file,
        tuple(toml_path),
        overridden_keys,
        Path(app.confdir),
    )


#: The keys of ``[variants]`` and, in the same order, their legacy ``[needs]`` spellings,
#: which are also the names of the confvals they set (with the ``needs_`` prefix).
_VARIANT_KEYS = ("data", "data_file")
_LEGACY_VARIANT_KEYS = ("variant_data", "variant_data_file")

#: The warning subtype of each ``ub_project`` diagnostic code that is a warning here.
_VARIANT_DIAGNOSTIC_SUBTYPES: dict[str, WarningSubTypes] = {
    VARIANT_DATA_LOCATION: "variant_data_location",
    VARIANTS_UNKNOWN_KEY: "variants_unknown_key",
}


def _is_present(doc: dict[str, object], path: tuple[str, ...]) -> bool:
    """Whether *doc* holds something (a table or not) at *path*."""
    current: object = doc
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return True


def _is_overridden(legacy_key: str, overridden_keys: set[str]) -> bool:
    """Whether the confval of *legacy_key* was set with ``-D``, in either spelling."""
    return legacy_key in overridden_keys or f"needs_{legacy_key}" in overridden_keys


def _load_variants_from_toml(
    config: Config,
    toml_doc: dict[str, object],
    toml_file: Path,
    prefix: tuple[str, ...],
    overridden_keys: set[str],
    confdir: Path,
) -> None:
    """Read the variant data of the ``needs_from_toml`` file, through ``ub_project``.

    ``[<prefix>.variants]`` is the current location and ``[<prefix>.needs]
    variant_data*`` the legacy one; ``ub_project`` decides which one is read, WHOLE, and
    reports the other's keys. What stays here is sphinx-needs' policy:

    - ``-D needs_variant_data_file`` is ub-project's data-file override (its reading
      contract, section 6.8): it swaps the file, never the table, so it replaces the data
      file of the location read without opening it, and the location, the refusals and
      the findings stay the document's. A relative one is anchored at the ``confdir``,
      as :func:`resolve_variant_data_config` anchors it, and ``-D
      needs_variant_data_file=`` (no file) is ``NO_DATA_FILE``: the toml's file is
      replaced by none, unopened;
    - each declared key of the location read is written to its confval, as the
      ``[needs]`` loop wrote it, unless ``-D`` set that confval, and the merge with
      ``conf.py`` values and the file load stay with
      :func:`resolve_variant_data_config`, which therefore reads the data file a second
      time. Writing the merged map instead would override a ``conf.py`` value for a key
      the TOML does not set, which must fill that gap;
    - the findings are reported as warnings, except the legacy location, which is
      reported with ``-v`` only for now.

    :raises NeedsConfigException: If ``ub_project`` refuses the variant data, or a table
        path with an empty ``needs_from_toml_table`` entry.
    """
    needs_table = (*prefix, "needs")
    variants_table = (*prefix, "variants")
    override: Path | NoDataFile | None = None
    if _is_overridden("variant_data_file", overridden_keys):
        value = NeedsSphinxConfig(config).variant_data_file
        # "" means "no file" on this route (ub-project's section 10.1)
        override = confdir / value if value else NO_DATA_FILE

    try:
        result = read_variants(
            toml_doc,
            toml_file,
            needs_table=needs_table,
            variants_table=variants_table,
            data_file_override=override,
        )
    except (ProjectConfigError, ValueError) as error:
        # ValueError: a table path ub_project refuses (an empty needs_from_toml_table
        # entry), and any it lets through unwrapped -- a data file holding an integer
        # beyond Python's conversion limit, until ub-project names the file itself (#1995)
        raise NeedsConfigException(str(error)) from error

    for diagnostic in result.diagnostics:
        subtype = _VARIANT_DIAGNOSTIC_SUBTYPES.get(diagnostic.code)
        if subtype is None:
            # the legacy location, and any finding a newer ub-project may add, which
            # must not fail a `-W` build that this version cannot know about
            LOGGER.verbose(diagnostic.message)
        else:
            log_warning(LOGGER, diagnostic.message, subtype, None)

    if result.location is None:
        return
    if result.location == "variants":
        # absent when an override is read with neither location declared
        table, keys = select_table(toml_doc, variants_table) or {}, _VARIANT_KEYS
    else:
        table, keys = select_table(toml_doc, needs_table) or {}, _LEGACY_VARIANT_KEYS
    inline_key, file_key = keys
    if (inline := table.get(inline_key)) is not None and not _is_overridden(
        "variant_data", overridden_keys
    ):
        config["needs_variant_data"] = inline
    if (file_value := table.get(file_key)) is not None and not _is_overridden(
        "variant_data_file", overridden_keys
    ):
        # today's converter (``_abs_path``), so the confval's string is what the [needs]
        # loop wrote; ``result.data_file`` is joined, not resolved
        config["needs_variant_data_file"] = NeedsSphinxConfig.convert_field_value(
            "variant_data_file", file_value, toml_file.parent
        )


#: The keys a ``needs_types`` entry may carry; any other key is reported and ignored.
#: ``id_regex``: the pattern the ids of the type's needs match, beside ``needs_id_regex``.
NEED_TYPE_KEYS = (
    "directive",
    "title",
    "prefix",
    "color",
    "style",
    "inherits",
    "id_regex",
    "fields",
    "links",
)

#: The keys of an entry of a need type's ``fields`` table (``derive``: the field's
#: ``derive_by_type`` entry for the type, and the types inheriting from it;
#: ``severity``: what a need failing the declaration is reported at).
NEED_TYPE_FIELD_KEYS = (
    "description",
    "schema",
    "nullable",
    "default",
    "predicates",
    "derive",
    "severity",
)

#: The keys of an entry of a need type's ``links`` table: a link type is not nullable.
#: ``target_types`` narrows as ``schema`` does: it is no part of a link type's shape.
NEED_TYPE_LINK_KEYS = (
    "description",
    "schema",
    "default",
    "predicates",
    "derive",
    "target_types",
    "severity",
)

#: The keys of an entry of a need type's ``links`` table naming a link type's back
#: links, ``<l>_back``: how many links of ``l`` point to a need of the type
#: (``schema``, of :data:`~sphinx_needs.needs_schema.BACK_LINKS_KEYWORDS` alone), and
#: the severity of a need failing the count. Any other key refuses the entry.
NEED_TYPE_BACK_LINK_KEYS = ("description", "schema", "severity")

#: The keys of a link type that are the same on every need type -- how its links are
#: drawn, whether they are copied into ``links``, whether a dead link is allowed: an
#: entry of a link type declared on need types alone may give them (its first root
#: declaration sets them, the others may repeat them); on a link type declared
#: otherwise they are refused.
NEED_TYPE_LINK_SHAPE_KEYS = (
    "incoming",
    "outgoing",
    "copy",
    "allow_dead_links",
    "color",
    "style",
    "style_part",
    "style_start",
    "style_end",
)

#: The keys of an entry of a need type's ``links`` table, of a link type's declaration.
_NEED_TYPE_LINK_ENTRY_KEYS = (*NEED_TYPE_LINK_KEYS, *NEED_TYPE_LINK_SHAPE_KEYS)


def _type_name(value: object) -> str:
    return type(value).__name__


def _is_names(value: object) -> bool:
    """Whether ``value`` is a non-empty list of non-empty strings."""
    return (
        isinstance(value, list | tuple)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
    )


def _is_pairs(value: object) -> bool:
    """Whether ``value`` is a list of (filter, value) pairs, each filter a string."""
    return isinstance(value, list | tuple) and all(
        isinstance(pair, list | tuple) and len(pair) == 2 and isinstance(pair[0], str)
        for pair in value
    )


#: what the value of a key must be, and the test of it: the keys of a need type, then
#: the keys of its declaration of a field or link type (``default`` is any value)
_SHAPES: Mapping[str, tuple[str, Callable[[object], bool]]] = {
    "color": ("a string", lambda v: isinstance(v, str)),
    "style": ("a string", lambda v: isinstance(v, str)),
    "inherits": ("a non-empty string", lambda v: isinstance(v, str) and bool(v)),
    "id_regex": ("a string", lambda v: isinstance(v, str)),
    "fields": ("a mapping", lambda v: isinstance(v, Mapping)),
    "links": ("a mapping", lambda v: isinstance(v, Mapping)),
    "description": ("a string", lambda v: isinstance(v, str)),
    "schema": ("a mapping", lambda v: isinstance(v, Mapping)),
    "nullable": ("a boolean", lambda v: isinstance(v, bool)),
    "predicates": ("a list of (filter, value) pairs", _is_pairs),
    "derive": ("a mapping", lambda v: isinstance(v, Mapping)),
    "target_types": ("a non-empty list of need type names", _is_names),
    "severity": (
        "one of 'violation', 'warning' and 'info'",
        lambda v: v in ("violation", "warning", "info"),
    ),
    "incoming": ("a string", lambda v: isinstance(v, str)),
    "outgoing": ("a string", lambda v: isinstance(v, str)),
    "copy": ("a boolean", lambda v: isinstance(v, bool)),
    "allow_dead_links": ("a boolean", lambda v: isinstance(v, bool)),
    "style_part": ("a string", lambda v: isinstance(v, str)),
    "style_start": ("a string", lambda v: isinstance(v, str)),
    "style_end": ("a string", lambda v: isinstance(v, str)),
}


def _not_of_their_shape(
    where: str, entry: Mapping[str, Any], keys: tuple[str, ...]
) -> tuple[list[str], str]:
    """The ``keys`` of ``entry`` whose value is not of its shape, and the finding."""
    wrong = [
        name
        for name in keys
        if name in _SHAPES and name in entry and not _SHAPES[name][1](entry[name])
    ]
    if not wrong:
        return [], ""
    return wrong, (
        f"{where} has "
        + " and ".join(
            f"{'an' if name[0] in 'aeiou' else 'a'} {name!r} that is not "
            f"{_SHAPES[name][0]} (got {_got(name, entry[name])})"
            for name in wrong
        )
        + f"; the {'key is' if len(wrong) == 1 else 'keys are'} ignored"
    )


def _got(name: str, value: object) -> str:
    """What a value that is not of its shape is, as a finding names it."""
    if name == "predicates" and isinstance(value, list | tuple):
        return "a list with an item that is not a (filter, value) pair"
    if name == "target_types" and isinstance(value, list | tuple):
        return (
            "an empty list"
            if not value
            else "a list with an item that is not a non-empty string"
        )
    if name == "severity" and isinstance(value, str):
        return repr(value)
    return repr(value) if value == "" else _type_name(value)


def _unknown(
    where: str, entry: Mapping[str, Any], known: tuple[str, ...]
) -> tuple[list[str], str]:
    """The keys of ``entry`` outside ``known``, and the finding."""
    unknown = [k for k in entry if k not in known]
    if not unknown:
        return [], ""
    return unknown, (
        f"{where} has {'an unknown key' if len(unknown) == 1 else 'unknown keys'} "
        f"{', '.join(repr(k) for k in unknown)}; known keys are "
        f"{', '.join(sorted(known))}; the "
        f"{'key is' if len(unknown) == 1 else 'keys are'} ignored"
    )


def _entry_keys(klass: Any) -> tuple[str, ...]:
    """The keys of a configuration entry: those of its TypedDict, sorted."""
    return tuple(sorted(klass.__required_keys__ | klass.__optional_keys__))


#: the keys of an entry of ``needs_fields``, of ``needs_extra_options``, of
#: ``needs_links`` and of ``needs_extra_links``: their TypedDicts', so that a key added
#: to one is known at once
FIELD_ENTRY_KEYS: Final[tuple[str, ...]] = _entry_keys(NeedFields)
EXTRA_OPTION_ENTRY_KEYS: Final[tuple[str, ...]] = _entry_keys(NeedField)
LINK_ENTRY_KEYS: Final[tuple[str, ...]] = _entry_keys(NeedLinksConfig)
EXTRA_LINK_ENTRY_KEYS: Final[tuple[str, ...]] = _entry_keys(LinkOptionsType)


def _report_unknown_keys(
    where: str,
    entry: Any,
    known: tuple[str, ...],
    *,
    own_name: tuple[str, str] | None = None,
    reported: tuple[str, ...] = (),
) -> None:
    """One ``needs.config`` warning per key of a global field or link type entry that
    the entry does not have; the readers of the entry read only the known keys, so the
    key is ignored and the entry kept. An entry that is not a mapping is left to its
    reader, which reports it.

    :param own_name: the key the entry's list spelling names it by (``name`` of a
        ``needs_extra_options`` entry, ``option`` of a ``needs_extra_links`` one) and the
        entry's name, for an entry of the table spelling (``needs_fields``,
        ``needs_links``), which takes its name from its table key: that key, left over
        from the list spelling, is accepted where it repeats the entry's name, and
        reported where it gives another (it was always ignored).
    :param reported: the keys outside ``known`` that a finding of their own reports
        (``severity``, a need type's entry's: :func:`_refuse_global_severity`), each
        reported once.
    """
    if not isinstance(entry, Mapping):
        return
    for key in entry:
        if own_name is not None and key == own_name[0]:
            if entry[key] != own_name[1]:
                log_warning(
                    LOGGER,
                    f"{where} gives {key!r} = {entry[key]!r}, which differs from the "
                    f"entry's name {own_name[1]!r}; it is ignored",
                    "config",
                    None,
                )
            continue
        if key not in known and key not in reported:
            log_warning(
                LOGGER,
                f"{where} has an unknown key {key!r}; known keys are "
                f"{', '.join(known)}; the key is ignored",
                "config",
                None,
            )


def _report_unknown_keywords(where: str, unknown: list[UnknownKeyword]) -> None:
    """One ``needs.config`` warning per keyword :func:`drop_unknown_keywords` dropped
    from the ``schema`` of a global field or link type entry."""
    for item in unknown:
        log_warning(
            LOGGER,
            f"{where}{item.path} has an unknown keyword {item.keyword!r}; known "
            f"keywords of {item.what} are {', '.join(item.known)}; the keyword is "
            "ignored",
            "config",
            None,
        )


def _normalise_declarations(
    named: str, table: str, value: Mapping[Any, Any], findings: list[str]
) -> dict[Any, dict[str, Any]]:
    """A need type's ``fields`` or ``links`` table, of its shape: each entry a mapping
    of the keys of its table, each value of its shape. What is not is reported in
    ``findings`` and left out: an entry that is not a mapping, a key that is not
    known or not of its shape. Every entry is a new mapping, its values copies.

    A ``links`` entry named ``<x>_back`` may declare the count of a link type's back
    links, which takes only :data:`NEED_TYPE_BACK_LINK_KEYS` and refuses the entry for
    any other (:func:`_declare_back_links`); whether it does is known once the link
    types are (:func:`_resolve_type_declarations`). So its other keys, not known or not
    of their shape, are kept and not reported here: the resolver reports them as here
    where the entry declares a link type, and refuses the entry where it is a count."""
    known = _NEED_TYPE_LINK_ENTRY_KEYS if table == "links" else NEED_TYPE_FIELD_KEYS
    resolved: dict[Any, dict[str, Any]] = {}
    for name, entry in value.items():
        where = f"{named}.{table}[{name!r}]"
        if not isinstance(entry, Mapping):
            findings.append(
                f"{where} is not a mapping (got {_type_name(entry)}); "
                "the entry is ignored"
            )
            continue
        checked = entry
        if table == "links" and isinstance(name, str) and name.endswith("_back"):
            # those of a count's keys alone; the others are the resolver's
            checked = {k: v for k, v in entry.items() if k in NEED_TYPE_BACK_LINK_KEYS}
        wrong, text = _not_of_their_shape(where, checked, known)
        if wrong:
            findings.append(text)
        unknown, text = _unknown(where, checked, known)
        if unknown:
            findings.append(text)
        resolved[name] = {
            key: deepcopy(item)
            for key, item in entry.items()
            if key not in wrong and key not in unknown
        }
    return resolved


def normalise_need_types(value: object) -> tuple[list[NeedType], list[str]]:
    """Resolve a ``needs_types`` value to the list every reader of it expects.

    Two shapes are accepted: a list of mappings, each naming its ``directive``, and a
    mapping from directive name to a mapping of the other keys. Both resolve to the list
    ``[{"directive": name, **keys}, ...]``, in the order the entries are given (a
    mapping keeps its insertion order, and ``tomllib`` the order of first appearance).

    A value of neither shape is refused (1). Otherwise each entry is checked in turn, and
    every problem is a finding rather than an error:

    2. an entry that is not a mapping is dropped;
    3. an entry that names no directive is dropped (list shape: ``directive`` missing,
       or not a non-empty string; mapping shape: an empty key); in the mapping shape a
       ``directive`` inside the value that differs from the key is reported and the key
       used;
    4. an entry whose ``title`` or ``prefix`` is missing or not a string is dropped (an
       empty string is valid), but for a *bare* entry, which gives neither key: one
       naming a default need type (:data:`~sphinx_needs.config.DEFAULT_NEED_TYPES`)
       is that type, narrowed, taking the ``title``, ``prefix``, ``color`` and
       ``style`` it leaves out (or removes below); one naming no default type is
       dropped;
    5. a ``color``, ``style`` or ``id_regex`` that is not a string, an ``inherits``
       that is not a non-empty string, and a ``fields`` or ``links`` that is not a
       mapping, are removed from the entry;
    6. a key outside :data:`NEED_TYPE_KEYS` is removed from the entry;
    7. a directive declared by more than one entry (list shape only) resolves to the
       last of them, at its own position, the others removed.

    The default need types are kept when the value has entries and none of them gives a
    ``title`` or a ``prefix`` (all are bare, or are dropped): the list is then the
    default types, in their order, each replaced by the bare entry naming it. Once an
    entry gives either key, the list is the entries kept, as given, and a bare entry
    naming a default type stands at its own position. A value with no entries is no
    types.

    In ``fields`` and ``links``, an entry that is not a mapping is removed, and so is
    a key of an entry outside :data:`NEED_TYPE_FIELD_KEYS` (fields) or
    :data:`NEED_TYPE_LINK_KEYS` and :data:`NEED_TYPE_LINK_SHAPE_KEYS` (links), or not
    of its shape: a ``description``, an ``incoming``, ``outgoing``, ``color`` or
    ``style*`` that is not a string, a ``schema`` or a ``derive`` that is not a
    mapping, a ``nullable``, ``copy`` or ``allow_dead_links`` that is not a boolean,
    ``predicates`` that are not a list of (filter, value) pairs, a ``severity`` that
    is not one of ``violation``, ``warning`` and ``info``. Only the
    shape is checked here: what a declaration names, and whether its values apply to
    the field, is for :func:`create_schema`, which knows the fields and every need type.

    A directive name is otherwise not checked: which names docutils accepts is
    docutils' concern.

    The function is pure: the value is not modified, and nothing is logged. A resolved
    list resolves to itself, with no findings.

    :param value: The configured value.
    :return: The resolved list, and the findings: in entry order, the duplicates last.
    :raises NeedsConfigException: If the value is neither a list nor a mapping.
    """
    if isinstance(value, Mapping):
        is_table = True
        entries: list[tuple[str, object, object]] = [
            (f"needs_types[{key!r}]", key, entry) for key, entry in value.items()
        ]
    elif isinstance(value, list):
        is_table = False
        entries = [
            (f"needs_types entry {position}", None, entry)
            for position, entry in enumerate(value, start=1)
        ]
    else:
        raise NeedsConfigException(
            "Config option 'needs_types' must be a list of need type mappings or a "
            f"mapping from directive name to need type, got {_type_name(value)}."
        )

    findings: list[str] = []
    #: the entries kept, each with its position (1-based)
    kept: list[tuple[int, dict[str, Any]]] = []
    defaults = {need_type["directive"]: need_type for need_type in DEFAULT_NEED_TYPES}
    #: whether an entry gives a title or a prefix: the default types are then replaced
    declares = False
    for position, (where, key, entry) in enumerate(entries, start=1):
        if not isinstance(entry, Mapping):
            findings.append(
                f"{where} is not a mapping (got {_type_name(entry)}); "
                "the entry is ignored"
            )
            continue
        declares = declares or "title" in entry or "prefix" in entry
        if not is_table:
            directive = entry.get("directive")
            if "directive" not in entry:
                findings.append(f"{where} has no 'directive'; the entry is ignored")
                continue
            if not isinstance(directive, str) or not directive:
                findings.append(
                    f"{where} has directive = {directive!r}, which is not a non-empty "
                    "string; the entry is ignored"
                )
                continue
            named = f"{where} ({directive!r})"
            resolved: dict[str, Any] = dict(entry)
        else:
            if not isinstance(key, str) or not key:
                findings.append(
                    f"{where} does not name a directive: the key must be a non-empty "
                    "string; the entry is ignored"
                )
                continue
            named = where
            if "directive" in entry and entry["directive"] != key:
                findings.append(
                    f"{where} sets directive = {entry['directive']!r}; the key names "
                    "the directive and the value is ignored"
                )
            resolved = {"directive": key}
            resolved.update((k, v) for k, v in entry.items() if k != "directive")

        # a bare entry naming a default type narrows it: it is filled below
        default = (
            defaults.get(resolved["directive"])
            if "title" not in resolved and "prefix" not in resolved
            else None
        )
        required = [
            f"no {name!r}"
            if name not in resolved
            else f"a {name!r} that is not a string (got {_type_name(resolved[name])})"
            for name in ("title", "prefix")
            if not isinstance(resolved.get(name), str)
        ]
        if required and default is None:
            findings.append(
                f"{named} has {' and '.join(required)}; the entry is ignored"
            )
            continue

        wrong, text = _not_of_their_shape(named, resolved, NEED_TYPE_KEYS)
        if wrong:
            findings.append(text)
        unknown, text = _unknown(named, resolved, NEED_TYPE_KEYS)
        if unknown:
            findings.append(text)
        for name in (*wrong, *unknown):
            del resolved[name]
        for table in ("fields", "links"):
            if table in resolved:
                # a mapping: what is not was removed above
                resolved[table] = _normalise_declarations(
                    named, table, cast(Mapping[Any, Any], resolved[table]), findings
                )
        if default is not None:
            # the keys the entry leaves out, or that were removed, are the default's
            resolved = {**default, **resolved}
        kept.append((position, resolved))

    # a duplicate is possible in the list shape only (a mapping cannot hold a key
    # twice): the last entry is used, at its own position, and the others are removed
    positions: dict[str, list[int]] = {}
    for position, resolved in kept:
        positions.setdefault(resolved["directive"], []).append(position)
    for directive, declared in positions.items():
        if len(declared) > 1:
            times = "twice" if len(declared) == 2 else f"{len(declared)} times"
            at = ", ".join(map(str, declared[:-1])) + f" and {declared[-1]}"
            findings.append(
                f"needs_types declares the directive {directive!r} {times}, at entries "
                f"{at}; the last entry is used"
            )
    need_types = [
        cast(NeedType, resolved)
        for position, resolved in kept
        if positions[resolved["directive"]][-1] == position
    ]
    if entries and not declares:
        # every entry is bare (or dropped): the default types are kept, each narrowed
        # in place by the entry naming it
        narrowed = {need_type["directive"]: need_type for need_type in need_types}
        need_types = [
            narrowed.get(directive) or default.copy()
            for directive, default in defaults.items()
        ]
    return need_types, findings


def resolve_need_types(_app: Sphinx, config: Config) -> None:
    """Resolve ``needs_types`` to the list every reader of it expects, and report each
    entry that cannot be used as a ``needs.config`` warning.

    The list is written back to the option, so ``load_config``, ``add_need_type`` and
    every later reader see a list whichever shape was configured, and Sphinx compares
    the same list on both sides of an incremental build.

    :param _app: The Sphinx application.
    :param config: The Sphinx configuration.
    :raises NeedsConfigException: If the value is neither a list nor a mapping.
    """
    need_types, findings = normalise_need_types(config.needs_types)
    for text in findings:
        log_warning(LOGGER, text, "config", None)
    config["needs_types"] = need_types


def _register_need_directive(app: Sphinx, name: str) -> None:
    """Register the need directive under a need type's name, once.

    Both ``load_config`` and ``add_need_type`` register the directive of a need type,
    and either may run first: ``add_need_type`` is called from other extensions'
    ``config-inited`` handlers, at the same priority as ``load_config`` or earlier. A
    name that already holds :class:`NeedDirective` itself is left alone, so a type
    registers its directive once whichever comes first (#2271). Any other directive
    under the name is overridden as before, with Sphinx's ``already registered``
    warning: only the need directive's own registration is skipped.

    :param app: The Sphinx application.
    :param name: The need type's directive name.
    """
    # the registry Sphinx's own ``is_directive_registered`` reads, which docutils'
    # stubs do not declare
    registry = rst_directives._directives  # ty: ignore[unresolved-attribute]
    if registry.get(name) is NeedDirective:
        return
    app.add_directive(name, NeedDirective)


def load_config(app: Sphinx, *_args: Any) -> None:
    """
    Register extra fields and directive based on config from conf.py
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
        derive = None
        derive_by_type = None
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
            _report_unknown_keys(
                f"needs_extra_options[{name!r}]", option, EXTRA_OPTION_ENTRY_KEYS
            )
            description = option.get("description", description)
            schema = option.get("schema")
            derive = option.get("derive")
            derive_by_type = option.get("derive_by_type")
        else:
            log_warning(
                LOGGER,
                f"extra_option is not a string or dict: {option}",
                "config",
                None,
            )
            continue

        _NEEDS_CONFIG.add_field(
            name,
            description,
            "needs_extra_options",
            schema=schema,
            derive=derive,
            derive_by_type=derive_by_type,
            override=True,
        )

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
        _refuse_global_severity("needs_fields", "fields", option_name, option_params)
        _report_unknown_keys(
            f"needs_fields[{option_name!r}]",
            option_params,
            FIELD_ENTRY_KEYS,
            own_name=("name", option_name),
            reported=("severity",),
        )
        if option_name in NeedsCoreFields or option_name in _link_type_names(
            needs_config
        ):
            # a core field's entry specializes it (create_schema), and a link type
            # is not a field (reported there)
            continue
        _NEEDS_CONFIG.add_field(
            option_name,
            option_params.get("description", "Added by needs_fields config"),
            "needs_fields",
            schema=option_params.get("schema"),
            nullable=option_params.get("nullable"),
            default=option_params.get("default"),
            predicates=option_params.get("predicates"),
            parse_variants=option_params.get("parse_variants"),
            parse_dynamic_functions=option_params.get("parse_dynamic_functions"),
            derive=option_params.get("derive"),
            derive_by_type=option_params.get("derive_by_type"),
            override=True,
        )

    # ensure fields for `needgantt` functionality are added to the fields
    for option in (needs_config.duration_option, needs_config.completion_option):
        default_schema: FieldIntegerSchemaType = {"type": "integer"}
        if option not in _NEEDS_CONFIG.fields:
            _NEEDS_CONFIG.add_field(
                option,
                "Added for needgantt functionality",
                "add_field",
                schema=default_schema,
            )
        else:
            # ensure schema is correct
            existing = _NEEDS_CONFIG.fields[option]
            if existing.schema is None:
                existing.schema = default_schema
            else:
                if existing.schema.get("type") not in {"integer", "number"}:
                    raise NeedsConfigException(
                        f"Schema type for option '{option}' is not 'integer' or 'number' as required by needgantt."
                    )

    for t in needs_config.types:
        # Register requested types of needs
        _register_need_directive(app, t["directive"])

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

    # Process needs_extra_links (deprecated list-based format)
    if not isinstance(needs_config._extra_links, list):
        raise NeedsConfigException("Config option 'needs_extra_links' must be a list.")

    if needs_config._extra_links:
        log_warning(
            LOGGER,
            'Config option "needs_extra_links" is deprecated. Please use "needs_links" instead.',
            "deprecated",
            None,
        )

    # Process needs_links (new dict-based format)
    if not isinstance(needs_config._links, dict):
        raise NeedsConfigException("Config option 'needs_links' must be a dict.")
    for link_name, link_params in needs_config._links.items():
        if isinstance(link_params, Mapping):
            _refuse_global_severity("needs_links", "links", link_name, link_params)

    load_schemas_config_from_json(app, app.config)


def _refuse_global_severity(
    option: str, table: str, name: object, params: Mapping[str, Any]
) -> None:
    """Report a ``severity`` on a ``needs_fields`` or ``needs_links`` entry, which
    takes none: a severity is a need type's declaration's, and the key is ignored.

    :param option: The configuration option, ``needs_fields`` or ``needs_links``.
    :param table: The table of a need type's entry that takes it, ``fields`` or
        ``links``.
    :param name: The entry's name.
    :param params: The entry.
    """
    if "severity" in params:
        log_warning(
            LOGGER,
            f"{option}[{name!r}] sets 'severity', which is declared on a need type's "
            f"entry ([needs.types.<type>.{table}.{name}]); it is ignored here",
            "config",
            None,
        )


def visitor_dummy(*_args: Any, **_kwargs: Any) -> None:
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def _derive_variant_data_proxy(config: NeedsSphinxConfig) -> None:
    """Derive the ``var`` proxy from the variant data map as it currently stands.

    This is a derivation, not a resolution: no file is read, nothing is merged and
    nothing is validated. It exists so that the map and the proxy built from it can
    never drift apart, whichever build phase last wrote the map.

    :param config: The Sphinx-Needs configuration.
    """
    config.variant_data_proxy = (
        VariantDataProxy(config.variant_data) if config.variant_data else None
    )


def resolve_variant_data_config(app: Sphinx, config: Config) -> None:
    """Resolve variant data from file + inline config, validate, and store back.

    This runs during ``config-inited``, so that the merged map is available to
    everything that follows, including configuration that decides which documents
    are read at all (``exclude_patterns``), which can only be changed at that point.

    After this call, ``needs_variant_data`` holds the fully merged result and
    ``needs_variant_data_proxy`` the matching ``var`` proxy for filter expressions.

    :param app: The Sphinx application.
    :param config: The Sphinx configuration.
    :raises NeedsConfigException: If the variant data file cannot be loaded,
        or the variant data is invalid.
    """
    needs_config = NeedsSphinxConfig(config)

    if needs_config.variant_data or needs_config.variant_data_file:
        # Resolve relative file paths against the Sphinx confdir
        file_path = needs_config.variant_data_file
        if file_path and not Path(file_path).is_absolute():
            file_path = str(Path(app.confdir) / file_path)

        try:
            # ``""`` means "no file" on this route, as ``None`` does: ub_project reads
            # ``""`` as a path, so it is mapped here (its reading contract, section 10.1)
            resolved = resolve_variant_data(
                needs_config.variant_data, Path(file_path) if file_path else None
            )
        except (ProjectConfigError, ValueError) as error:
            # ValueError: what ub_project lets through unwrapped -- a data file holding an
            # integer beyond Python's conversion limit, until it names the file itself (#1995)
            raise NeedsConfigException(str(error)) from error
        # Store the resolved result back so downstream code sees the merged dict (a new
        # top-level dict, never the inline dict itself; nested tables may be shared)
        needs_config.variant_data = resolved

    # Cache the variant data proxy for use in filter expressions
    _derive_variant_data_proxy(needs_config)


def _service_config_problem(service: dict[str, Any]) -> str | None:
    """Why a configured service cannot be registered from its ``class`` and
    ``class_init``, or ``None`` when it can.

    Exactly what :meth:`.ServiceManager.register` cannot take is refused: it reads the
    ``class``'s ``options`` and then calls it with ``class_init`` as keyword arguments,
    so a ``class`` that is not callable -- a ``needs_from_toml`` file can give it nothing
    but data, such as a string -- or has no ``options``, and a ``class_init`` that is not
    a mapping. Anything else is registered, as it always was, whether or not it derives
    from ``BaseService``.
    """
    advice = (
        "A service class derives from BaseService and is set in conf.py's "
        "needs_services or registered through the API; a needs_from_toml file can "
        "hold a service's options but not its class"
    )
    klass = service["class"]
    if not callable(klass):
        return (
            "its 'class' is not callable "
            f"(got a value of type {type(klass).__name__!r}). {advice}"
        )
    if not hasattr(klass, "options"):
        name = getattr(klass, "__qualname__", None)
        what = (
            repr(name)
            if isinstance(name, str)
            else f"(a value of type {type(klass).__name__!r})"
        )
        return (
            f"its 'class' {what} has no 'options', which a service class needs. "
            f"{advice}"
        )
    class_init = service["class_init"]
    if not isinstance(class_init, Mapping):
        return (
            "its 'class_init' is not a mapping of keyword arguments for the service "
            f"class (got a value of type {type(class_init).__name__!r})"
        )
    return None


def prepare_env(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:
    """
    Prepares the sphinx environment to store sphinx-needs internal data.
    """
    needs_config = NeedsSphinxConfig(app.config)
    data = SphinxNeedsData(env)

    # The map may have been written after it was resolved, e.g. by another extension's
    # ``config-inited`` handler. Such a value is used as-is (it is not merged with the
    # file, nor validated), but the ``variant`` role reads the map while filter
    # expressions read the proxy, so the proxy is derived again here to keep the two
    # read paths from disagreeing within one build.
    _derive_variant_data_proxy(needs_config)

    # Register the built-in services needs_services configures, as decided when their
    # need types were added (config-inited, priority 12), so the two cannot disagree
    services = data.get_or_create_services()
    for name in _NEEDS_CONFIG.builtin_services:
        services.register(name, GithubService, gh_type=GITHUB_SERVICES[name])

    # Register user defined services
    for name, service in needs_config.services.items():
        if (
            # a built-in name is the built-in service, registered above if configured
            name not in GITHUB_SERVICES
            and name not in services.services
            and "class" in service
            and "class_init" in service
        ):
            # We found a not yet registered service
            # But only register, if service-config contains class and class_init.
            # Otherwise, the service may get registered later by an external sphinx-needs extension
            if (problem := _service_config_problem(service)) is not None:
                log_warning(
                    LOGGER,
                    f"needs_services entry {name!r} is not registered: {problem}",
                    "config",
                    None,
                )
                continue
            services.register(name, service["class"], **service["class_init"])

    # Set time measurement flag
    if needs_config.debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build
        debug.EXECUTE_TIME_MEASUREMENTS = True

    if needs_config.debug_filters:
        with contextlib.suppress(FileNotFoundError):
            Path(str(app.outdir), "debug_filters.jsonl").unlink()


def reread_on_need_types_change(
    app: Sphinx, env: BuildEnvironment, docnames: list[str]
) -> None:
    """Re-read every document if the need types changed since the documents were read.

    A need type gives its needs their ``type_name`` and ``type_prefix`` (and the ids
    generated from it), its diagram color and style, and, through ``inherits``,
    ``fields`` and ``links``, the fields, link types, defaults and ``derive`` rules they
    are created with. The needs of an unchanged document are kept from the pickled
    environment, so they would keep what the previous entries gave them (#2287).

    The list compared is the complete one, ``NeedsSphinxConfig.types``: the configured
    need types and those added from code (``add_need_type``, the configured GitHub
    services), which
    sphinx-needs keeps in its own registry rather than in ``needs_types``. A
    ``rebuild = "env"`` on ``needs_types`` -- as ``needs_fields`` has -- would compare the
    configured types alone. The list is compared against the one recorded when the
    documents were read. Documents are added to ``docnames``, which this event allows.

    The configured built-in GitHub services are compared too: each registers twelve
    fields and the ``github`` layout, which the needs of every document are created
    with, while its need type may be the project's own, leaving the list unchanged. An
    environment that has not recorded them -- one pickled by a version that registered
    them in every build -- is re-read once.

    :param app: The Sphinx application.
    :param env: The build environment.
    :param docnames: The documents Sphinx is about to read; extended in place.
    """
    data = SphinxNeedsData(env)
    need_types = deepcopy(
        [dict(entry) for entry in NeedsSphinxConfig(app.config).types]
    )
    builtin_services = tuple(_NEEDS_CONFIG.builtin_services)
    if data.need_types_read_with != need_types:
        changed = "needs_types"
    elif data.builtin_services_read_with != builtin_services:
        changed = "the configured built-in services"
    else:
        changed = None
    if changed is not None:
        unread = sorted(env.found_docs.difference(docnames))
        if unread:
            LOGGER.info(
                f"{changed} changed: re-reading {len(unread)} unchanged document(s)"
            )
            docnames.extend(unread)
    data.need_types_read_with = need_types
    data.builtin_services_read_with = builtin_services


def merge_default_configs(_app: Sphinx, config: Config) -> None:
    """Merge built-in defaults with user configuration."""
    needs_config = NeedsSphinxConfig(config)

    needs_config._layouts = {**LAYOUTS, **needs_config._layouts}

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
    user_functions = needs_config._functions
    if not isinstance(user_functions, (list, tuple)):
        log_warning(
            LOGGER,
            f"needs_functions is of type {type(user_functions).__name__!r}, "
            "not a list of callables, and is ignored",
            "config",
            None,
        )
        # the value is replaced by the default, so that Sphinx's own type check, which
        # runs later in ``config-inited``, does not report the same value a second time
        needs_config._functions = []
        user_functions = []
    for needs_func in user_functions:
        if not callable(needs_func):
            log_warning(
                LOGGER,
                f"needs_functions entry {needs_func!r} is not callable and is ignored",
                "config",
                None,
            )
            continue
        if not isinstance(getattr(needs_func, "__name__", None), str):
            # a function is registered, and called, by its name
            log_warning(
                LOGGER,
                f"needs_functions entry {needs_func!r} has no __name__ and is ignored: "
                "an entry must be a callable with a __name__; use "
                "add_dynamic_function(app, func, name=...) for one without",
                "config",
                None,
            )
            continue
        _NEEDS_CONFIG.add_function(needs_func)

    # The default link name. Must exist in all configurations. Therefore we set it here for the user.
    if "links" not in needs_config._links:
        needs_config._links["links"] = {
            "outgoing": "links outgoing",
            "incoming": "links incoming",
            "copy": False,
            "color": "#000000",
        }
    if "parent_needs" not in needs_config._links:
        needs_config._links["parent_needs"] = {
            "outgoing": "parent needs",
            "incoming": "child needs",
            "copy": False,
            "color": "#333333",
        }

    # Ensure all links have outgoing and incoming defined, so that we can rely on it later on.
    for name, link in needs_config._links.items():
        _report_unknown_keys(
            f"needs_links[{name!r}]",
            link,
            LINK_ENTRY_KEYS,
            own_name=("option", name),
            reported=("severity",),
        )
    for link in needs_config._extra_links:
        _report_unknown_keys(
            f"needs_extra_links[{link['option']!r}]", link, EXTRA_LINK_ENTRY_KEYS
        )
    for name, link in chain(
        needs_config._links.items(),
        ((v["option"], v) for v in needs_config._extra_links),
    ):
        if "outgoing" not in link:
            link["outgoing"] = name
        if "incoming" not in link:
            link["incoming"] = f"{name} incoming"


def check_configuration(app: Sphinx, config: Config) -> None:
    """Checks the configuration for invalid options.

    E.g. defined need-option, which is already defined internally
    """
    needs_config = NeedsSphinxConfig(config)
    # a field declared on need types alone is checked as a field (a core field or a
    # link type a type's entry names is none: the entry narrows it, or is refused)
    fields = {
        *_NEEDS_CONFIG.fields,
        *(
            type_field_names(config)
            - set(NeedsCoreFields)
            - _link_type_names(needs_config)
        ),
    }
    link_types = [x["option"] for x in needs_config._extra_links]

    if validate_page_size(needs_config.table_page_size) is None:
        log_warning(
            LOGGER,
            "needs_table_page_size must be a positive integer, "
            f"got {needs_config.table_page_size!r}; "
            f"using {DEFAULT_PAGE_SIZE}.",
            "config",
            None,
        )
    if validate_page_sizes(needs_config.table_page_sizes) is None:
        log_warning(
            LOGGER,
            "needs_table_page_sizes must be a non-empty list of non-negative integers "
            f"(0 means all), got {needs_config.table_page_sizes!r}; "
            f"using {list(DEFAULT_PAGE_SIZES)}.",
            "config",
            None,
        )

    external_filter = needs_config.filter_data
    if external_filter:
        log_warning(
            LOGGER,
            "needs_filter_data is deprecated and will be removed in a future version. "
            "Use needs_variant_data instead.",
            "deprecated",
            None,
        )
    for extern_filter, value in external_filter.items():
        # Check if external filter values is really a string
        if not isinstance(value, str):
            raise NeedsConfigException(
                f"External filter value: {value} from needs_filter_data {external_filter} is not a string."
            )
        # Check if needs external filter and field are using the same name
        if extern_filter in fields:
            raise NeedsConfigException(
                f"Same name for external filter and field: {extern_filter}."
                " This is not allowed."
            )

    # Check for usage of internal names
    for internal in NeedsCoreFields:
        if internal in fields:
            raise NeedsConfigException(
                f"Field {internal!r} already used internally. "
                " Please use another name in your config (needs_fields)."
            )
        if internal in link_types:
            raise NeedsConfigException(
                f'Link type name "{internal}" already used internally. '
                " Please use another name in your config (needs_links)."
            )

    # Check if option and link are using the same name
    for link in link_types:
        if link in fields:
            raise NeedsConfigException(
                f"Same name for link and field: {link}. This is not allowed."
            )
        # a link type whose back links are named as a field is refused where the
        # schema is built (create_schema), which sees every field: a service's, and
        # one an extension adds after this check, too

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
            if option not in fields and option not in allowed_internal_variants:
                raise NeedsConfigException(
                    f"Variant option `{option}` is not added in needs_fields. "
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


def _link_type_names(needs_config: NeedsSphinxConfig) -> frozenset[str]:
    """The declared link types: ``needs_links``, ``needs_extra_links``, and the two
    every project has (``links``, ``parent_needs``)."""
    return frozenset(
        {
            "links",
            *CORE_LINK_TYPES,
            *needs_config._links,
            *(
                link["option"]
                for link in needs_config._extra_links
                if isinstance(link, dict) and isinstance(link.get("option"), str)
            ),
        }
    )


#: the link types every project has: their back links yield to no declaration
_CORE_LINK_NAMES = frozenset({"links", *CORE_LINK_TYPES})


def _global_link_entries(needs_config: NeedsSphinxConfig) -> dict[str, str]:
    """Each global link type, with the configuration value that declares it: a
    ``needs_extra_links`` entry wins over a ``needs_links`` one of the same name, as
    where the schema is built."""
    return dict.fromkeys(needs_config._links, "needs_links") | {
        link["option"]: "needs_extra_links"
        for link in needs_config._extra_links
        if isinstance(link, dict) and isinstance(link.get("option"), str)
    }


def _back_link_claims(
    fields: Mapping[str, NewFieldParams], links: Mapping[str, str]
) -> tuple[frozenset[str], frozenset[str], list[str]]:
    """The global declarations refused for the name of a link type's back links.

    The back links of a link type ``l`` are computed on every need as ``l_back``. The
    back links of ``links`` and ``parent_needs``, which every project has, yield to
    nothing: a field or a link type named ``links_back`` or ``parent_needs_back`` is
    refused. Between other global declarations, a name declared outright wins over
    back links: a link type whose back links would have the name of a field, or of a
    link type that is not refused itself, is refused (so of the link types ``x`` and
    ``x_back`` and a field ``x_back_back``, ``x_back`` is refused and ``x`` kept). What
    is refused does not exist. What need types declare is checked after this, against
    the declarations that remain.

    :param fields: The registered fields (from ``needs_fields``,
        ``needs_extra_options``, ``add_field`` and the services), by name.
    :param links: The global link types, each with the configuration value that
        declares it (:func:`_global_link_entries`).
    :return: The link types refused, the fields refused, and one finding for each,
        in the order of their names (a field before a link type of the same name).
    """
    core_back = {f"{name}_back": name for name in _CORE_LINK_NAMES}
    #: (name, 0 for a field or 1 for a link type) -> the finding: a field and a link
    #: type of one name are both refused, each its own finding
    findings: dict[tuple[str, int], str] = {}
    refused_fields: set[str] = set()
    refused_links: set[str] = set()
    for name, params in fields.items():
        if (core := core_back.get(name)) is not None:
            refused_fields.add(name)
            findings[name, 0] = (
                f"Field {name!r} (from {params.source}) names the back links of the "
                f"core link type {core!r}, which is not a field; the field is ignored"
            )
    for name, entry in links.items():
        if (core := core_back.get(name)) is not None:
            refused_links.add(name)
            findings[name, 1] = (
                f"{entry} entry {name!r} names the back links of the core link type "
                f"{core!r}, which is not a link type; the link type is ignored"
            )
    # the longest name first: whether a link type is refused may depend on the link
    # type named as its back links, which is longer
    for name in sorted(
        links.keys() - _CORE_LINK_NAMES - refused_links, key=lambda n: (-len(n), n)
    ):
        back = f"{name}_back"
        if (params := fields.get(back)) is not None:
            what = f"a field (from {params.source})"
        elif back in links and back not in refused_links:
            what = f"a link type (from {links[back]})"
        else:
            continue
        refused_links.add(name)
        findings[name, 1] = (
            f"{links[name]} entry {name!r} declares the link type {name!r}, whose back "
            f"links would be {back!r}, which is {what}; the link type is ignored"
        )
    return (
        frozenset(refused_links),
        frozenset(refused_fields),
        [findings[key] for key in sorted(findings)],
    )


def create_schema(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:
    needs_config = NeedsSphinxConfig(app.config)
    schema = FieldsSchema()
    #: the ``derive`` findings, reported once the schema is complete
    derive_problems: list[DeriveProblem] = []
    #: the declared need types, each directive name with its title
    need_types = {
        need_type["directive"]: str(need_type.get("title", ""))
        for need_type in needs_config.types
        if isinstance(need_type, dict) and isinstance(need_type.get("directive"), str)
    }
    schema.set_need_types(need_types)
    #: the link types the configuration declares, those refused below included
    declared_links = _link_type_names(needs_config)
    #: each need type's entry, its declarations of their shape, and the walk of their
    #: inherits; their findings are reported with the types' declarations, last
    type_entries, entry_findings = _checked_type_entries(needs_config.types)
    order, parent, inherits_findings = _inherits_order(type_entries)
    #: each need type with the types inheriting from it, as ``target_types`` reads them
    below = _type_descendants(order, parent)
    #: one rule for the name of a link type's back links, wherever the field or link
    #: type of that name comes from (every field is registered by now, a service's
    #: too): what it refuses does not exist, and is not read from the configuration
    #: again below (which is pickled with the environment, so it is not changed)
    refused_links, refused_fields, claim_findings = _back_link_claims(
        _NEEDS_CONFIG.fields, _global_link_entries(needs_config)
    )
    for text in claim_findings:
        log_warning(LOGGER, text, "config", None)
    link_types = declared_links - refused_links
    #: the registered fields, but those named as a core link type's back links
    registered = {
        name: params
        for name, params in _NEEDS_CONFIG.fields.items()
        if name not in refused_fields
    }
    #: the back links of the global link types: no need type declares a field of
    #: their name, nor a link type
    back_links = {f"{name}_back" for name in link_types}
    #: the fields need types declare alone: declared below as a needs_fields entry is
    #: (before the rules are checked), each then declared by its need types
    type_local, shape_refused, shape_findings, field_declarers = _type_local_fields(
        type_entries,
        order,
        parent,
        {*NeedsCoreFields, *registered, *link_types, *back_links},
    )
    #: the link types need types declare alone: declared below as a needs_links entry
    #: is (after the needs_links and needs_extra_links entries), with the display,
    #: copy and dead links their first root declaration gives; a name declared under
    #: fields too is a field, and the back links of a link type are none
    local_links, link_refused, link_findings, link_declarers = _type_local_links(
        type_entries,
        order,
        parent,
        {
            **dict.fromkeys((*NeedsCoreFields, *registered, *type_local), "a field"),
            **dict.fromkeys(link_types, "a link type"),
            **dict.fromkeys(back_links, "a link type's back links"),
        },
    )
    #: a name of either close to a declared field's or link type's is likely misspelt;
    #: a link type's is compared with the back links too, whose count a need type's
    #: ``links`` entry declares (``implements_bak``, ``implemnts_back``)
    for text in _near_name_findings(
        field_declarers,
        link_declarers,
        sorted({*_AUTHORED_CORE_FIELDS, *registered, *link_types}),
        back_links=sorted(back_links),
    ):
        log_warning(LOGGER, text, "type_near_name", None)
    #: each field's and link type's rules from the types' entries: folded below into
    #: its ``derive_by_type``, where it is read, so they are checked with the others
    field_rules, link_rules = (
        _type_derive_rules(type_entries, order, parent, table, refused)
        for table, refused in (("fields", shape_refused), ("links", link_refused))
    )
    #: (on a link type, name, need type) -> the entry a rule came from, as the
    #: findings of the rule name it
    spellings: dict[tuple[bool, str, str], str] = {}
    for name, params in needs_config._fields.items():
        # as load_config skipped them: a link type refused above included
        if not isinstance(params, dict) or (
            name not in NeedsCoreFields and name not in declared_links
        ):
            continue
        if _declares_derive(params) and (
            name in NeedsCoreFields or name in CORE_LINK_TYPES
        ):
            # a core field is not derived: the rule is reported and ignored
            derive_problems.append(
                DeriveProblem(name, False, core_message(name, on_link=False), core=True)
            )
        elif name in declared_links:
            what = "core link type" if name in CORE_LINK_TYPES else "link type"
            log_warning(
                LOGGER,
                f"needs_fields entry {name!r} names the {what} {name!r}, "
                "which is not a field; the entry is ignored",
                "config",
                None,
            )
    for name, rules in field_rules.items():
        # a core field is not derived: a type's rule is reported and ignored
        if name in NeedsCoreFields:
            derive_problems.extend(
                DeriveProblem(
                    name,
                    False,
                    core_message(name, on_link=False, spelling=entry),
                    core=True,
                )
                for _, entry, own in rules.values()
                if own
            )
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
            schema=_schema,  # ty: ignore[invalid-argument-type]
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
            if isinstance(core_override, dict) and "schema" in core_override:
                # a keyword its type does not have is reported and dropped (from a
                # copy: the configuration is not changed)
                cleaned, unknown = drop_unknown_keywords(
                    core_override["schema"], link=False, inherited=field.schema
                )
                _report_unknown_keywords(f"needs_fields[{name!r}].schema", unknown)
                if unknown:
                    core_override = cast(
                        NeedFields, {**core_override, "schema": cleaned}
                    )
            try:
                field = create_inherited_field(
                    field,
                    core_override,
                    allow_variants=data.get("allow_variants", False),
                    allow_dynamic_functions=data.get("allow_df", False),
                )
                if "default" in core_override:
                    _set_default_on_field(
                        field,
                        core_override["default"],
                        "needs_fields",
                        allow_coercion=True,
                    )
                if "predicates" in core_override:
                    _set_predicates_on_field(
                        field,
                        core_override["predicates"],
                        "needs_fields",
                        allow_coercion=True,
                    )
            except Exception as exc:
                raise NeedsConfigException(
                    f"Invalid `needs_fields` core option override for {name!r}: {exc}"
                ) from exc

        try:
            schema.add_core_field(field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid core option {name!r}: {exc}") from exc

    for name, field_data in (*registered.items(), *type_local.items()):
        try:
            back_compatible = field_data.source in {
                "needs_extra_options",
                "add_extra_option",
            }
            if (
                not back_compatible
                and field_data.schema is None
                and field_data.default is None
                and field_data.nullable is None
                # a derived field takes no default, so the advice does not apply
                and field_data.derive is None
                and field_data.derive_by_type is None
            ):
                log_warning(
                    LOGGER,
                    f"Field {name!r} (from {field_data.source}) has no 'schema', 'nullable' or 'default' defined, "
                    "which defaults to a string schema with nullable=True and no default. "
                    "To aide with backward compatibility please define at least one.",
                    "config",
                    None,
                )

            # a keyword the schema of its type does not have is reported and dropped
            declared_schema, unknown = drop_unknown_keywords(
                field_data.schema, link=False
            )
            _report_unknown_keywords(f"{field_data.source}[{name!r}].schema", unknown)
            _schema = (
                deepcopy(declared_schema)
                if declared_schema is not None
                else {"type": "string"}
            )
            nullable = True
            if field_data.nullable is not None:
                nullable = field_data.nullable
            elif back_compatible:
                # follows that of legacy (pre-schema) extra option,
                # i.e. nullable if schema is defined
                nullable = field_data.schema is not None
            parse_variants = (
                False
                if field_data.parse_variants is None
                else field_data.parse_variants
            )
            if name in needs_config._variant_options:
                # for backward compatibility with deprecated config option
                parse_variants = True
            parse_dynamic_functions = (
                needs_config._parse_dynamic_functions
                if field_data.parse_dynamic_functions is None
                else field_data.parse_dynamic_functions
            )
            derive = (
                None
                if field_data.derive is None
                else parse_derive(field_data.derive, on_link=False)
            )
            raw_by_type = field_data.derive_by_type
            entries: dict[str, str] = {}
            if rules := field_rules.get(name):
                raw_by_type, entries = _folded_rules(
                    name, raw_by_type, rules, f"{field_data.source}[{name!r}]"
                )
                spellings.update(
                    ((False, name, t), entry) for t, entry in entries.items()
                )
            by_type, by_type_problems = _read_derive_by_type(
                name, False, raw_by_type, need_types
            )
            derive_problems.extend(by_type_problems)
            # a derived field is computed: an author cannot set it, nor a needextend,
            # and it takes no default (bar the value of the need types without a rule)
            authored = derive is None and by_type is None
            field = FieldSchema(
                name=name,
                description=field_data.description,
                schema=_schema,
                nullable=nullable,
                # note, default follows that of legacy (pre-schema) extra option,
                # i.e. default to "" only if no schema is defined; a derived field
                # takes none
                default=None
                if not authored or not back_compatible or field_data.schema is not None
                else FieldLiteralValue(""),
                allow_defaults=authored,
                allow_extend=authored,
                parse_dynamic_functions=parse_dynamic_functions,
                parse_variants=parse_variants,
                directive_option=authored,
                derive=derive,
                derive_by_type=by_type,
            )
            if derive is not None:
                derive_problems.extend(
                    _derive_parse_problems(
                        name,
                        False,
                        derive,
                        beside=[
                            key
                            for key, value in (
                                ("default", field_data.default),
                                ("predicates", field_data.predicates),
                            )
                            if value is not None
                        ],
                    )
                )
            elif by_type is not None:
                field, refused = _with_off_type_default(
                    field, field_data.default, field_data.source
                )
                beside = [
                    key
                    for key, refused_key in (
                        ("default", refused),
                        ("predicates", field_data.predicates is not None),
                    )
                    if refused_key
                ]
                if beside:
                    derive_problems.append(
                        DeriveProblem(
                            name,
                            False,
                            beside_by_type_message(
                                name,
                                on_link=False,
                                keys=beside,
                                # the rules come only from need types' entries
                                entries=()
                                if field_data.derive_by_type is not None
                                else list(dict.fromkeys(entries.values())),
                            ),
                            part="beside",
                        )
                    )
            else:
                if field_data.default is not None:
                    _set_default_on_field(
                        field,
                        field_data.default,
                        field_data.source,
                        allow_coercion=True,
                    )
                if field_data.predicates is not None:
                    _set_predicates_on_field(
                        field,
                        field_data.predicates,
                        field_data.source,
                        allow_coercion=True,
                    )
            schema.add_extra_field(
                field,
                project=field_data.source
                in {"needs_fields", "needs_extra_options", "needs_types"},
            )
        except Exception as exc:
            raise NeedsConfigException(f"Invalid field {name!r}: {exc}") from exc

    # Get set of link names from needs_links (new config) vs needs_extra_links (deprecated)
    links: dict[str, tuple[LinkOptionsType | NeedLinksConfig, str]] = {
        name: entry
        for name, entry in (
            {k: (v, "needs_links") for k, v in needs_config._links.items()}
            | {
                link["option"]: (link, "needs_extra_links")
                for link in needs_config._extra_links
            }
        ).items()
        if name not in refused_links
    } | {name: (params, "needs_types") for name, params in local_links.items()}

    #: the declarations writing ``copy = true``, each deprecated
    copy_declarations: list[tuple[str, str]] = []
    #: per link type whose ``allow_dead_links`` is refused beside unions as read: the
    #: findings as read, and those of the key kept, should a union not be readable
    dead_refusals: dict[str, tuple[list[DeriveProblem], list[DeriveProblem]]] = {}
    for name, (link, config_source) in links.items():
        try:
            # create link schema, with defaults if not defined
            _schema = (
                deepcopy(link["schema"])
                if "schema" in link
                else {"type": "array", "items": {"type": "string"}}
            )
            # a keyword the schema of a link type does not have is reported and dropped
            _schema, unknown = drop_unknown_keywords(_schema, link=True)
            _report_unknown_keywords(f"{config_source}[{name!r}].schema", unknown)
            if "type" not in _schema:
                _schema["type"] = "array"
            if "items" not in _schema:
                _schema["items"] = {"type": "string"}
            if "type" not in _schema["items"]:
                _schema["items"]["type"] = "string"
            if "contains" in _schema and "type" not in _schema["contains"]:
                _schema["contains"]["type"] = "string"
            # Build display config from link options
            # Only pass explicitly set values; let LinkDisplayConfig use its defaults
            display_kwargs: dict[str, str] = {
                # These are required fields with no defaults in LinkDisplayConfig
                "incoming": link.get("incoming", f"{name} incoming"),
                "outgoing": link.get("outgoing", name),
            }
            # Only override optional fields if explicitly set in config
            for key in ("color", "style", "style_part", "style_start", "style_end"):
                if key in link:
                    display_kwargs[key] = link[key]
            display_config = LinkDisplayConfig(**display_kwargs)
            derive = None
            by_type = None
            raw_by_type = link.get("derive_by_type")
            entries: dict[str, str] = {}
            if type_rules := link_rules.get(name, {}):
                raw_by_type, entries = _folded_rules(
                    name, raw_by_type, type_rules, f"{config_source}[{name!r}]"
                )
            if link.get("derive") is not None or raw_by_type is not None:
                if name in CORE_LINK_TYPES or name in NeedsCoreFields:
                    # a core link type is not derived, nor a link type named after a
                    # core field (a need computes ``parts``, ``id_parent`` and others
                    # itself): the rules are reported and ignored
                    if _declares_derive(link):
                        derive_problems.append(
                            DeriveProblem(
                                name, True, core_message(name, on_link=True), core=True
                            )
                        )
                    derive_problems.extend(
                        DeriveProblem(
                            name,
                            True,
                            core_message(name, on_link=True, spelling=entry),
                            core=True,
                        )
                        for _, entry, own in type_rules.values()
                        if own
                    )
                else:
                    if (raw_derive := link.get("derive")) is not None:
                        derive = parse_derive(raw_derive, on_link=True)
                    spellings.update(
                        ((True, name, t), entry) for t, entry in entries.items()
                    )
                    by_type, by_type_problems = _read_derive_by_type(
                        name, True, raw_by_type, need_types
                    )
                    derive_problems.extend(by_type_problems)
            authored = derive is None and by_type is None
            # a union reports no dead link of its own, so where every rule is one its
            # allow_dead_links would say nothing: reported beside it, below, and
            # ignored; beside another rule it is that rule's. Decided here from the
            # rules as read, and again from the rules as checked, where a union that
            # cannot be read is no union and the key is kept
            # (_report_derive_problems)
            rules = [r for r in (derive, *(by_type or {}).values()) if r is not None]
            dead_beside = (
                "allow_dead_links" in link and bool(rules) and all(map(is_union, rules))
            )
            where = f"{config_source}[{name!r}]"
            # a target_types not of its shape is ignored, as a need type's entry's is
            given_targets = "target_types" in link
            if given_targets:
                wrong, text = _not_of_their_shape(where, link, ("target_types",))
                if wrong:
                    log_warning(LOGGER, text, "config", None)
                    given_targets = False
            # a derived link type takes none: reported beside its rule, below
            target_types = (
                _read_target_types(
                    where, link["target_types"], below, need_types, declared_by=None
                )
                if given_targets and authored
                else None
            )
            link_field = LinkSchema(
                name=name,
                description=link.get("description", "Link field"),
                schema=_schema,
                default=LinksLiteralValue([]),
                allow_defaults=authored,
                allow_extend=authored,
                parse_dynamic_functions=link.get(
                    "parse_dynamic_functions", needs_config._parse_dynamic_functions
                ),
                parse_variants=link.get("parse_variants", False),
                parse_conditions=link.get("parse_conditions", True),
                directive_option=authored,
                display=display_config,
                copy=link.get("copy", False),
                allow_dead_links=link.get("allow_dead_links", False)
                and not dead_beside,
                target_types=target_types,
                derive=derive,
                derive_by_type=by_type,
            )
            if derive is not None:
                beside = [
                    key
                    for key, beside_key in (
                        ("default", "default" in link),
                        ("predicates", "predicates" in link),
                        ("target_types", given_targets),
                        ("allow_dead_links", dead_beside),
                    )
                    if beside_key
                ]
                copied = bool(link.get("copy", False))
                read = _derive_parse_problems(
                    name, True, derive, beside=beside, copied=copied
                )
                derive_problems.extend(read)
                if dead_beside:
                    dead_refusals[name] = (
                        read,
                        _derive_parse_problems(
                            name,
                            True,
                            derive,
                            beside=beside[:-1],  # allow_dead_links is the last
                            copied=copied,
                        ),
                    )
            elif by_type is not None:
                link_field, refused = _with_off_type_default(
                    link_field, link.get("default"), config_source
                )
                beside = [
                    key
                    for key, refused_key in (
                        ("default", refused),
                        ("predicates", "predicates" in link),
                        ("target_types", given_targets),
                        ("allow_dead_links", dead_beside),
                    )
                    if refused_key
                ]
                # a link type need types alone declare takes allow_dead_links from its
                # first root, whose own entry gives the first rule
                spelling = (
                    next(
                        (
                            e.removesuffix(".derive")
                            for _, e, own in type_rules.values()
                            if own
                        ),
                        None,
                    )
                    if config_source == "needs_types"
                    else None
                )
                # the rules come only from need types' entries
                entry_rules = (
                    list(dict.fromkeys(entries.values()))
                    if "derive_by_type" not in link
                    else []
                )
                read = _beside_by_type_problems(
                    link_field,
                    beside,
                    spelling=spelling,
                    entries=entry_rules,
                    copied=link.get("copy", False),
                )
                derive_problems.extend(read)
                if dead_beside:
                    dead_refusals[name] = (
                        read,
                        _beside_by_type_problems(
                            link_field,
                            beside[:-1],  # allow_dead_links is the last
                            spelling=spelling,
                            entries=entry_rules,
                            copied=link.get("copy", False),
                        ),
                    )
            else:
                if "default" in link:
                    _set_default_on_field(
                        link_field,
                        link["default"],
                        config_source,
                        allow_coercion=True,
                    )
                if "predicates" in link:
                    _set_predicates_on_field(
                        link_field,
                        link["predicates"],
                        config_source,
                        allow_coercion=True,
                    )
            schema.add_link_field(link_field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid link {name!r}: {exc}") from exc
        # a need type's entry is reported where the need types are read; on a derived
        # link type, copy is refused (copy_on_derived_message) and so not deprecated
        if (
            config_source != "needs_types"
            and link_field.copy
            and not link_field.derived
        ):
            copy_declarations.append((where, name))
    # once every link type is read: whether links is derived, so copies nothing
    for where, name in copy_declarations:
        log_warning(LOGGER, _copy_deprecation(where, name, schema), "deprecated", None)

    # validated where the configuration is read, so that a project which misconfigures
    # one of these and happens to have no needflow anywhere is still told, exactly once
    validate_flow_config(
        direction=needs_config.flow_direction,
        show_links=needs_config.flow_show_links,
        legends=needs_config.flow_legends,
        show_legend=needs_config.flow_show_legend,
    )

    if needs_config._global_options:
        log_warning(
            LOGGER,
            'Config option "needs_global_options" is deprecated. Please use needs_fields and needs_links instead.',
            "deprecated",
            None,
        )
    for name, default_config in needs_config._global_options.items():
        if unknown := set(default_config).difference({"predicates", "default"}):
            log_warning(
                LOGGER,
                f"needs_global_options {name!r} value contains unknown keys: {sorted(unknown)}",
                "config",
                None,
            )
        _set_global_default(
            schema,
            "needs_global_options",
            name,
            default_config,
            allow_coercion=True,
            declared=_declared_defaults(needs_config, registered, links, name),
        )

    _report_derive_problems(
        schema, derive_problems, need_types, spellings, dead_refusals
    )

    # ``links`` takes no target types while a link type copies into it
    if (
        (copying := schema.copying_link_types())
        and (own := schema.global_declaration("links")) is not None
        and isinstance(own, LinkSchema)
        and own.target_types is not None
    ):
        where = f"{links['links'][1]}['links']" if "links" in links else "links"
        log_warning(LOGGER, _copy_refusal(where, copying), "config", None)
        schema.replace_field(dataclasses.replace(own, target_types=None))

    # last: each type's declarations start from the fields as they stand now, their
    # derive problems and legacy defaults included
    _resolve_type_declarations(
        schema,
        type_entries,
        order,
        parent,
        (entry_findings, inherits_findings, shape_findings + link_findings),
        (*type_local, *local_links),
        {"fields": shape_refused, "links": link_refused},
        type_tree=(below, need_types),
    )
    _resolve_id_patterns(schema, type_entries, order, parent)
    # the schema is complete: nothing declares a field once it is built
    schema.freeze()

    SphinxNeedsData(env)._set_schema(schema)


def _copy_deprecation(where: str, name: str, schema: FieldsSchema) -> str:
    """The ``needs.deprecated`` finding of a declaration writing ``copy = true``.

    The links are still copied: the key goes in 10.0, and a link type deriving the
    union of ``links`` and the copying link types replaces it. Where nothing is copied
    -- on ``links`` itself, or into a derived ``links`` -- the advice is to remove it.
    """
    deprecated = (
        f"{where} sets 'copy = true', which is deprecated and will be removed in "
        "sphinx-needs 10.0"
    )
    if name == "links":
        return f"{deprecated}; on links it copies nothing, so remove it"
    if (links := schema.get_link_field("links")) is not None and links.derived:
        return f"{deprecated}; links is derived, so it copies nothing: remove it"
    return (
        f"{deprecated}; declare a link type deriving the union instead, e.g. "
        f'derive = {{kind = "union", fields = ["links", "{name}"]}}, and read it '
        "where the copies in links were read"
    )


def _copy_refusal(where: str, copying: Sequence[str]) -> str:
    """The ``needs.config`` finding of a ``target_types`` on ``links`` beside the link
    types ``copying`` into it."""
    named = joined([repr(name) for name in copying])
    verb = "copies" if len(copying) == 1 else "copy"
    return (
        f"{where} has a 'target_types', but {named} {verb} into links (copy = true); "
        "the key is ignored until copy is replaced"
    )


def _type_descendants(
    types: Iterable[str], parent: Mapping[str, str]
) -> dict[str, frozenset[str]]:
    """Each need type with itself and every type inheriting from it, transitively.

    :param types: The need types.
    :param parent: The parent of each type that has one, once ``inherits`` is checked
        (:func:`_inherits_order`): a forest, so every walk up ends.
    """
    below: dict[str, set[str]] = {name: {name} for name in types}
    for name in below:
        node = parent.get(name)
        while node is not None:
            below.setdefault(node, {node}).add(name)
            node = parent.get(node)
    return {name: frozenset(names) for name, names in below.items()}


def _read_target_types(
    where: str,
    names: Sequence[str],
    below: Mapping[str, frozenset[str]],
    titles: Mapping[str, str],
    *,
    declared_by: str | None,
) -> LinkTargetTypes | None:
    """The target types a declaration gives, of their shape (:data:`_SHAPES`).

    A name that is no need type is one ``needs.config`` finding with the others, and
    ignored; a declaration none of whose names is a need type is ignored as a whole
    (``None``: the links are unrestricted, or keep what they inherit), never an empty
    set that no link could satisfy.

    :param where: The declaration, as the configuration names it.
    :param names: The names it gives.
    :param below: Each need type with the types inheriting from it.
    :param titles: Each need type's title, to point at a title given for a name.
    :param declared_by: The need type whose entry it is, if any.
    """
    known = tuple(dict.fromkeys(name for name in names if name in below))
    if unknown := list(dict.fromkeys(name for name in names if name not in below)):
        hints = [f"{name!r}{title_hint(name, titles)}" for name in unknown]
        many = len(unknown) > 1
        consequence = (
            "the key is ignored"
            if not known
            else f"the {'names are' if many else 'name is'} ignored"
        )
        log_warning(
            LOGGER,
            f"{where} has a 'target_types' naming {joined(hints)}, which "
            f"{'are not need types' if many else 'is not a need type'}; {consequence}",
            "config",
            None,
        )
    if not known:
        return None
    return LinkTargetTypes(
        names=known,
        types=frozenset().union(*(below[name] for name in known)),
        declared_by=declared_by,
    )


def _declares_derive(params: Mapping[str, Any]) -> bool:
    """Whether a field or link type entry carries a rule: ``derive`` or ``derive_by_type``."""
    return params.get("derive") is not None or params.get("derive_by_type") is not None


def _read_derive_by_type(
    name: str, on_link: bool, raw: Any, need_types: Mapping[str, str]
) -> tuple[dict[str, DeriveRule | DeriveInvalid] | None, list[DeriveProblem]]:
    """Read the ``derive_by_type`` of a field or link type, if it has one.

    :return: The rules by need type (``None`` without the key; empty when it cannot be
        read, so the field is derived on no type), and one finding per problem.
    """
    if raw is None:
        return None, []
    rules, read = parse_derive_by_type(raw, on_link=on_link, need_types=need_types)
    problems = []
    for part, reason in read:
        need_type = part.removeprefix("derive_by_type.")
        message = (
            invalid_entry_message(
                name, on_link=on_link, need_type=need_type, reason=reason
            )
            if part != "derive_by_type" and need_type in rules
            else by_type_message(name, on_link=on_link, part=part, reason=reason)
        )
        problems.append(DeriveProblem(name, on_link, message, reason=reason, part=part))
    return rules, problems


_SchemaT = TypeVar("_SchemaT", FieldSchema, LinkSchema)


def _with_off_type_default(
    field: _SchemaT, value: Any, config_name: str
) -> tuple[_SchemaT, bool]:
    """The field (or link type) with ``derive_by_type`` alone, given its ``default``.

    A literal is the value of the need types without a rule. A dynamic function or a
    variant is refused (a ``needs.derive_invalid`` the caller reports), and a value of
    the wrong type is the ``needs.config`` warning of any default; either is ignored.

    :return: The field, and whether the default was refused for not being a literal.
    """
    if value is None:
        return field, False
    try:
        converted = field.convert_or_type_check(value, allow_coercion=True)
    except Exception as exc:
        log_warning(
            LOGGER,
            f"{config_name}[{field.name!r}]['default'] value is incorrect: {exc}",
            "config",
            None,
        )
        return field, False
    if isinstance(converted, FieldLiteralValue | LinksLiteralValue):
        return dataclasses.replace(field, default=converted), False
    return field, converted is not None


def _derive_parse_problems(
    name: str,
    on_link: bool,
    derive: DeriveRule | DeriveInvalid,
    *,
    beside: list[str],
    copied: bool = False,
) -> list[DeriveProblem]:
    """The finding of a rule as read: it cannot be read, a default is beside it, or its
    link type is declared ``copy = true``.

    One finding per rule: a rule that cannot be read is reported for that alone.
    """
    if isinstance(derive, DeriveInvalid):
        return [
            DeriveProblem(
                name,
                on_link,
                invalid_message(name, on_link=on_link, reason=derive.reason),
            )
        ]
    # copy is refused too: said with the others by a finding replacing this one
    refused = (*beside, "copy") if copied else tuple(beside)
    if beside:
        return [
            DeriveProblem(
                name,
                on_link,
                beside_message(name, on_link=on_link, rule=derive, keys=beside),
                beside=refused,
            )
        ]
    if copied:
        return [
            DeriveProblem(
                name,
                on_link,
                copy_on_derived_message(name, described=derive.describe()),
                beside=refused,
            )
        ]
    return []


def _beside_by_type_problems(
    link_field: LinkSchema,
    beside: list[str],
    *,
    spelling: str | None,
    entries: Sequence[str],
    copied: bool,
) -> list[DeriveProblem]:
    """The finding of the keys beside a link type's ``derive_by_type`` alone, or of its
    ``copy = true``: one, or none."""
    name = link_field.name
    if beside:
        return [
            DeriveProblem(
                name,
                True,
                beside_by_type_message(
                    name, on_link=True, keys=beside, spelling=spelling, entries=entries
                ),
                part="beside",
            )
        ]
    if copied:
        return [
            DeriveProblem(
                name,
                True,
                copy_on_derived_message(name, described=link_field.describe_derived()),
                part="beside",
            )
        ]
    return []


def _report_derive_problems(
    schema: FieldsSchema,
    read_problems: list[DeriveProblem],
    need_types: Mapping[str, str],
    spellings: Mapping[tuple[bool, str, str], str] | None = None,
    dead_refusals: Mapping[str, tuple[list[DeriveProblem], list[DeriveProblem]]]
    | None = None,
) -> None:
    """Check the rules against the complete schema, and report every finding.

    A rule that cannot be read is replaced by its :class:`DeriveInvalid` marker (the
    field, or link type, is replaced by a copy carrying it), so the field stays derived
    (closed to authors and needextend) and holds its empty value -- on the need type of
    a ``derive_by_type`` entry, or on the types a ``derive`` cycles on, alone.
    One ``needs.derive_invalid`` warning per rule (a rule that cannot be read is
    reported for that alone, not for a default beside it, or a link type copying into
    a derived ``links``), in a fixed order: the core fields, then the fields, then the
    link types, each by name; within a name, ``derive``, the ``derive_by_type`` table,
    its entries by need type, and a key beside ``derive_by_type``. A finding of a rule
    a need type's entry gives names that entry (``spellings``), where the rule is read.

    ``allow_dead_links`` is refused beside a link type every rule of which is a union
    (``dead_refusals``: the findings as read, and those without the refusal). That is
    decided again from the rules as checked: a union that cannot be read is no union,
    so beside one the key is kept, and its refusal withdrawn. A ``derive`` cycling on
    some need types only is still a union on the others, and its markers there do not
    count.
    """
    checked = {
        (p.on_link, p.name, p.part): p
        for p in check_derive_rules(schema, need_types=need_types)
    }
    for (on_link, name, part), problem in checked.items():
        # the global declaration: the schema is still built, no need reads it yet
        target = schema.global_declaration(name)
        assert target is not None and (target.kind == "link") == on_link, (
            "a checked rule is on a field of the schema"
        )
        if part == "derive" and not problem.on_types:
            target = dataclasses.replace(
                target,
                derive=DeriveInvalid(
                    getattr(target.derive, "kind", None), problem.reason
                ),
            )
        else:
            # an entry, or a derive on the types it cycles on: invalid on those types
            # (the derive's marked as such, so the field is still described by it)
            by_type = dict(target.derive_by_type or {})
            if problem.on_types:
                for need_type, reason in problem.type_reasons:
                    by_type[need_type] = DeriveInvalid(
                        getattr(target.derive, "kind", None), reason, fallback=True
                    )
            else:
                need_type = part.removeprefix("derive_by_type.")
                by_type[need_type] = DeriveInvalid(
                    getattr(by_type.get(need_type), "kind", None), problem.reason
                )
            target = dataclasses.replace(target, derive_by_type=by_type)
        schema.replace_field(target)
    for name, (refused, kept) in (dead_refusals or {}).items():
        link = schema.global_declaration(name)
        assert isinstance(link, LinkSchema), "a refusal is of a link type"
        rules = [
            rule
            for rule in (link.derive, *(link.derive_by_type or {}).values())
            if rule is not None
            and not (isinstance(rule, DeriveInvalid) and rule.fallback)
        ]
        if rules and all(map(is_union, rules)):
            continue
        schema.replace_field(dataclasses.replace(link, allow_dead_links=True))
        withdrawn = {id(problem) for problem in refused}
        read_problems = [
            *(p for p in read_problems if id(p) not in withdrawn),
            *kept,
        ]
    core = sorted((p for p in read_problems if p.core), key=lambda p: p.name)
    findings = {
        (p.on_link, p.name, p.part): _with_table_text(schema, p)
        for p in read_problems
        if not p.core
    }
    read = dict(findings)
    findings.update(checked)
    # a derive cycling on some need types only still applies on the others, so the
    # keys refused beside it still are: its cycle's finding, replacing theirs, says so
    for key, problem in checked.items():
        if problem.on_types and (beside := read.get(key)) is not None and beside.beside:
            findings[key] = dataclasses.replace(
                problem, message=problem.message + beside_clause(beside.beside)
            )
    if (copied := copy_problem(schema)) is not None and (
        True,
        "links",
        copied.part,
    ) not in findings:
        findings[(True, "links", copied.part)] = copied
    ordered = sorted(findings.values(), key=lambda problem: problem.order)
    for problem in [*core, *ordered]:
        message = problem.message
        if (
            spellings
            and problem.part.startswith("derive_by_type.")
            and (
                entry := spellings.get(
                    (
                        problem.on_link,
                        problem.name,
                        need_type := problem.part.removeprefix("derive_by_type."),
                    )
                )
            )
        ):
            message = invalid_entry_message(
                problem.name,
                on_link=problem.on_link,
                need_type=need_type,
                reason=problem.reason,
                spelling=entry,
            )
        log_warning(LOGGER, message, "derive_invalid", None)


def _with_table_text(schema: FieldsSchema, problem: DeriveProblem) -> DeriveProblem:
    """A finding of an unreadable ``derive_by_type`` table, saying what the needs use:
    the ``derive`` beside it where it stands once checked (on every type, or but those
    it cycles on), else no rule."""
    if problem.part != "derive_by_type":
        return problem
    target = (
        schema.get_link_field(problem.name)
        if problem.on_link
        else schema.get_extra_field(problem.name)
    )
    uses_derive: Literal["every", "uncycled", "none"] = "none"
    if target is not None and isinstance(target.derive, DeriveRule):
        # the markers of a derive cycling on some types are its only entries here
        uses_derive = "uncycled" if target.derive_by_type else "every"
    return dataclasses.replace(
        problem,
        message=by_type_message(
            problem.name,
            on_link=problem.on_link,
            part=problem.part,
            reason=problem.reason,
            uses_derive=uses_derive,
        ),
    )


def _inherits_order(
    types: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], dict[str, str], list[str]]:
    """The need types, each after its parent; the parent of each type; and why an
    ``inherits`` is ignored.

    A type has one parent at most, so the types are a forest once every ``inherits``
    naming no need type, and every one on a cycle, is dropped: each is reported, every
    member of every cycle, and its type stays, a root. The types keep the order they
    are given in, but a parent comes before its children wherever it is given.

    :param types: Each need type's directive name with its ``needs_types`` entry.
    """
    findings: list[str] = []
    parent: dict[str, str] = {}
    for name, entry in types.items():
        if (inherits := entry.get("inherits")) is None:
            continue
        if inherits not in types:
            findings.append(
                f"Need type {name!r} inherits {inherits!r}, which is not a need type; "
                "its inherits is ignored."
            )
        else:
            parent[name] = inherits
    order: list[str] = []
    for start in types:
        #: the types from ``start`` up to the first one placed, or back to itself
        path: list[str] = []
        node: str | None = start
        while node is not None and node not in order and node not in path:
            path.append(node)
            node = parent.get(node)
        if node is not None and node in path:
            cycle = path[path.index(node) :]
            ring = " -> ".join([*cycle, cycle[0]])
            for member in cycle:
                findings.append(
                    f"Need type {member!r} inherits {parent.pop(member)!r} on a cycle "
                    f"({ring}); its inherits is ignored."
                )
        order.extend(reversed(path))
    return order, parent, findings


def _checked_type_entries(
    need_types: Iterable[NeedType],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Each need type's entry by directive name, its declarations of their shape.

    An entry an extension adds after the configuration is resolved has not been
    through the normaliser: its declarations are checked here, by its rules.

    :return: The entries, and the ``needs.config`` findings of their shape.
    """
    types: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    for need_type in need_types:
        if not isinstance(need_type, dict) or not isinstance(
            name := need_type.get("directive"), str
        ):
            continue
        named = f"needs_types[{name!r}]"
        wrong, text = _not_of_their_shape(
            named, need_type, ("inherits", "fields", "links")
        )
        if wrong:
            findings.append(text)
        entry = {key: value for key, value in need_type.items() if key not in wrong}
        for table in ("fields", "links"):
            if table in entry:
                entry[table] = _normalise_declarations(
                    named, table, cast(Mapping[Any, Any], entry[table]), findings
                )
        types[name] = entry
    return types, findings


def _shape_of(keys: Mapping[str, Any]) -> tuple[Any, Any] | None:
    """The type and items' type a declaration of a field gives, if it gives a type."""
    schema = keys.get("schema", {})
    if (type_ := schema.get("type")) is None:
        return None
    items = schema.get("items")
    return type_, (
        items.get("type") if type_ == "array" and isinstance(items, Mapping) else None
    )


def _type_local_fields(
    types: Mapping[str, Mapping[str, Any]],
    order: list[str],
    parent: Mapping[str, str],
    known: set[str],
) -> tuple[
    dict[str, NewFieldParams], set[tuple[str, str]], list[str], dict[str, list[str]]
]:
    """The fields need types declare that nothing else declares (no core field, no
    registered field, no link type, nor a link type's back links -- the resolver
    refuses such an entry): each the field of the types that declare it, of
    the one shape they agree on.

    A root declaration is one of a type none of whose ancestors declares the field:
    an entry refused for the field's shape declares nothing, so a child of a refused
    entry is a declaration of its own (a root), checked as any other.
    The first root declaration in ``order`` (a parent before its children) that gives
    a ``schema`` ``type`` sets the field's type and items' type, and whether it is
    derived (it gives a ``derive``); a root declaration that gives no type takes the
    type. A root declaration of another type, or derived where the field is not (or
    the other way round), one whose type is no field's, and every declaration of a
    field no root declaration gives a type, is a ``needs.type_conflict`` finding: its
    entry is ignored, and does not declare the field. A child's declaration narrows
    its parent's, as for any field, and inherits its rule; a child's ``derive`` of a
    field that is not derived is refused the same.

    Each field is declared as a ``needs_fields`` entry with the agreed ``schema``
    alone, nullable and without a default: each type that declares it narrows it.

    :param types: Each need type's entry, of its shape.
    :param order: The need types, each after its parent.
    :param parent: The parent of each type that has one.
    :param known: The names declared otherwise.
    :return: The fields, by name; the (need type, field) entries that do not declare
        their field; the findings, by field, in ``order``; and the need types whose
        root declarations declare each field, in ``order``.
    """

    #: field -> its declarations, in order
    entries: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for need_type in order:
        for name, keys in types[need_type].get("fields", {}).items():
            if isinstance(name, str) and name and name not in known:
                entries.setdefault(name, []).append((need_type, keys))
    local: dict[str, NewFieldParams] = {}
    declarers: dict[str, list[str]] = {}
    refused: set[tuple[str, str]] = set()
    inherited = partial(_declared_by_ancestor, types, parent, "fields", refused)
    findings: list[str] = []
    for name, declarations in entries.items():
        roots: list[str] = []
        #: the agreed type and items' type, and the need type that set them
        agreed: tuple[Any, Any, str] | None = None
        derived = False
        for need_type, keys in declarations:
            if inherited(need_type, name) or (shape := _shape_of(keys)) is None:
                continue
            try:
                validate_field_schema(_field_schema_of(*shape))
            except TypeError as exc:
                findings.append(
                    f"needs_types[{need_type!r}].fields[{name!r}] cannot be declared: "
                    f"Invalid schema: {_reason(exc)}; the entry is ignored"
                )
                refused.add((need_type, name))
                continue
            agreed = (*shape, need_type)
            derived = keys.get("derive") is not None
            break
        for need_type, keys in declarations:
            where = f"needs_types[{need_type!r}].fields[{name!r}]"
            if (need_type, name) in refused or inherited(need_type, name):
                continue
            roots.append(need_type)
            if agreed is not None and need_type == agreed[2]:
                continue
            if agreed is None:
                text = (
                    f"declares {name!r}, which no needs_fields entry declares, and no "
                    "need type without an ancestor declaring it gives it a 'schema' "
                    "'type'"
                )
            else:
                type_, items, by = agreed
                schema = keys.get("schema", {})
                own = schema.get("type", type_)
                own_items = None
                if own == "array":
                    own_items = items
                    if isinstance(schema.get("items"), Mapping):
                        own_items = schema["items"].get("type", items)
                if (own, own_items) != (type_, items):
                    text = (
                        f"cannot be declared with type {own!r} (items {own_items!r}): "
                        f"its type is {type_!r} (items {items!r}) on every need type, "
                        f"as need type {by!r} declares it"
                    )
                elif (keys.get("derive") is not None) != derived:
                    text = _derivation_text(derived, by)
                else:
                    continue
            findings.append(f"{where} {text}; the entry is ignored")
            refused.add((need_type, name))
        if agreed is None:
            continue
        if not derived:
            # a child's rule would derive the field on every type that declares it
            for need_type in order:
                keys = types[need_type].get("fields", {}).get(name)
                if (
                    keys is not None
                    and keys.get("derive") is not None
                    and inherited(need_type, name)
                ):
                    findings.append(
                        f"needs_types[{need_type!r}].fields[{name!r}] "
                        f"{_derivation_text(derived, agreed[2])}; the entry is ignored"
                    )
                    refused.add((need_type, name))
        declarers[name] = [t for t in roots if (t, name) not in refused]
        declaring = ", ".join(repr(t) for t in declarers[name])
        local[name] = NewFieldParams(
            source="needs_types",
            description=f"Declared by need types {declaring}",
            schema=cast(Any, _field_schema_of(agreed[0], agreed[1])),
            nullable=True,
        )
    return local, refused, findings, declarers


#: the core fields an author sets, which a field declared on need types alone may be
#: a misspelling of: the id and the core fields of the fields schema
_AUTHORED_CORE_FIELDS: Final[tuple[str, ...]] = (
    "id",
    *(
        name
        for name, data in NeedsCoreFields.items()
        if data.get("add_to_field_schema")
    ),
)


def _near_name_findings(
    field_declarers: Mapping[str, list[str]],
    link_declarers: Mapping[str, list[str]],
    known: list[str],
    *,
    back_links: Sequence[str] = (),
) -> list[str]:
    """For each field and link type declared on need types alone (each with the need
    types declaring it) whose name is close to a name in ``known`` (a core field an
    author sets, a registered field, a global link type), a finding naming the first
    declaring entry and the close name. A link type's name is compared with
    ``back_links`` too, the back links of the global link types, which a need type's
    ``links`` entry names to declare their count.

    Close is ``difflib.get_close_matches(name, known, n=1, cutoff=0.8)``: a misspelt
    name, or a deliberate near name (a plural), which is why it is a finding of its
    own subtype; the field or link type is declared all the same.
    """
    findings: list[str] = []
    for table, what, declarers, names in (
        ("fields", "a field", field_declarers, known),
        ("links", "a link type", link_declarers, [*known, *back_links]),
    ):
        for name, need_types in declarers.items():
            close = difflib.get_close_matches(name, names, n=1, cutoff=0.8)
            if not close or not need_types:
                continue
            findings.append(
                f"needs_types[{need_types[0]!r}].{table}[{name!r}] declares {what} of "
                f"need types {', '.join(repr(t) for t in need_types)} alone; did you "
                f"mean {close[0]!r}?"
            )
    return findings


def _declared_by_ancestor(
    types: Mapping[str, Mapping[str, Any]],
    parent: Mapping[str, str],
    table: Literal["fields", "links"],
    refused: set[tuple[str, str]],
    need_type: str,
    name: str,
) -> bool:
    """Whether an ancestor of ``need_type`` declares ``name`` in its ``table``; an
    entry in ``refused``, refused for the shape of what it declares, declares
    nothing."""
    node = parent.get(need_type)
    while node is not None:
        if name in types[node].get(table, {}) and (node, name) not in refused:
            return True
        node = parent.get(node)
    return False


def _type_local_links(
    types: Mapping[str, Mapping[str, Any]],
    order: list[str],
    parent: Mapping[str, str],
    known: Mapping[str, str],
) -> tuple[
    dict[str, NeedLinksConfig], set[tuple[str, str]], list[str], dict[str, list[str]]
]:
    """The link types need types declare that nothing else declares (no link type, no
    field, no core field): each the link type of the types that declare it, of the one
    shape they agree on -- whether it is derived, and its display, ``copy`` and
    ``allow_dead_links`` (:data:`NEED_TYPE_LINK_SHAPE_KEYS`).

    A root declaration is one of a type none of whose ancestors declares the link type:
    an entry refused for the link type's shape declares nothing, so a child of a
    refused entry is a declaration of its own (a root). The first root declaration in
    ``order`` (a parent before its children), an empty one too, sets the shape: the
    keys it gives, the defaults of a ``needs_links`` entry for the rest, and derived if
    it gives a ``derive``. Every other declaration, a root or a child, may repeat a
    key's value; one giving another value of a key, or derived where the link type is
    not (or, a root, the other way round), is a ``needs.type_conflict`` finding, and
    its entry is ignored: a root's then declares nothing, a child's still declares the
    link type through its parent.

    A name that is the back links of a link type (``links_back``, or ``z_back`` beside a
    link type ``z`` need types declare alone) is none: the resolver refuses it. A link
    type whose back links would have the name of a field or a link type is refused, a
    ``needs.type_conflict`` finding on each of its entries.

    Each link type is declared as a ``needs_links`` entry with the keys the first root
    gives: each type that declares it narrows it.

    :param types: Each need type's entry, of its shape.
    :param order: The need types, each after its parent.
    :param parent: The parent of each type that has one.
    :param known: The names declared otherwise, each with what it is (``a field``, ``a
        link type``, ``a link type's back links``); the fields declared on need types
        alone are among them (a name one type declares under ``fields`` and another
        under ``links`` is a field).
    :return: The link types, by name, in the order of their first root declarations;
        the (need type, link type) entries ignored; the findings, by link type, in
        ``order``; and the need types whose root declarations declare each link type,
        in ``order``.
    """
    #: link type -> its declarations, in order
    entries: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for need_type in order:
        for name, keys in types[need_type].get("links", {}).items():
            if isinstance(name, str) and name and name not in known:
                entries.setdefault(name, []).append((need_type, keys))
    # the back links of another: computed on every need, so no link type
    for name in [n for n in entries if n.endswith("_back") and n[:-5] in entries]:
        del entries[name]
    local: dict[str, NeedLinksConfig] = {}
    declarers: dict[str, list[str]] = {}
    refused: set[tuple[str, str]] = set()
    inherited = partial(_declared_by_ancestor, types, parent, "links", refused)
    findings: list[str] = []
    for name, declarations in entries.items():
        if (taken := known.get(back := f"{name}_back")) is not None:
            # every need would carry its back links under the other's name
            for need_type, _ in declarations:
                findings.append(
                    f"needs_types[{need_type!r}].links[{name!r}] declares {name!r}, "
                    f"whose back links would be {back!r}, which is {taken}; the entry "
                    "is ignored"
                )
                refused.add((need_type, name))
            continue
        # the first declaration is a root: an ancestor's would come before it
        by, first = declarations[0]
        given = {k: first[k] for k in NEED_TYPE_LINK_SHAPE_KEYS if k in first}
        shape = {**_link_shape_defaults(name), **given}
        derived = first.get("derive") is not None
        roots = [by]
        for need_type, keys in declarations[1:]:
            root = not inherited(need_type, name)
            other = [
                k
                for k in NEED_TYPE_LINK_SHAPE_KEYS
                if k in keys and keys[k] != shape[k]
            ]
            if other:
                key = other[0]
                text = (
                    f"cannot be declared with {key} {keys[key]!r}: its {key} is "
                    f"{shape[key]!r} on every need type, as need type {by!r} declares it"
                )
            elif (keys.get("derive") is not None) != derived and (root or not derived):
                # a child of a derived link type inherits its parent's rule
                text = _derivation_text(derived, by)
            else:
                if root:
                    roots.append(need_type)
                continue
            findings.append(
                f"needs_types[{need_type!r}].links[{name!r}] {text}; the entry is ignored"
            )
            refused.add((need_type, name))
        declarers[name] = roots
        declaring = ", ".join(repr(t) for t in roots)
        local[name] = NeedLinksConfig(
            description=f"Declared by need types {declaring}", **given
        )
    return local, refused, findings, declarers


def _link_shape_defaults(name: str) -> dict[str, Any]:
    """The display, ``copy`` and ``allow_dead_links`` of a ``needs_links`` entry that
    gives none of them."""
    display = LinkDisplayConfig(incoming=f"{name} incoming", outgoing=name)
    return {
        **{f.name: getattr(display, f.name) for f in dataclasses.fields(display)},
        "copy": False,
        "allow_dead_links": False,
    }


def _type_derive_rules(
    types: Mapping[str, Mapping[str, Any]],
    order: list[str],
    parent: Mapping[str, str],
    table: Literal["fields", "links"],
    refused: set[tuple[str, str]],
) -> dict[str, dict[str, tuple[Any, str, bool]]]:
    """The ``derive`` of each entry of the types' ``table``: name -> need type ->
    (the rule, the entry that gives it, whether it is the type's own entry). A type's
    rule reaches its children, each of which may give its own; an entry refused for
    its field's shape gives none.
    """
    if not any(
        "derive" in keys
        for entry in types.values()
        for keys in entry.get(table, {}).values()
    ):
        return {}  # no rule in any entry: nothing to walk
    #: need type -> name -> its rule, its own or its nearest ancestor's
    effective: dict[str, dict[str, tuple[Any, str, bool]]] = {}
    for need_type in order:
        rules = {
            name: (rule, entry, False)
            for name, (rule, entry, _) in effective.get(
                parent.get(need_type, ""), {}
            ).items()
        }
        for name, keys in types[need_type].get(table, {}).items():
            if (rule := keys.get("derive")) is not None and (
                (need_type, name) not in refused
            ):
                where = f"needs_types[{need_type!r}].{table}[{name!r}]"
                rules[name] = (rule, f"{where}.derive", True)
        effective[need_type] = rules
    by_name: dict[str, dict[str, tuple[Any, str, bool]]] = {}
    for need_type, rules in effective.items():
        for name, ruled in rules.items():
            by_name.setdefault(name, {})[need_type] = ruled
    return by_name


def _folded_rules(
    name: str,
    raw: Any,
    rules: Mapping[str, tuple[Any, str, bool]],
    declared: str,
) -> tuple[Any, dict[str, str]]:
    """A field's (or link type's) ``derive_by_type`` with the rules of the need types'
    entries folded in (:func:`_type_derive_rules`).

    A ``derive_by_type`` entry for a type wins for that type: beside the type's own
    rule it is a ``needs.config`` finding, the type's rule ignored there (the types
    inheriting from it still read it, unless they have a rule of their own); an
    inherited rule gives way to it silently. A ``derive_by_type`` that is not a
    table is read as it is.

    :param declared: Where the field is declared, as a finding names it.
    :return: The ``derive_by_type`` to read, and the entry each folded rule came from,
        by need type.
    """
    if not rules or (raw is not None and not isinstance(raw, Mapping)):
        return raw, {}
    folded = dict(raw or {})
    entries: dict[str, str] = {}
    for need_type, (rule, entry, own) in rules.items():
        if need_type in folded:
            if own:
                log_warning(
                    LOGGER,
                    f"{entry.removesuffix('.derive')} sets 'derive', and "
                    f"{declared}.derive_by_type[{need_type!r}] another rule for the "
                    "same type; the need type's rule is ignored for it (the need "
                    "types inheriting from it still read it)",
                    "config",
                    None,
                )
            continue
        folded[need_type] = rule
        entries[need_type] = entry
    return folded, entries


def _derivation_text(derived: bool, by: str) -> str:
    """Why a declaration of a field declared on need types alone disagrees with its
    derivation: derived on every type that declares it, or on none."""
    if derived:
        return (
            "cannot be declared without a 'derive': it is derived on every need type "
            f"that declares it, as need type {by!r} declares it"
        )
    return (
        "cannot be declared with a 'derive': it is not derived on every need type "
        f"that declares it, as need type {by!r} declares it"
    )


def _field_schema_of(type_: Any, items: Any) -> dict[str, Any]:
    """The schema of a field of a type (and, for an array, of items of a type): an
    array without an items' type is left without ``items``, so its finding is the one
    a ``needs_fields`` entry gets."""
    if type_ == "array" and items is not None:
        return {"type": type_, "items": {"type": items}}
    return {"type": type_}


def _resolve_type_declarations(
    schema: FieldsSchema,
    types: Mapping[str, Mapping[str, Any]],
    order: list[str],
    parent: Mapping[str, str],
    findings: tuple[list[str], list[str], list[str]],
    local: Iterable[str],
    refused: Mapping[Literal["fields", "links"], set[tuple[str, str]]],
    *,
    type_tree: tuple[Mapping[str, frozenset[str]], Mapping[str, str]] = ({}, {}),
) -> None:
    """Declare the fields and link types of each need type anew, as its ``needs_types``
    entry says: ``inherits``, ``fields`` and ``links``.

    The last change to the schema while it is built. A type's declaration of a field
    starts from the field's global declaration, takes the entries of its ancestors from
    the root down, then its own; each entry is a narrowing of the declaration before
    it (:func:`narrowing_problems`), and is registered for its type and every type
    inheriting from it (:meth:`FieldsSchema.add_type_overlay`). A type without an
    entry of a field, itself or by an ancestor, reads the field's global declaration.

    What cannot be used is reported, one warning per reason, and ignored, and the
    build goes on: an ``inherits`` naming no need type or on a cycle
    (``needs.type_inherits``; the type stays, a root); an entry naming no field of its
    table, or setting what the field does not take (``needs.type_conflict``); an entry
    that widens the declaration before it (``needs.type_widening``). An entry is taken
    whole or not at all: the type keeps the declaration before it. A ``links`` entry of
    a link type declared otherwise that gives its display, ``copy`` or
    ``allow_dead_links`` (:data:`NEED_TYPE_LINK_SHAPE_KEYS`) is a ``needs.config``
    finding, those keys ignored and the rest of the entry used: the link type keeps its
    own on every need type.

    A field or link type declared on need types alone (:func:`_type_local_fields`,
    :func:`_type_local_links`) is the field of the types that declare it, absent on
    every other type (:meth:`FieldsSchema._localise`): a type declares it by its entries
    and its ancestors', an empty entry included, and an entry that cannot be used, if it
    names a field of its table -- but an entry its shape refuses, which does not
    declare it.

    :param schema: The schema, complete but for the declarations of need types.
    :param types: Each configured need type's entry (:func:`_checked_type_entries`),
        those an extension or a service adds included.
    :param order: The need types, each after its parent (:func:`_inherits_order`).
    :param parent: The parent of each type that has one.
    :param findings: What was found reading the entries, reported first: the shape of
        an entry an extension added (``needs.config``), the walk
        (``needs.type_inherits``), and the shape of the fields, then of the link types,
        declared on need types alone (``needs.type_conflict``).
    :param local: The fields and link types declared on need types alone.
    :param refused: Per table, the (need type, name) entries refused for the shape of
        the field or link type they declare.
    :param type_tree: What a ``target_types`` is read against: each need type with the
        types inheriting from it, and each need type's title.
    """
    entry_findings, inherits_findings, shape_findings = findings
    #: a need type's ``links`` takes no target types beside them either
    copying = schema.copying_link_types()
    for text in entry_findings:
        log_warning(LOGGER, text, "config", None)
    for text in inherits_findings:
        log_warning(LOGGER, text, "type_inherits", None)
    for text in shape_findings:
        log_warning(LOGGER, text, "type_conflict", None)
    #: need type -> field name -> its declaration for the type, and the type whose
    #: entry made it
    declared: dict[str, dict[str, tuple[FieldSchema | LinkSchema, str]]] = {}
    #: need type -> back links name -> the type's declaration of them, and the type
    #: whose entry made it
    back_declared: dict[str, dict[str, tuple[BackLinksSchema, str]]] = {}
    #: need type -> the fields and link types it declares: its ancestors' and its own
    #: entries, used or not, each naming one of its table's kind
    names: dict[str, set[str]] = {}
    #: need type -> name -> the type whose entry gave the severity it has, if one did
    severity_by: dict[str, dict[str, str]] = {}
    for need_type in order:
        own = dict(declared[p]) if (p := parent.get(need_type)) else {}
        back_own = dict(back_declared[p]) if p else {}
        severity_own = dict(severity_by[p]) if p else {}
        names[need_type] = set(names[p]) if p else set()
        for table, kind, what, other in (
            ("fields", "field", "a field", "a link type"),
            ("links", "link", "a link type", "a field"),
        ):
            for name, keys in types[need_type].get(table, {}).items():
                where = f"needs_types[{need_type!r}].{table}[{name!r}]"
                glob = schema.global_declaration(name)
                owner = (
                    schema.global_declaration(name.removesuffix("_back"))
                    if glob is None and name.endswith("_back")
                    else None
                )
                if table == "links" and name.endswith("_back"):
                    keys = _deferred_keys(
                        where, keys, count=owner is not None and owner.kind == "link"
                    )
                if (need_type, name) in refused[table]:
                    continue  # reported with the field's (or link type's) shape
                if glob is None or glob.kind != kind:
                    # defensive: an entry named after a field's name and ``_back`` that
                    # declares nothing is refused before it reaches here (no state is
                    # known where ``owner`` is a field), so it would read "not ..."
                    if owner is not None and owner.kind == "link":
                        if table == "links":
                            # how many links point to the type's needs
                            previous, by = back_own.get(name, (None, None))
                            if (
                                back := _declare_back_links(
                                    previous,
                                    owner.name,
                                    keys,
                                    where,
                                    by,
                                    severity_by=severity_own.get(name),
                                )
                            ) is not None:
                                back_own[name] = (back, need_type)
                                if "severity" in keys:
                                    severity_own[name] = need_type
                            continue
                        is_ = (
                            "a link type's back links, whose count a need type "
                            f"declares under 'links' (needs_types[{need_type!r}]"
                            f".links[{name!r}])"
                        )
                    elif glob is None:
                        is_ = f"not {what}"
                    else:
                        is_ = f"{other}, not {what}"
                    log_warning(
                        LOGGER,
                        f"{where} declares {name!r}, which is {is_}; the entry is "
                        "ignored",
                        "type_conflict",
                        None,
                    )
                    continue
                if (
                    table == "links"
                    and name not in local
                    and (
                        shape_keys := [
                            k for k in NEED_TYPE_LINK_SHAPE_KEYS if k in keys
                        ]
                    )
                ):
                    # a link type declared otherwise is drawn, copied and checked the
                    # same on every need type: as needs_links declares it
                    named = [repr(k) for k in shape_keys]
                    log_warning(
                        LOGGER,
                        f"{where} sets {joined(named)}, which a "
                        "need type gives only a link type declared on need types alone; "
                        f"{name!r} keeps its own on every need type and the "
                        f"{'key is' if len(shape_keys) == 1 else 'keys are'} ignored",
                        "config",
                        None,
                    )
                if (
                    table == "links"
                    and name in local
                    and keys.get("copy") is True
                    and not glob.derived
                ):
                    # the shape a declaration of a link type need types alone give:
                    # on a derived one, copy is refused at its rule
                    log_warning(
                        LOGGER,
                        _copy_deprecation(where, name, schema),
                        "deprecated",
                        None,
                    )
                # declared, also if the entry cannot be used: the type keeps the
                # declaration before it
                names[need_type].add(name)
                previous, by = own.get(name, (glob, None))
                if (
                    table == "links"
                    and name == "links"
                    and copying
                    and "target_types" in keys
                ):
                    log_warning(LOGGER, _copy_refusal(where, copying), "config", None)
                    keys = {k: v for k, v in keys.items() if k != "target_types"}
                if (
                    field := _declare_for_type(
                        previous,
                        glob,
                        keys,
                        where,
                        by,
                        local=name in local,
                        need_type=need_type,
                        type_tree=type_tree,
                        severity_by=severity_own.get(name),
                    )
                ) is not None:
                    own[name] = (field, need_type)
                    if "severity" in keys:
                        severity_own[name] = need_type
        declared[need_type] = own
        back_declared[need_type] = back_own
        severity_by[need_type] = severity_own
        for field, _ in own.values():
            schema.add_type_overlay(need_type, field)
        for back, _ in back_own.values():
            schema.add_back_links(need_type, back)
    for name in local:
        schema._localise(name, [t for t in order if name in names[t]])


def _declare_for_type(
    previous: FieldSchema | LinkSchema,
    glob: FieldSchema | LinkSchema,
    keys: Mapping[str, Any],
    where: str,
    declared_by: str | None,
    *,
    local: bool = False,
    need_type: str = "",
    type_tree: tuple[Mapping[str, frozenset[str]], Mapping[str, str]] = ({}, {}),
    severity_by: str | None = None,
) -> FieldSchema | LinkSchema | None:
    """The declaration a need type's entry makes of a field, from the one before it
    (the global declaration, or an ancestor's); ``None``, reported, if the entry
    cannot be used.

    :param previous: The declaration before the entry.
    :param glob: The field's global declaration.
    :param keys: The entry.
    :param where: The entry, as the configuration names it.
    :param declared_by: The need type whose entry made ``previous``, if not global.
    :param local: Whether the field is declared on need types alone.
    :param need_type: The need type whose entry it is.
    :param type_tree: What a ``target_types`` is read against
        (:func:`_resolve_type_declarations`).
    :param severity_by: The need type whose entry gave ``previous`` its severity, if
        one did: a severity lowered is reported as that type declares it.
    """
    on_link = previous.kind == "link"
    keys = {
        key: value
        for key, value in keys.items()
        # a ``derive`` is the field's rule for the type, folded where it is read
        if key in (NEED_TYPE_LINK_KEYS if on_link else NEED_TYPE_FIELD_KEYS)
        and key != "derive"
    }
    if previous.derived and (
        refused := [k for k in ("default", "predicates", "target_types") if k in keys]
    ):
        # a derived field takes no default: the rules give its value
        log_warning(
            LOGGER,
            f"{where} sets {' and '.join(map(repr, refused))}, but {previous.name!r} is "
            f"derived ({previous.describe_derived()}): a need type declares only its "
            f"{'description, schema and severity' if on_link else 'description, schema, nullable and severity'}"
            "; the entry is ignored",
            "type_conflict",
            None,
        )
        return None
    changes: dict[str, Any] = {
        key: keys[key] for key in ("description", "nullable", "severity") if key in keys
    }
    if "schema" in keys:
        # a declaration names only what it changes: it takes the rest from before
        child = deepcopy(dict(keys["schema"]))
        _inherit_keywords(previous.schema, child)
        if (
            previous.derived
            and previous.type != "array"
            and child.get("enum")
            and not glob.schema.get("enum")
        ):
            # the rules of a derived field are checked against its global declaration
            why = (
                ", and a derived field declared on need types alone takes no 'enum'"
                if local
                else " and its rules are checked against its declaration, which has "
                "none"
            )
            log_warning(
                LOGGER,
                f"{where} adds an 'enum', but {previous.name!r} is derived "
                f"({previous.describe_derived()}){why}; the entry is ignored",
                "type_conflict",
                None,
            )
            return None
        changes["schema"] = child
    if "target_types" in keys:
        below, titles = type_tree
        # names no need type are reported here; none left: as if not given
        if (
            target_types := _read_target_types(
                where, keys["target_types"], below, titles, declared_by=need_type
            )
        ) is not None:
            changes["target_types"] = target_types
    try:
        field = dataclasses.replace(previous, **changes)
    except ValueError as exc:
        log_warning(
            LOGGER,
            f"{where} cannot be declared: {_reason(exc)}; the entry is ignored",
            "type_conflict",
            None,
        )
        return None
    # set on the new declaration, not yet in the schema
    for key, set_value, named in (
        ("default", field._set_default, "a 'default'"),
        ("predicates", field._set_predicate_defaults, "'predicates'"),
    ):
        if key not in keys:
            continue
        try:
            set_value(keys[key], allow_coercion=True)
        except ValueError as exc:
            log_warning(
                LOGGER,
                f"{where} sets {named} that cannot be used: {_reason(exc)}; the entry "
                "is ignored",
                "type_conflict",
                None,
            )
            return None
    if (problems := narrowing_problems(previous, field)) or (
        # as the schema will check it: an ancestor's own literal is not the global
        # declaration's, and the empty value rule 9 lets pass is the global one's
        previous is not glob and (problems := narrowing_problems(glob, field))
    ):
        for reason in problems:
            as_declared = _as_declared(
                severity_by if _is_severity_reason(reason) else declared_by
            )
            if reason.startswith("with "):
                # the field's type or derivation, the same on every need type: a
                # reason of these reads on from the field's name
                log_warning(
                    LOGGER,
                    f"{where} cannot be declared {reason.removesuffix('.')}; the entry "
                    "is ignored",
                    "type_conflict",
                    None,
                )
            else:
                log_warning(
                    LOGGER,
                    f"{where} widens the field{as_declared}: {reason}",
                    "type_widening",
                    None,
                )
        return None
    return field


def _resolve_id_patterns(
    schema: FieldsSchema,
    types: Mapping[str, Mapping[str, Any]],
    order: list[str],
    parent: Mapping[str, str],
) -> None:
    """Register the ``id_regex`` patterns the ids of each need type's needs match:
    its own and those of every type it inherits from, the root's first
    (:meth:`FieldsSchema.set_id_patterns`), each checked where ``needs_id_regex`` is.

    A pattern that does not compile is one ``needs.type_conflict`` warning, and is
    ignored: the type and the types inheriting from it are not checked against it.

    :param schema: The schema, complete but for freezing.
    :param types: Each configured need type's entry.
    :param order: The need types, each after its parent.
    :param parent: The parent of each type that has one.
    """
    patterns: dict[str, tuple[tuple[str, str], ...]] = {}
    for need_type in order:
        own = patterns.get(parent.get(need_type, ""), ())
        pattern = types[need_type].get("id_regex")
        if isinstance(pattern, str):
            try:
                re.compile(pattern)
            except re.error as exc:
                log_warning(
                    LOGGER,
                    f"needs_types[{need_type!r}] has an id_regex {pattern!r} that is "
                    f"not a regular expression ({exc}); the key is ignored",
                    "type_conflict",
                    None,
                )
            else:
                own = (*own, (need_type, pattern))
        patterns[need_type] = own
        if own:
            schema.set_id_patterns(need_type, own)


def _deferred_keys(
    where: str, keys: Mapping[str, Any], *, count: bool
) -> Mapping[str, Any]:
    """A ``links`` entry named ``<x>_back``, whose keys outside
    :data:`NEED_TYPE_BACK_LINK_KEYS` :func:`_normalise_declarations` left unchecked: as
    they are for the count of a link type's back links (``count``), which refuses the
    entry for any of them; else reported and removed as on any other ``links`` entry,
    one ``needs.config`` warning per reason.
    """
    if count:
        return keys
    wrong, text = _not_of_their_shape(where, keys, _NEED_TYPE_LINK_ENTRY_KEYS)
    if wrong:
        log_warning(LOGGER, text, "config", None)
    unknown, text = _unknown(where, keys, _NEED_TYPE_LINK_ENTRY_KEYS)
    if unknown:
        log_warning(LOGGER, text, "config", None)
    if not wrong and not unknown:
        return keys
    return {k: v for k, v in keys.items() if k not in wrong and k not in unknown}


def _declare_back_links(
    previous: BackLinksSchema | None,
    link_type: str,
    keys: Mapping[str, Any],
    where: str,
    declared_by: str | None,
    *,
    severity_by: str | None = None,
) -> BackLinksSchema | None:
    """The declaration a need type's ``links`` entry makes of a link type's back links,
    ``<l>_back``, from the one before it (an ancestor's, or none); ``None``, reported,
    if the entry cannot be used.

    The entry takes only :data:`NEED_TYPE_BACK_LINK_KEYS`, and its ``schema`` only
    ``minItems`` and ``maxItems``, each a non-negative integer: anything else is a
    ``needs.type_conflict``, the entry ignored. The keys it leaves out are kept from
    the declaration before it, which it narrows: a ``minItems`` not lower, a
    ``maxItems`` not higher, a ``severity`` not lower (``needs.type_widening``).

    :param previous: The declaration before the entry, an ancestor's.
    :param link_type: The link type whose back links the entry names.
    :param keys: The entry.
    :param where: The entry, as the configuration names it.
    :param declared_by: The need type whose entry made ``previous``.
    :param severity_by: The need type whose entry gave ``previous`` its severity.
    """
    name = f"{link_type}_back"
    if other := [key for key in keys if key not in NEED_TYPE_BACK_LINK_KEYS]:
        log_warning(
            LOGGER,
            f"{where} sets {joined([repr(key) for key in other])}, but {name!r} is "
            "a link type's back links: a need type declares only their description, "
            "schema (minItems, maxItems) and severity; the entry is ignored",
            "type_conflict",
            None,
        )
        return None
    given = dict(keys.get("schema", {}))
    if other := [key for key in given if key not in BACK_LINKS_KEYWORDS]:
        log_warning(
            LOGGER,
            f"{where} gives the schema {joined([repr(key) for key in other])}, but "
            f"{name!r} is a link type's back links: their schema takes only "
            "'minItems' and 'maxItems'; the entry is ignored",
            "type_conflict",
            None,
        )
        return None
    before: Mapping[str, Any] = {} if previous is None else previous.schema
    try:
        back = BackLinksSchema(
            name=name,
            link_type=link_type,
            description=keys.get(
                "description", "" if previous is None else previous.description
            ),
            schema={**before, **given},
            severity=keys.get(
                "severity", None if previous is None else previous.severity
            ),
        )
    except ValueError as exc:
        log_warning(
            LOGGER,
            f"{where} cannot be declared: {_reason(exc)}; the entry is ignored",
            "type_conflict",
            None,
        )
        return None
    if previous is not None and (
        problems := [
            *schema_narrowing_problems(
                previous.json_schema(), back.json_schema(), dropped_is_widening=False
            ),
            *severity_problems(previous.severity, back.severity),
        ]
    ):
        for reason in problems:
            as_declared = _as_declared(
                severity_by if _is_severity_reason(reason) else declared_by
            )
            log_warning(
                LOGGER,
                f"{where} widens the field{as_declared}: {reason}",
                "type_widening",
                None,
            )
        return None
    return back


def _as_declared(need_type: str | None) -> str:
    """Where a widened declaration comes from, as a ``type_widening`` finding says it."""
    return "" if need_type is None else f" as need type {need_type!r} declares it"


def _is_severity_reason(reason: str) -> bool:
    """Whether a narrowing problem is about the ``severity`` (rule 12 of
    :func:`~sphinx_needs.needs_schema.narrowing_problems`), whose source is the type
    that gave it, not the nearest declaring type."""
    return "parent 'severity'" in reason


def _reason(exc: Exception) -> str:
    """The first line of an error's message, without its full stop."""
    return str(exc).splitlines()[0].rstrip(".")


class _DefaultsDictType(TypedDict, total=False):
    predicates: list[tuple[str, Any]]
    default: Any


def _declared_defaults(
    needs_config: NeedsSphinxConfig,
    registered: Mapping[str, NewFieldParams],
    links: Mapping[str, tuple[Mapping[str, Any], str]],
    name: str,
) -> tuple[str, dict[str, Any]]:
    """The configuration value declaring a field or link type, and the ``default``
    and ``predicates`` its entry sets.

    The entry is a link type's ``needs_links`` or ``needs_extra_links`` entry
    (:issue:`2317`), or a field's ``needs_fields`` entry when that is the field's
    declaration (a core field's entry, or the one the field is registered from)
    (:issue:`2264`). A key counts when it is given, not ``None``: a field or link type
    declared without it takes the ``needs_global_options`` value, as before. A link
    type need types alone declare has no such entry: their own declarations are
    resolved afterwards, and win over both.
    """
    if (link := links.get(name)) is not None:
        entry, declared_in = link
        # a fence: a link type need types alone declare carries no default or
        # predicates today, and its own declarations win over both anyway
        if declared_in not in {"needs_links", "needs_extra_links"}:
            return declared_in, {}
    else:
        entry, declared_in = needs_config._fields.get(name), "needs_fields"
        if not isinstance(entry, dict) or (
            name not in NeedsCoreFields
            and (
                (params := registered.get(name)) is None
                or params.source != "needs_fields"
            )
        ):
            return declared_in, {}
    return declared_in, {
        key: entry[key]
        for key in ("default", "predicates")
        if entry.get(key) is not None
    }


def _set_global_default(
    schema: FieldsSchema,
    config_name: str,
    name: str,
    values: _DefaultsDictType,
    *,
    allow_coercion: bool,
    declared: tuple[str, Mapping[str, Any]] | None = None,
) -> None:
    """Set a field's or link type's ``needs_global_options`` default and predicates.

    :param declared: The configuration value declaring the field or link type, and
        the ``default`` and ``predicates`` its entry sets (:func:`_declared_defaults`):
        those win, and a key set in both is ignored here and reported, in one warning
        for the field or link type (:issue:`2264`, :issue:`2317`). ``None`` is none.
    """
    declared_in, keys = declared if declared is not None else ("", {})
    if not isinstance(values, dict):
        log_warning(
            LOGGER,
            f"{config_name}[{name!r}] value is not a dict",
            "config",
            None,
        )
        return
    if "default" not in values and "predicates" not in values:
        return

    # the global declaration: the schema is still built, no need reads it yet
    if (field_for_default := schema.global_declaration(name)) is None:
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
    # a key the declaring entry sets too is the entry's: this one is ignored, and
    # reported
    set_default = "default" in values and "default" not in keys
    set_predicates = "predicates" in values and "predicates" not in keys
    if both := [
        key for key in ("default", "predicates") if key in values and key in keys
    ]:
        verb = "is" if len(both) == 1 else "are"
        ignored = " and ".join(
            f"{config_name}[{name!r}][{key!r}] ({values.get(key)!r})" for key in both
        )
        used = " and ".join(
            f"{declared_in}[{name!r}][{key!r}] ({keys[key]!r})" for key in both
        )
        log_warning(
            LOGGER,
            f"{ignored} {verb} ignored: {used} "
            + ("takes precedence" if len(both) == 1 else "take precedence"),
            "config",
            None,
        )
        if not (set_default or set_predicates):
            return
    # the defaults are set on a copy, not yet in the schema, which then replaces the
    # field: a field in the schema is not changed in place (FieldsSchema.freeze)
    field = dataclasses.replace(field_for_default)
    if set_default:
        _set_default_on_field(field, values["default"], config_name, allow_coercion)
    if set_predicates:
        _set_predicates_on_field(
            field, values["predicates"], config_name, allow_coercion
        )
    schema.replace_field(field)


def _set_default_on_field(
    field: FieldSchema | LinkSchema, value: Any, config_name: str, allow_coercion: bool
) -> None:
    """Set default value on field, with errors turned into warnings."""
    try:
        field._set_default(value, allow_coercion=allow_coercion)
    except Exception as exc:
        log_warning(
            LOGGER,
            f"{config_name}[{field.name!r}]['default'] value is incorrect: {exc}",
            "config",
            None,
        )


def _set_predicates_on_field(
    field: FieldSchema | LinkSchema,
    predicates: list[tuple[str, Any]],
    config_name: str,
    allow_coercion: bool,
) -> None:
    """Set predicate defaults on field, with errors turned into warnings."""
    try:
        field._set_predicate_defaults(predicates, allow_coercion=allow_coercion)
    except Exception as exc:
        log_warning(
            LOGGER,
            f"{config_name}[{field.name!r}]['predicates'] value is incorrect: {exc}",
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
    app.env._needs_warnings_executed = False  # ty: ignore[unresolved-attribute]
