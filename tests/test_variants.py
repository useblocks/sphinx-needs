import json
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.variants import VariantFunctionParsed, match_variants


@pytest.mark.parametrize(
    "text,expected_exprs,expected_final_value",
    [
        ("", (), None),
        ("a", (), "a"),
        ("a,b", (), "a,b"),
        ("a;b", (), "a;b"),
        ("a:yes", (("a", False, "yes"),), None),
        ("a:yes, b:no", (("a", False, "yes"), ("b", False, "no")), None),
        ("a:yes; b:no", (("a", False, "yes"), ("b", False, "no")), None),
        ("a:yes, [b]:no", (("a", False, "yes"), ("b", True, "no")), None),
        ("a:yes; [b]:no", (("a", False, "yes"), ("b", True, "no")), None),
        ("a:yes, no", (("a", False, "yes"),), "no"),
        ("a:yes; no", (("a", False, "yes"),), "no"),
        ("a:yes,\nno", (("a", False, "yes"),), "no"),
        ("[a and b]:yes, no", (("a and b", True, "yes"),), "no"),
        ("a:yes, [b]:no; other", (("a", False, "yes"), ("b", True, "no")), "other"),
    ],
)
def test_parse_variants(text, expected_exprs, expected_final_value):
    variant = VariantFunctionParsed.from_string(text, allow_semicolon=True)
    assert variant.expressions == expected_exprs
    assert variant.final_value == expected_final_value


@pytest.mark.parametrize(
    "option,context,variants,expected",
    [
        ("", {}, {}, None),
        ("a", {}, {}, "a"),
        ("a:yes", {}, {}, None),
        ("a:yes", {"a": False}, {}, None),
        ("a:yes", {"a": True}, {}, "yes"),
        ("[a]:yes", {"a": True}, {}, "yes"),
        ("a:yes, no", {"a": False}, {}, "no"),
        ("a:yes; no", {"a": False}, {}, "no"),
        ("a:yes,\nno", {"a": False}, {}, "no"),
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
def test_variant_options_html(test_app, snapshot):
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    # print(warnings)
    assert warnings == [
        f"{Path(str(app.srcdir)) / 'index.rst'}:29: WARNING: Error while resolving dynamic values for field 'status', of need 'SPEC_004': name 'tag_c' is not defined [needs.dynamic_function]"
    ]

    needs = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )

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


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/variant_options", "tags": ["tag_a"]}],
    indirect=True,
)
def test_empty_variant_options_html(test_app, snapshot):
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == []

    needs = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )

    html = Path(app.outdir, "index.html").read_text()
    assert "Empty Variant Options" in html
    assert "EMPTY_VAR_003" in html
