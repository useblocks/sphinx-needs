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


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/needs_linking_docs_usage"}],
    indirect=True,
)
def test_tr_link_documented_usage_has_no_warnings(test_app):
    """``tr_link('classname', 'title')`` as documented must not warn on needs without a classname.

    Fields default to ``None`` on needs that do not set them, which must yield no links
    rather than a ``'NoneType' object has no attribute 'split'`` warning.
    """
    app = test_app
    app.build()
    assert "NoneType" not in app._warning.getvalue()
    html = Path(app.outdir, "index.html").read_text()
    assert 'href="#TESTSPEC_001"' in html
