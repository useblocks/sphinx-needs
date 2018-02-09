import os
import sys
from sphinx.util.osutil import copyfile
from sphinx.util.osutil import ensuredir
from sphinx.util.console import brown

STATICS_DIR_NAME = '_static'


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_styles_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs')

    files_to_copy = [env.app.config.needs_css]

    for source_file_path in app.builder.status_iterator(
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

        if dest_file_path.endswith('.js'):
            app.add_javascript(os.path.relpath(dest_file_path, STATICS_DIR_PATH))
        elif dest_file_path.endswith('.css'):
            app.add_stylesheet(os.path.relpath(dest_file_path, STATICS_DIR_PATH))


def install_datatables_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs/libs/html')

    source_folder = os.path.join(os.path.dirname(__file__), "libs/html")
    files_to_copy = []

    for root, dirs, files in os.walk(source_folder):
        for single_file in files:
            files_to_copy.append(os.path.join(root, single_file))

    for source_file_path in app.builder.status_iterator(
        files_to_copy,
        'Copying static files for sphinx-needs datatables support...',
        brown, len(files_to_copy)):

        if not os.path.isabs(source_file_path):
            raise FileNotFoundError("Path must be absolute. Got: {}".format(source_file_path))

        if not os.path.exists(source_file_path):
            raise FileNotFoundError("File not found: {}".format(source_file_path))

        dest_file_path = os.path.join(dest_path, os.path.relpath(source_file_path, source_folder))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

    # Add the needed datatables js and css file
    app.add_javascript("sphinx-needs/libs/html/datatables.min.js")
    app.add_javascript("sphinx-needs/libs/html/datatables_loader.js")
    app.add_stylesheet("sphinx-needs/libs/html/datatables.min.css")
