from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/unicode_support")])
def test_unicode_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "Загрузка" in html
    assert "Aufräumlösung" in html
