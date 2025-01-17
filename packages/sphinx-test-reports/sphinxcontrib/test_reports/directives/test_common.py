"""
A Common directive, from which all other test directives inherit the shared functions.
"""

# fmt: off
import os
import pathlib
from importlib.metadata import version

from docutils.parsers.rst import Directive
from sphinx.util import logging
from sphinx_needs.config import NeedsSphinxConfig

from sphinxcontrib.test_reports.exceptions import (
    SphinxError, TestReportFileNotSetException)
from sphinxcontrib.test_reports.jsonparser import JsonParser
from sphinxcontrib.test_reports.junitparser import JUnitParser

sn_major_version = int(version("sphinx-needs").split('.')[0])

if sn_major_version >= 4:
    from sphinx_needs.api.need import _make_hashed_id
else:
    from sphinx_needs.api import make_hashed_id


# fmt: on


class TestCommonDirective(Directive):
    """
    Common directive, which provides some shared functions to "real" directives.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.env = self.state.document.settings.env
        self.app = self.env.app
        if not hasattr(self.app, "testreport_data"):
            self.app.testreport_data = {}

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
        self.need_type = None

        self.log = logging.getLogger(__name__)

    def load_test_file(self):
        """
        Loads the defined test_file under self.test_file.

        ``prepare_basic_options`` must be called first

        :return: None
        """
        if self.test_file is None:
            raise TestReportFileNotSetException("Option test_file must be set.")

        test_path = pathlib.Path(self.test_file)
        if not test_path.is_absolute():
            root_path = pathlib.Path(self.app.config.tr_rootdir)
            test_path = root_path / test_path
        self.test_file = str(test_path)
        if not test_path.exists():
            # raise TestReportFileInvalidException('Given test_file path invalid: {}'.format(self.test_file))
            self.log.warning(f"Given test_file path invalid: {self.test_file} in {self.docname} (Line: {self.lineno})")
            return None

        if self.test_file not in self.app.testreport_data.keys():
            if os.path.splitext(self.test_file)[1] == ".json":
                mapping = list(self.app.config.tr_json_mapping.values())[0]
                parser = JsonParser(self.test_file, json_mapping=mapping)
            else:
                parser = JUnitParser(self.test_file)
            self.app.testreport_data[self.test_file] = parser.parse()

        self.results = self.app.testreport_data[self.test_file]
        return self.results

    def prepare_basic_options(self):
        """
        Reads and checks the needed basic data like name, id, links, status, ...
        :return: None
        """
        self.docname = self.state.document.settings.env.docname

        self.test_name = self.arguments[0]
        self.test_content = "\n".join(self.content)
        if self.name != "test-report":
            self.need_type = self.app.tr_types[self.name][0]
            if sn_major_version >= 4:
                hashed_id = _make_hashed_id(
                    self.need_type,
                    self.test_name,
                    self.test_content,
                    NeedsSphinxConfig(self.app.config),
                )
            else:  # Sphinx-Needs < 4
                hashed_id = make_hashed_id(self.app, self.need_type, self.test_name, self.test_content)

            self.test_id = self.options.get(
                "id",
                hashed_id,
            )
        else:
            self.test_id = self.options.get("id")

        if self.test_id is None:
            raise SphinxError("ID must be set for test-report.")

        self.test_file = self.options.get("file")
        self.test_file_given = self.test_file[:]

        self.test_links = self.options.get("links", "")
        self.test_tags = self.options.get("tags", "")
        self.test_status = self.options.get("status")

        self.collapse = str(self.options.get("collapse", ""))

        if isinstance(self.collapse, str) and len(self.collapse) > 0:
            if self.collapse.upper() in ["TRUE", 1, "YES"]:
                self.collapse = True
            elif self.collapse.upper() in ["FALSE", 0, "NO"]:
                self.collapse = False
            else:
                raise Exception("collapse attribute must be true or false")
        else:
            self.collapse = getattr(self.app.config, "needs_collapse_details", True)
