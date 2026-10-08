import hashlib
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives

import sphinx_test_reports.directives.test_case
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc
from sphinx_test_reports.directives.test_common import (
    TestCommonDirective,
    _links_with,
    error_node,
    find_suite,
)
from sphinx_test_reports.exceptions import TestReportInvalidOptionError


class TestSuite(nodes.General, nodes.Element):
    pass


class TestSuiteDirective(TestCommonDirective):
    """
    Directive for showing test suites.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "id": directives.unchanged_required,
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "links": directives.unchanged_required,
        "collapse": directives.unchanged_required,
        "file": directives.unchanged_required,
        "suite": directives.unchanged_required,
    }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.case_ids = []

    def run(self, suite: dict[str, Any] | None = None):
        """The suite's need and, from an ``:auto_cases:`` expansion, its direct cases'.

        ``suite`` is the parsed suite when ``test-file``'s ``:auto_suites:`` runs this
        directive (its nested suites are that expansion's to walk); a hand-written
        ``test-suite`` passes none, and the suite is the one its ``:suite:`` names.
        """
        self.prepare_basic_options()
        if self.load_test_file() is None:
            # The report does not exist or cannot be read: `load_test_file` has warned.
            return [error_node(self.report_error)]

        suite_name = self.options.get("suite")

        if suite_name is None:
            raise TestReportInvalidOptionError("Suite not given!")

        if suite is None:
            suite = find_suite(self.results, suite_name)

        if suite is None:
            raise TestReportInvalidOptionError(
                f"Suite {suite_name} not found in test file {self.test_file}"
            )

        cases = suite["tests"]

        passed = suite["passed"]
        skipped = suite["skips"]
        errors = suite["errors"]
        failed = suite["failures"]

        # Flatten JUnit <properties> into extra_options so that
        # suite-level properties are surfaced as sphinx-needs fields.
        # Only propagate properties that are explicitly listed in
        # tr_extra_options to avoid unknown-kwarg errors from add_need.
        allowed_extras = set(getattr(self.app.config, "tr_extra_options", []))
        suite_properties = suite.get("properties", {})
        for prop_name, prop_value in suite_properties.items():
            if (
                prop_name in allowed_extras
                and prop_name not in suite
                and prop_value not in ["", None]
            ):
                self.extra_options[prop_name] = str(prop_value)

        self._apply_property_links(suite_properties)

        main_section = []
        docname = self.state.document.settings.env.docname
        # The fields whose NAMES come from configuration -- the renameable report-path
        # field and the configured extra options -- in one mapping. `dict[str, Any]`
        # because `add_need` types each keyword parameter separately.
        report_fields: dict[str, Any] = {
            self.report_file_field(): self.test_file_given,
            **self.extra_options,
        }
        main_section += add_need(
            self.app,
            self.state,
            docname,
            self.lineno,
            need_type=self.need_type,
            title=self.test_name,
            id=self.test_id,
            content=self.test_content,
            links=self.test_links,
            tags=self.test_tags,
            status=self.test_status,
            collapse=self.collapse,
            suite=suite["name"],
            cases=cases,
            passed=passed,
            skipped=skipped,
            failed=failed,
            errors=errors,
            **report_fields,
        )

        # the suite's direct cases
        if "auto_cases" in self.options and len(suite["testcases"]) > 0:
            for case in suite["testcases"]:
                case_id = self.deterministic_case_id_for(case)
                if case_id is None:
                    # Default: a hash fragment scoped to the parent suite.
                    case_id = self.test_id
                    case_id += (
                        "_"
                        + hashlib.sha1(
                            case["classname"].encode("UTF-8")
                            + case["name"].encode("UTF-8")
                        )
                        .hexdigest()
                        .upper()[: self.app.config.tr_case_id_length]
                    )

                if case_id not in self.case_ids:
                    self.case_ids.append(case_id)
                else:
                    raise Exception(f"Case ID exists: {case_id}")

                # We need to copy self.options, otherwise it gets updated and sets same values
                # for all testsuites.
                options = self.options.copy()

                options["case"] = case["name"]
                options["classname"] = case["classname"]
                options["id"] = case_id

                options["links"] = _links_with(options.get("links", ""), self.test_id)

                arguments = [case["name"]]
                case_directive = (
                    sphinx_test_reports.directives.test_case.TestCaseDirective(
                        self.app.config.tr_case[0],
                        arguments,
                        options,
                        "",
                        self.lineno,  # no content
                        self.content_offset,
                        self.block_text,
                        self.state,
                        self.state_machine,
                    )
                )

                main_section += case_directive.run(suite=suite)

        add_doc(self.env, docname)

        return main_section
