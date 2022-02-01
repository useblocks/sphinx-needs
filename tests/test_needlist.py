from pathlib import Path

import pytest

from tests.conftest import clean_up_tmpdir, copy_srcdir_to_tmpdir

# @pytest.mark.sphinx(buildername="html", testroot="doc_needlist")
# def test_doc_build_html(app, status, warning):
#     app.build()
#     html = Path(app.outdir, "index.html").read_text()
#     assert "SP_TOO_001" in html
#     assert 'id="needlist-index-0"' in html


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/test-doc_needlist")])
def test_doc_build_html(make_app, buildername, srcdir, sphinx_test_tempdir):
    # copy srcdir to sphinx_test_tempdir
    srcdir = copy_srcdir_to_tmpdir(srcdir, sphinx_test_tempdir)

    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SP_TOO_001" in html
    assert 'id="needlist-index-0"' in html

    # clean up test tmpdir
    clean_up_tmpdir(sphinx_test_tempdir)
