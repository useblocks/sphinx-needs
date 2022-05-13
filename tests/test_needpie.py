import os
import shutil
import tempfile
from pathlib import Path

import pytest
import sphinx


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needpie"}], indirect=True)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert '<img alt="_images/need_pie_' in html


def test_sphinx_api_needpie():
    """
    Tests a build via the Sphinx Build API.
    """
    temp_dir = Path(tempfile.mkdtemp())
    build_dir = temp_dir / "_build"
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test/doc_needpie")
    shutil.copytree(src_dir, temp_dir, dirs_exist_ok=True)

    with open(os.path.join(temp_dir, "warnings.txt"), "w") as warnings:
        sphinx_app = sphinx.application.Sphinx(
            srcdir=temp_dir,
            confdir=temp_dir,
            outdir=build_dir,
            doctreedir=temp_dir,
            buildername="html",
            parallel=4,
            warning=warnings,
        )
        sphinx_app.build()
        assert sphinx_app.statuscode == 0

        # touch file to force sphinx to purge stuff
        with open(temp_dir / "index.rst", "a") as f:
            f.write("\n\nNew content to force rebuild")

        sphinx_app.build()
        assert sphinx_app.statuscode == 0
