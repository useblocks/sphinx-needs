from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needimport")  # , warningiserror=True)
def test_needimport_path(app, status, warning):
    app.build()

    # Check import JSON file not in the same folder of rst file
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST IMPORT TITLE" in html
    assert "TEST_01" in html

    # Check import JSON file in the same folder of rst file but in subfolder of conf.py folder
    subdoc_html = Path(app.outdir, "doc_sub/subdoc.html").read_text()
    assert "TEST_02" in subdoc_html
