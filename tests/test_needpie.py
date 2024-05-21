from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needpie"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert '<img alt="_images/need_pie_' in html


def test_sphinx_api_needpie(tmp_path: Path, make_app: type[SphinxTestApp]):
    """
    Tests a build via the Sphinx Build API.
    """
    build_dir = tmp_path / "_build"
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test/doc_needpie")
    shutil.copytree(src_dir, tmp_path, dirs_exist_ok=True)

    if version_info >= (7, 2):
        src_dir = Path(src_dir)
    else:
        from sphinx.testing.path import path

        src_dir = path(src_dir)
        build_dir = path(build_dir)

    sphinx_app = make_app(
        srcdir=src_dir,
        builddir=build_dir,
        buildername="html",
        parallel=4,
    )
    sphinx_app.build()
    assert sphinx_app.statuscode == 0

    # touch file to force sphinx to purge stuff
    with tmp_path.joinpath("index.rst").open("a") as f:
        f.write("\n\nNew content to force rebuild")

    sphinx_app.build()
    assert sphinx_app.statuscode == 0
