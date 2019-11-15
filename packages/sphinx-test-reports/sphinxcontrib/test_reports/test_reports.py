
import sphinx
# from docutils import nodes
from pkg_resources import parse_version

from sphinxcontrib.needs.api import add_need_type, add_extra_option, add_dynamic_function

from sphinxcontrib.test_reports.directives.test_results import TestResults, TestResultsDirective
from sphinxcontrib.test_reports.directives import TestFile, TestFileDirective, TestSuite, TestSuiteDirective, \
    TestCase, TestCaseDirective
from sphinxcontrib.test_reports.directives.test_env import EnvReport, EnvReportDirective
from sphinxcontrib.test_reports.environment import install_styles_static_files
from sphinxcontrib.test_reports.functions import tr_link

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

    # configurations
    app.add_config_value('test_reports_rootdir', app.confdir, 'html')

    # nodes
    app.add_node(TestResults)
    app.add_node(TestFile)
    app.add_node(TestSuite)
    app.add_node(TestCase)
    app.add_node(EnvReport)

    # directives
    app.add_directive('test-results', TestResultsDirective)
    app.add_directive('test-file', TestFileDirective)
    app.add_directive('test-suite', TestSuiteDirective)
    app.add_directive('test-case', TestCaseDirective)
    app.add_directive('test-env', EnvReportDirective)

    # events
    app.connect('env-updated', install_styles_static_files)

    ############################
    # sphinx-needs configuration
    ############################

    # Extra options
    # For details read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_extra_option
    add_extra_option(app, 'file')
    add_extra_option(app, 'suite')
    add_extra_option(app, 'case')
    add_extra_option(app, 'classname')
    add_extra_option(app, 'time')

    add_extra_option(app, 'suites')
    add_extra_option(app, 'cases')

    add_extra_option(app, 'passed')
    add_extra_option(app, 'skipped')
    add_extra_option(app, 'failed')
    add_extra_option(app, 'errors')
    add_extra_option(app, 'result')  # used by test cases only

    # Extra dynamic functions
    # For details about usage read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_dynamic_function
    add_dynamic_function(app, tr_link)

    # Extra need types
    # For details about usage read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_need_type
    add_need_type(app, 'testfile', 'Test-File', 'TF_', '#ffffff', 'node')
    add_need_type(app, 'testsuite', 'Test-Suite', 'TS_', '#cccccc', 'folder')
    add_need_type(app, 'testcase', 'Test-Case', 'TC_', '#999999', 'rectangle')

    return {'version': '0.3.1'}  # identifies the version of our extension
