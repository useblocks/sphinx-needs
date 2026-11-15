import json
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs.variants import VariantFunctionParsed, match_variants
from sphinx_needs_testkit import build_warnings


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
def test_variant_fields_html(test_app, snapshot):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert warning_records == [
        "WARNING: needs_filter_data is deprecated and will be removed in a future version. Use needs_variant_data instead. [needs.deprecated]",
        "<srcdir>/index.rst:33: WARNING: Need could not be created: Link option 'links' is invalid: Unexpected text after closing condition bracket in link \"<<['tag_a' in build_tags]:SPEC_003\": ':SPEC_003'. [needs.create_need]",
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
def test_empty_variant_fields_html(test_app, snapshot):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert warning_records == [
        "WARNING: needs_filter_data is deprecated and will be removed in a future version. Use needs_variant_data instead. [needs.deprecated]",
        'WARNING: Config option "needs_variant_options" is deprecated. Please use "needs_fields" with "parse_variants" instead. [needs.deprecated]',
    ]

    needs = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )

    html = Path(app.outdir, "index.html").read_text()
    assert "Empty Variant Options" in html
    assert "EMPTY_VAR_003" in html


@pytest.mark.parametrize(
    "text,expected_exprs,expected_final_value",
    [
        # a final (default) item may hold ``::``: what remains holds no lone colon
        (
            "[False]:X, SUPPLIER::REQ_2",
            (("False", True, "X"),),
            "SUPPLIER::REQ_2",
        ),
        ("nc::REQ_1", (), "nc::REQ_1"),
        ("x:nc::A, nc::B", (("x", False, "nc::A"),), "nc::B"),
        ("x:nc::A; nc::B", (("x", False, "nc::A"),), "nc::B"),
        (
            "x:nc::A, y:nc::m2::B, a::b::C",
            (("x", False, "nc::A"), ("y", False, "nc::m2::B")),
            "a::b::C",
        ),
        ("a:::b", (), "a:::b"),
        # unchanged
        ("x:nc::A", (("x", False, "nc::A"),), None),
        (
            "[True]:SUPPLIER::REQ_2, Y",
            (("True", True, "SUPPLIER::REQ_2"),),
            "Y",
        ),
        # what remains holds a lone colon: it ends at the FIRST colon, as before
        ("debug::need:`X`", (("debug", False, ":need:`X`"),), None),
        ("nc::A, x:B", (("nc", False, ":A"), ("x", False, "B")), None),
        (
            "x:a, http://example.com",
            (("x", False, "a"), ("http", False, "//example.com")),
            None,
        ),
        ("http://example.com", (("http", False, "//example.com"),), None),
        # the start and the end of the text are not a colon: an edge colon is lone
        (":A", (("", False, "A"),), None),
        ("A:", (("A", False, ""),), None),
        ("nc::A:", (("nc", False, ":A:"),), None),
        ("plain", (), "plain"),
    ],
)
def test_parse_variants_final_item_with_double_colons(
    text, expected_exprs, expected_final_value
):
    """A final item that holds ``::`` and no lone colon is the final value.

    A lone colon is one with no ``:`` before it nor after it. While what remains of
    the text holds one, an item ends its expression at its first colon, as before.
    """
    variant = VariantFunctionParsed.from_string(text, allow_semicolon=True)
    assert variant.expressions == expected_exprs
    assert variant.final_value == expected_final_value


VARIANT_DEFAULT_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"vref": {"nullable": True, "parse_variants": True}}
needs_links = {"vlinks": {"parse_variants": True}}
needs_build_json = True
"""

VARIANT_DEFAULT_INDEX = """\
Variant defaults
================

.. req:: Supplier 1
   :id: SUPPLIER::REQ_1

.. req:: Supplier 2
   :id: SUPPLIER::REQ_2

.. req:: Variant 1
   :id: VARIANT_1
   :vref: <<[False]:X, SUPPLIER::REQ_2>>
   :vlinks: <<[False]:SUPPLIER::REQ_1, SUPPLIER::REQ_2>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), VARIANT_DEFAULT_CONF),
                (Path("index.rst"), VARIANT_DEFAULT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_variant_default_item_holding_double_colons(test_app):
    """A variant's default item may be an id holding ``::`` (default id pattern)."""
    app = test_app
    app.build()

    assert build_warnings(app) == []
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    need = data["versions"][data["current_version"]]["needs"]["VARIANT_1"]
    assert need["vref"] == "SUPPLIER::REQ_2"
    assert need["vlinks"] == ["SUPPLIER::REQ_2"]
