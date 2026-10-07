"""A warning's ``[mounts.<topic>]`` suffix is rendered at most once (#2091)."""

from __future__ import annotations

import re

import pytest
from sphinx import version_info

from tests.conftest import write_ubproject_toml

ONCE = ["[mounts.missing_path]"]


@pytest.mark.parametrize(
    ("show", "expected"),
    [
        # Sphinx renders the suffix itself, so sphinx-mounts adds none
        pytest.param(True, ONCE, id="on"),
        # before Sphinx 8 sphinx-mounts appends it; from 8 nothing renders it
        pytest.param(False, ONCE if version_info < (8,) else [], id="off"),
    ],
)
def test_the_type_suffix_is_rendered_at_most_once(
    make_app, make_host_project, tmp_path, show, expected
):
    host = make_host_project()
    (host / "index.rst").write_text("Host\n====\n\nOnly page.\n", encoding="utf-8")
    with (host / "conf.py").open("a", encoding="utf-8") as fp:
        fp.write(f"\nshow_warning_types = {show}\n")
    write_ubproject_toml(
        host, [{"files": [str(tmp_path / "missing.rst")], "mount_at": "_g/api"}]
    )
    app = make_app(srcdir=host, freshenv=True)
    app.build()
    lines = [w for w in app._warning.getvalue().splitlines() if "does not exist" in w]
    assert [re.findall(r"\[mounts\.[a-z_]+\]", w) for w in lines] == [expected]
