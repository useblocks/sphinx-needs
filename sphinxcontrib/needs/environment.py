from pathlib import Path
from typing import Iterable

import sphinx
from pkg_resources import parse_version
from sphinx.application import Sphinx
from sphinx.util.console import brown
from sphinx.util.osutil import copyfile

from sphinxcontrib.needs.utils import logger

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import status_iterator  # NOQA Sphinx 1.5


IMAGE_DIR_NAME = "_static"


def safe_add_file(filename: Path, app: Sphinx):
    """
    Adds files to builder resources only, if the given filename was not already
    registered.

    Needed mainly for tests to avoid multiple registration of the same file and
    therefore also multiple execution of e.g. a javascript file during page load.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    static_data_file = Path("_static") / filename
    if filename.suffix == ".js":
        if hasattr(app.builder, "script_files") and static_data_file not in app.builder.script_files:
            app.add_js_file(str(filename))
    elif filename.suffix == ".css":
        if hasattr(app.builder, "css_files") and static_data_file not in app.builder.css_files:
            app.add_css_file(str(filename))
    else:
        raise NotImplementedError("File type {} not support by save_add_file".format(filename.suffix))


def safe_remove_file(filename: Path, app: Sphinx):
    """
    Removes a given resource file from builder resources.

    Needed mostly during test, if multiple sphinx-build are started. During these tests
    js/cass-files are not cleaned, so a css_file from run A is still registered in run
    B.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    static_data_file = Path("_static") / filename

    def remove_file(file: Path, attribute: str):
        files = getattr(app.builder, attribute, [])
        if str(file) in files:
            files.remove(str(file))

    attributes = {
        ".js": "script_files",
        ".css": "css_files",
    }

    attribute = attributes.get(filename.suffix)
    if attribute:
        remove_file(static_data_file, attribute)


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app: Sphinx, env):

    # Do not copy static_files for our "needs" builder
    if app.builder.name == "needs":
        return

    statics_dir = Path(app.builder.outdir) / IMAGE_DIR_NAME
    css_root = Path(__file__).parent / "css"
    dest_dir = statics_dir / "sphinx-needs"

    def find_css_files() -> Iterable[Path]:
        for theme in ["modern", "dark", "blank"]:
            if app.config.needs_css == "{}.css".format(theme):
                css_dir = css_root / theme
                return [f for f in css_dir.glob("**/*") if f.is_file()]
        return [app.config.needs_css]

    files_to_copy = [Path("common.css")]
    files_to_copy.extend(find_css_files())

    # Be sure no "old" css layout is already set
    for theme in ["common", "modern", "dark", "blank"]:
        path = Path("sphinx-needs") / "{}.css".format(theme)
        safe_remove_file(path, app)

    if parse_version(sphinx_version) < parse_version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
        files_to_copy,
        "Copying static files for sphinx-needs custom style support...",
        brown,
        len(files_to_copy),
    ):
        source_file_path = Path(source_file_path)

        if not source_file_path.is_absolute():
            source_file_path = css_root / source_file_path

        if not source_file_path.exists():
            source_file_path = css_root / "blank" / "blank.css"
            logger.warning("{0} not found. Copying sphinx-internal blank.css".format(source_file_path))

        dest_file = dest_dir / source_file_path.name
        dest_dir.mkdir(exist_ok=True)

        copyfile(str(source_file_path), str(dest_file))

        relative_path = Path(dest_file).relative_to(statics_dir)
        safe_add_file(relative_path, app)


def install_static_files(
    app: Sphinx,
    source_dir: Path,
    destination_dir: Path,
    files_to_copy: Iterable[Path],
    message: str,
):
    # Do not copy static_files for our "needs" builder
    if app.builder.name == "needs":
        return

    if parse_version(sphinx_version) < parse_version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
        files_to_copy,
        message,
        brown,
    ):
        source_file = Path(source_file_path)

        if not source_file.is_absolute():
            raise IOError("Path must be absolute. Got: {}".format(source_file))

        if not source_file.exists():
            raise IOError("File not found: {}".format(source_file))

        relative_path = source_file.relative_to(source_dir)
        destination_file = destination_dir / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)

        copyfile(str(source_file), str(destination_file))


def install_lib_static_files(app: Sphinx, env):
    """
    Copies ccs and js files from needed js/css libs
    :param app:
    :param env:
    :return:
    """
    # Do not copy static_files for our "needs" builder
    if app.builder.name == "needs":
        return

    statics_dir = Path(app.builder.outdir) / IMAGE_DIR_NAME
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
