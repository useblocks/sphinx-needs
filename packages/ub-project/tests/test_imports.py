"""The package imports the standard library, what its manifest declares, and nothing else.

That is its contract with every consumer: the tools that read ``ubproject.toml`` include
ones that run with no documentation toolchain installed, and a shared reader that pulled
Sphinx in -- directly or through a sibling -- would take that away from all of them at
once. The manifest is not enough on its own: an ``import sphinx`` in a module installs
nothing and still breaks every such consumer. So an import is admitted only when it is the
standard library's, the package's own, or a module of a distribution the manifest declares
for THIS interpreter (markers evaluated): ``tomli`` below Python 3.15, whose compiled wheel
also brings a hash-named ``*__mypyc`` module, and nothing from 3.15 on.

The import runs in a FRESH interpreter, so that whatever this test session has already
imported (pytest's plugins, other suites' fixtures) cannot hide or fake a result.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import packages_distributions, requires

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

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


def _declared_distributions() -> set[str]:
    """The distributions the manifest declares for this interpreter, markers evaluated."""
    declared = set()
    for line in requires("ub-project") or []:
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            declared.add(canonicalize_name(requirement.name))
    return declared


def _declared_modules() -> set[str]:
    """The top-level modules of every distribution the manifest declares for this interpreter."""
    declared = _declared_distributions()
    return {
        module
        for module, distributions in packages_distributions().items()
        if any(canonicalize_name(name) in declared for name in distributions)
    }


def test_only_the_standard_library_is_imported(imported: list[str]) -> None:
    """...and the modules of what the manifest declares: below 3.15, the TOML 1.1 backport."""
    admitted = _declared_modules()
    foreign = [
        name
        for name in imported
        if name != "ub_project"
        and name not in sys.stdlib_module_names
        and name not in admitted
    ]
    assert foreign == []


def test_only_the_declared_distributions_are_admitted() -> None:
    """The admission is the manifest's, not whatever this environment has installed."""
    expected = {"tomli"} if sys.version_info < (3, 15) else set()
    # the markers are evaluated for THIS interpreter, whatever is installed
    assert _declared_distributions() == expected
    # and every admitted module belongs to a declared distribution and nothing else
    distributions = packages_distributions()
    admitted = _declared_modules()
    assert {
        canonicalize_name(name) for module in admitted for name in distributions[module]
    } <= expected
    # installed wherever this suite runs, and declared by nothing in the manifest
    assert {"pytest", "_pytest", "packaging"}.isdisjoint(admitted)
    assert ("tomli" in admitted) is (sys.version_info < (3, 15))
