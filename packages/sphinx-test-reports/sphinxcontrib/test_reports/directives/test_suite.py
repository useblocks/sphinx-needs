import hashlib
import os
from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinxcontrib.test_reports.directives import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOption
from sphinxcontrib.needs.api import add_need


class TestSuite(nodes.General, nodes.Element):
    pass


class TestSuiteDirective(TestCommonDirective):
    """
    Directive for showing test suites.
    """
    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {'id': directives.unchanged_required,
                   'status': directives.unchanged_required,
                   'tags': directives.unchanged_required,
                   'links': directives.unchanged_required,
                   'collapse': directives.unchanged_required,
                   'file': directives.unchanged_required,
                   'suite': directives.unchanged_required,
                   }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self.prepare_basic_options()
        self.load_test_file()

        suite_name = self.options.get('suite', None)
        if suite_name is None:
            raise TestReportInvalidOption('Suite not given!')


        suite = None
        for suite_obj in self.results:
            if suite_obj['name'] == suite_name:
                suite = suite_obj
                break

        if suite is None:
            raise TestReportInvalidOption('Suite {} not found in test file {}'.format(suite_name, self.test_file))

        cases = suite['tests']

        passed = suite['passed']
        skipped = suite['skips']
        errors = suite['errors']
        failed = suite['failures']

        main_section = []
        docname = self.state.document.settings.env.docname
        main_section += add_need(self.env.app, self.state, docname, self.lineno,
                                 need_type="testsuite", title=self.test_name, id=self.test_id,
                                 content=self.test_content, links=self.test_links, tags=self.test_tags,
                                 status=self.test_status, collapse=self.collapse,
                                 file=self.test_file_given, suite=suite['name'], cases=cases,
                                 passed=passed, skipped=skipped, failed=failed, errors=errors)
        return main_section
