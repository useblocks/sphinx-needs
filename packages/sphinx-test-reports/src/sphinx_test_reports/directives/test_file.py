import hashlib
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives

import sphinx_test_reports.directives.test_suite
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc
from sphinx_test_reports.directives.test_common import (
    TestCommonDirective,
    _links_with,
)
from sphinx_test_reports.exceptions import TestReportIncompleteConfigurationError


class TestFile(nodes.General, nodes.Element):
    pass


class TestFileDirective(TestCommonDirective):
    """
    Directive for showing test results.
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
        "auto_suites": directives.flag,
        "auto_cases": directives.flag,
    }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: Every suite id this expansion minted, at every depth, with its suite's name. Keyed
        #: on the full id, which carries the parent's: two suites named alike under
        #: different parents do not collide, two of one name under one parent do.
        self.suite_ids: dict[str, str] = {}

    def _expand_suites(
        self,
        suites: list[dict[str, Any]],
        parent_id: str,
        parent_options: dict[str, Any],
    ) -> list[nodes.Node]:
        """The needs of ``suites`` and, at every depth, of the suites nested in them.

        In pre-order: a suite's need, then (with ``:auto_cases:``) its direct cases, then
        its nested suites the same way. A suite's id is its parent's id -- the file's for
        a top-level suite, the enclosing suite's for a nested one -- plus the first
        ``tr_suite_id_length`` hex digits of the SHA1 of its name; it links its parent on
        top of the parent's own links, so the chain up to the file accumulates.
        """
        nodes_: list[nodes.Node] = []
        for suite in suites:
            suite_id = (
                parent_id
                + "_"
                + hashlib.sha1(suite["name"].encode("UTF-8"))
                .hexdigest()
                .upper()[: self.app.config.tr_suite_id_length]
            )

            if suite_id not in self.suite_ids:
                self.suite_ids[suite_id] = suite["name"]
            else:
                raise Exception(
                    f"Suite ID {suite_id} already exists by {self.suite_ids[suite_id]} ({suite['name']})"
                )

            # A copy per suite: the dict is handed on to the suite's cases and nested
            # suites, and a shared one would carry this suite's id and links into its
            # siblings and every later suite.
            options = parent_options.copy()
            options["suite"] = suite["name"]
            options["id"] = suite_id

            options["links"] = _links_with(options.get("links", ""), parent_id)

            arguments = [suite["name"]]
            suite_directive = (
                sphinx_test_reports.directives.test_suite.TestSuiteDirective(
                    self.app.config.tr_suite[0],
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

            nodes_ += suite_directive.run(suite=suite)
            nodes_ += self._expand_suites(
                suite.get("testsuite_nested", []), suite_id, options
            )
        return nodes_

    def run(self):
        self.prepare_basic_options()
        results = self.load_test_file()

        # Error handling, if file not found
        if results is None:
            main_section = []
            content = nodes.error()
            para = nodes.paragraph()
            text_string = f"Test file not found: {self.test_file}"
            text = nodes.Text(text_string)
            para += text
            content.append(para)
            main_section.append(content)
            return main_section

        suites = len(self.results)
        cases = sum(int(x["tests"]) for x in self.results)

        passed = sum(x["passed"] for x in self.results)
        skipped = sum(x["skips"] for x in self.results)
        errors = sum(x["errors"] for x in self.results)
        failed = sum(x["failures"] for x in self.results)

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
            suites=suites,
            cases=cases,
            passed=passed,
            skipped=skipped,
            failed=failed,
            errors=errors,
            **report_fields,
        )

        if "auto_cases" in self.options and "auto_suites" not in self.options:
            raise TestReportIncompleteConfigurationError(
                "option auto_cases must be used together with "
                "auto_suites for test-file directives."
            )

        if "auto_suites" in self.options:
            main_section += self._expand_suites(
                self.results, self.test_id, self.options
            )

        add_doc(self.env, docname)

        return main_section
