from docutils import nodes
from docutils.parsers.rst import directives

from sphinxcontrib.test_reports.directives import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOption
from sphinxcontrib.needs.api import add_need


class TestCase(nodes.General, nodes.Element):
    pass


class TestCaseDirective(TestCommonDirective):
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
                   'case': directives.unchanged_required,
                   'classname': directives.unchanged_required,
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

        case_name = self.options.get('case', None)
        class_name = self.options.get('classname', None)
        if case_name is None and class_name is None:
            raise TestReportInvalidOption('Case or classname not given!')

        suite = None
        for suite_obj in self.results:
            if suite_obj['name'] == suite_name:
                suite = suite_obj
                break

        if suite is None:
            raise TestReportInvalidOption('Suite {} not found in test file {}'.format(suite_name, self.test_file))

        case = None
        for case_obj in suite['testcases']:
            if case_obj['name'] == case_name and class_name is None:
                case = case_obj
            elif case_obj['classname'] == class_name and case_name is None:
                case = case_obj
                break
            elif case_obj['name'] == case_name and case_obj['classname'] == class_name:
                case = case_obj
                break

        if case is None:
            raise TestReportInvalidOption('Case {} with classname {} not found in test file {} '
                                          'and testsuite {}'.format(case_name, class_name, self.test_file, suite_name))

        result = case['result']
        content = self.test_content
        if len(case['text']) > 0:
            content += """
            
**Text**::

   {}

""".format('\n   '.join([x.lstrip() for x in case['text'].split('\n')]))

        if len(case['message']) > 0:
            content += """

**Message**::

   {}

""".format('\n   '.join([x.lstrip() for x in case['message'].split('\n')]))

        if len(case['system-out']) > 0:
            content += """

**System-out**::

   {}

""".format('\n   '.join([x.lstrip() for x in case['system-out'].split('\n')]))

        time = case['time']
        style = 'tr_' + case['result']

        main_section = []
        docname = self.state.document.settings.env.docname
        main_section += add_need(self.env.app, self.state, docname, self.lineno,
                                 need_type="testcase", title=self.test_name, id=self.test_id,
                                 content=content, links=self.test_links, tags=self.test_tags,
                                 status=self.test_status, collapse=self.collapse,
                                 file=self.test_file_given, suite=suite['name'], case=case_name, classname=class_name,
                                 result=result, time=time, style=style)
        return main_section
