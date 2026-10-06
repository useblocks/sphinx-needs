"""The ``[mounts.<topic>]`` suffix of a warning is rendered exactly once (#2091).

Sphinx appends `` [type.subtype]`` to a typed warning itself when ``show_warning_types``
is on: the option exists since Sphinx 7.3 (default ``False``) and defaults to ``True``
since 8.0. Before 8.0 sphinx-mounts appends the suffix itself, so it must do so only
when Sphinx will not -- on 7.4 with the option on, both appended it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sphinx import version_info

from tests.conftest import write_ubproject_toml

if TYPE_CHECKING:
    from pathlib import Path

    from sphinx.testing.util import SphinxTestApp


def _suffixes(make_app, make_host_project, tmp_path: Path, show: bool) -> list[str]:
    """The ``[mounts.*]`` bracket groups of the one ``mounts.missing_path`` warning a
    build with a missing listed file emits, with ``show_warning_types = show``."""
    host = make_host_project()
    (host / "index.rst").write_text("Host\n====\n\nOnly page.\n", encoding="utf-8")
    write_ubproject_toml(
        host,
        [{"files": [str(tmp_path / "does_not_exist.rst")], "mount_at": "_g/api"}],
    )
    app: SphinxTestApp = make_app(
        srcdir=host, freshenv=True, confoverrides={"show_warning_types": show}
    )
    app.build()
    lines = [
        line
        for line in app._warning.getvalue().splitlines()
        if "does not exist" in line
    ]
    assert len(lines) == 1, app._warning.getvalue()
    return re.findall(r"\[mounts\.[a-z_]+\]", lines[0])


def test_suffix_once_when_sphinx_shows_warning_types(
    make_app, make_host_project, tmp_path
):
    """With ``show_warning_types = True`` Sphinx renders the suffix on every version
    (7.4 included), so sphinx-mounts adds none: exactly one ``[mounts.missing_path]``."""
    assert _suffixes(make_app, make_host_project, tmp_path, True) == [
        "[mounts.missing_path]"
    ]


def test_suffix_per_version_when_sphinx_hides_warning_types(
    make_app, make_host_project, tmp_path
):
    """With ``show_warning_types = False`` the expectation depends on the version:
    before Sphinx 8 sphinx-mounts appends the suffix itself (once); from 8 on it never
    appends and Sphinx renders nothing, so the line carries no suffix at all."""
    expected = ["[mounts.missing_path]"] if version_info < (8,) else []
    assert _suffixes(make_app, make_host_project, tmp_path, False) == expected
