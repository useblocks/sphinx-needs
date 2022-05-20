from docutils import nodes
from docutils.parsers.rst import directives
from sphinxcontrib.needs.api import add_need

from sphinxcontrib.test_reports.directives.test_common import TestCommonDirective
from sphinxcontrib.test_reports.exceptions import TestReportInvalidOption


class TestCase(nodes.General, nodes.Element):
    pass


class TestCaseDirective(TestCommonDirective):
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
        "case": directives.unchanged_required,
        "classname": directives.unchanged_required,
    }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, nested=False, suite_count=-1, case_count=-1):
        self.prepare_basic_options()
        self.load_test_file()

        if nested and suite_count >= 0:
            # access n-th nested suite here
            self.results = self.results[0]["testsuites"][suite_count]

        suite_name = self.options.get("suite", None)

        if suite_name is None:
            raise TestReportInvalidOption("Suite not given!")

        case_full_name = self.options.get("case", None)
        class_name = self.options.get("classname", None)
        if case_full_name is None and class_name is None:
            raise TestReportInvalidOption("Case or classname not given!")

        suite = None
        for suite_obj in self.results:

            if nested:  # nested testsuites
                suite = self.results
                break

            elif suite_obj["name"] == suite_name:
                suite = suite_obj
                break

        if suite is None:
            raise TestReportInvalidOption(
                f"Suite {suite_name} not found in test file {self.test_file}"
            )

        case = None

        for case_obj in suite["testcases"]:

            if (
                case_obj["name"] == case_full_name  # noqa: SIM114
                and class_name is None  # noqa: W503
            ):
                case = case_obj
                break

            elif (
                case_obj["classname"] == class_name  # noqa: SIM114
                and case_full_name is None  # noqa: W503
            ):
                case = case_obj
                break

            elif (
                case_obj["name"] == case_full_name
                and case_obj["classname"] == class_name  # noqa: W503
            ):
                case = case_obj
                break

            elif nested and case_count >= 0:
                # access correct case in list
                case = suite["testcases"][case_count]
                break

            elif nested:
                case = case_obj
                break

        if case is None:
            raise TestReportInvalidOption(
                "Case {} with classname {} not found in test file {} "
                "and testsuite {}".format(
                    case_full_name, class_name, self.test_file, suite_name
                )
            )

        result = case["result"]
        content = self.test_content
        if len(case["text"]) > 0:
            content += """

**Text**::

   {}

""".format(
                "\n   ".join([x.lstrip() for x in case["text"].split("\n")])
            )

        if len(case["message"]) > 0:
            content += """

**Message**::

   {}

""".format(
                "\n   ".join([x.lstrip() for x in case["message"].split("\n")])
            )

        if len(case["system-out"]) > 0:
            content += """

**System-out**::

   {}

""".format(
                "\n   ".join([x.lstrip() for x in case["system-out"].split("\n")])
            )

        time = case["time"]
        style = "tr_" + case["result"]

        import re

        groups = re.match(r"^(?P<name>[^\[]+)($|\[(?P<param>.*)?\])", case["name"])
        try:
            case_name = groups["name"]
            case_parameter = groups["param"]
        except TypeError:
            case_name = case_full_name
            case_parameter = ""

        if case_parameter is None:
            case_parameter = ""

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
            content=content,
            links=self.test_links,
            tags=self.test_tags,
            status=self.test_status,
            collapse=self.collapse,
            file=self.test_file_given,
            suite=suite["name"],
            case=case_full_name,
            case_name=case_name,
            case_parameter=case_parameter,
            classname=class_name,
            result=result,
            time=time,
            style=style,
        )
        return main_section
