import pytest

from tests.util import extract_needs_from_html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_layout", "no_plantuml": True}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    assert len(app.warning_list) == 0

    html = (app.outdir / "index.html").read_text()
    assert "title_clean_layout" in html
    assert "title_complete_layout" in html
    assert "title_focus_layout" not in html
    assert "title_example_layout" in html

    needs = extract_needs_from_html(html)
    assert len(needs) == 7

    assert (
        '<span class="needs_label"><strong>author</strong>: </span><span class="needs_data">some author</span>'
        in html
    )
    assert '<tr class="footer row-even"><td class="footer_left" colspan="2">' in html

    # check simple_footer grid layout
    assert "custom footer for" in html

    # Check image is correctly referenced
    assert (
        '<img alt="_images/smile.png" class="needs_image align-center" src="_images/smile.png" />'
        in html
    )

    # Check a "root"-image is correctly referenced in subfolders
    html_subfolder_1 = (app.outdir / "subfolder_1/index.html").read_text()
    assert (
        '<img alt="../_images/smile.png" class="needs_image align-center" src="../_images/smile.png" />'
        in html_subfolder_1
    )
    assert '<span class="needs_data">_images/smile.png</span>' in html_subfolder_1

    # Check a "subfolder"-image is correctly referenced in subfolders
    html_subfolder_2 = (app.outdir / "subfolder_2/index.html").read_text()
    assert (
        '<img alt="../_images/subfolder_smile.png" class="needs_image align-center" src="../_images/subfolder_smile.png" />'
        in html_subfolder_2
    )
    assert (
        '<span class="needs_data">subfolder_2/subfolder_smile.png</span>'
        in html_subfolder_2
    )
