from collections.abc import Iterator  # only in python 3.11 afterwards
import contextlib
from pathlib import Path
from timeit import default_timer as timer  # Used for timing measurements
import tomllib
from typing import Any, cast

from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig
from sphinx.environment import BuildEnvironment
from sphinx.util import logging
from sphinx.util.fileutil import copy_asset
from sphinx_needs.api import (  # type: ignore[import-untyped]
    add_extra_option,
    add_need_type,
)

from sphinx_codelinks.sphinx_extension import debug
from sphinx_codelinks.sphinx_extension.config import (
    SRC_TRACE_CACHE,
    SrcTraceConfigType,
    SrcTraceProjectConfigType,
    SrcTraceSphinxConfig,
    adpat_src_discovery_config,
    check_configuration,
    file_lineno_href,
)
from sphinx_codelinks.sphinx_extension.directives.src_trace import (
    SourceTracing,
    SourceTracingDirective,
)
from sphinx_codelinks.sphinx_extension.html_wrapper import html_wrapper
from sphinx_codelinks.virtual_docs.config import (
    OneLineCommentStyle,
    OneLineCommentStyleType,
)
from sphinx_codelinks.virtual_docs.virtual_docs import VirtualDocs

logger = logging.getLogger(__name__)


def setup(app: Sphinx) -> dict[str, Any]:  # type: ignore[explicit-any]
    app.add_node(SourceTracing)
    app.add_directive("src-trace", SourceTracingDirective)
    SrcTraceSphinxConfig.add_config_values(app)

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


def add_custom_css(  # type: ignore[explicit-any]
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, Any],
    _doctree: Any,
) -> None:
    target_htmls = {
        str(Path(file_path).relative_to(app.outdir).with_suffix(""))
        for file_path in file_lineno_href.mappings
    }

    if pagename in target_htmls and templatename == "page.html":
        if "css_files" not in context:
            context["css_files"] = []
        context["css_files"].append(
            "_static/source_tracing/ub_sct.css"
        )  # Add the custom CSS file to the context


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
    """Load the configuration from a TOML file, if defined in conf.py."""
    src_trc_sphinx_config = SrcTraceSphinxConfig(config)
    if src_trc_sphinx_config.config_from_toml is None:
        return

    # resolve relative to confdir
    toml_file = Path(app.confdir, src_trc_sphinx_config.config_from_toml).resolve()
    # toml_path = src_trc_sphinx_config.from_toml_table

    if not toml_file.exists():
        logger.warning(
            f"Source tracing configuration file {toml_file} does not exist. Using configuration from conf.py."
        )
        return
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)
        toml_data = toml_data["src_trace"]
        if not isinstance(toml_data, dict):
            raise Exception(f"data must be a dict in {toml_file}")

    except Exception as e:
        logger.warning(
            f"Failed to load source tracing configuration from {toml_file}: {e}"
        )
        return

    set_config_to_sphinx(
        src_trace_config=cast(SrcTraceConfigType, toml_data), config=config
    )


def set_config_to_sphinx(
    src_trace_config: SrcTraceConfigType, config: _SphinxConfig
) -> None:
    allowed_keys = SrcTraceSphinxConfig.field_names()
    for key, value in src_trace_config.items():
        if key not in allowed_keys:
            continue
        if key == "projects":
            for project_config in cast(
                dict[str, SrcTraceProjectConfigType], value
            ).values():
                # address SourceDiscovery related config
                adpat_src_discovery_config(project_config)

                # address OneLoneCommenyStyle config and its default
                oneline_comment_style: OneLineCommentStyleType | None = cast(
                    OneLineCommentStyleType, project_config.get("oneline_comment_style")
                )
                if oneline_comment_style:
                    project_config["oneline_comment_style"] = OneLineCommentStyle(
                        **cast(
                            OneLineCommentStyleType,
                            project_config["oneline_comment_style"],
                        )
                    )
                else:
                    project_config["oneline_comment_style"] = OneLineCommentStyle()

        config[f"src_trace_{key}"] = value


def update_sn_extra_options(app: Sphinx, config: _SphinxConfig) -> None:
    src_trace_sphinx_config = SrcTraceSphinxConfig(config)
    add_extra_option(app, "project")
    add_extra_option(app, "file")
    add_extra_option(app, "directory")
    if src_trace_sphinx_config.set_local_url:
        add_extra_option(app, src_trace_sphinx_config.local_url_field)
    if src_trace_sphinx_config.set_remote_url:
        add_extra_option(app, src_trace_sphinx_config.remote_url_field)


def update_sn_types(app: Sphinx, _config: _SphinxConfig) -> None:
    add_need_type(app, "srctrace", "Src-Trace", "ST_", "#ffffff", "node")


def prepare_env(app: Sphinx, env: BuildEnvironment, _docnames: list[str]) -> None:  # noqa: ARG001  # required by Sphinx
    """
    Prepares the sphinx environment to store stc-trace internal data.
    """
    src_trace_sphinx_config = SrcTraceSphinxConfig(app.config)

    # Set time measurement flag
    if src_trace_sphinx_config.debug_measurement:
        debug.START_TIME = timer()  # Store the rough start time of Sphinx build
        debug.EXECUTE_TIME_MEASUREMENTS = True

    if src_trace_sphinx_config.debug_filters:
        with contextlib.suppress(FileNotFoundError):
            Path(str(app.outdir), "debug_filters.jsonl").unlink()


def check_sphinx_configuration(app: Sphinx, _config: _SphinxConfig) -> None:
    config = SrcTraceSphinxConfig(app.config)
    errors = check_configuration(config)
    if errors:
        raise Exception("\n".join(errors))


def emit_warnings(
    app: Sphinx,
    _env: BuildEnvironment,
) -> None:
    warnings = VirtualDocs.load_warnings(Path(app.outdir) / SRC_TRACE_CACHE)
    if not warnings:
        return
    for warning in warnings:
        logger.warning(
            f"{warning.file_path}:{warning.lineno}: {warning.msg}",
            type=warning.type,
            subtype=warning.sub_type,
        )
