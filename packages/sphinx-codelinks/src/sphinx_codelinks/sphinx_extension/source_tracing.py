import contextlib
import tomllib
from collections.abc import Iterator  # only in python 3.11 afterwards
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
from typing import Any, cast

from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig
from sphinx.environment import BuildEnvironment
from sphinx.util import logging
from sphinx.util.fileutil import copy_asset
from sphinx_needs.api import add_field, add_need_type

from sphinx_codelinks.analyse.projects import AnalyseProjects
from sphinx_codelinks.config import (
    DEFAULT_CONFIG_TOML,
    SRC_TRACE_CACHE,
    CodeLinksConfig,
    CodeLinksConfigType,
    CodeLinksProjectConfigType,
    check_configuration,
    file_lineno_href,
    generate_project_configs,
)
from sphinx_codelinks.logger import configure_sphinx
from sphinx_codelinks.sphinx_extension import debug
from sphinx_codelinks.sphinx_extension.directives.src_trace import (
    SourceTracing,
    SourceTracingDirective,
)
from sphinx_codelinks.sphinx_extension.html_wrapper import html_wrapper

logger = logging.getLogger(__name__)


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
    app.connect("config-inited", update_sn_types)
    app.connect("config-inited", check_sphinx_configuration)

    app.connect("env-before-read-docs", prepare_env)
    app.connect("html-collect-pages", generate_code_page)
    app.connect("html-page-context", add_custom_css)
    app.connect("builder-inited", builder_inited)
    app.connect("build-finished", emit_warnings)
    app.connect("build-finished", debug.process_timing)
    return {
        "version": "builtin",
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
    target_htmls = {
        str(Path(file_path).relative_to(app.outdir).with_suffix(""))
        for file_path in file_lineno_href.mappings
    }

    if pagename in target_htmls and templatename == "page.html":
        app.add_css_file("_static/source_tracing/ub_sct.css")


def generate_code_page(
    app: Sphinx,
) -> Iterator[tuple[str, dict[str, str], str]] | None:
    for file, lineno_href in file_lineno_href.mappings.items():
        file_path = Path(file)
        pagename = str((file_path.relative_to(app.outdir)).with_suffix(""))

        html_content = html_wrapper(
            file_path,
            lineno_href=lineno_href,
        )

        context = {
            "title": f"Source Code Tracing: {file_path.name}",
            "body": html_content,
        }

        yield pagename, context, "page.html"

    file_lineno_href.mappings.clear()  # Clear the mappings after generating the pages
    return None


def load_config_from_toml(app: Sphinx, config: _SphinxConfig) -> None:
    """Load the configuration from a TOML file, if defined in conf.py.

    The default ``ubproject.toml`` is shared with other useblocks tools, which
    may use the file without any ``[codelinks]`` configuration. It is therefore
    silently ignored when it does not exist or has no ``[codelinks]`` table,
    whereas a missing explicitly configured file emits a warning.
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
                f"Source tracing configuration file {toml_file} does not exist. Using configuration from conf.py."
            )
        return
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)
        toml_data = toml_data["codelinks"]
        if not isinstance(toml_data, dict):
            raise Exception(f"data must be a dict in {toml_file}")

    except Exception as e:
        if not default_file:
            logger.warning(
                f"Failed to load source tracing configuration from {toml_file}: {e}"
            )
        return

    set_config_to_sphinx(
        src_trace_config=cast(CodeLinksConfigType, toml_data), config=config
    )


def set_config_to_sphinx(
    src_trace_config: CodeLinksConfigType, config: _SphinxConfig
) -> None:
    allowed_keys = CodeLinksConfig.field_names()
    for key, value in src_trace_config.items():
        if key not in allowed_keys:
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


def update_sn_types(app: Sphinx, _config: _SphinxConfig) -> None:
    add_need_type(app, "srctrace", "Src-Trace", "ST_", "#ffffff", "node")


def prepare_env(
    app: Sphinx, env: BuildEnvironment, _docnames: list[str]
) -> None:  # required by Sphinx
    """
    Prepares the sphinx environment to store stc-trace internal data.
    """
    src_trace_sphinx_config = CodeLinksConfig.from_sphinx(app.config)

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


def emit_warnings(
    app: Sphinx,
    _env: BuildEnvironment,
) -> None:
    warnings = AnalyseProjects.load_warnings(Path(app.outdir) / SRC_TRACE_CACHE)
    if not warnings:
        return
    for warning in warnings:
        logger.warning(
            f"{warning.file_path}:{warning.lineno}: {warning.msg}",
            type=warning.type,
            subtype=warning.sub_type,
        )
