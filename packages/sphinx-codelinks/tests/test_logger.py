# Test suite for the environment-aware logging facade (issue #72).
import importlib
import logging

import pytest
import sphinx
from sphinx.util.logging import VERBOSE

from sphinx_codelinks import logger as logmod


@pytest.fixture(autouse=True)
def _reset_backend():
    """Each test starts and ends with the default (library) backend."""
    logmod.reset()
    logmod.logger.configure(verbose=False, quiet=False)
    yield
    logmod.reset()
    logmod.logger.configure(verbose=False, quiet=False)


def test_default_backend_drops_info_and_emits_warning(caplog):
    """As a plain library (no frontend configured), routine INFO is silently
    dropped while genuine warnings still propagate."""
    log = logmod.get_logger("sphinx_codelinks.analyse.sample")

    log.info("routine progress")
    log.warning("real problem", subtype="git_root")

    messages = [record.getMessage() for record in caplog.records]
    assert "routine progress" not in messages
    assert "real problem" in messages


def test_cli_backend_routes_info_to_stdout_and_warning_to_stderr(capsys):
    """CLI frontend: routine progress goes to stdout, warnings to stderr."""
    logmod.configure_cli(verbose=False, quiet=False)
    log = logmod.get_logger("sphinx_codelinks.analyse.sample")

    log.info("files loaded: 3")
    log.warning("git root not found", subtype="git_root")

    captured = capsys.readouterr()
    assert "files loaded: 3" in captured.out
    assert "files loaded: 3" not in captured.err
    assert "git root not found" in captured.err
    assert "git root not found" not in captured.out


def test_cli_backend_quiet_suppresses_info_but_keeps_warning(capsys):
    """--quiet hides routine progress but never hides warnings."""
    logmod.configure_cli(verbose=False, quiet=True)
    log = logmod.get_logger("sphinx_codelinks.analyse.sample")

    log.info("files loaded: 3")
    log.warning("git root not found", subtype="git_root")

    captured = capsys.readouterr()
    assert "files loaded: 3" not in captured.out
    assert "git root not found" in captured.err


def test_cli_backend_debug_is_gated_by_verbose(capsys):
    """CLI frontend: detailed debug output is hidden by default, shown with -v."""
    logmod.configure_cli(verbose=False, quiet=False)
    logmod.get_logger("sphinx_codelinks.analyse.sample").debug("breakdown detail")
    assert "breakdown detail" not in capsys.readouterr().out

    logmod.configure_cli(verbose=True, quiet=False)
    logmod.get_logger("sphinx_codelinks.analyse.sample").debug("breakdown detail")
    assert "breakdown detail" in capsys.readouterr().out


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_sphinx_backend_routes_through_sphinx_logging():
    """Sphinx frontend: info is default-visible (INFO), debug is -v only
    (VERBOSE), warnings carry the codelinks type/subtype; all under sphinx.*"""
    logmod.configure_sphinx()

    handler = _ListHandler()
    sphinx_logger = logging.getLogger("sphinx")
    sphinx_logger.addHandler(handler)
    old_level = sphinx_logger.level
    sphinx_logger.setLevel(VERBOSE)
    try:
        log = logmod.get_logger("sphinx_codelinks.analyse.sample")
        log.info("project summary")
        log.debug("breakdown detail")
        log.warning("git root not found", subtype="git_root", location="x.cpp")
    finally:
        sphinx_logger.removeHandler(handler)
        sphinx_logger.setLevel(old_level)

    # routed under the sphinx-prefixed namespace Sphinx actually captures
    assert all(
        rec.name == "sphinx.sphinx_codelinks.analyse.sample" for rec in handler.records
    )

    info_records = [r for r in handler.records if "project summary" in r.getMessage()]
    assert info_records and info_records[0].levelno == logging.INFO

    debug_records = [r for r in handler.records if "breakdown detail" in r.getMessage()]
    assert debug_records and debug_records[0].levelno == VERBOSE

    warn_records = [
        r for r in handler.records if "git root not found" in r.getMessage()
    ]
    assert warn_records
    assert warn_records[0].levelno == logging.WARNING
    assert getattr(warn_records[0], "type", None) == "codelinks"
    assert getattr(warn_records[0], "subtype", None) == "git_root"


ANALYSE_MODULE_LOGGERS = (
    "sphinx_codelinks.analyse.analyse",
    "sphinx_codelinks.analyse.oneline_parser",
    "sphinx_codelinks.analyse.projects",
    "sphinx_codelinks.analyse.utils",
)


def test_analyse_modules_install_no_handlers_at_import():
    """Regression guard for #72: importing the analyse layer must not install
    handlers or pin levels on its own loggers."""
    for name in ANALYSE_MODULE_LOGGERS:
        importlib.import_module(name)
        module_logger = logging.getLogger(name)
        assert module_logger.handlers == [], (
            f"{name} installed handlers at import: {module_logger.handlers}"
        )
        assert module_logger.level == logging.NOTSET, (
            f"{name} pinned its level at import to {module_logger.level}"
        )


class _StubSphinxLogger:
    """Records what ``_SphinxBackend.warning`` hands ``sphinx.util.logging``."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def warning(self, msg: str, **kwargs: object) -> None:
        self.warnings.append((msg, kwargs))


@pytest.fixture
def stub_sphinx_logger(monkeypatch):
    stub = _StubSphinxLogger()
    monkeypatch.setattr(logmod.sphinx_logging, "getLogger", lambda _name: stub)
    return stub


@pytest.mark.parametrize(
    ("subtype", "suffix"),
    [("git_root", " [codelinks.git_root]"), ("", " [codelinks]")],
)
def test_sphinx_backend_appends_the_type_only_when_sphinx_does_not(
    stub_sphinx_logger, subtype, suffix
):
    """Where the suffix is left to Sphinx (always from 8, before 8 when
    ``show_warning_types`` is on -- Sphinx then renders ``[type.subtype]``, or
    ``[type]`` for a warning without a subtype) the message is passed unchanged; where
    it is not, the backend appends it -- either way it is rendered at most once
    (#2091)."""
    backend = logmod._SphinxBackend()

    backend._leave_to_sphinx = True
    backend.warning("sphinx_codelinks.x", "a problem", subtype, "x.cpp")
    backend._leave_to_sphinx = False
    backend.warning("sphinx_codelinks.x", "a problem", subtype, "x.cpp")

    assert [msg for msg, _ in stub_sphinx_logger.warnings] == [
        "a problem",
        f"a problem{suffix}",
    ]
    assert all(
        kwargs == {"type": "codelinks", "subtype": subtype, "location": "x.cpp"}
        for _, kwargs in stub_sphinx_logger.warnings
    )


@pytest.mark.parametrize("show_warning_types", [True, False])
def test_configure_sphinx_follows_show_warning_types(
    stub_sphinx_logger, show_warning_types
):
    """``configure_sphinx`` is told the build's ``show_warning_types``: with it on,
    Sphinx renders the suffix on every version, so the backend appends none; with it
    off the backend appends it before Sphinx 8 only (8+ renders it by default)."""
    logmod.configure_sphinx(show_warning_types=show_warning_types)
    logmod.get_logger("sphinx_codelinks.x").warning("a problem", subtype="git_root")

    leave_to_sphinx = show_warning_types or sphinx.version_info >= (8,)
    expected = "a problem" if leave_to_sphinx else "a problem [codelinks.git_root]"
    assert [msg for msg, _ in stub_sphinx_logger.warnings] == [expected]
