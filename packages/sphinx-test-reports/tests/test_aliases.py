"""The pre-3.0 import name still works where it is aliased, and nowhere else.

``sphinxcontrib.test_reports`` keeps four names until 4.0: the package itself as a Sphinx
extension, which warns through Sphinx's logger as ``[test_reports.deprecated]``, and the
``pytest_plugin``, ``junitparser`` and ``jsonparser`` modules, which ARE the real modules
and raise one ``FutureWarning`` at the importing line. Every other old module name fails
as an ordinary missing module.

The module tests run where the documentation toolchain is not installed (the
``toolchain-free`` CI job runs this file against the BUILT wheel); the builds carry the
``toolchain`` mark.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path
from unittest import mock

import pytest

import sphinx_test_reports

OLD = "sphinxcontrib.test_reports"
NEW = "sphinx_test_reports"

#: The aliased modules, each with one public name to check identity and patching by.
ALIASES = {
    "pytest_plugin": "add_test_properties",
    "junitparser": "JUnitParser",
    "jsonparser": "JsonParser",
}

#: Every other module of the real package, walked rather than listed, so a module added
#: later is covered without anyone remembering this file. Read off the files rather than
#: through `pkgutil`, which imports each subpackage -- and `directives` imports Sphinx.
_ROOT = Path(sphinx_test_reports.__file__).parent
UNALIASED = sorted(
    name
    for name in (
        ".".join(path.relative_to(_ROOT).with_suffix("").parts).removesuffix(
            ".__init__"
        )
        for path in _ROOT.rglob("*.py")
        if path.name != "__init__.py" or path.parent != _ROOT
    )
    if name not in ALIASES
)


def _forget(module: str) -> None:
    """Drop the OLD name from the import system, so the next import runs the alias again."""
    sys.modules.pop(f"{OLD}.{module}", None)
    parent = sys.modules.get(OLD)
    if parent is not None and module in vars(parent):
        delattr(parent, module)


def _import_old(module: str) -> tuple[object, list[warnings.WarningMessage]]:
    """Import the old name from a frame whose file is ``<caller>``, recording warnings."""
    _forget(module)
    namespace: dict[str, object] = {}
    code = compile(f"import {OLD}.{module} as imported\n", "<caller>", "exec")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(code, namespace)
    return namespace["imported"], caught


@pytest.fixture(autouse=True)
def _restore_old_names():
    """Leave the old names as the test found them."""
    before = {k: v for k, v in sys.modules.items() if k.startswith(OLD)}
    yield
    for key in [k for k in sys.modules if k.startswith(OLD)]:
        if key not in before:
            del sys.modules[key]
    sys.modules.update(before)


def test_every_real_module_is_either_aliased_or_walked() -> None:
    # the fence's fence: an empty walk would make the unaliased tests pass vacuously
    assert "identity" in UNALIASED
    assert "directives.test_case" in UNALIASED
    assert set(ALIASES).isdisjoint(UNALIASED)


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_the_alias_is_the_real_module(module: str) -> None:
    imported, _ = _import_old(module)
    real = importlib.import_module(f"{NEW}.{module}")
    assert imported is real
    assert sys.modules[f"{OLD}.{module}"] is real
    assert getattr(sys.modules[OLD], module) is real
    name = ALIASES[module]
    assert getattr(imported, name) is getattr(real, name)


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_the_alias_warns_once_at_the_importing_line(module: str) -> None:
    _, caught = _import_old(module)
    assert [w.category for w in caught] == [FutureWarning]
    (warning,) = caught
    assert (warning.filename, warning.lineno) == ("<caller>", 1)
    message = str(warning.message)
    assert f"{OLD}.{module} has moved to {NEW}.{module}" in message
    assert "4.0" in message


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_a_second_import_does_not_warn_again(module: str) -> None:
    _import_old(module)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(f"{OLD}.{module}")
    assert caught == []


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_the_real_module_keeps_its_own_spec(module: str) -> None:
    _import_old(module)
    real = importlib.import_module(f"{NEW}.{module}")
    assert real.__name__ == f"{NEW}.{module}"
    assert real.__spec__ is not None
    assert real.__spec__.name == f"{NEW}.{module}"


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_patching_through_the_old_path_reaches_the_real_module(module: str) -> None:
    _import_old(module)
    name = ALIASES[module]
    real = importlib.import_module(f"{NEW}.{module}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        with mock.patch(f"{OLD}.{module}.{name}") as patched:
            assert getattr(real, name) is patched


@pytest.mark.parametrize("module", UNALIASED)
def test_an_unaliased_old_name_fails_plainly(module: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ModuleNotFoundError) as excinfo:
            importlib.import_module(f"{OLD}.{module}")
    assert caught == []
    # the missing name is the one the user wrote -- the first missing component of it
    assert excinfo.value.name is not None
    assert excinfo.value.name.startswith(OLD)
    assert NEW not in str(excinfo.value)


def _run_user_code(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run *source* as an imported module in a fresh interpreter under DEFAULT filters.

    Imported rather than run as ``__main__``: Python's default filters show a
    ``DeprecationWarning`` raised in ``__main__``, which would hide exactly the
    difference this is here to see.
    """
    (tmp_path / "user_code.py").write_text(textwrap.dedent(source), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONWARNINGS"}
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path), *filter(None, [env.get("PYTHONPATH")])]
    )
    return subprocess.run(
        [sys.executable, "-c", "import user_code"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("module", sorted(ALIASES))
def test_the_warning_is_visible_under_default_filters(tmp_path, module: str) -> None:
    result = _run_user_code(tmp_path, f"import {OLD}.{module}\n")
    assert result.returncode == 0, result.stderr
    assert f"user_code.py:1: FutureWarning: {OLD}.{module} has moved" in result.stderr


def test_the_aliases_import_without_sphinx(tmp_path) -> None:
    result = _run_user_code(
        tmp_path,
        f"""\
        import sys
        import {OLD}
        import {OLD}.junitparser
        import {OLD}.jsonparser
        loaded = sorted(m for m in ("sphinx", "sphinx_needs", "docutils") if m in sys.modules)
        assert not loaded, loaded
        """,
    )
    assert result.returncode == 0, result.stderr


def test_the_extension_alias_has_only_setup() -> None:
    package = importlib.import_module(OLD)
    assert callable(package.setup)
    with pytest.raises(AttributeError):
        _ = package.cli


class TestPytestPlugin:
    """``-p sphinxcontrib.test_reports.pytest_plugin`` loads the real plugin."""

    OLD_PLUGIN = f"{OLD}.pytest_plugin"

    SOURCE = """
from sphinx_test_reports.pytest_plugin import add_test_properties

@add_test_properties(test_type="unit")
def test_decorated():
    assert True
"""

    def _run(self, pytester, *plugins: str, ini: str = "", family: str = "xunit1"):
        pytester.makeini(
            "[pytest]\ntest_reports_properties =\n    test_type = TestType\n" + ini
        )
        pytester.makepyfile(self.SOURCE)
        report = pytester.path / "report.xml"
        args = [arg for plugin in plugins for arg in ("-p", plugin)]
        result = pytester.runpytest_subprocess(
            *args, "--junitxml", str(report), "-o", f"junit_family={family}"
        )
        return result, report

    def test_the_old_name_loads_the_plugin_and_warns(self, pytester) -> None:
        result, report = self._run(pytester, self.OLD_PLUGIN)
        result.assert_outcomes(passed=1)
        result.stderr.fnmatch_lines(
            [f"*FutureWarning: {self.OLD_PLUGIN} has moved to {NEW}.pytest_plugin*"]
        )
        xml = report.read_text(encoding="utf-8")
        # the plugin's hooks ran: the property is written, and written once
        assert xml.count('<property name="TestType" value="unit"') == 1

    def test_the_old_filter_line_still_silences_the_config_warning(
        self, pytester
    ) -> None:
        result, _ = self._run(
            pytester,
            self.OLD_PLUGIN,
            family="xunit2",
            ini=f"filterwarnings =\n    error\n    ignore::{self.OLD_PLUGIN}.TestReportsConfigWarning\n",
        )
        result.assert_outcomes(passed=1, warnings=0)

    def test_the_old_filter_line_matches_the_real_class(self, pytester) -> None:
        # without the filter the same run is a usage error, so the pass above is the filter
        result, _ = self._run(
            pytester, self.OLD_PLUGIN, family="xunit2", ini="filterwarnings = error\n"
        )
        assert result.ret == pytest.ExitCode.USAGE_ERROR

    def test_both_names_fail_loudly_naming_both(self, pytester) -> None:
        result, report = self._run(pytester, f"{NEW}.pytest_plugin", self.OLD_PLUGIN)
        assert result.ret != 0
        assert not report.exists()
        result.stderr.fnmatch_lines(
            [
                "*Plugin already registered under a different name: "
                f"{self.OLD_PLUGIN}=<module '{NEW}.pytest_plugin'*"
            ]
        )

    def test_the_old_filter_line_must_move_with_the_p_line(self, pytester) -> None:
        # `-p` already names the new module, the old filter line is still there, and the
        # project makes warnings errors: resolving the filter's category imports the alias
        # for the first time INSIDE pytest's filter parsing, and its FutureWarning stops the
        # run with a usage error that names the move. Loud rather than silent, so it is
        # fenced here and documented, not worked around.
        result, report = self._run(
            pytester,
            f"{NEW}.pytest_plugin",
            family="xunit2",
            ini=f"filterwarnings =\n    error\n    ignore::{self.OLD_PLUGIN}.TestReportsConfigWarning\n",
        )
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        assert not report.exists()
        result.stderr.fnmatch_lines(
            [
                f"*ignore::{self.OLD_PLUGIN}.TestReportsConfigWarning*",
                f"*FutureWarning: {self.OLD_PLUGIN} has moved to {NEW}.pytest_plugin*",
            ]
        )


OLD_PROJECT = {"buildername": "html", "srcdir": "doc_test/old_extension_name"}
#: The warning's text, which every supported Sphinx prints ...
MESSAGE = f"the extension name '{OLD}' is deprecated"
#: ... and its type and subtype, which Sphinx appends only from 8.0 on. On 7.4 the
#: `suppress_warnings` test is what proves them.
DEPRECATED = "[test_reports.deprecated]"


#: The prefix Sphinx gives every warning raised while an extension's `setup` runs. It is
#: counted on every Sphinx, so a second, differently worded warning from the alias is
#: seen on 7.4 too, where there is no type suffix to count. The one exception is 7.4's
#: `-W` abort, which prints the first warning under ``Warning, treated as error:`` without
#: the prefix -- and, since it aborts, never a second one.
SETTING_UP = f"while setting up extension {OLD}"
TREATED_AS_ERROR = "Warning, treated as error:"


def _assert_the_deprecation_once(output: str) -> None:
    import sphinx

    assert output.count(MESSAGE) == 1, output
    assert output.count(SETTING_UP) + output.count(TREATED_AS_ERROR) == 1, output
    if sphinx.version_info >= (8,):
        assert output.count(DEPRECATED) == 1, output


def _needs(app) -> dict:
    from sphinx_needs.data import SphinxNeedsData

    return dict(SphinxNeedsData(app.env).get_needs_view())


@pytest.mark.toolchain
class TestExtensionAlias:
    """``extensions = ["sphinxcontrib.test_reports"]`` builds, and says so."""

    @pytest.mark.parametrize("test_app", [OLD_PROJECT], indirect=True)
    def test_the_old_name_builds_with_the_deprecation_warning(self, test_app) -> None:
        app = test_app
        app.build()
        warnings_ = app._warning.getvalue()
        _assert_the_deprecation_once(warnings_)
        assert f"extension {OLD}" in warnings_
        assert f"'{NEW}'" in warnings_
        assert "4.0" in warnings_
        assert "OLDNAME_TF_1" in _needs(app)
        # the real extension is registered, and its metadata is what the alias reports
        real = app.extensions[NEW]
        alias = app.extensions[OLD]
        assert alias.version == real.version == sphinx_test_reports.__version__
        assert alias.parallel_read_safe == real.parallel_read_safe

    @pytest.mark.parametrize(
        "test_app",
        [
            {
                **OLD_PROJECT,
                "confoverrides": {"suppress_warnings": ["test_reports.deprecated"]},
            }
        ],
        indirect=True,
    )
    def test_suppress_warnings_silences_it(self, test_app) -> None:
        app = test_app
        app.build()
        assert app._warning.getvalue() == ""
        assert "OLDNAME_TF_1" in _needs(app)

    @pytest.mark.parametrize(
        "extensions",
        [
            ["sphinx_needs", NEW, OLD],
            ["sphinx_needs", OLD, NEW],
        ],
        ids=["new-first", "old-first"],
    )
    def test_listing_both_names_registers_once(self, make_app, tmp_path, extensions):
        app = _make_old_project(make_app, tmp_path, {"extensions": extensions})
        app.build()
        warnings_ = app._warning.getvalue()
        # the deprecation, and nothing about a directive or config value registered twice
        _assert_the_deprecation_once(warnings_)
        assert warnings_.count("WARNING") == 1, warnings_
        assert "OLDNAME_TF_1" in _needs(app)

    @pytest.mark.parametrize("test_app", [OLD_PROJECT], indirect=True)
    def test_a_strict_build_fails_on_it_and_suppress_warnings_clears_it(
        self, test_app
    ) -> None:
        from sphinx_needs_testkit import sphinx_build_command

        srcdir = Path(test_app.srcdir)
        failed = subprocess.run(
            sphinx_build_command("-W", "-b", "html", srcdir, srcdir / "_build" / "a"),
            capture_output=True,
            text=True,
            check=False,
        )
        assert failed.returncode != 0
        _assert_the_deprecation_once(failed.stderr)
        passed = subprocess.run(
            sphinx_build_command(
                "-W",
                "-D",
                "suppress_warnings=test_reports.deprecated",
                "-b",
                "html",
                srcdir,
                srcdir / "_build" / "b",
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert passed.returncode == 0, passed.stderr


@pytest.mark.toolchain
def test_the_deprecation_comes_before_a_toolchain_error(
    make_app, tmp_path, monkeypatch
) -> None:
    """A project that names the old extension with an outdated toolchain sees the
    deprecation first, then the real extension's toolchain error, which names the new one.
    """
    import io

    from sphinx.errors import ExtensionError

    from sphinx_test_reports import toolchain

    monkeypatch.setattr(
        toolchain, "unmet_requirements", lambda: ["sphinx-needs 5.1.0 < 8.5.0"]
    )
    warning = io.StringIO()
    with pytest.raises(ExtensionError, match=f"Could not load extension {NEW}"):
        _make_old_project(make_app, tmp_path, {}, warning=warning)
    # the error aborted the application, so the warning stream holds only what came first
    _assert_the_deprecation_once(warning.getvalue())


def _make_old_project(make_app, tmp_path: Path, confoverrides: dict, **kwargs):
    import shutil

    tests = Path(__file__).parent
    shutil.copytree(tests / "doc_test" / "utils", tmp_path / "utils")
    srcdir = tmp_path / "old_extension_name"
    shutil.copytree(tests / "doc_test" / "old_extension_name", srcdir)
    return make_app(
        buildername="html", srcdir=srcdir, confoverrides=confoverrides, **kwargs
    )
