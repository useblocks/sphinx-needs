from pathlib import Path

import pytest
from sphinx.util.console import strip_colors

from sphinx_needs.utils import match_variants


@pytest.mark.parametrize(
    "option,context,variants,expected",
    [
        ("", {}, {}, None),
        ("a", {}, {}, None),
        ("a:yes", {}, {}, None),
        ("a:yes", {"a": False}, {}, None),
        ("a:yes", {"a": True}, {}, "yes"),
        ("a:yes, no", {"a": False}, {}, "no"),
        ("a:yes; no", {"a": False}, {}, "no"),
        ("[a and b]:yes, no", {"a": True, "b": True}, {}, "yes"),
        ("a:yes, no", {}, {"a": "True"}, "yes"),
        ("a:yes, no", {"b": 1}, {"a": "b == 1"}, "yes"),
        ("a:yes, no", {"b": 2}, {"a": "b == 1"}, "no"),
    ],
)
def test_match_variants(option, context, variants, expected):
    assert match_variants(option, context, variants) == expected


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/variant_doc", "tags": ["tag_a"]}],
    indirect=True,
)
def test_variant_options_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == [
        f"{Path(str(app.srcdir)) / 'index.rst'}:25: WARNING: Error in filter 'tag_c': name 'tag_c' is not defined [needs.variant]"
    ]

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
        'internal" href="#VA_003" title="SPEC_003">VA_003</a></span></span></div>'
        in html
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/variant_options", "tags": ["tag_a"]}],
    indirect=True,
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
