from __future__ import annotations

import contextlib
import dataclasses
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from itertools import chain
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
import sphinx_needs.logging as needs_logging
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
from sphinx_needs.card_layouts import compile_card_layouts
from sphinx_needs.config import (
    _NEEDS_CONFIG,
    LinkOptionsType,
    NeedLinksConfig,
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
from sphinx_needs.derive import (
    CORE_LINK_TYPES,
    DeriveInvalid,
    DeriveProblem,
    DeriveRule,
    beside_message,
    check_derive_rules,
    copy_problem,
    core_message,
    invalid_message,
    parse_derive,
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
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
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
from sphinx_needs.roles.variant import VariantRole
from sphinx_needs.schema.config import (
    FieldIntegerSchemaType,
    SchemasFileRootType,
)
from sphinx_needs.schema.config_utils import (
    resolve_schemas_config,
    validate_schemas_config,
)
from sphinx_needs.schema.process import process_schemas
from sphinx_needs.services.github import GithubService
from sphinx_needs.string_links import compile_string_links
from sphinx_needs.utils import node_match
from sphinx_needs.variant_data import VariantDataProxy
from sphinx_needs.warnings import process_warnings
from ub_project import (
    VARIANT_DATA_LOCATION,
    VARIANTS_UNKNOWN_KEY,
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
    app.connect("config-inited", load_config)
    app.connect("config-inited", merge_default_configs)
    # runs after the built-in layouts are merged in, and before the config is checked
    app.connect("config-inited", compile_card_layouts, priority=550)
    app.connect("config-inited", compile_string_links, priority=551)
    app.connect("config-inited", check_configuration, priority=600)  # runs late

    app.connect("env-before-read-docs", prepare_env)
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
        config, toml_doc, toml_file, tuple(toml_path), overridden_keys
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


def _without_key(
    doc: dict[str, object], path: tuple[str, ...], key: str
) -> dict[str, object]:
    """*doc* without *key* in the table at *path*, which is copied along the path only.

    *doc* is returned itself when there is nothing to remove, so the parsed document is
    never modified.
    """
    if not path:
        return {k: v for k, v in doc.items() if k != key} if key in doc else doc
    child = doc.get(path[0])
    if not isinstance(child, dict):
        return doc
    new_child = _without_key(child, path[1:], key)
    return doc if new_child is child else {**doc, path[0]: new_child}


def _load_variants_from_toml(
    config: Config,
    toml_doc: dict[str, object],
    toml_file: Path,
    prefix: tuple[str, ...],
    overridden_keys: set[str],
) -> None:
    """Read the variant data of the ``needs_from_toml`` file, through ``ub_project``.

    ``[<prefix>.variants]`` is the current location and ``[<prefix>.needs]
    variant_data*`` the legacy one; ``ub_project`` decides which one is read, WHOLE, and
    reports the other's keys. What stays here is sphinx-needs' policy:

    - a key overridden with ``-D`` is removed from both locations before the read, so it
      neither opens a file nor decides the location, just as a ``-D`` overrides any
      other ``[needs]`` key one at a time;
    - each declared key of the location read is written to its confval, as the
      ``[needs]`` loop wrote it, and the merge with ``conf.py`` values and the file load
      stay with :func:`resolve_variant_data_config`, which therefore reads the data file
      a second time. Writing the merged map instead would override a ``conf.py`` value
      for a key the TOML does not set, which must fill that gap;
    - the findings are reported as warnings, except the legacy location, which is
      reported with ``-v`` only for now.

    :raises NeedsConfigException: If ``ub_project`` refuses the variant data, or a table
        path with an empty ``needs_from_toml_table`` entry.
    """
    needs_table = (*prefix, "needs")
    variants_table = (*prefix, "variants")
    doc = toml_doc
    for key, legacy_key in zip(_VARIANT_KEYS, _LEGACY_VARIANT_KEYS, strict=True):
        if legacy_key in overridden_keys or f"needs_{legacy_key}" in overridden_keys:
            doc = _without_key(doc, variants_table, key)
            doc = _without_key(doc, needs_table, legacy_key)

    try:
        result = read_variants(
            doc, toml_file, needs_table=needs_table, variants_table=variants_table
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
        table, keys = select_table(doc, variants_table), _VARIANT_KEYS
    else:
        table, keys = select_table(doc, needs_table), _LEGACY_VARIANT_KEYS
    assert table is not None, "a location that was read is a table"
    inline_key, file_key = keys
    if (inline := table.get(inline_key)) is not None:
        config["needs_variant_data"] = inline
    if (file_value := table.get(file_key)) is not None:
        # today's converter (``_abs_path``), so the confval's string is what the [needs]
        # loop wrote; ``result.data_file`` is joined, not resolved
        config["needs_variant_data_file"] = NeedsSphinxConfig.convert_field_value(
            "variant_data_file", file_value, toml_file.parent
        )


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
            derive = option.get("derive")
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
        if option_name in NeedsCoreFields or option_name in CORE_LINK_TYPES:
            # a core field's entry specializes it (create_schema), and a core link
            # type is not a field (reported there)
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

    load_schemas_config_from_json(app, app.config)


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

    # Register embedded services
    services = data.get_or_create_services()
    services.register("github-issues", GithubService, gh_type="issue")
    services.register("github-prs", GithubService, gh_type="pr")
    services.register("github-commits", GithubService, gh_type="commit")

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
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build  # ty: ignore[invalid-assignment]
        debug.EXECUTE_TIME_MEASUREMENTS = True  # ty: ignore[invalid-assignment]

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
    fields = _NEEDS_CONFIG.fields
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
        if link + "_back" in fields:
            raise NeedsConfigException(
                "Same name for automatically created link and field: {}."
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


def create_schema(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:
    needs_config = NeedsSphinxConfig(app.config)
    schema = FieldsSchema()
    #: the ``derive`` findings, reported once the schema is complete
    derive_problems: list[DeriveProblem] = []
    for name, params in needs_config._fields.items():
        if not isinstance(params, dict) or (
            name not in NeedsCoreFields and name not in CORE_LINK_TYPES
        ):
            continue
        if params.get("derive") is not None:
            # a core field is not derived: the rule is reported and ignored
            derive_problems.append(
                DeriveProblem(name, False, core_message(name, on_link=False), core=True)
            )
        elif name in CORE_LINK_TYPES:
            log_warning(
                LOGGER,
                f"needs_fields entry {name!r} names the core link type {name!r}, "
                "which is not a field; the entry is ignored",
                "config",
                None,
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

    for name, field_data in _NEEDS_CONFIG.fields.items():
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
            ):
                log_warning(
                    LOGGER,
                    f"Field {name!r} (from {field_data.source}) has no 'schema', 'nullable' or 'default' defined, "
                    "which defaults to a string schema with nullable=True and no default. "
                    "To aide with backward compatibility please define at least one.",
                    "config",
                    None,
                )

            _schema = (
                deepcopy(field_data.schema)
                if field_data.schema is not None
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
            # a derived field is computed: an author cannot set it, nor a needextend,
            # and it takes no default
            authored = derive is None
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
            schema.add_extra_field(field)
        except Exception as exc:
            raise NeedsConfigException(f"Invalid field {name!r}: {exc}") from exc

    # Get set of link names from needs_links (new config) vs needs_extra_links (deprecated)
    links: dict[str, tuple[LinkOptionsType | NeedLinksConfig, str]] = {
        k: (v, "needs_links") for k, v in needs_config._links.items()
    } | {
        link["option"]: (link, "needs_extra_links")
        for link in needs_config._extra_links
    }

    for name, (link, config_source) in links.items():
        try:
            # create link schema, with defaults if not defined
            _schema = (
                deepcopy(link["schema"])
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
            if (raw_derive := link.get("derive")) is not None:
                if name in CORE_LINK_TYPES:
                    # a core link type is not derived: the rule is reported and ignored
                    derive_problems.append(
                        DeriveProblem(
                            name, True, core_message(name, on_link=True), core=True
                        )
                    )
                else:
                    derive = parse_derive(raw_derive, on_link=True)
            authored = derive is None
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
                allow_dead_links=link.get("allow_dead_links", False),
                derive=derive,
            )
            if derive is not None:
                derive_problems.extend(
                    _derive_parse_problems(
                        name,
                        True,
                        derive,
                        beside=[
                            key for key in ("default", "predicates") if key in link
                        ],
                    )
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
                f"needs_global_options {name!r} value contains unknown keys: {unknown}",
                "config",
                None,
            )
        _set_global_default(
            schema, "needs_global_options", name, default_config, allow_coercion=True
        )

    _report_derive_problems(schema, derive_problems)

    SphinxNeedsData(env)._set_schema(schema)


def _derive_parse_problems(
    name: str, on_link: bool, derive: DeriveRule | DeriveInvalid, *, beside: list[str]
) -> list[DeriveProblem]:
    """The finding of a rule as read: it cannot be read, or a default is beside it.

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
    if beside:
        return [
            DeriveProblem(
                name,
                on_link,
                beside_message(name, on_link=on_link, rule=derive, keys=beside),
            )
        ]
    return []


def _report_derive_problems(
    schema: FieldsSchema, read_problems: list[DeriveProblem]
) -> None:
    """Check the rules against the complete schema, and report every finding.

    A rule that cannot be read is replaced by its :class:`DeriveInvalid` marker (the
    field, or link type, is replaced by a copy carrying it), so the field stays derived
    (closed to authors and needextend) and holds its empty value.
    One ``needs.derive_invalid`` warning per rule (a rule that cannot be read is
    reported for that alone, not for a default beside it, or a link type copying into
    a derived ``links``), in a fixed order: the core fields, then the fields, then the
    link types, each by name.
    """
    checked = {(p.on_link, p.name): p for p in check_derive_rules(schema)}
    for (on_link, name), problem in checked.items():
        target = (
            schema.get_link_field(name) if on_link else schema.get_extra_field(name)
        )
        assert target is not None, "a checked rule is on a field of the schema"
        schema.replace_field(
            dataclasses.replace(
                target,
                derive=DeriveInvalid(
                    getattr(target.derive, "kind", None), problem.reason
                ),
            )
        )
    core = sorted((p for p in read_problems if p.core), key=lambda p: p.name)
    findings = {(p.on_link, p.name): p for p in read_problems if not p.core}
    findings.update(checked)
    if (True, "links") not in findings and (copied := copy_problem(schema)) is not None:
        findings[(True, "links")] = copied
    for problem in [*core, *(findings[key] for key in sorted(findings))]:
        log_warning(LOGGER, problem.message, "derive_invalid", None)


class _DefaultsDictType(TypedDict, total=False):
    predicates: list[tuple[str, Any]]
    default: Any


def _set_global_default(
    schema: FieldsSchema,
    config_name: str,
    name: str,
    values: _DefaultsDictType,
    *,
    allow_coercion: bool,
) -> None:
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
        _set_default_on_field(
            field_for_default, values["default"], config_name, allow_coercion
        )
    if "predicates" in values:
        _set_predicates_on_field(
            field_for_default, values["predicates"], config_name, allow_coercion
        )


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
