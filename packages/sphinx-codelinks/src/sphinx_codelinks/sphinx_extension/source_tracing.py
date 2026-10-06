import contextlib
import os
import shutil
from collections.abc import Iterator  # only in python 3.11 afterwards
from pathlib import Path, PurePosixPath
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, cast

from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.config import Config as _SphinxConfig
from sphinx.environment import BuildEnvironment
from sphinx.util import logging
from sphinx.util.fileutil import copy_asset

from sphinx_codelinks.config import (
    DEFAULT_CONFIG_TOML,
    CodeLinksConfig,
    CodeLinksConfigType,
    CodeLinksProjectConfigType,
    check_configuration,
    generate_project_configs,
    load_codelinks_table,
    need_id_refs_fields,
    remote_url_pattern_warnings,
)
from sphinx_codelinks.logger import configure_sphinx
from sphinx_codelinks.sphinx_extension import debug
from sphinx_codelinks.sphinx_extension.directives.src_trace import (
    SourceTracing,
    SourceTracingDirective,
)
from sphinx_codelinks.sphinx_extension.html_wrapper import html_wrapper
from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_codelinks.sphinx_extension.project_analysis import (
    SourcePage,
    git_root_warnings,
)
from sphinx_codelinks.sphinx_extension.rediscovery import (
    attach_on_post_processing,
    config_only_refs_store,
    effective_pages,
    find_affected_documents,
    find_outdated_scopes,
    merge_info,
    note_documents_to_read,
    purge_doc,
    purged_documents,
    purged_targets,
    scope_store,
    source_pages_store,
)
from sphinx_codelinks.sphinx_extension.string_links import register_string_links
from sphinx_needs.api import add_field, add_need_type
from ub_project import ProjectConfigError

logger = logging.getLogger(__name__)

#: The ``[codelinks]`` keys a ``-D`` never suppresses. Sphinx refuses a ``-D`` for
#: these two -- ``projects`` is a dict, ``outdir`` has a ``Path`` default ("unsupported
#: type") -- yet keeps the key in ``config.overrides``, so skipping the TOML value would
#: honour an override that was never applied.
NOT_OVERRIDABLE_FROM_D = ("projects", "outdir")


def _register_sn_field(name: str, description: str) -> None:
    """Register a typed string field with sphinx-needs.

    A typed field defaults to ``None`` and is stripped before schema validation,
    whereas an untyped registration (``add_extra_option`` with no ``schema``)
    defaults to ``""`` and would trip a strict ``unevaluatedProperties: false``
    schema on needs that never set it.
    """
    add_field(name, description, schema={"type": "string"})


def _check_sphinx_needs_dependency(app: Sphinx) -> bool:
    """Check if sphinx-needs is actually loaded as an extension."""
    # Check if sphinx-needs is in the loaded extensions
    if "sphinx_needs" not in app.extensions:
        error_msg = (
            "sphinx-codelinks requires sphinx-needs to be loaded as an extension.\n"
            "Please ensure 'sphinx_needs' is properly installed and added to your extensions list in conf.py:\n"
            "   extensions = ['sphinx_needs', 'sphinx_codelinks', ...]\n"
            f"Currently loaded extensions: {list(app.extensions.keys())}\n"
            f"Configured extensions: {app.config.extensions}"
        )
        logger.error(error_msg)
        return False
    return True


def setup(app: Sphinx) -> dict[str, Any]:
    # Route the shared analyse layer's logging through Sphinx (verbosity,
    # colour, suppress_warnings, warning stream) instead of stderr.
    configure_sphinx()
    # Check if sphinx-needs is available and properly configured
    if not _check_sphinx_needs_dependency(app):
        logger.error(
            "Failed to initialize sphinx-codelinks due to missing sphinx-needs dependency"
        )
        return {
            "version": "builtin",
            "parallel_read_safe": True,
            "parallel_write_safe": True,
        }

    app.add_node(SourceTracing)
    app.add_directive("src-trace", SourceTracingDirective)
    CodeLinksConfig.add_config_values(app)

    app.connect("config-inited", load_config_from_toml, priority=10)
    app.connect(
        "config-inited", update_sn_extra_options, priority=11
    )  # run early otherwise, extra options are not set for nested_parse
    # after the fields are registered, and before Sphinx-Needs compiles the string
    # links (its ``compile_string_links`` listener runs at priority 551)
    app.connect("config-inited", register_string_links, priority=12)
    app.connect("config-inited", update_sn_types)
    app.connect("config-inited", check_sphinx_configuration)

    app.connect("env-before-read-docs", prepare_env)
    # a file added to a src-trace scope re-reads the hosting document (#2040)
    app.connect("env-get-outdated", find_outdated_scopes)
    app.connect("env-purge-doc", purge_doc)
    app.connect("env-merge-info", merge_info)
    # after every read and merge: the projects no directive traces are scanned, and
    # the documents whose needs' references changed are written
    # (early, before an env-updated handler of another extension resolves the needs)
    app.connect("env-updated", find_affected_documents, priority=100)
    # after every need is collected and before needextend is applied: a user's
    # needextend of the references field wins
    app.connect("needs-before-post-processing", attach_on_post_processing)
    app.connect("html-collect-pages", generate_code_page)
    app.connect("html-page-context", add_custom_css)
    app.connect("builder-inited", builder_inited)
    app.connect("build-finished", debug.process_timing)
    return {
        "version": "builtin",
        # the environment holds the source pages since #2070: an older one (no page
        # records) is discarded by Sphinx, so the first build after an upgrade reads
        # every document once and records them
        "env_version": 1,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def builder_inited(app: Sphinx) -> None:
    custom_css = Path(__file__).parent / "ub_sct.css"
    copy_asset(custom_css, Path(app.outdir) / "_static" / "source_tracing")


def add_custom_css(
    app: Sphinx,
    pagename: str,
    templatename: str,
    _context: dict[str, Any],
    _doctree: Any,
) -> None:
    # the key the context of every page generate_code_page yields carries
    if templatename == "page.html" and _context.get(SOURCE_PAGE_KEY):
        app.add_css_file("_static/source_tracing/ub_sct.css")


#: the context key that marks a source page, for :func:`add_custom_css`
SOURCE_PAGE_KEY = "codelinks_source_page"


def _copy_outdated(copied: Path, source: os.stat_result) -> bool:
    """Whether the copy is missing, or its size or modification time differs from its
    source's: a copy carries its source's modification time (set after the copy), so a
    source replaced by an OLDER file is caught too."""
    try:
        current = copied.stat()
    except OSError:
        return True
    return (
        current.st_size != source.st_size or current.st_mtime_ns != source.st_mtime_ns
    )


def _page_outdated(
    outfile: Path,
    page: SourcePage,
    documents: frozenset[str],
    targets: frozenset[str],
) -> bool:
    """Whether a source page whose copy is up to date must be written: its output file
    is missing, or its ``[docs]`` links may have changed with no source edit -- a
    document they name now was purged in this build (read again, or added: a need that
    moved to it), or a purged document had recorded the page (removed, or no longer
    tracing the file)."""
    if not outfile.is_file():
        return True
    if any(docname in documents for _line, docname, _need_id in page.anchors):
        return True
    return page.target in targets


def _pagename(target: str) -> str:
    """The page of a source copy: its path without the suffix (``src/refs``)."""
    return PurePosixPath(target).with_suffix("").as_posix()


def generate_code_page(app: Sphinx) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Copy every recorded source file into the output and yield its page, where they
    are not up to date (``html-collect-pages``, so for HTML builders only).

    The pages come from the environment (:func:`~.rediscovery.effective_pages`), so a
    cleaned output directory, a second builder sharing the doctrees, or a document read
    by a ``-j N`` worker gets them as a serial first build does. A copy is written when
    it is missing or its size or modification time differs from its source's; a page
    when its copy was written, its output file is missing, or a document it was
    recorded by -- now or before -- was purged in this build (read again, added or
    removed). Each ``[docs]`` link is the builder's own relative URI from the page to
    the need's document. A source that cannot be read any more (removed since its
    document was read) warns and is skipped.
    """
    builder = app.builder
    if not isinstance(builder, StandaloneHTMLBuilder):  # the event is theirs alone
        return
    config = CodeLinksConfig.from_sphinx(app.config)
    outdir = Path(app.outdir)
    documents = purged_documents(app.env)
    targets = purged_targets(app.env)
    for page in effective_pages(app.env, config):
        copied = outdir / page.target
        try:
            source = os.stat(page.source)
            copy = _copy_outdated(copied, source)
            if copy:
                copied.parent.mkdir(parents=True, exist_ok=True)
                # as bytes (no codec, no newline translation); then the source's times,
                # not its mode -- a read-only source would make the copy unwritable
                shutil.copyfile(page.source, copied)
                os.utime(copied, ns=(source.st_atime_ns, source.st_mtime_ns))
        except OSError as error:
            logger.warning(
                f"source page {page.target!r} not written: cannot copy "
                f"{Path(page.source).as_posix()}: {error.strerror or error}",
                type="codelinks",
                subtype="source_page",
            )
            continue
        pagename = _pagename(page.target)
        outfile = Path(builder.get_outfilename(pagename))
        if not copy and not _page_outdated(outfile, page, documents, targets):
            continue
        lineno_href = {
            line: f"{builder.get_relative_uri(pagename, docname)}#{need_id}"
            for line, docname, need_id in page.anchors
        }
        context = {
            "title": f"Source Code Tracing: {copied.name}",
            "body": html_wrapper(copied, lineno_href=lineno_href),
            SOURCE_PAGE_KEY: True,
        }
        yield pagename, context, "page.html"


def load_config_from_toml(app: Sphinx, config: _SphinxConfig) -> None:
    """Load the configuration from a TOML file, if defined in conf.py.

    The default ``ubproject.toml`` is shared with other useblocks tools, which
    may use the file without any ``[codelinks]`` configuration. The default is
    the value ``ubproject.toml`` exactly -- left unset, or written in conf.py as
    that string (a string comparison, not a file comparison) -- and is silently
    ignored when it does not exist or has no ``[codelinks]`` table. Any other
    value, ``./ubproject.toml`` included, is an explicit file and warns in both
    cases. A file that exists but cannot be read or parsed warns either way, as
    any configured file did at 1.4.0: it is broken for every tool that reads it.

    Every warning here is ``codelinks.config``, so ``suppress_warnings`` can
    silence them.
    """
    src_trc_sphinx_config = CodeLinksConfig.from_sphinx(config)
    if src_trc_sphinx_config.config_from_toml is None:
        return

    default_file = src_trc_sphinx_config.config_from_toml == DEFAULT_CONFIG_TOML

    # resolve relative to confdir
    toml_file = Path(app.confdir, src_trc_sphinx_config.config_from_toml).resolve()
    # toml_path = src_trc_sphinx_config.from_toml_table

    if not toml_file.exists():
        if not default_file:
            logger.warning(
                f"Source tracing configuration file {toml_file} does not exist. Using configuration from conf.py.",
                type="codelinks",
                subtype="config",
            )
        return
    try:
        toml_data = load_codelinks_table(toml_file)
    except ProjectConfigError as error:
        # ub-project's message names the file itself
        logger.warning(
            f"Failed to load source tracing configuration: {error}",
            type="codelinks",
            subtype="config",
        )
        return
    except Exception as error:
        # the TOML parser can also fail with a RecursionError, which ``load_toml`` does
        # not wrap and whose text names no file. Either way the file only warns -- the
        # default one too.
        logger.warning(
            f"Failed to load source tracing configuration from {toml_file}: {error}",
            type="codelinks",
            subtype="config",
        )
        return
    if toml_data is None:
        if not default_file:
            logger.warning(
                f"Source tracing configuration file {toml_file} has no [codelinks] table. Using configuration from conf.py.",
                type="codelinks",
                subtype="config",
            )
        return

    set_config_to_sphinx(
        src_trace_config=cast(CodeLinksConfigType, toml_data), config=config
    )


def set_config_to_sphinx(
    src_trace_config: CodeLinksConfigType, config: _SphinxConfig
) -> None:
    allowed_keys = CodeLinksConfig.field_names()
    # A value given on the command line (``-D src_trace_<key>=...``, which Sphinx
    # keeps in ``config.overrides``) wins over the TOML. Only the full confval
    # name counts: a bare ``-D set_local_url=0`` names no confval, Sphinx ignores
    # it, and the TOML value has to stand.
    overridden: set[str] = set()
    config_overrides = getattr(config, "overrides", None)
    if isinstance(config_overrides, dict):
        overridden = {str(key) for key in config_overrides}
    for key, value in src_trace_config.items():
        if key not in allowed_keys:
            continue
        if key not in NOT_OVERRIDABLE_FROM_D and f"src_trace_{key}" in overridden:
            continue
        if key == "projects":
            src_trace_projects: dict[str, CodeLinksProjectConfigType] = cast(
                dict[str, CodeLinksProjectConfigType], value
            )
            generate_project_configs(src_trace_projects)
        config[f"src_trace_{key}"] = value


def update_sn_extra_options(_app: Sphinx, config: _SphinxConfig) -> None:
    src_trace_sphinx_config = CodeLinksConfig.from_sphinx(config)
    _register_sn_field("project", "Source-tracing project")
    _register_sn_field("file", "Source file")
    _register_sn_field("directory", "Source directory")
    if src_trace_sphinx_config.set_local_url:
        _register_sn_field(src_trace_sphinx_config.local_url_field, "Local source URL")
    if src_trace_sphinx_config.set_remote_url:
        _register_sn_field(
            src_trace_sphinx_config.remote_url_field, "Remote source URL"
        )
    # One list-valued field per distinct ``ref_url_field``, shared by the projects naming
    # it. ``nullable`` with no default, so a need no reference names carries ``None``,
    # which is stripped before schema validation: a strict ``unevaluatedProperties:
    # false`` schema never sees the field on it (a ``[]`` default would not be stripped).
    user_fields = _user_declared_fields(config)
    for field_name in sorted(
        set(need_id_refs_fields(src_trace_sphinx_config).values())
    ):
        if field_name in user_fields:
            logger.warning(
                f"codelinks registers {field_name!r} for @need-ids references; remove "
                "the needs_fields declaration of it, or set ref_url_field",
                type="codelinks",
                subtype="config",
            )
        add_field(
            field_name,
            "Code references (@need-ids markers)",
            schema={"type": "array", "items": {"type": "string"}},
            nullable=True,
            default=None,
        )


def _user_declared_fields(config: _SphinxConfig) -> set[str]:
    """The field names a user declares in ``needs_fields`` / ``needs_extra_options``."""
    names: set[str] = set()
    needs_fields = getattr(config, "needs_fields", None)
    if isinstance(needs_fields, dict):
        names.update(str(name) for name in needs_fields)
    extra_options = getattr(config, "needs_extra_options", None)
    if isinstance(extra_options, list | tuple):
        for option in extra_options:
            if isinstance(option, str):
                names.add(option)
            elif isinstance(option, dict) and isinstance(option.get("name"), str):
                names.add(option["name"])
    return names


def update_sn_types(app: Sphinx, _config: _SphinxConfig) -> None:
    add_need_type(app, "srctrace", "Src-Trace", "ST_", "#ffffff", "node")


def prepare_env(
    app: Sphinx, env: BuildEnvironment, docnames: list[str]
) -> None:  # required by Sphinx
    """
    Prepares the sphinx environment to store stc-trace internal data.
    """
    src_trace_sphinx_config = CodeLinksConfig.from_sphinx(app.config)
    need_id_refs_store(env)
    scope_store(env)
    source_pages_store(env)
    config_only_refs_store(env)
    # a need of a document still to be read is stale: the directives may replace it
    note_documents_to_read(env, docnames)

    # Set time measurement flag
    if src_trace_sphinx_config.debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build  # ty: ignore[invalid-assignment]
        debug.EXECUTE_TIME_MEASUREMENTS = True  # ty: ignore[invalid-assignment]

    if src_trace_sphinx_config.debug_filters:
        with contextlib.suppress(FileNotFoundError):
            Path(str(app.outdir), "debug_filters.jsonl").unlink()


def check_sphinx_configuration(app: Sphinx, _config: _SphinxConfig) -> None:
    config = CodeLinksConfig.from_sphinx(app.config)
    errors = check_configuration(config)
    if errors:
        raise Exception("\n".join(errors))
    for warning in remote_url_pattern_warnings(config):
        logger.warning(warning, type="codelinks", subtype="remote_url_pattern")
    for warning in git_root_warnings(app.confdir, config):
        logger.warning(warning, type="codelinks", subtype="git_root")
