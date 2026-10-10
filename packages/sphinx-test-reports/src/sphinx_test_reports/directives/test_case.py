from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives

from sphinx_needs.api import add_need
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.utils import add_doc
from sphinx_test_reports.config import DEFAULT_OPTIONS
from sphinx_test_reports.directives.test_common import (
    TestCommonDirective,
    error_node,
    find_suite,
)
from ub_test_reports.identity import split_case_name


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

    def run(self, suite: dict[str, Any] | None = None):
        """The case's need.

        ``suite`` is the parsed suite when a ``:auto_cases:`` expansion runs this directive
        for one of that suite's cases; a hand-written ``test-case`` passes none, and the
        suite is the one its ``:suite:`` names.
        """
        self.prepare_basic_options()

        suite_name: str = self.options.get("suite", "")
        if "suite" not in self.options:
            self.refuse_option("option_missing", "Suite not given!")

        case_full_name = self.options.get("case")
        class_name = self.options.get("classname")
        if case_full_name is None and class_name is None:
            self.refuse_option("option_missing", "Case or classname not given!")

        if self.refusal is not None:
            return self.refuse(*self.refusal)

        if self.load_test_file() is None:
            # The report does not exist or cannot be read: `load_test_file` has warned.
            return [error_node(self.report_error)]

        if suite is None:
            suite = find_suite(self.results, suite_name)

        if suite is None:
            return self.refuse(
                "suite_not_found",
                f"Suite {suite_name} not found in test file {self.test_file}",
            )

        case = None

        for case_obj in suite["testcases"]:
            if case_obj["name"] == case_full_name and class_name is None:  # noqa: SIM114  # noqa: W503
                case = case_obj
                break

            elif (case_obj["classname"] == class_name and case_full_name is None) or (
                case_obj["name"] == case_full_name
                and case_obj["classname"] == class_name
            ):
                case = case_obj
                break

        if case is None:
            return self.refuse(
                "case_not_found",
                f"Case {case_full_name} with classname {class_name} not found in test file "
                f"{self.test_file} and testsuite {suite_name}",
            )

        # A deterministic ID must come from the located case, which is only
        # known here. An explicitly authored :id: always wins.
        if "id" not in self.options:
            deterministic_id = self.deterministic_case_id_for(case)
            if deterministic_id is not None:
                self.test_id = deterministic_id

        result = case["result"]
        content = self.test_content
        # Each block's text is split where docutils will split it -- `str.splitlines()`:
        # CR, CR+LF, VT, FF, FS, GS, RS, NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR, not
        # only `\n` -- and EVERY line indented, so none ends the literal block early (a
        # line left at column 0 was read as reStructuredText). An empty line is written
        # as the indent alone.
        if case["text"] is not None and len(case["text"]) > 0:
            content += """

**Text**::

   {}

""".format("\n   ".join([x.lstrip() for x in case["text"].splitlines()]))

        if case["message"] is not None and len(case["message"]) > 0:
            content += """

**Message**::

   {}

""".format("\n   ".join([x.lstrip() for x in case["message"].splitlines()]))

        if case["system-out"] is not None and len(case["system-out"]) > 0:
            content += """

**System-out**::

   {}

""".format("\n   ".join([x.lstrip() for x in case["system-out"].splitlines()]))

        time = case["time"]
        # Ensure time is a string, SN 6.0.0 requires to be in one specific type
        # and it is set to string for backwards compatibility
        if isinstance(time, (int, float)):
            # Keep as numeric seconds (decimal format)
            time = float(time) if time >= 0 else 0.0
        elif time is None:
            time = 0.0
        else:
            # Try to parse string to float, fallback to 0.0
            try:
                time = float(time)
            except (ValueError, TypeError):
                time = 0.0
        time_str = str(time)

        # If time is already a string or None, keep it as is
        style = "tr_" + case["result"]

        case_name, case_parameter = split_case_name(case["name"])

        # Flatten JUnit <properties> into top-level case keys so that
        # the extra-data loop below picks them up as sphinx-needs fields.
        # Only propagate properties that are explicitly listed in
        # tr_extra_options to avoid unknown-kwarg errors from add_need.
        # Properties do not overwrite core JUnit attributes (name, time, etc.).
        allowed_extras = set(getattr(self.app.config, "tr_extra_options", []))
        case_properties = case.get("properties", {})
        for prop_name, prop_value in case_properties.items():
            if prop_name in allowed_extras and prop_name not in case:
                case[prop_name] = prop_value

        self._apply_property_links(case_properties)

        # Set extra data, which is not part of the Sphinx-Test-Reports default options
        for key, value in case.items():
            if key == "id" and value not in ["", None]:
                self.test_id = str(value)
            elif key == "status" and value not in ["", None]:
                self.test_status = str(value)
            elif key == "tags":
                self.test_tags = ",".join([self.test_tags, str(value)])
            elif key not in DEFAULT_OPTIONS and value not in ["", None]:
                # May overwrite globally set values
                self.extra_options[key] = str(value)

        docname = self.state.document.settings.env.docname

        main_section = []
        # The fields whose NAMES come from configuration, in one mapping: the report-path
        # field is renameable, the source-location pair with it, and the configured extra
        # options are arbitrary. `dict[str, Any]` because `add_need` types each keyword
        # parameter separately and none of these names is known here.
        report_fields: dict[str, Any] = {
            self.report_file_field(): self.test_file_given,
            **self.source_location_fields(case),
            **self.extra_options,
        }
        # Merge all options including extra ones
        try:
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
                suite=suite["name"],
                case=case_full_name,
                case_name=case_name,
                case_parameter=case_parameter,
                classname=class_name,
                result=result,
                time=time_str,
                style=style,
                **report_fields,
            )
        except InvalidNeedException as error:
            return self.need_refused(error)

        add_doc(self.env, docname)
        return main_section
