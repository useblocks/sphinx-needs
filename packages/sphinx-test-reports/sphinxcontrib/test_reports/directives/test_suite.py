import hashlib

from docutils import nodes
from docutils.parsers.rst import directives
from sphinxcontrib.needs.api import add_need

import sphinxcontrib.test_reports.directives.test_case
from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOption


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

    def run(self, nested=False, count=-1):
        self.prepare_basic_options()
        self.load_test_file()

        if nested:
            # access n-th nested suite here
            self.results = self.results[0]["testsuites"]

        suite_name = self.options.get("suite", None)

        if suite_name is None:
            raise TestReportInvalidOption("Suite not given!")

        suite = None
        for suite_obj in self.results:
            if suite_obj["name"] == suite_name:
                suite = suite_obj
                break

            elif nested:  # access correct nested testsuite here
                suite = self.results[count]
                break

        if suite is None:
            raise TestReportInvalidOption(
                f"Suite {suite_name} not found in test file {self.test_file}"
            )

        cases = suite["tests"]

        passed = suite["passed"]
        skipped = suite["skips"]
        errors = suite["errors"]
        failed = suite["failures"]

        main_section = []
        docname = self.state.document.settings.env.docname
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
            file=self.test_file_given,
            suite=suite["name"],
            cases=cases,
            passed=passed,
            skipped=skipped,
            failed=failed,
            errors=errors,
        )

        # TODO double nested logic
        # nested testsuite present, if testcases are present -> reached most inner testsuite
        access_count = 0
        if len(suite_obj["testcases"]) == 0:

            for suite in suite_obj["testsuites"]:

                suite_id = self.test_id
                suite_id += (
                    "_"
                    + hashlib.sha1(suite["name"].encode("UTF-8"))  # noqa: W503
                    .hexdigest()
                    .upper()[:3]
                )

                options = self.options
                options["suite"] = suite["name"]
                options["id"] = suite_id

                if "links" not in self.options:
                    options["links"] = self.test_id
                elif self.test_id not in options["links"]:
                    options["links"] = options["links"] + ";" + self.test_id

                arguments = [suite["name"]]
                suite_directive = (
                    sphinxcontrib.test_reports.directives.test_suite.TestSuiteDirective(
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

                is_nested = len(suite_obj["testsuites"]) > 0

                # create suite_directive for each nested suite, directive appends content in html files
                # access_count keeps track of which nested testsuite to access in the directive
                main_section += suite_directive.run(nested=True, count=access_count)
                access_count += 1

        # suite has testcases
        if "auto_cases" in self.options.keys() and len(suite_obj["testcases"]) > 0:

            case_count = 0

            for case in suite["testcases"]:
                case_id = self.test_id
                case_id += (
                    "_"
                    + hashlib.sha1(  # noqa: W503
                        case["classname"].encode("UTF-8") + case["name"].encode("UTF-8")
                    )
                    .hexdigest()
                    .upper()[:5]
                )

                options = self.options
                options["case"] = case["name"]
                options["classname"] = case["classname"]
                options["id"] = case_id

                if "links" not in self.options:
                    options["links"] = self.test_id
                elif self.test_id not in options["links"]:
                    options["links"] = options["links"] + ";" + self.test_id

                arguments = [case["name"]]
                case_directive = (
                    sphinxcontrib.test_reports.directives.test_case.TestCaseDirective(
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

                is_nested = len(suite_obj["testsuites"]) > 0 or nested

                # depending if nested or not, runs case directive to add content to testcases
                # count is for correct suite access, if multiple present, case_count is for correct case access
                main_section += case_directive.run(is_nested, count, case_count)

                if is_nested:
                    case_count += 1

        return main_section
