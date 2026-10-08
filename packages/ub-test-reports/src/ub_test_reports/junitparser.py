"""
JUnit XML parser
"""

import os

from lxml import etree, objectify  # ty: ignore[unresolved-import]

from ub_test_reports.errors import ReportReadError
from ub_test_reports.results import normalize_result

__all__ = ["JUnitFileMissing", "JUnitParser", "ReportReadError"]

#: Attributes the JUnit/googletest dialects define themselves. Every *other*
#: attribute is a ``RecordProperty`` value in attribute form: googletest wrote
#: test-case properties as attributes before 1.8.1 (the form its official docs
#: still show), and suite-level properties stayed attribute-only up to 1.15.x.
TESTCASE_KNOWN_ATTRIBUTES = frozenset(
    {
        "assertions",
        "classname",
        "file",
        "line",
        "name",
        "result",
        "status",
        "time",
        "timestamp",
        "type_param",
        "value_param",
    }
)

TESTSUITE_KNOWN_ATTRIBUTES = frozenset(
    {
        "disabled",
        "errors",
        "failures",
        "hostname",
        "id",
        "name",
        "package",
        "random_seed",
        "skip",
        "skipped",
        "skips",
        "tests",
        "time",
        "timestamp",
    }
)

#: ``<testcase>`` children carrying a result, in the precedence order used to
#: classify a case that has more than one kind of them. These are XML element
#: names, not ``result`` values -- ``<failure>`` is read as the result
#: ``failed`` (see :mod:`ub_test_reports.results`).
RESULT_PART_KINDS = ("skipped", "failure", "error")


def _child_tag(child: objectify.ObjectifiedElement) -> str | None:
    """Tag name of an lxml child, or ``None`` for comments and instructions."""
    tag = child.tag
    return tag if isinstance(tag, str) else None


def _collect_properties(
    xml_object: objectify.ObjectifiedElement, known_attributes: frozenset[str]
) -> dict[str, str]:
    """Read ``RecordProperty`` values from both dialect forms.

    Unknown attributes are the legacy/attribute form; ``<properties>`` children
    are the modern form and therefore win on conflict.
    """
    properties = {
        name: value
        for name, value in xml_object.attrib.items()
        if name not in known_attributes
    }

    if hasattr(xml_object, "properties") and hasattr(xml_object.properties, "property"):
        for prop in xml_object.properties.property:
            name = prop.attrib.get("name", "")
            if name:
                properties[name] = prop.attrib.get("value", "")

    return properties


def _collect_result_parts(
    testcase: objectify.ObjectifiedElement,
) -> list[dict[str, str]]:
    """Every ``<failure>``/``<error>``/``<skipped>`` child, in document order.

    googletest emits one element per failed assertion and ``GTEST_SKIP`` can
    fire repeatedly, so reading only the first part silently drops evidence.
    The per-part ``type``/``message`` defaults match what the flat, historical
    ``type``/``message`` keys have always reported for that kind.
    """
    parts: list[dict[str, str]] = []
    for child in testcase.iterchildren():
        kind = _child_tag(child)
        if kind not in RESULT_PART_KINDS:
            continue
        parts.append(
            {
                "kind": kind,
                "type": child.attrib.get("type", "unknown"),
                "message": child.attrib.get(
                    "message", "" if kind == "failure" else "unknown"
                ),
                "text": child.text or "",
            }
        )
    return parts


def _collect_captured_output(xml_object: objectify.ObjectifiedElement, tag: str) -> str:
    """Join every ``<system-out>``/``<system-err>`` block of an element."""
    blocks = [
        child.text or ""
        for child in xml_object.iterchildren()
        if _child_tag(child) == tag
    ]
    return "\n".join(block for block in blocks if block)


def _numeric(path, element, name, convert):
    """The ``name`` attribute of ``element`` as ``convert`` (``int`` or ``float``) reads it.

    An absent attribute is ``-1``, the reader's long-standing sentinel. A value the
    conversion refuses is a :class:`ReportReadError` naming the element, the attribute and
    the value -- the report is refused as a whole.
    """
    value = element.attrib.get(name)
    if value is None:
        return convert(-1)
    try:
        return convert(value)
    except ValueError:
        kind = "an integer" if convert is int else "a number"
        raise ReportReadError(
            f'{path}: <{_child_tag(element)}> attribute {name}="{value}" is not {kind}'
        ) from None


class JUnitParser:
    def __init__(self, junit_xml, junit_xsd=None):
        self.junit_xml_path = junit_xml

        if junit_xsd is None:
            junit_xsd = os.path.join(os.path.dirname(__file__), "schemas", "JUnit.xsd")
        self.junit_xsd_path = junit_xsd

        self.junit_schema_doc = None
        self.xmlschema = None
        self.valid_xml = None

        if not os.path.exists(self.junit_xml_path):
            raise JUnitFileMissing(
                f"The given file does not exist: {self.junit_xml_path}"
            )
        try:
            self.junit_xml_doc = etree.parse(self.junit_xml_path)
        except etree.XMLSyntaxError as error:
            line, column = error.position
            # lxml's sentence ends with the position ours leads with: said once.
            message = error.msg
            suffix = f", line {line}, column {column}"
            if message.endswith(suffix):
                message = message[: -len(suffix)]
            raise ReportReadError(
                f"{self.junit_xml_path} (line {line}, column {column}): {message}"
            ) from error
        except OSError as error:
            # lxml reports bytes that are not valid in the document's encoding (and a
            # path it cannot read, such as a directory) as an OSError naming the file,
            # `Error reading file '<path>': …`; ours names it once.
            message = str(error)
            prefix = f"Error reading file '{self.junit_xml_path}': "
            if message.startswith(prefix):
                message = message[len(prefix) :]
            raise ReportReadError(f"{self.junit_xml_path}: {message}") from error

        self.junit_xml_string = etree.tostring(self.junit_xml_doc)
        self.junit_xml_object = objectify.fromstring(self.junit_xml_string)
        self.junit_xml_string = str(self.junit_xml_string)

    def validate(self):
        self.junit_schema_doc = etree.parse(self.junit_xsd_path)
        self.xmlschema = etree.XMLSchema(self.junit_schema_doc)
        self.valid_xml = self.xmlschema.validate(self.junit_xml_doc)

        return self.valid_xml

    def parse(self):
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed xml file for test results junit().

        :return: list of test suites as dictionaries
        """

        path = self.junit_xml_path

        def parse_testcase(xml_object):
            testcase = xml_object

            tc_dict = {
                "classname": testcase.attrib.get("classname", "unknown"),
                "file": testcase.attrib.get("file", "unknown"),
                "line": _numeric(path, testcase, "line", int),
                "name": testcase.attrib.get("name", "unknown"),
                "time": _numeric(path, testcase, "time", float),
                # googletest attributes; empty (never absent) so that consumers
                # can emit every field unconditionally.
                "timestamp": testcase.attrib.get("timestamp", ""),
                "value_param": testcase.attrib.get("value_param", ""),
                "type_param": testcase.attrib.get("type_param", ""),
            }

            # The result data is normally a subnode (e.g. skipped/failure).
            # We integrate it right into the testcase for better handling, and
            # keep *every* part -- the flat type/text/message keys below stay on
            # the first one for backwards compatibility.
            parts = _collect_result_parts(testcase)
            tc_dict["parts"] = parts

            first_part = next(
                (
                    part
                    for kind in RESULT_PART_KINDS
                    for part in parts
                    if part["kind"] == kind
                ),
                None,
            )
            if first_part is not None:
                # The part's `kind` is the name of the XML element the evidence
                # came from and stays that way -- the converter capitalises it
                # into the evidence heading. `result` is this package's
                # vocabulary, so it goes through the mapping.
                tc_dict["result"] = normalize_result(first_part["kind"])
                tc_dict["type"] = first_part["type"]
                # part text can be None for pytest xfail test cases
                tc_dict["text"] = first_part["text"]
                tc_dict["message"] = first_part["message"]
            else:
                # No result child at all, so the case either passed or never
                # ran; failures, errors and skips are all handled above.
                # googletest reports a disabled test as status="notrun"
                # (result="suppressed"), which otherwise reads as a pass.
                disabled = (
                    testcase.attrib.get("status") == "notrun"
                    or testcase.attrib.get("result") == "suppressed"
                )
                tc_dict["result"] = "disabled" if disabled else "passed"
                tc_dict["type"] = ""
                tc_dict["text"] = ""
                tc_dict["message"] = ""

            tc_dict["system-out"] = _collect_captured_output(testcase, "system-out")
            tc_dict["system-err"] = _collect_captured_output(testcase, "system-err")

            tc_dict["properties"] = _collect_properties(
                testcase, TESTCASE_KNOWN_ATTRIBUTES
            )

            return tc_dict

        def parse_testsuite(xml_object):
            testsuite = xml_object

            tests = _numeric(path, testsuite, "tests", int)
            errors = _numeric(path, testsuite, "errors", int)
            failures = _numeric(path, testsuite, "failures", int)

            # The first of the three spellings that carries a value; an empty one counts
            # as absent, as it did when this was an `or` chain.
            skips_name = next(
                (
                    name
                    for name in ("skips", "skip", "skipped")
                    if testsuite.attrib.get(name)
                ),
                None,
            )
            skips = (
                -1 if skips_name is None else _numeric(path, testsuite, skips_name, int)
            )

            passed = int(tests - sum(x for x in [errors, failures, skips] if x > 0))

            ts_dict = {
                "name": testsuite.attrib.get("name", "unknown"),
                "tests": tests,
                "errors": errors,
                "failures": failures,
                "skips": skips,
                "passed": passed,
                "time": _numeric(path, testsuite, "time", float),
                "testcases": [],
                "testsuite_nested": [],
            }

            ts_dict["properties"] = _collect_properties(
                testsuite, TESTSUITE_KNOWN_ATTRIBUTES
            )

            # A suite may hold nested suites AND test cases of its own: keep both. Two
            # independent steps, not `if … elif …`, which dropped the direct cases of every
            # suite that also held a nested one (#2050).
            if hasattr(testsuite, "testsuite"):
                for ts in testsuite.testsuite:
                    # dict from inner parse
                    inner_testsuite = parse_testsuite(ts)
                    ts_dict["testsuite_nested"].append(inner_testsuite)

            if hasattr(testsuite, "testcase"):
                for tc in testsuite.testcase:
                    new_testcase = parse_testcase(tc)
                    ts_dict["testcases"].append(new_testcase)

            return ts_dict

        # main flow starts here

        junit_dict = []

        if self.junit_xml_object.tag == "testsuites":
            # `<testsuites/>` holds no suite: an empty report, not `AttributeError: no
            # such child: testsuite` (#2052; ubCode reads it the same way).
            if hasattr(self.junit_xml_object, "testsuite"):
                for testsuite_xml_object in self.junit_xml_object.testsuite:
                    complete_testsuite = parse_testsuite(testsuite_xml_object)
                    junit_dict.append(complete_testsuite)
        else:
            complete_testsuite = parse_testsuite(self.junit_xml_object)
            junit_dict.append(complete_testsuite)

        return junit_dict

    def docutils_table(self):
        pass


class JUnitFileMissing(Exception):
    """The report path does not exist."""
