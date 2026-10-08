"""Every module of the package compiles without a warning (fix round 2 of #2052).

A string that holds a backslash escape Python does not know (``"\\ "`` written as
``"\ "``) is a ``SyntaxWarning`` when the module is compiled without a cache -- a fresh
install's byte-compile, a new interpreter -- and under ``python -W error`` the extension
then fails to IMPORT. Lint does not see it (ruff's selected rules omit ``W605``), so the
class is fenced here: every ``.py`` file of the two packages this distribution ships is
compiled with every warning turned into an error. Found through the installed packages'
locations, so it holds for an editable and a built install alike.
"""

import importlib.util
import warnings
from pathlib import Path

import pytest

import sphinx_test_reports


def _package_dirs() -> list[Path]:
    old_name = importlib.util.find_spec("sphinxcontrib.test_reports")
    assert old_name is not None and old_name.origin is not None
    return [Path(sphinx_test_reports.__file__).parent, Path(old_name.origin).parent]


SOURCES = sorted(path for root in _package_dirs() for path in root.rglob("*.py"))


def test_the_package_has_modules_to_compile():
    """The control: the walk finds the modules (an empty walk would pass vacuously)."""
    names = {path.name for path in SOURCES}
    assert {"test_common.py", "test_env.py", "test_reports.py", "__init__.py"} <= names


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: path.name)
def test_a_module_compiles_without_a_warning(path):
    source = path.read_text(encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile(source, str(path), "exec")
