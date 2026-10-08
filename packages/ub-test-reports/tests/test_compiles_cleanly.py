"""Every module of the package compiles without a warning (fix round 2 of #2052).

A string that holds a backslash escape Python does not know is a ``SyntaxWarning`` when
the module is compiled without a cache, and under ``python -W error`` an import error.
ruff's selected rules omit ``W605``, so the class is fenced here: every ``.py`` file of the
installed package is compiled with every warning turned into an error.
"""

import warnings
from pathlib import Path

import pytest

import ub_test_reports

SOURCES = sorted(Path(ub_test_reports.__file__).parent.rglob("*.py"))


def test_the_package_has_modules_to_compile():
    """The control: the walk finds the modules (an empty walk would pass vacuously)."""
    names = {path.name for path in SOURCES}
    assert {"junitparser.py", "jsonparser.py", "errors.py", "cli.py"} <= names


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: path.name)
def test_a_module_compiles_without_a_warning(path):
    source = path.read_text(encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile(source, str(path), "exec")
