"""
A Common directive, from which all other test directives inherit the shared functions.
"""
import os
from docutils.parsers.rst import Directive

from sphinxcontrib.needs.api import make_hashed_id

from sphinxcontrib.test_reports.junitparser import JUnitParser
from sphinxcontrib.test_reports.exceptions import TestReportFileNotSetException, TestReportFileInvalidException


class TestCommonDirective(Directive):
    """
    Common directive, which provides some shared functions to "real" directives.
    """
    def __init__(self, *args, **kwargs):
        super(TestCommonDirective, self).__init__(*args, **kwargs)
        self.env = self.state.document.settings.env
        if not hasattr(self.env, 'testreport_data'):
            self.env.testreport_data = {}

        self.test_file = None
        self.results = None
        self.docname = None
        self.test_name = None
        self.test_id = None
        self.test_content = None
        self.test_file_given = None
        self.test_links = None
        self.test_tags = None
        self.test_status = None
        self.collapse = None

    def load_test_file(self):
        """
        Loads the defined test_file under self.test_file.

        ``prepare_basic_options`` must be called first

        :return: None
        """
        if self.test_file is None:
            raise TestReportFileNotSetException('Option test_file must be set.')

        root_path = self.env.app.config.test_reports_rootdir
        if not os.path.isabs(self.test_file):
            self.test_file = os.path.join(root_path, self.test_file)
        if not os.path.exists(self.test_file):
            raise TestReportFileInvalidException('Given test_file path invalid: {}'.format(self.test_file))

        if self.test_file not in self.env.testreport_data.keys():
            parser = JUnitParser(self.test_file)
            self.env.testreport_data[self.test_file] = parser.parse()

        self.results = self.env.testreport_data[self.test_file]
        return self.results

    def prepare_basic_options(self):
        """
        Reads and checks the needed basic data like name, id, links, status, ...
        :return: None
        """
        self.docname = self.state.document.settings.env.docname

        self.test_name = self.arguments[0]
        self.test_content = "\n".join(self.content)
        need_type = self.name.replace('-', '').replace('_', '')
        self.test_id = self.options.get('id',
                                        make_hashed_id(self.env.app, need_type, self.test_name, self.test_content))

        self.test_file = self.options.get('file', None)
        self.test_file_given = self.test_file[:]

        self.test_links = self.options.get('links', '')
        self.test_tags = self.options.get('tags', '')
        self.test_status = self.options.get('status', None)

        self.collapse = str(self.options.get("collapse", ""))

        if isinstance(self.collapse, str) and len(self.collapse) > 0:
            if self.collapse.upper() in ["TRUE", 1, "YES"]:
                self.collapse = True
            elif self.collapse.upper() in ["FALSE", 0, "NO"]:
                self.collapse = False
            else:
                raise Exception("collapse attribute must be true or false")
        else:
            self.collapse = getattr(self.env.app.config, "needs_collapse_details", True)
