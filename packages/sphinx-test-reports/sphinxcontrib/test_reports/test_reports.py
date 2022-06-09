# fmt: off
import os

import sphinx
# from docutils import nodes
from pkg_resources import parse_version
from sphinxcontrib.needs.api import add_dynamic_function, add_extra_option, add_need_type

from sphinxcontrib.test_reports.directives.test_case import TestCase, TestCaseDirective
from sphinxcontrib.test_reports.directives.test_env import EnvReport, EnvReportDirective
from sphinxcontrib.test_reports.directives.test_file import TestFile, TestFileDirective
from sphinxcontrib.test_reports.directives.test_report import TestReport, TestReportDirective
from sphinxcontrib.test_reports.directives.test_results import TestResults, TestResultsDirective
from sphinxcontrib.test_reports.directives.test_suite import TestSuite, TestSuiteDirective
from sphinxcontrib.test_reports.environment import install_styles_static_files
from sphinxcontrib.test_reports.functions import tr_link

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

# fmt: on

VERSION = "0.3.7"


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
    app.add_config_value("tr_rootdir", app.confdir, "html")
    app.add_config_value(
        "tr_file",
        ["test-file", "testfile", "Test-File", "TF_", "#ffffff", "node"],
        "html",
    )
    app.add_config_value(
        "tr_suite",
        ["test-suite", "testsuite", "Test-Suite", "TS_", "#cccccc", "folder"],
        "html",
    )
    app.add_config_value(
        "tr_case",
        ["test-case", "testcase", "Test-Case", "TC_", "#999999", "rectangle"],
        "html",
    )

    # adds option for custom template
    template_dir = os.path.join(
        os.path.dirname(__file__), "directives/test_report_template.txt"
    )
    app.add_config_value("tr_report_template", template_dir, "html")

    # nodes
    app.add_node(TestResults)
    app.add_node(TestFile)
    app.add_node(TestSuite)
    app.add_node(TestCase)
    app.add_node(TestReport)
    app.add_node(EnvReport)

    # directives
    app.add_directive("test-results", TestResultsDirective)
    app.add_directive("test-env", EnvReportDirective)
    app.add_directive("test-report", TestReportDirective)

    # events
    app.connect("env-updated", install_styles_static_files)
    app.connect("config-inited", tr_preparation)
    app.connect("config-inited", sphinx_needs_update)

    return {
        "version": VERSION,  # identifies the version of our extension
        "parallel_read_safe": True,  # support parallel modes
        "parallel_write_safe": True,
    }


def tr_preparation(app, *args):
    """
    Prepares needed vars in the app context.
    """
    if not hasattr(app, "tr_types"):
        app.tr_types = {}

    # Collects the configured test-report node types
    app.tr_types[app.config.tr_file[0]] = app.config.tr_file[1:]
    app.tr_types[app.config.tr_suite[0]] = app.config.tr_suite[1:]
    app.tr_types[app.config.tr_case[0]] = app.config.tr_case[1:]

    app.add_directive(app.config.tr_file[0], TestFileDirective)
    app.add_directive(app.config.tr_suite[0], TestSuiteDirective)
    app.add_directive(app.config.tr_case[0], TestCaseDirective)


def sphinx_needs_update(app, *args):
    """
    sphinx-needs configuration
    """

    # Extra options
    # For details read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_extra_option
    add_extra_option(app, "file")
    add_extra_option(app, "suite")
    add_extra_option(app, "case")
    add_extra_option(app, "case_name")
    add_extra_option(app, "case_parameter")
    add_extra_option(app, "classname")
    add_extra_option(app, "time")

    add_extra_option(app, "suites")
    add_extra_option(app, "cases")

    add_extra_option(app, "passed")
    add_extra_option(app, "skipped")
    add_extra_option(app, "failed")
    add_extra_option(app, "errors")
    add_extra_option(app, "result")  # used by test cases only

    # Extra dynamic functions
    # For details about usage read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_dynamic_function
    add_dynamic_function(app, tr_link)

    # Extra need types
    # For details about usage read
    # https://sphinxcontrib-needs.readthedocs.io/en/latest/api.html#sphinxcontrib.needs.api.configuration.add_need_type
    add_need_type(app, *app.config.tr_file[1:])
    add_need_type(app, *app.config.tr_suite[1:])
    add_need_type(app, *app.config.tr_case[1:])
