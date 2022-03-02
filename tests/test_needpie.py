import os
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
    temp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test/doc_needpie")

    with open(os.path.join(temp_dir, "warnings.txt"), "w") as warnings:
        sphinx_app = sphinx.application.Sphinx(
            srcdir=src_dir,
            confdir=src_dir,
            outdir=temp_dir,
            doctreedir=temp_dir,
            buildername="html",
            parallel=4,
            warning=warnings,
        )
        sphinx_app.build()
        assert sphinx_app.statuscode == 0
        sphinx_app.build()
        assert sphinx_app.statuscode == 0
