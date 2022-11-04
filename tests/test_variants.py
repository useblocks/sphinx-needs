from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/variant_doc", "tags": ["tag_a"]}], indirect=True
)
def test_variant_options_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "Tags Example" in html
    assert "tags_implemented" in html
    assert "VA_003" in html

    assert "No ID" in html
    assert "progress" in html
    assert "extension" in html

    assert "Test story" in html
    assert "ST_001" in html
    assert "Daniel Woste" in html
    assert "Randy Duodu" not in html

    assert "Custom Variant" in html
    assert "CV_0002" in html
    assert "open" in html
    assert "start" in html
    assert "commence" in html

    # Check if referenced link exists in html
    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference '
        'internal" href="#VA_003" title="SPEC_003">VA_003</a></span></span></div>' in html
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/variant_options", "tags": ["tag_a"]}], indirect=True
)
def test_empty_variant_options_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "Empty Variant Options" in html
    assert "EMPTY_VAR_003" in html
    assert (
        '<div class="line"><span class="needs_status"><span class="needs_label">status: </span><span '
        'class="needs_data">[tag_a]:open, unknown</span></span></div>' in html
    )

    assert (
        '<div class="line">links outgoing: <span class="links"><span><span class="needs_dead_link '
        'forbidden">[tag_c]:CV_0002</span>, <span class="needs_dead_link forbidden">[tag_b]:VA_003</span>, '
        '<span class="needs_dead_link '
        'forbidden">unknown</span></span></span></div>' in html
    )
