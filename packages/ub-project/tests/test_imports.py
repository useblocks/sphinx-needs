"""The package imports the standard library and nothing else.

That is its contract with every consumer: the tools that read ``ubproject.toml`` include
ones that run with no documentation toolchain installed, and a shared reader that pulled
Sphinx in -- directly or through a sibling -- would take that away from all of them at
once. The manifest declaring no dependencies is not enough on its own: an ``import
sphinx`` in a module installs nothing and still breaks every such consumer.

The import runs in a FRESH interpreter, so that whatever this test session has already
imported (pytest's plugins, other suites' fixtures) cannot hide or fake a result.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

#: Imports every module of the package in a clean interpreter, and prints the top-level
#: names of every module that importing it added to ``sys.modules``.
PROBE = """
import json, pkgutil, sys
before = set(sys.modules)
import ub_project
for info in pkgutil.walk_packages(ub_project.__path__, "ub_project."):
    __import__(info.name)
added = sorted({name.partition(".")[0] for name in set(sys.modules) - before})
print(json.dumps(added))
"""


@pytest.fixture(scope="module")
def imported() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_no_sphinx_docutils_or_sibling_is_imported(imported: list[str]) -> None:
    toolchain = [
        name
        for name in imported
        if name in {"sphinx", "docutils", "sphinxcontrib"} or name.startswith("sphinx_")
    ]
    assert toolchain == []


def test_only_the_standard_library_is_imported(imported: list[str]) -> None:
    foreign = [
        name
        for name in imported
        if name != "ub_project" and name not in sys.stdlib_module_names
    ]
    assert foreign == []
