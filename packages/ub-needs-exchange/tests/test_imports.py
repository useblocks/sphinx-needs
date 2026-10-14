"""The package imports the standard library and nothing else.

That is its contract with every consumer: the tools that read a needs.json include ones
that run with no documentation toolchain installed, and a shared reader that pulled Sphinx
in -- directly or through a sibling -- would take that away from all of them at once. The
manifest declaring no dependencies is not enough on its own: an ``import sphinx`` in a
module installs nothing and still breaks every such consumer.

Two fences, because each misses what the other sees. The import runs in a FRESH
interpreter, so that whatever this test session has already imported (pytest's plugins,
other suites' fixtures) cannot hide or fake a result -- but it sees only what runs at import
time. The source walk sees every import STATEMENT, one inside a function included, which
the import never executes: a third-party module imported in ``load`` would pass the first
fence wherever that module happens to be installed, and fail every consumer that lacks it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

#: Imports every module of the package in a clean interpreter, and prints the top-level
#: names of every module that importing it added to ``sys.modules``.
PROBE = """
import json, pkgutil, sys
before = set(sys.modules)
import ub_needs_exchange
for info in pkgutil.walk_packages(ub_needs_exchange.__path__, "ub_needs_exchange."):
    __import__(info.name)
added = sorted({name.partition(".")[0] for name in set(sys.modules) - before})
print(json.dumps(added))
"""

#: What a needs.json reader is most tempted to reach for, and must not: the toolchain, and
#: the two libraries sphinx-needs reads and validates the file with today.
FORBIDDEN = {
    "sphinx",
    "docutils",
    "sphinxcontrib",
    "sphinx_needs",
    "jsonschema",
    "jsonschema_rs",
    "requests",
}


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


def test_the_probe_sees_the_package(imported: list[str]) -> None:
    """The positive control: a probe that imported nothing would pass both tests below."""
    assert "ub_needs_exchange" in imported


def test_no_toolchain_validator_or_sibling_is_imported(imported: list[str]) -> None:
    reached = [
        name
        for name in imported
        if name in FORBIDDEN
        or name.startswith("sphinx_")
        or (name.startswith("ub_") and name != "ub_needs_exchange")
    ]
    assert reached == []


def test_only_the_standard_library_is_imported(imported: list[str]) -> None:
    foreign = [
        name
        for name in imported
        if name != "ub_needs_exchange" and name not in sys.stdlib_module_names
    ]
    assert foreign == []


def test_every_import_statement_names_the_standard_library() -> None:
    """Every ``import`` and ``from … import`` in every module of the package, at any depth
    (a function body included), names the standard library or the package itself."""
    import ub_needs_exchange

    root = Path(ub_needs_exchange.__file__).parent
    modules = sorted(root.rglob("*.py"))
    assert modules, f"no module found under {root}"
    foreign: dict[str, list[str]] = {}
    for module in modules:
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module is not None
                names = [node.module]
            else:
                continue  # not an import, or a relative one: the package itself
            for name in names:
                top = name.partition(".")[0]
                if top != "ub_needs_exchange" and top not in sys.stdlib_module_names:
                    foreign.setdefault(module.name, []).append(name)
    assert foreign == {}
