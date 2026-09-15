"""
A Common directive, from which all other test directives inherit the shared functions.
"""

# fmt: off
import os
import pathlib
from typing import Any

from docutils.parsers.rst import Directive
from sphinx.util import logging

# `_make_hashed_id` has been sphinx-needs' spelling since its 4.0; the import narrowed to
# `sphinx-needs>=8.5.0,<9` at the workspace import, so the `make_hashed_id` fallback this
# used to carry could no longer run -- and no longer resolves, since the name is gone from
# `sphinx_needs.api` entirely (measured against 8.5.0).
from sphinx_needs.api.need import _make_hashed_id
from sphinx_needs.config import NeedsSphinxConfig
from sphinxcontrib.test_reports.exceptions import (
    SphinxError,
    TestReportFileNotSetError,
)
from sphinxcontrib.test_reports.identity import deterministic_case_id
from sphinxcontrib.test_reports.jsonparser import JsonParser
from sphinxcontrib.test_reports.junitparser import JUnitParser

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

        # Every one of these is populated by `prepare_basic_options` (and `results` by
        # `load_test_file`) before any directive reads it. Declared here with the type each
        # one actually holds, because the bare `None` they used to start as is what the
        # subclasses' `self.results[0]`, `for x in self.results`, `self.extra_options[k]`
        # and `add_need(title=self.test_name, ...)` were all being type-checked against.
        # `test_file` and `test_id` start EMPTY rather than `None`: both are required, and
        # the two guards that enforced that are now falsiness checks. For `test_id` that is
        # exactly identical behaviour. For `test_file` it is NOT, and the difference is a
        # bug fix: `prepare_basic_options` runs before `load_test_file` in all four
        # directives, so `test_file_given = self.test_file[:]` raised TypeError on a
        # directive written without `:file:` before the guard in `load_test_file` could
        # ever be reached -- that guard was dead code. The slice is now a no-op and the
        # guard is live, so such a directive raises TestReportFileNotSetError, a
        # SphinxError.
        self.test_file: str = ""
        #: Whatever the JUnit/JSON parser returned -- untyped by construction.
        self.results: Any = None
        self.docname: str = ""
        self.test_name: str = ""
        self.test_id: str = ""
        self.test_content: str = ""
        self.test_file_given: str = ""
        self.test_links: str = ""
        self.test_tags: str = ""
        self.test_status: str | None = None
        self.collapse: bool | str = False
        self.need_type: str = ""
        #: Values read off the Sphinx config and the report, so `Any` rather than `str`:
        #: this mapping is splatted into `add_need`, whose keyword parameters are typed
        #: individually, and a `dict[str, str]` would be checked against every one of them.
        self.extra_options: dict[str, Any] = {}

        self.log = logging.getLogger(__name__)

    def report_file_field(self) -> str:
        """Need field carrying the XML report path (renameable via config).

        Renaming it is what frees ``file``/``line`` for the *test source*
        location, so every directive must honour the option -- not only the
        field registration.
        """
        return getattr(self.app.config, "tr_file_option", "file")

    def source_location_fields(self, case: Any) -> dict[str, Any]:
        """Need fields for the ``<testcase>`` file/line attributes.

        The parser reports ``"unknown"``/``-1`` when the attributes are absent,
        which is the norm for pytest: its default ``junit_family = xunit2``
        filters them out. Those sentinels become empty strings, so the fields
        are always present and never carry a fake location.
        """
        file_field = getattr(self.app.config, "tr_source_file_option", "case_file")
        line_field = getattr(self.app.config, "tr_source_line_option", "case_line")

        source_file = case.get("file", "unknown")
        source_line = case.get("line", -1)

        return {
            file_field: "" if source_file in ("unknown", None) else str(source_file),
            line_field: "" if source_line in (-1, None) else str(source_line),
        }

    def deterministic_case_id_for(self, case):
        """Deterministic ID for ``case``, or ``None`` if the option is off."""
        if not getattr(self.app.config, "tr_deterministic_case_ids", False):
            return None

        return deterministic_case_id(
            classname=case.get("classname", ""),
            name=case.get("name", ""),
            file=case.get("file", ""),
            prefix=self.app.config.tr_case[1],
        )

    def collect_extra_options(self):
        """Collect any extra options and their values that were specified in the directive"""
        tr_extra_options = getattr(self.app.config, "tr_extra_options", [])
        self.extra_options = {}

        if tr_extra_options:
            for option_name in tr_extra_options:
                if option_name in self.options:
                    self.extra_options[option_name] = self.options[option_name]

    def load_test_file(self):
        """
        Loads the defined test_file under self.test_file.

        ``prepare_basic_options`` must be called first

        :return: None
        """
        if not self.test_file:
            raise TestReportFileNotSetError("Option test_file must be set.")

        test_path = pathlib.Path(self.test_file)
        if not test_path.is_absolute():
            root_path = pathlib.Path(self.app.config.tr_rootdir)
            test_path = root_path / test_path
        self.test_file = str(test_path)
        if not test_path.exists():
            # raise TestReportFileInvalidException('Given test_file path invalid: {}'.format(self.test_file))
            self.log.warning(
                f"Given test_file path invalid: {self.test_file} in {self.docname} (Line: {self.lineno})"
            )
            return None

        if self.test_file not in self.app.testreport_data:
            if os.path.splitext(self.test_file)[1] == ".json":
                mapping = next(iter(self.app.config.tr_json_mapping.values()))
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
            hashed_id = _make_hashed_id(
                self.need_type,
                self.test_name,
                self.test_content,
                NeedsSphinxConfig(self.app.config),
            )

            self.test_id = self.options.get(
                "id",
                hashed_id,
            )
        else:
            self.test_id = self.options.get("id", "")

        if not self.test_id:
            raise SphinxError("ID must be set for test-report.")

        self.test_file = self.options.get("file", "")
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

        # Also collect any extra options while we're at it
        self.collect_extra_options()

    def _apply_property_links(self, properties):
        """Map JUnit <properties> values to sphinx-needs link fields via tr_property_link_types."""
        tr_property_link_types = getattr(self.app.config, "tr_property_link_types", {})
        for prop_name, link_field in tr_property_link_types.items():
            prop_value = properties.get(prop_name, "")
            if prop_value:
                link_ids = ";".join(
                    id_val.strip() for id_val in prop_value.split(",") if id_val.strip()
                )
                if link_field == "links":
                    existing = self.test_links
                else:
                    existing = self.extra_options.get(link_field, "")
                merged = existing + ";" + link_ids if existing else link_ids
                if link_field == "links":
                    self.test_links = merged
                else:
                    self.extra_options[link_field] = merged
