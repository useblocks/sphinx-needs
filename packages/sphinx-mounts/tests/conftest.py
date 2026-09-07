"""Pytest fixtures for sphinx-mounts tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

# The workspace's shared test layer, `packages/sphinx-needs-testkit`. This suite takes two
# things from it: the warning normalisation (`build_warnings` / `warning_count`, imported
# by name in the test modules) and the renderer resolution, whose lazy half is the
# `plantuml_command` fixture this line is what provides -- so a tree that lost the entry
# fails at setup with `fixture 'plantuml_command' not found` rather than silently
# collecting less.
#
# The ORDER of the list is load-bearing where both plugins define a fixture, and the kit
# must come last; see the note in its `fixtures` module. **Nothing in this suite fences it,
# and that is acceptable here**: the only fixture the two share is `sphinx_test_tempdir`,
# which this suite never resolves -- it builds through sphinx's `make_app` into `tmp_path`
# -- and could not resolve if it tried, because the kit's version needs a `tests_dir`
# fixture that only sphinx-needs' conftest defines. The day a test here uses sphinx's `app`
# fixture, that arrives as `fixture 'tests_dir' not found`, which is loud rather than
# wrong. `--sn-build-dir`, which the kit also adds, does nothing in this suite.
pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture()
def bundle_simple() -> Path:
    """Absolute path to the simple bundle fixture."""
    return FIXTURES_DIR / "bundle_simple"


@pytest.fixture()
def bundle_nested() -> Path:
    """Absolute path to the nested bundle fixture."""
    return FIXTURES_DIR / "bundle_nested"


@pytest.fixture()
def bundle_markdown() -> Path:
    """Absolute path to a Markdown-only bundle fixture."""
    return FIXTURES_DIR / "bundle_markdown"


@pytest.fixture()
def make_host_project(tmp_path: Path) -> Callable[[str], Path]:
    """Return a factory that materialises a copy of the host_project fixture.

    The factory copies ``tests/fixtures/host_project`` into ``tmp_path`` so
    each test gets its own writable srcdir. The caller writes a TOML config
    via :func:`write_ubproject_toml` (preferred) or, for legacy coverage,
    appends ``mounts = ...`` to ``conf.py`` via :func:`patch_conf_py`.
    """

    def _factory(name: str = "host") -> Path:
        target = tmp_path / name
        shutil.copytree(FIXTURES_DIR / "host_project", target)
        return target

    return _factory


def patch_conf_py(srcdir: Path, mounts_literal: str) -> None:
    """Append a ``mounts = ...`` block to ``conf.py`` in ``srcdir``.

    This drives the *legacy* conf.py-based config path. New tests should
    prefer :func:`write_ubproject_toml`, which exercises the primary
    TOML-driven path. The host_project fixture ships with a minimal conf.py
    and ``sphinx_mounts`` already in ``extensions``.
    """
    conf = srcdir / "conf.py"
    text = conf.read_text(encoding="utf-8")
    conf.write_text(
        text + f"\nmounts = {mounts_literal}\n",
        encoding="utf-8",
    )


def write_ubproject_toml(
    srcdir: Path,
    mounts: Iterable[dict[str, Any]],
    filename: str = "ubproject.toml",
    *,
    namespaced: bool = True,
) -> Path:
    """Write a ``ubproject.toml`` file declaring the given mounts.

    Returns the absolute path of the written file.

    :param srcdir: Sphinx confdir / srcdir.
    :param mounts: Iterable of mount dicts with the same keys
        ``MountConfig.from_dict`` accepts.
    :param filename: TOML file name. Defaults to ``ubproject.toml``.
    :param namespaced: Write the recommended ``[[source.mounts]]`` spelling
        (the default) rather than the deprecated top-level ``[[mounts]]`` one.
        Both load identically, but the top-level spelling now emits
        ``mounts.deprecated_location``, so tests that assert a warning count
        would all have to account for it. Pass ``namespaced=False`` only to
        exercise the deprecated spelling itself.
    """
    header = "[[source.mounts]]" if namespaced else "[[mounts]]"
    lines: list[str] = []
    for mount in mounts:
        lines.append(header)
        if "dir" in mount:
            lines.append(f"dir = {_toml_string(str(mount['dir']))}")
        if "files" in mount:
            rendered = ", ".join(_toml_string(str(f)) for f in mount["files"])
            lines.append(f"files = [{rendered}]")
        if "mount_at" in mount:
            lines.append(f"mount_at = {_toml_string(mount['mount_at'])}")
        for list_field in ("include", "exclude"):
            values = mount.get(list_field)
            if values:
                rendered = ", ".join(_toml_string(p) for p in values)
                lines.append(f"{list_field} = [{rendered}]")
        for bool_field in ("gitignore", "strict_mount_at", "attach_each"):
            if bool_field in mount:
                value = "true" if mount[bool_field] else "false"
                lines.append(f"{bool_field} = {value}")
        if "path_check" in mount:
            lines.append(f"path_check = {_toml_string(mount['path_check'])}")
        if mount.get("attach_to") is not None:
            lines.append(f"attach_to = {_toml_string(mount['attach_to'])}")
        if "toctree_index" in mount:
            lines.append(f"toctree_index = {int(mount['toctree_index'])}")
        if "entry_doc" in mount:
            lines.append(f"entry_doc = {_toml_string(mount['entry_doc'])}")
        lines.append("")
    path = srcdir / filename
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _toml_string(value: str) -> str:
    """Encode a Python string as a TOML basic string literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# `count_warnings` and `count_mount_warnings` are NOT here any more. The first counted
# occurrences of the substring ``WARNING:``; both are replaced by the workspace's one
# normalisation, `sphinx_needs_testkit.warning_count`, which counts warning RECORDS and,
# given a type, only those carrying exactly that ``[type]`` token -- so a scenario now
# pins WHICH sphinx-mounts warning it emits rather than how many mounts warnings of any
# kind. The two family assertions that genuinely mean "no mounts warning at all" spell
# that out over `build_warnings` at their call sites.
