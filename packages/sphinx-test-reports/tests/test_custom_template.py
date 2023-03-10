from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/custom_tr_template"}],
    indirect=True,
)
def test_custom_template(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir / "index.html").read_text()

    # assert changed order when creating a testreport html page
    pos1 = html.index("<strong>Imported data</strong>")
    pos2 = html.index('<div class="line">Test suites:')

    assert pos1 < pos2


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/custom_tr_utf8_template"}],
    indirect=True,
)
def test_custom_utf8_template(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir / "index.html").read_text()

    assert "Änderungen" in html
    assert "Testfälle" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/custom_tr_koi8_template"}],
    indirect=True,
)
def test_custom_koi8_template(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir / "index.html").read_text(encoding="utf8")

    print(html)

    assert "бцдеф" in html
    assert "Testfбlle" in html
