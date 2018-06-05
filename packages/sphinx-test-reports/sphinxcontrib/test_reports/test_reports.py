
import sphinx
# from docutils import nodes
from pkg_resources import parse_version

from sphinxcontrib.test_reports.directives.test_results import TestResults, TestResultsDirective
from sphinxcontrib.test_reports.environment import install_styles_static_files

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging


def setup(app):
    """
    Setup following directives:
    * test_results
    * test_env
    * test_report
    """
    log = logging.getLogger(__name__)
    log.info("Setting up sphinx-test-reports extension")

    app.add_config_value('test_reports_rootdir', app.confdir, 'html')

    app.add_node(TestResults)

    app.add_directive('test-results', TestResultsDirective)

    # events
    app.connect('env-updated', install_styles_static_files)

    return {'version': '0.1.0'}  # identifies the version of our extension
