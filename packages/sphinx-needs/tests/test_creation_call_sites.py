"""Every producer in this repository creates its needs through ``create_need`` or the
record path, never through ``add_need`` or ``add_external_need``.

``add_need`` and ``add_external_need`` take a need's fields as ``**kwargs``, beside
keyword parameters a field may be named like (#2392, #2403); ``create_need`` takes them as
mappings. The two stay for extensions, and this fence keeps the packages of this
repository off them: it reads the SOURCE of every package under ``packages/*/src``, so a
call that a test never reaches is caught too. ``sphinx_needs/api/need.py``, where the
functions are defined, is the one module exempt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: the functions a producer of this repository does not call
LEGACY = frozenset({"add_need", "add_external_need"})

PACKAGES = Path(__file__).resolve().parents[2]
"""``packages/``: this suite's package and its siblings."""

DEFINED_IN = Path("sphinx-needs", "src", "sphinx_needs", "api", "need.py")


def legacy_calls(source: str) -> list[tuple[int, str]]:
    """The calls of a :data:`LEGACY` function in ``source``, by line: a call of the bare
    name (``add_need(...)``), and of the name as an attribute of a module
    (``api.add_need(...)``). ``SphinxNeedsData.add_need`` (``data.add_need(need)``)
    records a created need and is not a call of the API: an attribute call on any other
    name than an imported module is not one."""
    tree = ast.parse(source)
    modules = {
        alias.asname or alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name not in LEGACY
    }
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in LEGACY:
            found.append((node.lineno, func.id))
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in LEGACY
            and isinstance(func.value, ast.Name | ast.Attribute)
            and _root(func.value) in modules
            and not _is_data(func.value)
        ):
            found.append((node.lineno, func.attr))
    return sorted(found)


def _root(node: ast.expr) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _is_data(node: ast.expr) -> bool:
    """``SphinxNeedsData(env).add_need``: a call on the store, not the API."""
    return isinstance(node, ast.Name) and node.id in {"data", "needs_data"}


def _modules() -> list[Path]:
    return sorted(
        path
        for path in PACKAGES.glob("*/src/**/*.py")
        if path.relative_to(PACKAGES) != DEFINED_IN
    )


def test_no_producer_calls_the_legacy_functions():
    found = {
        f"{path.relative_to(PACKAGES).as_posix()}:{line}": name
        for path in _modules()
        for line, name in legacy_calls(path.read_text(encoding="utf-8"))
    }
    assert found == {}


def test_the_fence_reads_every_package():
    """The control: the walk reaches the sibling packages that create needs."""
    walked = {path.relative_to(PACKAGES).parts[0] for path in _modules()}
    assert {"sphinx-needs", "sphinx-codelinks", "sphinx-test-reports"} <= walked


@pytest.mark.parametrize(
    "source",
    [
        "from sphinx_needs.api import add_need\nnodes = add_need(app, state)\n",
        "from sphinx_needs.api import add_need\nreturn_nodes += add_need(\n    app,\n)\n",
        "from sphinx_needs.api import add_external_need\nadd_external_need(app, 't')\n",
        "import sphinx_needs.api\nsphinx_needs.api.add_need(app, state)\n",
        "from sphinx_needs import api\napi.add_external_need(app, 't')\n",
    ],
)
def test_the_fence_finds_a_legacy_call(source: str):
    """The positive control: each shape a call takes is found."""
    assert len(legacy_calls(source)) == 1


@pytest.mark.parametrize(
    "source",
    [
        "data = SphinxNeedsData(env)\ndata.add_need(need)\n",
        "# a comment naming add_need(app, state)\n",
        '"""A docstring naming ``add_need(docname=None)``."""\n',
        "from sphinx_needs.api import create_need\ncreate_need(app, state, s, 't', 'T')\n",
    ],
)
def test_the_fence_ignores_what_is_no_legacy_call(source: str):
    assert legacy_calls(source) == []


# --- the source classes ------------------------------------------------------------

#: the names a module of this repository does not use: the five source classes of
#: 9.1.0, deprecated factories until 10.0, and the base class they shared
DEPRECATED_SOURCES = frozenset(
    {
        "NeedItemSourceUnknown",
        "NeedItemSourceDirective",
        "NeedItemSourceService",
        "NeedItemSourceExternal",
        "NeedItemSourceImport",
        "HopsSource",
    }
)


def deprecated_source_names(source: str) -> list[tuple[int, str]]:
    """The uses of a :data:`DEPRECATED_SOURCES` name in ``source``, by line: a name, an
    attribute, an import, a definition. A string or a docstring naming one is not a use
    (``sphinx_needs/need_item.py`` maps the names to their factories by string)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name.rsplit(".", 1)[-1]
        elif isinstance(node, ast.ClassDef | ast.FunctionDef):
            name = node.name
        else:
            continue
        if name in DEPRECATED_SOURCES:
            found.append((getattr(node, "lineno", 0), name))
    return sorted(found)


@pytest.mark.xfail(strict=True, reason="slice 3a: every producer on NeedItemSource")
def test_no_module_uses_a_deprecated_source_name():
    """Every producer of this repository builds ``NeedItemSource``, and nothing tests
    for the base class the five shared."""
    found = {
        f"{path.relative_to(PACKAGES).as_posix()}:{line}": name
        for path in sorted(PACKAGES.glob("*/src/**/*.py"))
        for line, name in deprecated_source_names(path.read_text(encoding="utf-8"))
    }
    assert found == {}


@pytest.mark.parametrize(
    "source",
    [
        # the uses at 8bd37988a, as they were written
        "from sphinx_needs.need_item import NeedItemSourceUnknown\n",
        "from sphinx_needs._need_source import (\n    HopsSource,\n    NeedSourceHop,\n)\n",
        "class NeedItemSourceUnknown(HopsSource):\n    pass\n",
        "source = NeedItemSourceDirective(\n    lineno=resolved_lineno or self.lineno,\n)\n",
        "need_source = NeedItemSourceImport(lineno=self.lineno, path=p, hops=hops)\n",
        "x = source.parser_lineno if isinstance(source, NeedItemSourceDirective) else None\n",
        "if not isinstance(source, HopsSource) or source.placement is None:\n    pass\n",
        # and as an attribute of the module
        "from sphinx_needs import need_item\nneed_item.NeedItemSourceService(lineno=1)\n",
        "import sphinx_needs.need_item\nsphinx_needs.need_item.NeedItemSourceExternal()\n",
    ],
)
def test_the_fence_finds_a_deprecated_source_name(source: str):
    """The positive control: each use of a name found at the base is found."""
    assert len(deprecated_source_names(source)) >= 1


@pytest.mark.parametrize(
    "source",
    [
        '"""``NeedItemSourceUnknown(docname=, lineno=)`` is a factory now."""\n',
        "# NeedItemSourceDirective\n",
        "_LEGACY = {'NeedItemSourceUnknown': _unknown}\n",
        "from sphinx_needs.need_item import NeedItemSource, NeedItemSourceProtocol\n",
    ],
)
def test_the_fence_ignores_what_is_no_use_of_a_deprecated_source(source: str):
    assert deprecated_source_names(source) == []
