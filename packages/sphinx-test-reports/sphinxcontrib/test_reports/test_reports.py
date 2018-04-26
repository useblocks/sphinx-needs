
import sphinx
# from docutils import nodes
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging


def setup(app):
    log = logging.getLogger(__name__)
    log.info("Setting up sphinx-test-reports extension")

    return {'version': '0.1.0'}  # identifies the version of our extension
