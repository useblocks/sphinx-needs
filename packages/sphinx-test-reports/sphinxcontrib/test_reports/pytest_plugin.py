"""pytest plugin: shape the JUnit XML the way this extension reads it.

Enable it with ``-p sphinxcontrib.test_reports.pytest_plugin`` (or in
``addopts``) and write the report with ``--junitxml`` under
``junit_family = xunit1``. Two things then happen to every ``<testcase>``:

* its ``file``/``line`` attributes -- the source location that the directives
  put into ``tr_source_file_option``/``tr_source_line_option`` and that a
  deterministic case ID is derived from -- are the ones an editor shows. pytest
  writes the two under ``xunit1`` on its own, but counts the line from 0, keeps
  Bazel's runfiles prefix and has no way to point a case at the file that drove
  it; the plugin corrects the first two and adds the third
  (:func:`apply_test_metadata`). Under the default ``xunit2`` pytest drops both
  attributes, which is why ``xunit1`` is required;
* the properties given with :func:`add_test_properties` (or, for parameterised
  tests, :func:`apply_test_metadata`) are written as ``<properties>``, which the
  directives turn into need fields (``tr_extra_options``) and link fields
  (``tr_property_link_types``) pointing at the requirements a test verifies.

Which keywords the two helpers know, the ``<property>`` name each is written
under and whether it takes a list is configuration, not code: the
``test_reports_properties`` ini option, one line per property (see
:func:`parse_properties`). The plugin ships no metamodel of its own; S-CORE's
is a four-line example in the docs.

Both things happen through hooks on the test reports, not through fixtures, so
a case that is skipped or errors during setup is shaped like one that ran, and
under pytest-xdist the location is written on the controller, where pytest
keeps the XML writer.

Ported from the ``score_pytest`` attribute plugin of S-CORE's docs-as-code.
With that example configured the XML comes out the same, with four exceptions:
a case skipped or erroring at setup carries its location and properties here
and pytest's stock values there; the properties keep the order of the keywords
rather than a fixed one; the Bazel prefix is cut at a whole ``_main`` component
only; and a file handed to :func:`apply_test_metadata` is cut the same way
rather than passed through. Two of that plugin's rules are not ported: the
``TestType``/``DerivationTechnique`` vocabularies are documented, not enforced,
and a test does not have to carry a docstring -- both are process rules of that
project, not of this tool.

This module imports pytest and nothing else from the package's Sphinx side; it
is only ever loaded by pytest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generator, Mapping, Sequence

import pluggy
import pytest

if TYPE_CHECKING:
    from _pytest.junitxml import LogXML

#: Name of the marker :func:`add_test_properties` attaches. Registered in
#: :func:`pytest_configure` so ``--strict-markers`` accepts it.
MARKER = "test_properties"

#: The ini option holding the property model, one line per property.
OPTION = "test_reports_properties"

#: How one line of :data:`OPTION` reads.
GRAMMAR = "keyword [= XmlName] [, list]"

#: One line of :data:`OPTION`: a keyword, an optional ``= XmlName`` and an
#: optional ``, flag``; ``flag`` is checked afterwards so the message can name
#: it.
_LINE = re.compile(
    r"^\s*(?P<keyword>[^\s=,]+)\s*(?:=\s*(?P<name>[^\s=,]+)\s*)?(?:,\s*(?P<flag>[^\s,]+)\s*)?$"
)

#: Bazel runs a test from a runfiles tree in which the workspace is the
#: directory ``_main``: ``../_main/pkg/test_x.py`` names ``pkg/test_x.py``. Only
#: a whole path component counts -- ``app_main/`` is somebody's directory -- and
#: the last one wins, since under bzlmod the execroot's workspace directory is
#: ``_main`` as well.
_RUNFILES_PREFIX = re.compile(r"^(?:.*[\\/])?_main[\\/]")

#: The location override of :func:`apply_test_metadata` travels with the test
#: report as two entries of its ``user_properties`` under these names, and is
#: taken out again before pytest writes the properties -- on the process that
#: holds the XML writer, which under pytest-xdist is the controller, not the
#: worker the test ran on. Maps the entry name to the attribute it sets.
_OVERRIDES = {
    "sphinxcontrib.test_reports:file": "file",
    "sphinxcontrib.test_reports:line": "line",
}

#: Registration name of the per-session hook object, :class:`_XmlShape`.
_HOOKS = "sphinxcontrib.test_reports.xml_shape"

Recorder = Callable[[str, str], None]

#: What a property keyword accepts: one value, or -- for a multi-valued
#: property -- a sequence of values. ``None`` and empty values are not written.
Value = str | Sequence[str] | None


@dataclass(frozen=True)
class Property:
    """How one keyword of :func:`add_test_properties` reaches the XML."""

    #: The ``<property name="...">`` written.
    name: str
    #: Multi-valued: a sequence of strings is joined with ``", "``, which
    #: ``tr_property_link_types`` splits again on the build side; a bare string
    #: counts as one value. A single-valued property takes one value, and a
    #: sequence is an error rather than a silent join.
    multi: bool = False


#: Keyword -> how it is written: the model of :data:`OPTION`, installed by
#: :func:`pytest_configure` for the duration of the session (an inner session
#: gets its own and hands the outer one back). A keyword not found here is
#: written under its own name and takes a single value only.
PROPERTIES: dict[str, Property] = {}

#: The models of the sessions an in-process inner session interrupted.
_OUTER_MODELS: list[dict[str, Property]] = []


def parse_properties(lines: Sequence[str]) -> dict[str, Property]:
    """The property model declared by the lines of :data:`OPTION`.

    Each line reads ``keyword [= XmlName] [, list]``: *keyword* is what a test
    writes, *XmlName* the ``<property>`` name it is written under (the keyword
    itself when omitted), and ``list`` marks a multi-valued property. Blank
    lines are skipped. S-CORE's model, for example::

        test_reports_properties =
            partially_verifies = PartiallyVerifies, list
            fully_verifies = FullyVerifies, list
            test_type = TestType
            derivation_technique = DerivationTechnique

    :raises ValueError: for a line outside the grammar, a flag other than
        ``list``, a keyword declared twice, or two keywords sharing an XML name.
    """
    model: dict[str, Property] = {}
    for line in lines:
        if not line.strip():
            continue
        match = _LINE.match(line)
        if match is None:
            raise ValueError(
                f"{OPTION}: cannot read {line.strip()!r}; a line is '{GRAMMAR}'"
            )
        keyword, name, flag = match.group("keyword", "name", "flag")
        if flag not in (None, "list"):
            raise ValueError(
                f"{OPTION}: unknown flag {flag!r} in {line.strip()!r}; the only "
                "flag is 'list'"
            )
        if keyword in model:
            raise ValueError(f"{OPTION}: {keyword!r} is declared twice")
        name = name or keyword
        if any(existing.name == name for existing in model.values()):
            raise ValueError(
                f"{OPTION}: {name!r} is the XML name of two keywords; one "
                "property, one line"
            )
        model[keyword] = Property(name, multi=flag == "list")
    return model


def _lookup(keyword: str) -> Property | None:
    """The configured property for *keyword*.

    A declared keyword first; failing that, a property whose XML name is
    spelled like *keyword*, so the XML name doubles as keyword.
    """
    configured = PROPERTIES.get(keyword)
    if configured is not None:
        return configured
    return next((p for p in PROPERTIES.values() if p.name == keyword), None)


def _serialise(keyword: str, configured: Property | None, value: object) -> str | None:
    """The text written for *value*, or ``None`` when there is nothing to write.

    Strict about shape, because the build side splits a link property on
    commas and turns every piece into a need ID: what is not a string, or a
    list of strings under a ``list`` property, is a ``TypeError`` rather than
    a ``repr`` that becomes bogus IDs.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        raise TypeError(f"{keyword!r} takes a string, not {type(value).__name__}")
    if isinstance(value, Sequence):
        # Empty items first: a parser handing back [] for an absent field has
        # nothing to write under any keyword, so no arity applies.
        items: list[str] = []
        for index, item in enumerate(value):
            if item is None or item == "":
                continue
            if not isinstance(item, str):
                raise TypeError(
                    f"item {index} of {keyword!r} is {type(item).__name__}, not "
                    "str; every item of a list is one value"
                )
            items.append(item)
        if not items:
            return None
        if configured is None:
            raise TypeError(
                f"{keyword!r} is not a configured property and takes a single "
                f"value; a line '{keyword}, list' in {OPTION} lets it write a list"
            )
        if not configured.multi:
            raise TypeError(
                f"{keyword!r} takes a single value, not a sequence; declare it "
                f"'{keyword} = {configured.name}, list' in {OPTION} for lists"
            )
        return ", ".join(items)
    raise TypeError(
        f"{keyword!r} takes a string"
        + (" or a list of strings" if configured and configured.multi else "")
        + f", not {type(value).__name__}"
    )


def _normalise(properties: Mapping[str, object]) -> dict[str, str]:
    """The XML properties for keyword/value pairs; empty values dropped."""
    written: dict[str, str] = {}
    for keyword, value in properties.items():
        configured = _lookup(keyword)
        text = _serialise(keyword, configured, value)
        if text is not None:
            written[configured.name if configured else keyword] = text
    return written


def _empty(value: object) -> bool:
    """Whether :func:`_serialise` would write nothing for a well-formed *value*.

    ``None``, ``""`` and a sequence holding nothing else are empty. Anything
    else is not -- a list holding a list is not empty, it is wrong, and
    :func:`_serialise` says so.
    """
    if value is None or value == "":
        return True
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return all(item is None or item == "" for item in value)
    return False


def properties_mapping(**properties: Value) -> dict[str, str]:
    """The property mapping that ends up in the XML, empty values dropped.

    Single source of truth for the decorator and the runtime helper. How a
    value is written is decided by the configured model (:data:`PROPERTIES`),
    not by the keyword it arrived under.

    :raises ValueError: when nothing would be written.
    :raises TypeError: for a sequence under a single-valued or unconfigured
        keyword, a list item that is not a string, or a value of another kind.
    """
    cleaned = _normalise(properties)
    if not cleaned:
        raise ValueError("no test properties given: every value is empty")
    return cleaned


def add_test_properties(
    **properties: Value,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Decorator recording requirement links and classification for a test.

    With S-CORE's model configured (see the docs)::

        @add_test_properties(
            partially_verifies=["REQ_1", "REQ_2"],
            test_type="requirements-based",
            derivation_technique="requirements-analysis",
        )
        def test_addition():
            ...

    The keywords are the ones ``test_reports_properties`` declares; any other
    keyword is written under its own name with a single value. The values are
    kept as given and written when the test is set up, against the model known
    then, so the decorator itself does not depend on configuration having been
    read. A call that would write nothing is refused here, at import time.
    """
    if all(_empty(value) for value in properties.values()):
        raise ValueError("no test properties given: every value is empty")
    marker = getattr(pytest.mark, MARKER)

    def decorator(function: Callable[..., object]) -> Callable[..., object]:
        decorated: Callable[..., object] = marker(dict(properties))(function)
        return decorated

    return decorator


def apply_test_metadata(
    *,
    record_property: Recorder,
    metadata: Mapping[str, object],
    record_xml_attribute: Recorder | None = None,
    file: str | None = None,
    line: int | None = None,
) -> None:
    """Runtime equivalent of :func:`add_test_properties`.

    For tests whose metadata is only known inside the test body -- typically a
    parameterised test driven by files that carry their own metadata. Call it
    *early*, before any assertion, so the properties are attached even when the
    test then fails. *metadata* uses the decorator's keywords as keys; metadata
    without a value -- absent, or with nothing but empty entries -- writes no
    properties and is not an error.

    *file* and *line* override the location the plugin recorded, so a case can
    point at the file that drove it rather than at the test function. The
    override travels with the test report as two ``user_properties`` entries,
    ``sphinxcontrib.test_reports:file`` and ``sphinxcontrib.test_reports:line``,
    and is applied where the XML is written, so it holds under pytest-xdist as
    well; the plugin takes the two entries out before the properties are
    written, so a property recorded under either name is read as an override.
    *record_xml_attribute* is accepted for calls written against
    ``score_pytest`` and ignored -- and requesting that fixture is what draws
    pytest's experimental-feature notice, so drop it from the signature.
    """
    for name, value in _normalise(metadata).items():
        record_property(name, value)
    if file is not None:
        record_property("sphinxcontrib.test_reports:file", clean_source_path(file))
    if line is not None:
        record_property("sphinxcontrib.test_reports:line", str(line))


def clean_source_path(path: str) -> str:
    """The workspace-relative source path of a test.

    pytest reports locations relative to its rootdir already; under Bazel the
    rootdir sits inside a runfiles tree, so the path leads through ``_main``,
    the workspace directory of that tree -- as does an absolute path handed to
    :func:`apply_test_metadata`. Everything up to and including the last
    ``_main/`` component is cut.
    """
    return _RUNFILES_PREFIX.sub("", path, count=1)


class TestReportsConfigWarning(pytest.PytestWarning):
    """A run configured such that the plugin cannot write the full XML shape.

    Issued once at start-up. Where the project turns warnings into errors
    (``filterwarnings = error``, ``-W error``) it becomes a clean usage error
    rather than a traceback;
    ``ignore::sphinxcontrib.test_reports.pytest_plugin.TestReportsConfigWarning``
    silences it.
    """


def _report_family(config: pytest.Config) -> str | None:
    """The ``junit_family`` of the report this run writes, ``None`` without one.

    ``legacy`` is pytest's alias of ``xunit1``. The option does not exist under
    ``-p no:junitxml``.
    """
    if not getattr(config.option, "xmlpath", None):
        return None
    family = str(config.getini("junit_family"))
    return "xunit1" if family == "legacy" else family


def _notify(config: pytest.Config, message: str) -> None:
    """Issue *message* as :class:`TestReportsConfigWarning` at configure time."""
    warning = TestReportsConfigWarning(
        f"sphinxcontrib.test_reports.pytest_plugin: {message}"
    )
    try:
        config.issue_config_time_warning(warning, stacklevel=3)
    except TestReportsConfigWarning as error:
        # The project's filters make warnings errors; raised out of
        # pytest_configure this would be an INTERNALERROR traceback.
        raise pytest.UsageError(str(error)) from None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        OPTION,
        type="linelist",
        help=f"Properties add_test_properties() knows, one '{GRAMMAR}' per line; "
        "the sphinx-test-reports docs, page 'pytest plugin', have the details.",
    )


def pytest_configure(config: pytest.Config) -> None:
    # First thing: pytest_unconfigure pops whatever happens here, so a session
    # that fails to configure (a bad ini line) must have pushed already.
    _OUTER_MODELS.append(dict(PROPERTIES))
    config.addinivalue_line(
        "markers",
        f"{MARKER}(properties): properties written to the JUnit XML of the "
        "test; attached by sphinxcontrib.test_reports.pytest_plugin.add_test_properties",
    )
    lines: Sequence[str] = config.getini(OPTION)
    try:
        model = parse_properties(lines)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None
    PROPERTIES.clear()
    PROPERTIES.update(model)
    config.pluginmanager.register(_XmlShape(config), name=_HOOKS)

    family = _report_family(config)
    # Once per run: an xdist worker has the same options, and its own notice
    # would only repeat the controller's.
    if family is not None and family != "xunit1" and not hasattr(config, "workerinput"):
        _notify(
            config,
            f"junit_family is {family!r}, but pytest writes the file/line "
            "attributes of a <testcase> only under 'xunit1'. Set junit_family = "
            "xunit1, or the test cases will have no source location.",
        )


def pytest_unconfigure(config: pytest.Config) -> None:
    config.pluginmanager.unregister(name=_HOOKS)
    PROPERTIES.clear()
    if _OUTER_MODELS:
        PROPERTIES.update(_OUTER_MODELS.pop())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pluggy.Result[pytest.TestReport], None]:
    """Attach the markers' properties to the item before its setup report is made.

    A hook rather than a fixture, so a case that is skipped or errors during
    setup carries them too. The report copies the item's ``user_properties``,
    which is how they reach the XML writer -- across the wire under xdist. A
    value of the wrong shape turns the setup report into an error for that
    case, with the message.
    """
    problem: Exception | None = None
    if call.when == "setup":
        try:
            item.user_properties.extend(_marked_properties(item).items())
        except (TypeError, pytest.UsageError) as error:
            problem = error
    outcome = yield
    if problem is not None:
        report = outcome.get_result()
        message = f"{type(problem).__name__}: {problem}"
        # Appended, not replacing: a fixture that failed in the same setup
        # stays visible, so both problems show at once.
        existing = report.longreprtext
        report.longrepr = f"{existing}\n\n{message}" if existing else message
        report.outcome = "failed"


class _XmlShape:
    """The per-session hooks that shape pytest's XML writer's output.

    Registered by :func:`pytest_configure` so that they hold the session's
    config. They act on the process that owns the XML writer: in a plain run
    this one, under pytest-xdist the controller, where the workers' reports
    arrive.
    """

    def __init__(self, config: pytest.Config) -> None:
        self.config = config

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # tryfirst: before pytest's junitxml handler reads the report's
        # user_properties, the override entries have to be gone from them.
        # A worker forwards its reports untouched; the controller does this.
        if hasattr(self.config, "workerinput"):
            return
        overrides = [
            (name, value)
            for name, value in report.user_properties
            if name in _OVERRIDES
        ]
        if overrides:
            report.user_properties[:] = [
                entry for entry in report.user_properties if entry[0] not in _OVERRIDES
            ]
        xml = _xml_writer(self.config)
        if xml is None or _report_family(self.config) != "xunit1":
            return
        reporter = xml.node_reporter(report)
        if report.when == "setup":
            path, line_number, _domain = report.location
            reporter.add_attribute("file", clean_source_path(path))
            if line_number is not None:
                # pytest's line numbers are 0-based; editors and the report
                # count from 1.
                reporter.add_attribute("line", str(line_number + 1))
        for name, value in overrides:
            reporter.add_attribute(_OVERRIDES[name], str(value))


def _xml_writer(config: pytest.Config) -> LogXML | None:
    """pytest's XML writer of this run: ``None`` without ``--junitxml``, under
    ``-p no:junitxml``, and on an xdist worker, where pytest does not build it.

    The writer is what the ``record_xml_attribute`` fixture talks to as well;
    it lives behind a private key, so its absence is handled, not assumed.
    """
    try:
        from _pytest.junitxml import xml_key
    except ImportError:  # pragma: no cover -- pytest moved its junitxml plugin
        return None
    return config.stash.get(xml_key, None)


def _marked_properties(node: pytest.Item) -> dict[str, str]:
    """The properties of every ``test_properties`` marker on *node*, merged.

    Each marker carries the keywords as the decorator received them; they are
    written here, against the configured model. A marker on the class or the
    module counts as much as one on the function; where two set the same
    property, the one closest to the function wins.
    """
    merged: dict[str, str] = {}
    for marker in node.iter_markers(MARKER):  # closest first
        arguments: tuple[object, ...] = marker.args
        if not arguments or not isinstance(arguments[0], Mapping):
            raise pytest.UsageError(
                f"marker '{MARKER}' on {node.name} carries no property mapping; "
                "attach it with add_test_properties(...)"
            )
        given: Mapping[object, object] = arguments[0]
        for name, value in _normalise(
            {str(keyword): value for keyword, value in given.items()}
        ).items():
            merged.setdefault(name, value)
    return merged
