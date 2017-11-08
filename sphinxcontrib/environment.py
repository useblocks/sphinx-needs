import os
import sys
from sphinx.util.osutil import copyfile
from sphinx.util.osutil import ensuredir
from sphinx.util.console import brown

STATICS_DIR_NAME = '_static'


# Base implementation from sphinxcontrib-images
# https://github.com/spinus/sphinxcontrib-images/blob/master/sphinxcontrib/images.py#L203
def install_backend_static_files(app, env):
    STATICS_DIR_PATH = os.path.join(app.builder.outdir, STATICS_DIR_NAME)
    dest_path = os.path.join(STATICS_DIR_PATH, 'sphinx-needs')

    files_to_copy = [env.app.config.needs_css]

    for source_file_path in app.builder.status_iterator(
        files_to_copy,
        'Copying static files for sphinx-needs...',
        brown, len(files_to_copy)):

        if not os.path.isabs(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", source_file_path)

        if not os.path.exists(source_file_path):
            source_file_path = os.path.join(os.path.dirname(__file__), "css", "blank.css")

        dest_file_path = os.path.join(dest_path, os.path.basename(source_file_path))

        if not os.path.exists(os.path.dirname(dest_file_path)):
            ensuredir(os.path.dirname(dest_file_path))

        copyfile(source_file_path, dest_file_path)

        if dest_file_path.endswith('.js'):
            app.add_javascript(os.path.relpath(dest_file_path, STATICS_DIR_PATH))
        elif dest_file_path.endswith('.css'):
            app.add_stylesheet(os.path.relpath(dest_file_path, STATICS_DIR_PATH))
