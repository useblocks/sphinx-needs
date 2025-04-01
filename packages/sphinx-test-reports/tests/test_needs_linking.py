from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/needs_linking"}],
    indirect=True,
)
def test_doc_testsuites_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    print(html)
    assert html
    assert "links outgoing: " in html
    assert (
        """<a class="reference internal" href="#TEST_1" title="TEST_4">TEST_1</a>"""
        in html
    )
    assert (
        """<a class="reference internal" href="#TEST_2" title="TEST_4">TEST_2</a>"""
        in html
    )
    assert "links incoming: " in html
    assert (
        """<a class="reference internal" href="#TEST_3" title="TEST_4">TEST_3</a>"""
        in html
    )
