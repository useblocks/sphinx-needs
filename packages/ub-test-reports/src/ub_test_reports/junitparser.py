"""
JUnit XML parser
"""

import os
from collections.abc import Callable
from typing import Any, Literal, TypeGuard, TypeVar

from lxml import etree, objectify  # ty: ignore[unresolved-import]

from ub_test_reports.errors import ReportReadError
from ub_test_reports.results import normalize_result

__all__ = [
    "LINE_BASES",
    "LINE_BASE_PROPERTY",
    "JUnitFileMissing",
    "JUnitParser",
    "LineBase",
    "ReportReadError",
    "is_line_base",
]

#: The ``<property>`` of a ``<testsuite>`` that says what its test cases' ``line`` counts
#: from: ``"1"``, or ``"0"``. The ub-test-reports pytest plugin writes ``"1"`` on every
#: suite it writes; any other producer may declare its base the same way. A wire name,
#: in the namespace of this package, beside the plugin's reserved case-level
#: ``sphinxcontrib.test_reports:file`` / ``:line``.
LINE_BASE_PROPERTY = "ub_test_reports:line_base"

#: What the base of an unmarked report's lines is read as: ``"auto"``, by the reader's
#: rule (:meth:`JUnitParser.parse`), or ``0`` / ``1`` for every unmarked suite. The
#: ``[test_reports] line_base`` key of ``ubproject.toml``.
LineBase = Literal["auto", 0, 1]

#: Every :data:`LineBase`, in the order they are documented.
LINE_BASES: tuple[LineBase, ...] = ("auto", 0, 1)

#: The suite name pytest writes unless ``junit_suite_name`` changes it, and the name it
#: always gives the root.
_PYTEST_SUITE = "pytest"
_PYTEST_ROOT = "pytest tests"


def is_line_base(value: object) -> TypeGuard[LineBase]:
    """Whether *value* is a :data:`LineBase`: ``"auto"``, or the integer ``0`` or ``1``
    (not ``True``, ``False``, ``1.0`` or ``"1"``)."""
    return (
        value == "auto"
        if isinstance(value, str)
        else (type(value) is int and value in (0, 1))
    )


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

#: What ``_numeric`` converts an attribute to: ``int`` or ``float``.
_Number = TypeVar("_Number", int, float)


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


def _numeric(
    path: str,
    element: objectify.ObjectifiedElement,
    name: str,
    convert: Callable[[str | int], _Number],
) -> _Number:
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
    """A JUnit XML report (pytest, Google Test, CTest and the other dialects), read into
    plain dictionaries by :meth:`parse`.

    :param junit_xml: The report's path.
    :param junit_xsd: The schema :meth:`validate` checks against; the bundled one by
        default.
    :param line_base: What an unmarked report's ``line`` counts from (a
        :data:`LineBase`): ``"auto"``, the reader's rule, or ``0`` / ``1``.
    :raises ValueError: for any other ``line_base``.
    """

    def __init__(
        self,
        junit_xml: str,
        junit_xsd: str | None = None,
        *,
        line_base: LineBase = "auto",
    ) -> None:
        if not is_line_base(line_base):
            raise ValueError(f"line_base must be 'auto', 0 or 1, got {line_base!r}")
        self.line_base: LineBase = line_base
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

    def validate(self) -> bool:
        self.junit_schema_doc = etree.parse(self.junit_xsd_path)
        self.xmlschema = etree.XMLSchema(self.junit_schema_doc)
        self.valid_xml = self.xmlschema.validate(self.junit_xml_doc)

        return self.valid_xml

    def parse(self, *, line_base_known: bool = False) -> list[dict[str, Any]]:
        """
        Creates a common python list of object, no matter what information are
        supported by the parsed xml file for test results junit().

        **A test case's** ``line`` **is a line of its file counted from 1** wherever the
        reader knows what the report counts from (#2381). pytest's own writer counts
        from 0, the ub-test-reports plugin and Google Test from 1, and nothing else
        tells their reports apart. So the base is decided per ``<testsuite>``, and a
        nested suite inherits its parent's:

        1. a suite's :data:`LINE_BASE_PROPERTY` property, ``"1"`` or ``"0"``, gives it
           (any other value is no mark);
        2. else a suite named ``pytest``, or the root ``<testsuites name="pytest
           tests">``, counts from 0, so its lines are read one more (pytest names the
           root so from 8.4.0 on: with an older pytest, a suite renamed with
           ``junit_suite_name`` falls under rule 4);
        3. else a test case carrying both of Google Test's ``status`` and ``result``
           attributes counts from 1, and is read as it is;
        4. else the line is passed through, and its base is not known.

        An explicit ``line_base`` (``0`` or ``1``) is the base of every suite without a
        mark, in place of rules 2 to 4: a mark still wins. A ``line`` below 0 is the "no
        line" sentinel and is never shifted, so ``-1`` stays ``-1``; a ``line`` of 0
        counted from 0 is line 1.

        For a pytest test the line is that of its first decorator, or of its ``def``
        (CPython's ``co_firstlineno``).

        :param line_base_known: Give each test case the key ``line_base_known``: whether
            the reader knew its base (``True`` by rules 1 to 3 and an explicit
            ``line_base``, ``False`` by rule 4). Where it is ``True``, a ``line`` of 1 or
            more is a line of the file, counted from 1. Off by default, so a caller
            that does not ask gets exactly the keys it always got: sphinx-test-reports
            3.0.1 and earlier turn every key they do not know into a need field.
        :return: list of test suites as dictionaries
        """
        with_known = line_base_known

        path = self.junit_xml_path
        root = self.junit_xml_object
        pytest_root = (
            root.tag == "testsuites" and root.attrib.get("name") == _PYTEST_ROOT
        )

        def suite_line_base(
            testsuite: objectify.ObjectifiedElement,
            properties: dict[str, str],
            inherited: int | None,
        ) -> int | None:
            """The base a suite's lines count from, ``None`` where it is not known."""
            mark = properties.get(LINE_BASE_PROPERTY)
            if mark in ("0", "1"):
                return int(mark)
            if inherited is not None:
                return inherited
            if self.line_base != "auto":
                return self.line_base
            if pytest_root or testsuite.attrib.get("name") == _PYTEST_SUITE:
                return 0
            return None

        def parse_testcase(
            xml_object: objectify.ObjectifiedElement, line_base: int | None
        ) -> dict[str, Any]:
            testcase = xml_object

            if line_base is None and (
                "status" in testcase.attrib and "result" in testcase.attrib
            ):
                line_base = 1
            line = _numeric(path, testcase, "line", int)
            if line_base == 0 and line >= 0:
                line += 1

            tc_dict = {
                "classname": testcase.attrib.get("classname", "unknown"),
                "file": testcase.attrib.get("file", "unknown"),
                "line": line,
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
            if with_known:
                tc_dict["line_base_known"] = line_base is not None

            return tc_dict

        def parse_testsuite(
            xml_object: objectify.ObjectifiedElement, inherited: int | None = None
        ) -> dict[str, Any]:
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
            line_base = suite_line_base(testsuite, ts_dict["properties"], inherited)

            # A suite may hold nested suites AND test cases of its own: keep both. Two
            # independent steps, not `if … elif …`, which dropped the direct cases of every
            # suite that also held a nested one (#2050).
            if hasattr(testsuite, "testsuite"):
                for ts in testsuite.testsuite:
                    # dict from inner parse
                    inner_testsuite = parse_testsuite(ts, line_base)
                    ts_dict["testsuite_nested"].append(inner_testsuite)

            if hasattr(testsuite, "testcase"):
                for tc in testsuite.testcase:
                    new_testcase = parse_testcase(tc, line_base)
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

    def docutils_table(self) -> None:
        pass


class JUnitFileMissing(Exception):
    """The report path does not exist."""
