from pathlib import Path, PurePosixPath
from typing import Iterable, List

from jinja2 import Environment, PackageLoader, select_autoescape
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.display import status_iterator
from sphinx.util.console import brown  # type: ignore[attr-defined]
from sphinx.util.osutil import copyfile

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.utils import logger

IMAGE_DIR_NAME = "_static"


def safe_add_file(filename: Path, app: Sphinx) -> None:
    """
    Adds files to builder resources only, if the given filename was not already
    registered.

    Needed mainly for tests to avoid multiple registration of the same file and
    therefore also multiple execution of e.g. a javascript file during page load.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    # Use PurePosixPath, so that the path can be used as "web"-path
    pure_path = PurePosixPath(filename)

    if pure_path.suffix == ".js":
        # Make sure the calculated (posix)-path is not already registered as "web"-path
        app.add_js_file(str(pure_path))
    elif pure_path.suffix == ".css":
        app.add_css_file(str(pure_path))
    else:
        raise NotImplementedError(f"File type {pure_path.suffix} not support by save_add_file")


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app: Sphinx, env: BuildEnvironment) -> None:
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name == "needs":
        return

    statics_dir = Path(builder.outdir) / IMAGE_DIR_NAME
    css_root = Path(__file__).parent / "css"
    dest_dir = statics_dir / "sphinx-needs"

    def _find_css_files() -> Iterable[Path]:
        needs_css = NeedsSphinxConfig(app.config).css
        for theme in ["modern", "dark", "blank"]:
            if needs_css == f"{theme}.css":
                css_dir = css_root / theme
                return [f for f in css_dir.glob("**/*") if f.is_file()]
        return [Path(needs_css)]

    files_to_copy = [Path("common.css")]
    files_to_copy.extend(_find_css_files())

    for source_file_path in status_iterator(
        files_to_copy,
        "Copying static files for sphinx-needs custom style support...",
        brown,
        length=len(files_to_copy),
        stringify_func=lambda x: x.name,
    ):
        source_file_path = Path(source_file_path)

        if not source_file_path.is_absolute():
            source_file_path = css_root / source_file_path

        if not source_file_path.exists():
            source_file_path = css_root / "blank" / "blank.css"
            logger.warning(f"{source_file_path} not found. Copying sphinx-internal blank.css [needs]", type="needs")

        dest_file = dest_dir / source_file_path.name
        dest_dir.mkdir(exist_ok=True)

        copyfile(str(source_file_path), str(dest_file))

        relative_path = Path(dest_file).relative_to(statics_dir)
        safe_add_file(relative_path, app)


def install_static_files(
    app: Sphinx,
    source_dir: Path,
    destination_dir: Path,
    files_to_copy: List[Path],
    message: str,
) -> None:
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name == "needs":
        return

    for source_file_path in status_iterator(
        files_to_copy,
        message,
        brown,
        length=len(files_to_copy),
        stringify_func=lambda x: Path(x).name,
    ):
        source_file = Path(source_file_path)

        if not source_file.is_absolute():
            raise OSError(f"Path must be absolute. Got: {source_file}")

        if not source_file.exists():
            raise OSError(f"File not found: {source_file}")

        relative_path = source_file.relative_to(source_dir)
        destination_file = destination_dir / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)

        copyfile(str(source_file), str(destination_file))


def install_lib_static_files(app: Sphinx, env: BuildEnvironment) -> None:
    """
    Copies ccs and js files from needed js/css libs
    :param app:
    :param env:
    :return:
    """
    builder = app.builder
    # Do not copy static_files for our "needs" builder
    if builder.name == "needs":
        return

    statics_dir = Path(builder.outdir) / IMAGE_DIR_NAME
    source_dir = Path(__file__).parent / "libs" / "html"
    destination_dir = statics_dir / "sphinx-needs" / "libs" / "html"

    files_to_copy = [f for f in source_dir.glob("**/*") if f.is_file()]

    install_static_files(
        app,
        source_dir,
        destination_dir,
        files_to_copy,
        "Copying static files for sphinx-needs datatables support...",
    )

    # Add the needed datatables js and css file
    lib_path = Path("sphinx-needs") / "libs" / "html"
    for f in ["datatables.min.js", "datatables_loader.js", "datatables.min.css", "sphinx_needs_collapse.js"]:
        safe_add_file(lib_path / f, app)


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
    jinja_env = Environment(loader=PackageLoader("sphinx_needs"), autoescape=select_autoescape())
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
