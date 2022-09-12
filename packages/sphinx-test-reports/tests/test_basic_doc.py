from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/basic_doc"}], indirect=True
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>Basic Document" in html
    assert "ASuccessfulTest" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/pytest_6_2"}],
    indirect=True,
)
def test_doc_build_html_for_pytest_6_2(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

    assert "Tests: 6" in html
    assert "Failures: 2" in html
    assert "Errors: 0" in html
    assert "Skips: 3" in html
