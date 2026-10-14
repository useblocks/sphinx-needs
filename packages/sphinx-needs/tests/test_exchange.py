"""``sphinx_needs.exchange``, the deprecated alias of ``ub_needs_exchange``.

The reader of a needs exchange file (needs.json) moved to the ``ub-needs-exchange``
library, whose own suite -- its conformance corpus above all -- is where the reader is
tested. What is sphinx-needs' own, and so tested here, is the alias sphinx-needs 9.0.0's
users may still import: it warns once, and every name it exports is the package's own
object. (``tests/test_exchange_readers.py`` tests sphinx-needs' two readers of the file.)
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from pathlib import Path

import sphinx_needs
import ub_needs_exchange

#: Every name sphinx-needs 9.0.0's ``sphinx_needs.exchange`` exported.
NAMES_9_0 = (
    "CURRENT_VERSION_MISSING",
    "DEFAULTS_REMOVED_WITHOUT_SCHEMA",
    "ID_MISMATCH",
    "INVALID_JSON",
    "NEEDS_MISSING",
    "NOT_AN_OBJECT",
    "RECORD_NOT_OBJECT",
    "VERSIONS_MISSING",
    "VERSION_NOT_FOUND",
    "Diagnostic",
    "Document",
    "ExchangeError",
    "Record",
    "Version",
    "load",
    "map_legacy_keys",
    "parse",
)


def test_the_alias_warns_once_and_exports_the_package_s_objects(monkeypatch):
    # imported afresh, whatever imported it before this test
    monkeypatch.delitem(sys.modules, "sphinx_needs.exchange", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        alias = importlib.import_module("sphinx_needs.exchange")
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert [str(w.message) for w in deprecations] == [
        "sphinx_needs.exchange is deprecated and will be removed in sphinx-needs 10.0; "
        "import ub_needs_exchange instead"
    ]
    assert tuple(alias.__all__) == NAMES_9_0
    assert all(
        getattr(alias, name) is getattr(ub_needs_exchange, name) for name in NAMES_9_0
    )


def test_sphinx_needs_itself_does_not_import_the_alias():
    """Its readers import the package: the alias is for its users' imports alone."""
    root = Path(sphinx_needs.__file__).parent
    spellings = (
        "sphinx_needs.exchange",
        "from sphinx_needs import exchange",
        "from . import exchange",
        "from .exchange",
        "from ..exchange",
    )
    importers = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.name != "exchange.py"
        and any(s in path.read_text(encoding="utf-8") for s in spellings)
    )
    assert importers == []


#: Imports every module of sphinx-needs but the alias, with the alias's warning made an
#: error, and prints whether the alias was imported along the way.
WALK = """
import pkgutil, sys, warnings
warnings.filterwarnings(
    "error", message="sphinx_needs.exchange is deprecated", category=DeprecationWarning
)
import sphinx_needs
count = 0
for info in pkgutil.walk_packages(sphinx_needs.__path__, "sphinx_needs."):
    if info.name != "sphinx_needs.exchange":
        __import__(info.name)
        count += 1
print(count, "sphinx_needs.exchange" in sys.modules)
"""


def test_no_module_of_sphinx_needs_imports_the_alias():
    """Whatever the spelling (``from sphinx_needs import config, exchange``, an
    ``importlib`` call): importing every module of sphinx-needs never imports the alias,
    so a build run with DeprecationWarnings as errors never sees its warning."""
    completed = subprocess.run(
        [sys.executable, "-c", WALK], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    count, imported = completed.stdout.split()
    assert int(count) > 50
    assert imported == "False"
