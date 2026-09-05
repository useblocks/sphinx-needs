"""Scratch workspaces for the repository's own tooling (`tools/src/sn_tools/`).

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

# `tools` is a VIRTUAL member (`[tool.uv] package = false`), so nothing installs
# `sn_tools` into any environment -- deliberately: the tooling is run by path, from the
# repository, and is never imported by anything the suite ships. These tests therefore put
# it on `sys.path` themselves.
#
# `tools/src`, NOT `tools/`. Putting `tools/` on a path root would make this very
# directory importable as a top-level package called `tests`, competing for the name with
# `packages/sphinx-needs/tests` in any session that collects both -- which a bare root
# `pytest` does, because `testpaths` names them both. `tools/src` contains exactly one
# name, `sn_tools`, which nothing else claims.
#
# Doing it here rather than in a repository-wide `[tool.pytest.ini_options] pythonpath`
# also confines the change to the sessions that collect these tests: the CI matrix cells,
# which pass the package's `tests` path explicitly, never execute this file at all.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
    virtual: bool = False,
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
    if virtual:
        # a member this repository never releases: `package = false` hides it from uv's
        # workspace selectors, and the release plan refuses a tag that names it
        lines += ["", "[tool.uv]", "package = false"]
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
