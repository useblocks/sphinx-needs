from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from sphinx import version_info as sphinx_version
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.fileutil import copy_asset, copy_asset_file

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import logger

_STATIC_DIR_NAME = "_static"


def _add_css_file(app: Sphinx, rel_path: Path) -> None:
    # note this deduplication is already done in Sphinx v7.2.1+
    # https://github.com/sphinx-doc/sphinx/commit/0c22d9c9ff4a0a6b3ce2f0aa6bc591b4525b4163
    rel_str = rel_path.as_posix()
    if sphinx_version < (7, 2) and f"_static/{rel_str}" in getattr(
        app.builder, "css_files", []
    ):
        return
    app.add_css_file(rel_str)


def _add_js_file(app: Sphinx, rel_path: Path) -> None:
    # note this deduplication is already done in Sphinx v7.2.1+
    # https://github.com/sphinx-doc/sphinx/commit/0c22d9c9ff4a0a6b3ce2f0aa6bc591b4525b4163
    rel_str = rel_path.as_posix()
    if sphinx_version < (7, 2) and f"_static/{rel_str}" in getattr(
        app.builder, "script_files", []
    ):
        return
    app.add_js_file(rel_str)


def install_styles_static_files(app: Sphinx, env: BuildEnvironment) -> None:
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name == "needs":
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
    )
    for common_path in dest_dir.joinpath("common_css").glob("*.css"):
        _add_css_file(app, common_path.relative_to(statics_dir))

    # Add theme css file
    if config.css in [f.name for f in css_root.joinpath("themes").glob("*.css")]:
        copy_asset_file(str(css_root.joinpath("themes", config.css)), str(dest_dir))
        _add_css_file(app, dest_dir.joinpath(config.css).relative_to(statics_dir))
    elif Path(config.css).is_file():
        copy_asset_file(config.css, str(dest_dir))
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
    if builder.name == "needs":
        return

    logger.info("Copying static files for sphinx-needs datatables support")

    statics_dir = Path(builder.outdir) / _STATIC_DIR_NAME
    source_dir = Path(__file__).parent / "libs" / "html"
    destination_dir = statics_dir / "sphinx-needs" / "libs" / "html"

    # "Copying static files for sphinx-needs datatables support..."
    copy_asset(str(source_dir), str(destination_dir))

    # Add the needed datatables js and css file
    lib_path = Path("sphinx-needs") / "libs" / "html"
    _add_js_file(app, lib_path.joinpath("datatables.min.js"))
    _add_js_file(app, lib_path.joinpath("datatables_loader.js"))
    _add_css_file(app, lib_path.joinpath("datatables.min.css"))
    _add_js_file(app, lib_path.joinpath("sphinx_needs_collapse.js"))


def install_permalink_file(app: Sphinx, env: BuildEnvironment) -> None:
    """
    Creates permalink.html in build dir
    :param app:
    :param env:
    :return:
    """
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name == "needs":
        return

    # load jinja template
    jinja_env = Environment(
        loader=PackageLoader("sphinx_needs"), autoescape=select_autoescape()
    )
    template = jinja_env.get_template("permalink.html")

    # save file to build dir
    sphinx_config = NeedsSphinxConfig(env.config)
    out_file = Path(builder.outdir) / Path(sphinx_config.permalink_file).name
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(
            template.render(
                permalink_file=sphinx_config.permalink_file,
                needs_file=sphinx_config.permalink_data,
                **sphinx_config.render_context,
            )
        )
