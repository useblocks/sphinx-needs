# fmt: off
import os
from pathlib import Path

from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util import logging

# from docutils import nodes
# sphinx-needs ships no py.typed marker and no stubs exist, so every import
# from it is untyped to mypy. Nothing to fix on this side.
from sphinx_needs.api import (  # type: ignore[import-untyped]
    add_dynamic_function,
    add_need_type,
)
from sphinx_needs.exceptions import (  # type: ignore[import-untyped]
    NeedsApiConfigWarning,
)

from sphinxcontrib.test_reports.directives.test_case import TestCase, TestCaseDirective
from sphinxcontrib.test_reports.directives.test_env import EnvReport, EnvReportDirective
from sphinxcontrib.test_reports.directives.test_file import TestFile, TestFileDirective
from sphinxcontrib.test_reports.directives.test_report import (
    TestReport,
    TestReportDirective,
)
from sphinxcontrib.test_reports.directives.test_results import (
    TestResults,
    TestResultsDirective,
)
from sphinxcontrib.test_reports.directives.test_suite import (
    TestSuite,
    TestSuiteDirective,
)
from sphinxcontrib.test_reports.environment import install_styles_static_files
from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError
from sphinxcontrib.test_reports.fields import (
    FIELDS,
    RENAMEABLE_FIELDS,
    RESERVED_NAMES,
    declaration,
)
from sphinxcontrib.test_reports.functions import tr_link
from sphinxcontrib.test_reports.projectconfig import (
    BRIDGE_KEYS,
    DEFAULT_FIELD_NAMES,
    DEFAULT_TOML_FILENAME,
    SECTION,
    TomlConfigError,
    find_project_config,
    load_project_config,
)

# fmt: on

VERSION = "2.0.0"

try:
    # sphinx-needs >= 7.0: fields are registered through add_field.
    from sphinx_needs.api import add_field as _add_field

    def _register_field(app: Sphinx, name: str, role: str | None = None) -> None:
        type_, description = declaration(name, role)
        try:
            _add_field(name, description, schema={"type": type_})
        except NeedsApiConfigWarning:
            # Already registered, e.g. via needs_fields or needs_extra_options
            # in conf.py. Anything else is a real error and must surface.
            logging.getLogger(__name__).debug(
                f"Field '{name}' already registered, skipping"
            )

except ImportError:
    from sphinx_needs.api import add_extra_option as _add_extra_option

    def _register_field(app: Sphinx, name: str, role: str | None = None) -> None:
        # add_extra_option takes description and schema from sphinx-needs
        # 6.0.1 on, which is the package's floor.
        type_, description = declaration(name, role)
        try:
            _add_extra_option(
                app, name, description=description, schema={"type": type_}
            )
        except NeedsApiConfigWarning:
            logging.getLogger(__name__).debug(
                f"Field '{name}' already registered, skipping"
            )


def setup(app: Sphinx) -> dict[str, object]:
    """
    Setup following directives:
    * test_results
    * test_env
    * test_report
    """

    # Name of the need field carrying the path of the XML *report*.
    app.add_config_value("tr_file_option", DEFAULT_FIELD_NAMES["file_option"], "html")
    # Names of the need fields carrying the *test source* location taken from
    # the <testcase> file/line attributes. Defaults avoid the collision with
    # tr_file_option above; set both to "file"/"line" (and tr_file_option to
    # something else) to match a metamodel that spells them verbatim.
    app.add_config_value(
        "tr_source_file_option", DEFAULT_FIELD_NAMES["source_file_option"], "html"
    )
    app.add_config_value(
        "tr_source_line_option", DEFAULT_FIELD_NAMES["source_line_option"], "html"
    )
    # Derive test-case IDs from the source location and case name instead of
    # hashing (type, title, content) -- the latter moves the ID when a test
    # starts failing differently. Off by default: enabling it changes IDs.
    # Required (not just recommended) when the build consumes a needs.json
    # produced by `test-reports build needs`, which always writes them.
    app.add_config_value("tr_deterministic_case_ids", False, "html")
    # Declarative configuration: the [test_reports] section of this file
    # overrides the tr_* config values above at config-inited. The default is
    # searched for upwards from the confdir to the repository root; an explicit
    # value is resolved against the confdir and warns if it does not exist (the
    # build then runs on the conf.py configuration). None disables TOML reading
    # entirely -- which is why NoneType has to be an accepted type here, or
    # Sphinx's own check_confval_types warns about the documented way to switch
    # it off.
    app.add_config_value(
        "tr_config_from_toml",
        DEFAULT_TOML_FILENAME,
        "env",
        types=(str, type(None)),
    )

    log = logging.getLogger(__name__)
    log.info("Setting up sphinx-test-reports extension")

    # configurations
    # The default is Sphinx's confdir, a _StrPath. Without explicit types, a
    # plain string -- the only thing TOML or a string literal in conf.py can
    # supply -- fails Sphinx's check_confval_types ("has type 'str', defaults
    # to '_StrPath'") and takes a -W build down. Every consumer accepts both.
    app.add_config_value("tr_rootdir", app.confdir, "html", types=(str, os.PathLike))
    app.add_config_value(
        "tr_file",
        ["test-file", "testfile", "Test-File", "TF_", "#ffffff", "node"],
        "html",
    )
    app.add_config_value(
        "tr_suite",
        ["test-suite", "testsuite", "Test-Suite", "TS_", "#cccccc", "folder"],
        "html",
    )
    app.add_config_value(
        "tr_case",
        ["test-case", "testcase", "Test-Case", "TC_", "#999999", "rectangle"],
        "html",
    )

    # adds option for custom template
    template_dir = os.path.join(
        os.path.dirname(__file__), "directives/test_report_template.txt"
    )
    app.add_config_value("tr_report_template", template_dir, "html")

    app.add_config_value("tr_suite_id_length", 3, "html")
    app.add_config_value("tr_case_id_length", 5, "html")
    app.add_config_value("tr_import_encoding", "utf8", "html")
    app.add_config_value("tr_extra_options", [], "env")
    app.add_config_value("tr_property_link_types", {}, "env")

    json_mapping = {
        "json_config": {
            "testsuite": {
                "name": (["name"], "unknown"),
                "tests": (["tests"], "unknown"),
                "errors": (["errors"], "unknown"),
                "failures": (["failures"], "unknown"),
                "skips": (["skips"], "unknown"),
                "passed": (["passed"], "unknown"),
                "time": (["time"], "unknown"),
                "testcases": (["testcase"], "unknown"),
            },
            "testcase": {
                "name": (["name"], "unknown"),
                "classname": (["classname"], "unknown"),
                "file": (["file"], "unknown"),
                "line": (["line"], "unknown"),
                "time": (["time"], "unknown"),
                "result": (["result"], "unknown"),
                "type": (["type"], "unknown"),
                "text": (["text"], "unknown"),
                "message": (["message"], "unknown"),
                "system-out": (["system-out"], "unknown"),
            },
        }
    }

    app.add_config_value("tr_json_mapping", json_mapping, "html", types=[dict])

    # nodes
    app.add_node(TestResults)
    app.add_node(TestFile)
    app.add_node(TestSuite)
    app.add_node(TestCase)
    app.add_node(TestReport)
    app.add_node(EnvReport)

    # directives
    app.add_directive("test-results", TestResultsDirective)
    app.add_directive("test-env", EnvReportDirective)
    app.add_directive("test-report", TestReportDirective)

    # events
    app.connect("env-updated", install_styles_static_files)
    # The TOML bridge must run BEFORE tr_preparation and sphinx_needs_update,
    # which read the values it writes. Spelled as an explicit priority rather
    # than relying on registration order, so reordering these lines cannot
    # silently break it. (Sphinx's own check_confval_types sits at 800, so it
    # still validates what the bridge wrote.)
    app.connect("config-inited", load_toml_config, priority=100)
    app.connect("config-inited", tr_preparation)
    app.connect("config-inited", sphinx_needs_update)

    app.connect("builder-inited", register_tr_extra_options)

    return {
        "version": VERSION,  # identifies the version of our extension
        "parallel_read_safe": True,  # support parallel modes
        "parallel_write_safe": True,
    }


def register_tr_extra_options(app: Sphinx) -> None:
    """Register extra options with directives."""

    log = logging.getLogger(__name__)
    tr_extra_options = getattr(app.config, "tr_extra_options", [])
    log.debug(f"tr_extra_options = {tr_extra_options}")

    if tr_extra_options:
        for direc in [TestSuiteDirective, TestFileDirective, TestCaseDirective]:
            # docutils types `option_spec` as optional on the directive base
            # class. All three define one, so this keeps mutating the existing
            # mapping; the assignment only matters in the case the type allows
            # for and the classes do not produce.
            spec = direc.option_spec or {}
            for option_name in tr_extra_options:
                spec[option_name] = directives.unchanged
                log.debug(f"Registered {option_name} with {direc}")
                log.debug(f"{direc}.option_spec now has keys: {list(spec.keys())}")
            direc.option_spec = spec


def _command_line_overrides(config: Config) -> set[str]:
    """Config value names given on the command line with ``-D``.

    Sphinx materialises those overrides *before* ``config-inited`` is emitted,
    so a plain ``setattr`` here would silently win over them. The mapping is
    spelled ``_overrides`` on newer Sphinx and ``overrides`` before that.
    """
    overrides = getattr(config, "_overrides", None)
    if overrides is None:
        overrides = getattr(config, "overrides", None)
    return set(overrides or ())


def load_toml_config(app: Sphinx, config: Config) -> None:
    """Apply the ``[test_reports]`` section of the declarative config file.

    Connected at a priority ahead of every other ``config-inited`` handler of
    this extension, so the bridged values are in place when the directives and
    the sphinx-needs registration read them.

    Precedence is ``-D`` > TOML > ``conf.py`` > built-in default, mirroring the
    CLI's flag > TOML > default. The file is the declarative source of truth
    and conf.py the fallback, but ``-D`` stays the per-invocation escape hatch:
    a key given there is left alone, because Sphinx has already applied it by
    the time this runs.

    Only :data:`BRIDGE_KEYS` reach the config values; the conversion-only keys
    (``project``, ``version``, ...) belong to the CLI and are skipped here.
    """
    setting = config.tr_config_from_toml
    if setting is None:
        return

    log = logging.getLogger(__name__)
    confdir = Path(app.confdir)
    if setting == DEFAULT_TOML_FILENAME:
        # The shared file conventionally sits at the project root while conf.py
        # sits in docs/, so search upwards -- anchoring at the confdir alone
        # would leave the root file unread by the build while the CLI, started
        # at the root, reads it.
        # A fruitless search is not a warning -- most projects have no file
        # -- but it says where it ended (visible with -v), so a misplaced file
        # does not fail silently.
        path = find_project_config(confdir, setting, report=log.verbose)
        if path is None:
            return
    else:
        path = Path(confdir, setting)
        if not path.is_file():
            log.warning(
                f"tr_config_from_toml points at {path}, which does not exist; "
                f"building with the conf.py configuration instead.",
                type="test_reports",
                subtype="missing_config",
            )
            return

    def warn(message: str) -> None:
        log.warning(message, type="test_reports", subtype="unknown_key")

    try:
        section = load_project_config(path, warn)
    except TomlConfigError as error:
        raise InvalidConfigurationError(str(error)) from error

    if not section:
        return

    overridden = _command_line_overrides(config)
    applied = []
    skipped = []
    for key in BRIDGE_KEYS:
        if key not in section:
            continue
        name = f"tr_{key}"
        if name in overridden:
            skipped.append(name)
            continue
        setattr(config, name, section[key])
        applied.append(key)
    if applied:
        log.info(f"Applied {', '.join(sorted(applied))} from {path}")
    if skipped:
        log.info(
            f"Kept the -D value of {', '.join(sorted(skipped))} over "
            f"[{SECTION}] in {path}"
        )


def tr_preparation(app: Sphinx, *args: object) -> None:
    """
    Prepares needed vars in the app context.
    """
    # `tr_types` is attached to the application object, which has no such
    # attribute as far as a type checker is concerned -- the directives read it
    # back the same way (see `test_common.py`). One narrow ignore for the
    # attachment; the rest of the function works on a typed mapping.
    types: dict[str, list[str]] = getattr(app, "tr_types", None) or {}
    app.tr_types = types  # type: ignore[attr-defined]

    # Collects the configured test-report node types
    types[app.config.tr_file[0]] = app.config.tr_file[1:]
    types[app.config.tr_suite[0]] = app.config.tr_suite[1:]
    types[app.config.tr_case[0]] = app.config.tr_case[1:]

    app.add_directive(app.config.tr_file[0], TestFileDirective)
    app.add_directive(app.config.tr_suite[0], TestSuiteDirective)
    app.add_directive(app.config.tr_case[0], TestCaseDirective)


def check_field_name_collisions(config: Config) -> None:
    """Reject configurations where a field option names a field already taken.

    The report path and the test-source location are separate fields; if two
    options resolve to one name, or one of them to a fixed field such as
    ``case`` or ``result``, ``add_need`` receives the same keyword twice and
    fails with a bare ``TypeError`` from inside a directive. The loader makes
    the same check for the declarative file; this covers ``conf.py``.
    """
    options = {
        "tr_file_option": getattr(config, "tr_file_option", "file"),
        "tr_source_file_option": getattr(config, "tr_source_file_option", "case_file"),
        "tr_source_line_option": getattr(config, "tr_source_line_option", "case_line"),
    }

    for name, value in options.items():
        if value in RESERVED_NAMES:
            raise InvalidConfigurationError(
                f"{name} is set to '{value}', a field every test-case need has "
                f"already; it must name a field of its own."
            )
        clashing = [
            other
            for other, other_value in options.items()
            if other != name and other_value == value
        ]
        if clashing:
            raise InvalidConfigurationError(
                f"{name} and {', '.join(sorted(clashing))} are all set to "
                f"'{value}'; each must name a different need field."
            )


def sphinx_needs_update(app: Sphinx, config: Config) -> None:
    """
    sphinx-needs configuration
    """

    check_field_name_collisions(config)

    # sphinx-needs >= 6 registers fields with a schema; there is no older
    # branch to keep, the package requires that version.
    #
    # Type and description of every field come from the shared table in
    # `fields`, which the converter writes into the `needs_schema` of the
    # needs.json it produces -- a field registered here and the same field
    # declared there cannot say different things. `result_text` and
    # `remote_url` are written by the converter only, and registered here so
    # that a needs.json it produced imports without sphinx-needs dropping them
    # as unknown keys.
    # The renameable fields are registered under the name their `tr_*` value
    # selects -- spelled like the role with the prefix, as every bridged key is.
    for role in RENAMEABLE_FIELDS:
        name = getattr(config, f"tr_{role}", DEFAULT_FIELD_NAMES[role])
        _register_field(app, name, role=role)
    for name in FIELDS:
        _register_field(app, name)
    # Extra dynamic functions
    # For details about usage read
    # https://sphinx-needs.readthedocs.io/en/latest/api.html#sphinx_needs.api.configuration.add_dynamic_function
    add_dynamic_function(app, tr_link)

    # Register tr_extra_options as sphinx-needs fields so that properties
    # extracted from JUnit XML are accepted by sphinx-needs
    tr_extra_options = getattr(config, "tr_extra_options", [])
    for option_name in tr_extra_options:
        _register_field(app, option_name)

    # Extra need types
    # For details about usage read
    # https://sphinx-needs.readthedocs.io/en/latest/api.html#sphinx_needs.api.configuration.add_need_type
    add_need_type(app, *app.config.tr_file[1:])
    add_need_type(app, *app.config.tr_suite[1:])
    add_need_type(app, *app.config.tr_case[1:])
