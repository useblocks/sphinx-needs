import os
from sphinx.util.osutil import copyfile
from sphinx.util.osutil import ensuredir
from sphinx.util.console import brown

import sphinx
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import status_iterator  # NOQA Sphinx 1.5

STATICS_DIR_NAME = '_static'


def safe_add_file(filename, app):
    """
    Adds files to builder resources only, if the given filename was not already registered.
    Needed mainly for tests to avoid multiple registration of the same file and therefore also multiple execution
    of e.g. a javascript file during page load.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file = filename
    static_data_file = os.path.join("_static", data_file)

    if data_file.split(".")[-1] == "js":
        if hasattr(app.builder, "script_files") and static_data_file not in app.builder.script_files:
            app.add_javascript(data_file)
    elif data_file.split(".")[-1] == "css":
        if hasattr(app.builder, "css_files") and static_data_file not in app.builder.css_files:
            app.add_stylesheet(data_file)
    else:
        raise NotImplemented("File type {} not support by save_add_file".format(data_file.split(".")[-1]))


def safe_remove_file(filename, app):
    """
    Removes a given resource file from builder resources.
    Needed mostly during test, if multiple sphinx-build are started.
    During these tests js/cass-files are not cleaned, so a css_file from run A is still registered in run B.

    :param filename: filename to remove
    :param app: app object
    :return: None
    """
    data_file = filename
    static_data_file = os.path.join("_static", data_file)

    if data_file.split(".")[-1] == "js":
        if hasattr(app.builder, "script_files") and static_data_file in app.builder.script_files:
            app.builder.script_files.remove(static_data_file)
    elif data_file.split(".")[-1] == "css":
        if hasattr(app.builder, "css_files") and static_data_file in app.builder.css_files:
            app.builder.css_files.remove(static_data_file)


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs')

    files_to_copy = ["common.css", app.config.needs_css]

    # Be sure no "old" css layout is already set
    safe_remove_file("sphinx-needs/common.css", app)
    safe_remove_file("sphinx-needs/blank.css", app)
    safe_remove_file("sphinx-needs/modern.css", app)
    safe_remove_file("sphinx-needs/dark.css", app)

    if parse_version(sphinx_version) < parse_version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
            files_to_copy,
            'Copying static files for sphinx-needs custom style support...',
            brown, len(files_to_copy)):

        if not os.path.isabs(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", source_file_path)

        if not os.path.exists(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", "blank.css")
            print("{0} not found. Copying sphinx-internal blank.css".format(source_file_path))

        dest_file_path = os.path.join(dest_path, os.path.basename(source_file_path))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

        safe_add_file(os.path.relpath(dest_file_path, STATICS_DIR_PATH), app)


def install_datatables_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs/libs/html')

    source_folder = os.path.join(os.path.dirname(__file__), "libs/html")
    files_to_copy = []

    for root, dirs, files in os.walk(source_folder):
        for single_file in files:
            files_to_copy.append(os.path.join(root, single_file))

    if parse_version(sphinx_version) < parse_version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
            files_to_copy,
            'Copying static files for sphinx-needs datatables support...',
            brown, len(files_to_copy)):

        if not os.path.isabs(source_file_path):
            raise IOError("Path must be absolute. Got: {}".format(source_file_path))

        if not os.path.exists(source_file_path):
            raise IOError("File not found: {}".format(source_file_path))

        dest_file_path = os.path.join(dest_path, os.path.relpath(source_file_path, source_folder))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

    # Add the needed datatables js and css file
    safe_add_file("sphinx-needs/libs/html/datatables.min.js", app)
    safe_add_file("sphinx-needs/libs/html/datatables_loader.js", app)
    safe_add_file("sphinx-needs/libs/html/datatables.min.css", app)


def install_collapse_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs')

    source_folder = os.path.join(os.path.dirname(__file__), "libs/html")
    files_to_copy = [os.path.join(source_folder, "sphinx_needs_collapse.js")]

    if parse_version(sphinx_version) < parse_version("1.6"):
        global status_iterator
        status_iterator = app.status_iterator

    for source_file_path in status_iterator(
            files_to_copy,
            'Copying static files for sphinx-needs collapse support...',
            brown, len(files_to_copy)):

        if not os.path.isabs(source_file_path):
            raise IOError("Path must be absolute. Got: {}".format(source_file_path))

        if not os.path.exists(source_file_path):
            raise IOError("File not found: {}".format(source_file_path))

        dest_file_path = os.path.join(dest_path, os.path.relpath(source_file_path, source_folder))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

        safe_remove_file("sphinx-needs/libs/html/sphinx_needs_collapse.js", app)
        safe_add_file("sphinx-needs/libs/html/sphinx_needs_collapse.js", app)
