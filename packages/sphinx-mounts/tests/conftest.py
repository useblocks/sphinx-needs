"""Pytest fixtures for sphinx-mounts tests."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

pytest_plugins = ["sphinx.testing.fixtures"]

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
) -> Path:
    """Write a ``ubproject.toml`` file declaring the given mounts.

    Produces a top-level ``[[mounts]]`` array of tables — the schema the
    extension expects. Returns the absolute path of the written file.

    :param srcdir: Sphinx confdir / srcdir.
    :param mounts: Iterable of mount dicts with the same keys
        ``MountConfig.from_dict`` accepts.
    :param filename: TOML file name. Defaults to ``ubproject.toml``.
    """
    lines: list[str] = []
    for mount in mounts:
        lines.append("[[mounts]]")
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


def count_warnings(app) -> int:
    """Total number of warning records in the captured Sphinx warning stream.

    Each Sphinx warning is emitted as a single ``WARNING:`` record, so
    counting them pins the *exact* number of warnings a scenario may emit.
    """
    return app._warning.getvalue().count("WARNING:")


def count_mount_warnings(app) -> int:
    """Number of sphinx-mounts warnings (``mounts.*`` types) captured.

    Every sphinx-mounts warning carries the ``[mounts.<subtype>]`` type
    suffix on Sphinx 8/9 natively and Sphinx 7 via the manual append, so
    counting those occurrences pins exactly how many of *our* warnings a
    scenario emits — independent of unrelated Sphinx toctree noise and
    stable across supported Sphinx versions.
    """
    return app._warning.getvalue().count("[mounts.")
