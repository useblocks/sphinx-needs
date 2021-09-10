from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needextract")
def test_doc_needextract_html(app, status, warning):
    app.build()
    index_html = Path(app.outdir, "index.html").read_text()

    # Check needs external filter works for needextract
    assert (
        '<span><div class="line"><span class="needs_secret_level"><span class="needs_label">'
        'secret_level: </span><span class="needs_data">top_level</span>' in index_html
    )

    # Check needextract table style
    assert "needs_style_green_border needs_type_story" in index_html
