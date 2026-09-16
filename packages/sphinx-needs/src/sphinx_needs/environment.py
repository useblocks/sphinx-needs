from __future__ import annotations

import inspect
from functools import lru_cache
from pathlib import Path
from typing import Any

from docutils import nodes
from sphinx import version_info as sphinx_version
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.fileutil import copy_asset, copy_asset_file

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.directives.needtable import HAS_INTERACTIVE_TABLE
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import logger

_STATIC_DIR_NAME = "_static"


@lru_cache(maxsize=1)
def _overwrite() -> dict[str, Any]:
    """The keyword that lets sphinx overwrite an asset whose bytes have changed.

    Everything this module copies is the extension's own, under
    ``_static/sphinx-needs/``, and never anything a project wrote -- so when the file on
    disk differs from the file in the package, the package is right.

    Sphinx does not agree by default, and has not agreed the same way for long. Up to 7.4
    ``copy_asset``/``copy_asset_file`` take a private ``__overwrite_warning__`` and copy
    anyway; from 8.1 they take ``force`` and, when the destination exists with different
    bytes, warn ``misc.copy_overwrite`` and **abort the copy**. So on any modern sphinx an
    upgrader's first incremental build keeps the OLD stylesheet on disk -- the widget then
    runs on the fallback colours -- and fails outright under ``-W``.

    Asking the signature rather than the version number means a release that changes the
    spelling again resolves itself, and that the 7.4 floor is passed nothing it does not
    understand.
    """
    if "force" in inspect.signature(copy_asset).parameters:
        return {"force": True}
    return {}


def _add_css_file(app: Sphinx, rel_path: Path) -> None:
    # note this deduplication is already done in Sphinx v7.2.1+
    # https://github.com/sphinx-doc/sphinx/commit/0c22d9c9ff4a0a6b3ce2f0aa6bc591b4525b4163
    rel_str = rel_path.as_posix()
    if sphinx_version < (7, 2) and f"_static/{rel_str}" in getattr(
        app.builder, "css_files", []
    ):
        return
    app.add_css_file(rel_str)


def _add_js_file(app: Sphinx, rel_path: Path, **kwargs: Any) -> None:
    # note this deduplication is already done in Sphinx v7.2.1+
    # https://github.com/sphinx-doc/sphinx/commit/0c22d9c9ff4a0a6b3ce2f0aa6bc591b4525b4163
    rel_str = rel_path.as_posix()
    if sphinx_version < (7, 2) and f"_static/{rel_str}" in getattr(
        app.builder, "script_files", []
    ):
        return
    app.add_js_file(rel_str, **kwargs)


def install_styles_static_files(app: Sphinx, env: BuildEnvironment) -> None:
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name in ["needs", "schema"]:
        return

    logger.info("Copying static style files for sphinx-needs")

    config = NeedsSphinxConfig(app.config)

    statics_dir = Path(builder.outdir) / _STATIC_DIR_NAME
    dest_dir = statics_dir / "sphinx-needs"
    css_root = Path(__file__).parent / "css"

    # Add common css files
    copy_asset(
        str(css_root.joinpath("common")),
        str(dest_dir.joinpath("common_css")),
        lambda path: not path.endswith(".css"),
        **_overwrite(),
    )
    # Sphinx preserves registration order for stylesheets with the same priority.
    # Sort by filename to keep generated HTML and the CSS cascade deterministic.
    common_css_files = sorted(
        dest_dir.joinpath("common_css").glob("*.css"), key=lambda path: path.name
    )
    for common_path in common_css_files:
        _add_css_file(app, common_path.relative_to(statics_dir))

    # Add theme css file
    if config.css in [f.name for f in css_root.joinpath("themes").glob("*.css")]:
        copy_asset_file(
            str(css_root.joinpath("themes", config.css)), str(dest_dir), **_overwrite()
        )
        _add_css_file(app, dest_dir.joinpath(config.css).relative_to(statics_dir))
    elif Path(config.css).is_file():
        copy_asset_file(config.css, str(dest_dir), **_overwrite())
        _add_css_file(
            app, dest_dir.joinpath(Path(config.css).name).relative_to(statics_dir)
        )
    else:
        log_warning(
            logger,
            f"needs_css not an existing file: {config.css}",
            "config",
            None,
        )


def install_lib_static_files(app: Sphinx, env: BuildEnvironment) -> None:
    """
    Copies css and js files from needed js/css libs
    :param app:
    :param env:
    :return:
    """
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name in ["needs", "schema"]:
        return

    logger.info("Copying static files for sphinx-needs")

    statics_dir = Path(builder.outdir) / _STATIC_DIR_NAME
    source_dir = Path(__file__).parent / "libs" / "html"
    destination_dir = statics_dir / "sphinx-needs" / "libs" / "html"

    copy_asset(str(source_dir), str(destination_dir), **_overwrite())

    lib_path = Path("sphinx-needs") / "libs" / "html"
    # the needtable pair is registered per page, in `install_needtable_assets` below.
    # `loading_method="defer"`: this route goes through `Sphinx.add_js_file`, which
    # translates the keyword into the `defer` attribute (passing `defer="defer"` would
    # write the same tag). `install_needtable_assets` below has to spell the attribute out
    # because the builder-level `add_js_file` has no such keyword
    _add_js_file(
        app, lib_path.joinpath("sphinx_needs_collapse.js"), loading_method="defer"
    )


def install_needtable_assets(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, Any],
    doctree: nodes.document | None,
) -> None:
    """Register ``needstable.{js,css}`` on the pages that hold an interactive needtable.

    Closes #462 for the table assets: before this, every page of every project -- and
    that includes ``search.html`` and ``genindex.html``, which have no doctree at all --
    carried the table's script and stylesheet.

    ``handle_page`` resets the builder's asset lists to their build-wide state just
    before it emits ``html-page-context``, so an asset added from here reaches that page
    and no other. It goes through the BUILDER rather than through ``app.add_js_file``
    because the application's route also appends to the extension registry, once per
    page, and a builder re-initialised afterwards would pick every one of them up
    globally -- which is the behaviour this handler exists to remove.
    """
    if doctree is None or not doctree.get(HAS_INTERACTIVE_TABLE):
        return
    # imported here rather than at module level, so that a `needs`- or `schema`-builder
    # run does not pay for Sphinx's HTML writer stack it never uses
    from sphinx.builders.html import StandaloneHTMLBuilder

    builder = app.builder
    if not isinstance(builder, StandaloneHTMLBuilder):
        return  # nothing else emits this event, but nothing else has the two methods
    lib_path = Path("sphinx-needs") / "libs" / "html"
    # `defer="defer"`, not `loading_method="defer"`: only `Sphinx.add_js_file` translates
    # that keyword, and the builder method this handler has to use writes every keyword
    # straight into the tag's attributes
    builder.add_js_file(lib_path.joinpath("needstable.js").as_posix(), defer="defer")
    builder.add_css_file(lib_path.joinpath("needstable.css").as_posix())


def install_permalink_file(app: Sphinx, env: BuildEnvironment) -> None:
    """
    Creates permalink.html in build dir
    :param app:
    :param env:
    :return:
    """
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name in ["needs", "schema"]:
        return

    # load jinja template
    template_path = Path(__file__).parent / "templates" / "permalink.html"
    template_content = template_path.read_text(encoding="utf-8")

    # save file to build dir
    sphinx_config = NeedsSphinxConfig(env.config)
    out_file = Path(builder.outdir) / Path(sphinx_config.permalink_file).name
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(
            render_template_string(
                template_content,
                {
                    "permalink_file": sphinx_config.permalink_file,
                    "needs_file": sphinx_config.permalink_data,
                    **sphinx_config.render_context,
                },
                autoescape=True,
            )
        )
