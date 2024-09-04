import os.path
from pathlib import Path

import pytest
from lxml import html as html_parser


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needextract",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_basic(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    def run_checks(checks, html_path):
        html_path = str(Path(app.outdir, html_path))
        tree = html_parser.parse(html_path)
        for check in checks:
            img_src = tree.xpath(
                f"//table[@id='{check[0]}']//td[@class='need content']//img/@src"
            )[0]
            assert img_src == check[1]
            assert os.path.exists(
                str(Path(app.outdir, os.path.dirname(html_path), img_src))
            )

    checks = [
        ("US_SUB_001", "_images/smile.png"),
        ("US_SUB_002", "_images/smile.png"),
        ("US_SUB_003", "_images/smile1.png"),
        ("US_SUB_004", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_002", "_images/smile.png"),
        ("US_003", "_images/smile.png"),
    ]
    run_checks(checks, "check_images.html")

    checks = [
        ("US_002", "../_images/smile.png"),
        ("US_003", "../_images/smile.png"),
    ]
    run_checks(checks, "subfolder/check_images_2.html")

    index_html = Path(app.outdir, "check_need_refs.html").read_text()
    assert "Awesome Sphinx-Needs" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needextract_with_nested_needs",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_with_nested_needs(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    needextract_html = Path(app.outdir, "needextract.html").read_text()

    # ensure that the needs exist and that their hrefs point to the correct location
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1" title="SPEC_1">SPEC_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1_1" title="SPEC_1_1">SPEC_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_1" title="SPEC_1_1_1">SPEC_1_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_2" title="SPEC_1_1_2">SPEC_1_1_2</a>'
        in needextract_html
    )

    assert "This is id SPEC_1" in needextract_html
    assert "This is grandchild id SPEC_1_1_2" in needextract_html
