"""No module of ub-test-reports names the documentation toolchain, at any depth.

A static walk, not an import: it reads every module's source, so it refuses an import
statement -- at module level, in a function body, in a ``try`` arm or under
``TYPE_CHECKING`` -- whether or not any test reaches that line, and in every environment,
the default one (which has Sphinx installed) included. String-spelled
``importlib.import_module("...")`` and ``__import__("...")`` calls are read too. What a
static walk cannot see -- a dependency that drags Sphinx in, an import spelled some other
way -- is what CI's ``toolchain-free`` job is for.
"""

import ast
from pathlib import Path

import pytest

import ub_test_reports

#: Top-level names this package must never import: the documentation toolchain, and the
#: extension, which depends on this package and not the other way round.
FORBIDDEN = {
    "sphinx",
    "sphinx_needs",
    "docutils",
    "sphinx_test_reports",
    "sphinxcontrib",
}

ROOT = Path(ub_test_reports.__file__).parent
MODULES = sorted(ROOT.rglob("*.py"))


def _imported_names(node: ast.AST) -> list[str]:
    """The absolute module names *node* imports, if it is an import of any spelling."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module]
    if (
        isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and ast.unparse(node.func).endswith(("import_module", "__import__"))
    ):
        return [node.args[0].value]
    return []


def test_the_walk_sees_the_whole_package() -> None:
    # the fence's fence: a walk of the wrong directory would pass every module vacuously
    names = {path.relative_to(ROOT).as_posix() for path in MODULES}
    assert {"__init__.py", "cli.py", "jsonparser.py", "pytest_plugin.py"} <= names


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_module_imports_the_toolchain(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    leaks = [
        f"{path.name}:{node.lineno}: {name}"
        for node in ast.walk(tree)
        for name in _imported_names(node)
        if name.split(".")[0] in FORBIDDEN
    ]
    assert leaks == []
