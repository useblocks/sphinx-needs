from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/unicode_support")  # , warningiserror=True)
def test_unicode_html(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "Загрузка" in html
    assert "Aufräumlösung" in html
