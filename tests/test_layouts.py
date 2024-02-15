import pytest

from tests.util import extract_needs_from_html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_layout"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = (app.outdir / "index.html").read_text()
    assert "title_clean_layout" in html
    assert "title_complete_layout" in html
    assert "title_focus_layout" not in html
    assert "title_example_layout" in html

    needs = extract_needs_from_html(html)
    assert len(needs) == 6

    assert (
        '<span class="needs_label"><strong>author</strong>: </span><span class="needs_data">some author</span>'
        in html
    )
    assert '<tr class="footer row-even"><td class="footer_left" colspan="2">' in html

    # check simple_footer grid layout
    assert "custom footer for" in html
