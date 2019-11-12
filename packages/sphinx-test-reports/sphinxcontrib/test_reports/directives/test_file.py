import hashlib
import os
from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinxcontrib.test_reports.directives import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportFileNotSetException, TestReportFileInvalidException
from sphinxcontrib.needs.api import add_need


class TestFile(nodes.General, nodes.Element):
    pass


class TestFileDirective(TestCommonDirective):
    """
    Directive for showing test results.
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
                   }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self):
        self.prepare_basic_options()
        self.load_test_file()

        suites = len(self.results)
        cases = sum([int(x['tests']) for x in self.results])

        passed = sum([x['passed'] for x in self.results])
        skipped = sum([x['skips'] for x in self.results])
        errors = sum([x['errors'] for x in self.results])
        failed = sum([x['failures'] for x in self.results])

        main_section = []
        docname = self.state.document.settings.env.docname
        main_section += add_need(self.env.app, self.state, docname, self.lineno,
                                 need_type="testfile", title=self.test_name, id=self.test_id,
                                 content=self.test_content, links=self.test_links, tags=self.test_tags,
                                 status=self.test_status, collapse=self.collapse,
                                 file=self.test_file_given, suites=suites, cases=cases,
                                 passed=passed, skipped=skipped, failed=failed, errors=errors)
        return main_section
