"""Scratch workspaces for the repository's own scripts (`.github/scripts/*.py`).

Every test here builds a throwaway uv workspace under `tmp_path` and runs one script's
`main()` against it. Nothing reaches the network and nothing runs `uv`: the scripts under
test read manifests and source text, and where they do talk to PyPI or git the tests
monkeypatch that one function. A fence that needed the network to be tested would not be
run often enough to be a fence.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# The scripts under test are loose files, not a package, and nothing installs them. Putting
# `.github/scripts` on `sys.path` HERE rather than in the root `[tool.pytest.ini_options]
# pythonpath` confines the change to the sessions that collect these tests -- a bare root
# `pytest` collects both trees and so shares one `sys.path` throughout, which is harmless
# because the name that could collide (`tests`) no longer exists outside a package. That
# rename is the half of this that does the work; a repository-wide `pythonpath` entry would
# have exposed this directory's siblings by name to every pytest run rooted here, including
# the ones that never look at these tests. Hence `selftests`, and hence this line.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT_TEMPLATE = """\
[project]
name = "scratch-workspace"
version = "0"
requires-python = "{requires_python}"
dependencies = [{dependencies}]

[tool.uv]
package = false

[tool.uv.sources]
{sources}
[tool.uv.workspace]
members = [{members}]
"""


def toml_list(values: list[str]) -> str:
    return ", ".join(f'"{value}"' for value in values)


def write_member(
    directory: Path,
    name: str,
    *,
    version: str | None = "1.0.0",
    dependencies: list[str] | None = None,
    optional_dependencies: dict[str, list[str]] | None = None,
    requires_python: str = ">=3.11,<4",
    module_version: str | None = None,
    module_name: str | None = None,
) -> Path:
    """One member manifest, plus (optionally) a module carrying a `__version__` literal."""
    directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "[project]",
        f'name = "{name}"',
    ]
    if version is None:
        lines.append('dynamic = ["version"]')
    else:
        lines.append(f'version = "{version}"')
    lines.append(f'requires-python = "{requires_python}"')
    lines.append(f"dependencies = [{toml_list(dependencies or [])}]")
    if optional_dependencies:
        lines.append("")
        lines.append("[project.optional-dependencies]")
        for extra, specs in optional_dependencies.items():
            lines.append(f"{extra} = [{toml_list(specs)}]")
    if module_name:
        lines += ["", "[tool.flit.module]", f'name = "{module_name}"']
    manifest = directory / "pyproject.toml"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if module_version is not None:
        module = directory / "src" / (module_name or name.replace("-", "_"))
        module.mkdir(parents=True, exist_ok=True)
        (module / "__init__.py").write_text(
            f'"""scratch."""\n\n__version__ = "{module_version}"\n', encoding="utf-8"
        )
    return manifest


@pytest.fixture
def workspace(tmp_path: Path):
    """Build a scratch workspace; returns its root."""

    def build(
        members: dict[str, dict[str, Any]],
        *,
        root_dependencies: list[str] | None = None,
        sources: dict[str, str] | None = None,
        requires_python: str = ">=3.11,<4",
        member_globs: list[str] | None = None,
        directories: dict[str, str] | None = None,
    ) -> Path:
        for name, options in members.items():
            where = (directories or {}).get(name, f"packages/{name}")
            write_member(tmp_path / where, name, **options)
        names = list(members)
        source_lines = (
            sources
            if sources is not None
            else dict.fromkeys(names, "{ workspace = true }")
        )
        (tmp_path / "pyproject.toml").write_text(
            ROOT_TEMPLATE.format(
                requires_python=requires_python,
                dependencies=toml_list(
                    names if root_dependencies is None else root_dependencies
                ),
                sources="".join(
                    f"{name} = {value}\n" for name, value in source_lines.items()
                ),
                members=toml_list(member_globs or ["packages/*"]),
            ),
            encoding="utf-8",
        )
        return tmp_path

    return build
