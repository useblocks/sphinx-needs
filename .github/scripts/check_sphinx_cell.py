"""Check that a CI cell installed the sphinx series its dependency group asks for.

A group whose python marker excludes the running interpreter contributes nothing, so the
environment falls back to the project's own `sphinx>=7.4,<10` range and the sync still
exits 0 — the cell would then test a sphinx it never asked for, silently and green.
Comparing the installed version against the group's own specifier catches that.

Usage: python .github/scripts/check_sphinx_cell.py sphinx-9
"""

import sys
from pathlib import Path

import sphinx
from packaging.requirements import Requirement
from packaging.version import Version

try:
    import tomllib
except ModuleNotFoundError:  # python < 3.11
    import tomli as tomllib


def check(group):
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    requirements = config["dependency-groups"].get(group)
    if requirements is None:
        print(f"::error::pyproject.toml has no dependency group '{group}'")
        return 2
    for requirement in requirements:
        if not isinstance(
            requirement, str
        ):  # a PEP 735 `{ include-group = ... }` entry
            continue
        parsed = Requirement(requirement)
        if parsed.name == "sphinx":
            break
    else:
        print(f"::error::dependency group '{group}' does not require sphinx")
        return 2
    if Version(sphinx.__version__) not in parsed.specifier:
        print(
            f"::error::{group} asks for sphinx{parsed.specifier}, but {sphinx.__version__} is installed"
        )
        return 1
    print(f"{group}: sphinx {sphinx.__version__} satisfies {parsed.specifier}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_sphinx_cell.py <dependency-group>")
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
