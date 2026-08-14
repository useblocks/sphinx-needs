"""Tests for ``needs_card_layouts`` and the card specification compiler.

The compiler turns declarative card specifications into ``needs_layouts`` entries,
so the tests come in three flavours:

* unit tests of the pure compiler, covering the whole specification vocabulary,
* end-to-end builds proving that a compiled entry actually renders,
* warning tests proving that an invalid card is skipped without costing the build.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.card_layouts import BUILTIN_CARD_SPECS, compile_card_spec
from sphinx_needs.defaults import LAYOUTS

CLEAN_HEAD = (
    '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>> '
    '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
    'visible="icon:arrow-right-circle", initial=False)>> '
)
CLEAN_META = ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"]

KNOWN_FIELDS = frozenset(
    {
        "badge",
        "image",
        "layout",
        "owner",
        "picture",
        "status",
        "style",
        "tags",
        "title",
        "type_name",
        "verified_by",
    }
)

#: The layout functions the compiler is allowed to emit.
#: Anything else would reach the ``unknown layout function`` raise site.
ALLOWED_FUNCTIONS = frozenset(
    {"collapse_button", "image", "meta", "meta_all", "meta_id", "meta_links_all"}
)

#: The four specifications shared verbatim with the ubCode implementation of the
#: same vocabulary. They are the conformance oracle for both: identical input,
#: comparable output.
CONFORMANCE_SPECS: dict[str, dict[str, Any]] = {
    "conformance_full": {
        "header": True,
        "meta": {
            "fields": "effective",
            "exclude": ["tags"],
            "empties": False,
            "links": True,
            "links_back": True,
        },
        "footer": [
            "id",
            "type",
            "layout_echo",
            "style_echo",
            "field:verified_by",
            "image:badge",
        ],
        "collapse": "closed",
    },
    "conformance_side": {
        "header": True,
        "meta": {"fields": "stored"},
        "side": {
            "elements": ["image:picture", "id"],
            "position": "right",
            "span": "partial",
        },
    },
    "conformance_headerless": {
        "header": False,
        "meta": False,
        "footer": ["title", "id"],
    },
    # the object-form twin: headerless, so side and footer can coexist on a grid
    "conformance_object": {
        "header": False,
        "meta": False,
        "side": {
            "elements": [{"type": "image", "field": "image", "height": "40px"}],
            "position": "left",
            "span": "full",
        },
        "footer": [
            {"type": "field", "field": "owner", "label": "Owned by"},
            {"type": "id"},
        ],
    },
}

CONFORMANCE_GRIDS = {
    "conformance_full": "simple_footer",
    "conformance_side": "simple_side_right_partial",
    "conformance_headerless": "content_footer",
    "conformance_object": "content_footer_side_left",
}

#: Every valid specification exercised anywhere in this file, so that the
#: "never emit anything dangerous" test can sweep the full matrix.
VALID_SPECS: dict[str, dict[str, Any]] = {
    **{f"builtin_{name}": spec for name, spec in BUILTIN_CARD_SPECS.items()},
    **CONFORMANCE_SPECS,
    "empty": {},
    "content_explicit": {"content": True},
    "no_meta": {"meta": False},
    "meta_effective": {"meta": {"fields": "effective"}},
    "meta_all": {"meta": {"fields": "all"}},
    "meta_all_empties": {"meta": {"fields": "all", "empties": True}},
    "meta_all_no_links": {"meta": {"fields": "all", "links": False}},
    "meta_exclude": {"meta": {"exclude": ["status", "tags"]}},
    "meta_include": {"meta": {"include": ["status", "tags"]}},
    "meta_include_empties": {"meta": {"include": ["status"], "empties": True}},
    "meta_include_exclude": {
        "meta": {"include": ["status", "tags"], "exclude": ["tags"]}
    },
    "meta_no_links": {"meta": {"links": False}},
    "meta_empties": {"meta": {"empties": True}},
    "collapse_closed": {"collapse": "closed"},
    "collapse_open": {"collapse": "open"},
    "footer_all_elements": {
        "footer": [
            "id",
            "type",
            "layout_echo",
            "style_echo",
            "field:verified_by",
            "image:badge",
        ]
    },
    "footer_title_headerless": {
        "header": False,
        "meta": False,
        "footer": ["title"],
    },
    "side_left_full": {"side": {"elements": ["image:image"], "position": "left"}},
    "side_right_partial": {
        "side": {"elements": ["id"], "position": "right", "span": "partial"}
    },
    "side_empty": {"side": {"elements": []}},
    "side_false": {"side": False},
    "extends_side_false": {"extends": "clean_l", "side": False},
    "headerless_side": {
        "header": False,
        "meta": False,
        "side": {"elements": ["id"], "position": "right"},
    },
    "headerless_side_footer": {
        "header": False,
        "meta": False,
        "footer": ["id"],
        "side": {"elements": ["image:badge"], "position": "left"},
    },
    "headerless_plain": {"header": False, "meta": False},
    "extends_override": {
        "extends": "clean_r",
        "meta": {"fields": "all"},
        "collapse": "closed",
    },
    "object_footer_optionless": {
        "footer": [
            {"type": "id"},
            {"type": "field", "field": "verified_by"},
            {"type": "image", "field": "badge"},
        ]
    },
    "object_footer_label": {
        "footer": [{"type": "field", "field": "verified_by", "label": "Verified by"}]
    },
    "object_image_options": {
        "footer": [
            {"type": "image", "field": "badge", "height": "40px", "width": "3.5em"}
        ]
    },
    "object_side_height": {
        "side": {
            "elements": [{"type": "image", "field": "picture", "height": "40"}],
            "position": "right",
        }
    },
    "object_title_headerless": {
        "header": False,
        "meta": False,
        "footer": [{"type": "title"}],
    },
    "object_mixed_spellings": {
        "footer": ["id", {"type": "field", "field": "status", "label": "State"}]
    },
}


def compile_spec(
    spec: dict[str, Any],
    *,
    name: str = "card",
    specs: dict[str, Any] | None = None,
    known_fields: Any = KNOWN_FIELDS,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Compile a specification, collecting the warnings it produces."""
    messages: list[str] = []
    compiled = compile_card_spec(
        name,
        spec,
        specs={} if specs is None else specs,
        known_fields=known_fields,
        warn=messages.append,
    )
    return compiled, messages


def scrub(html: str) -> str:
    """Replace the random collapse-container ids, which differ per build."""
    return re.sub(r"SNCB-[0-9a-f]{8}", "SNCB-XXXXXXXX", html)


def need_table(html: str, need_id: str) -> str:
    """Extract the rendered table of a single need."""
    end = html.index("</table>", html.index(f'id="{need_id}">'))
    start = html.rindex('<table class="need ', 0, end)
    return html[start : end + len("</table>")]


# --------------------------------------------------------------------------
# unit tests: the specification vocabulary
# --------------------------------------------------------------------------


def test_default_spec_is_clean() -> None:
    """An empty specification is, by definition, the ``clean`` card."""
    compiled, messages = compile_spec({})
    assert messages == []
    assert compiled == {
        "grid": "simple",
        "layout": {"head": [CLEAN_HEAD], "meta": CLEAN_META},
    }


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        ("id", "<<meta_id()>>"),
        ("title", '<<meta("title")>>'),
        ("type", '<<meta("type_name")>>'),
        ("layout_echo", 'layout: <<meta("layout")>>'),
        ("style_echo", 'style: <<meta("style")>>'),
        ("field:verified_by", '<<meta("verified_by")>>'),
        ("image:badge", '<<image("field:badge", align="center")>>'),
        ({"type": "id"}, "<<meta_id()>>"),
        ({"type": "title"}, '<<meta("title")>>'),
        ({"type": "type"}, '<<meta("type_name")>>'),
        ({"type": "layout_echo"}, 'layout: <<meta("layout")>>'),
        ({"type": "style_echo"}, 'style: <<meta("style")>>'),
        ({"type": "field", "field": "verified_by"}, '<<meta("verified_by")>>'),
        (
            {"type": "image", "field": "badge"},
            '<<image("field:badge", align="center")>>',
        ),
        (
            {"type": "field", "field": "verified_by", "label": "Verified by"},
            '<<meta("verified_by", prefix="Verified by: ")>>',
        ),
        (
            {"type": "image", "field": "badge", "height": "40px"},
            '<<image("field:badge", height="40px", align="center")>>',
        ),
        (
            {"type": "image", "field": "badge", "width": "50%"},
            '<<image("field:badge", width="50%", align="center")>>',
        ),
        (
            {"type": "image", "field": "badge", "height": "40px", "width": "3.5em"},
            '<<image("field:badge", height="40px", width="3.5em", align="center")>>',
        ),
    ],
)
def test_footer_element_mapping(element: str | dict[str, Any], expected: str) -> None:
    """Every element of the shared vocabulary maps to one layout line."""
    compiled, messages = compile_spec(
        {"header": False, "meta": False, "footer": [element]}
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["footer"] == [expected]


def test_side_uses_the_same_element_set() -> None:
    """``side.elements`` ranges over the same vocabulary as ``footer``."""
    compiled, messages = compile_spec(
        {"side": {"elements": ["image:picture", "id"], "position": "right"}}
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["side"] == [
        '<<image("field:picture", align="center")>>',
        "<<meta_id()>>",
    ]


def test_footer_keeps_element_order() -> None:
    """Elements are emitted in the order they were declared."""
    compiled, _ = compile_spec(
        {"header": False, "meta": False, "footer": ["type", "id", "layout_echo"]}
    )
    assert compiled is not None
    assert compiled["layout"]["footer"] == [
        '<<meta("type_name")>>',
        "<<meta_id()>>",
        'layout: <<meta("layout")>>',
    ]


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        pytest.param({"fields": "stored"}, CLEAN_META, id="stored"),
        # upstream has no stored/effective distinction: `meta_all` always iterates
        # the whole need, so both tiers compile to the same call
        pytest.param({"fields": "effective"}, CLEAN_META, id="effective"),
        pytest.param(
            {"fields": "all"},
            ["<<meta_all(exclude=[], defaults=False)>>"],
            id="all",
        ),
        pytest.param(
            {"fields": "all", "empties": True},
            ["<<meta_all(exclude=[], defaults=False, show_empty=True)>>"],
            id="all-empties",
        ),
        pytest.param(
            {"fields": "all", "links": False},
            ["<<meta_all(exclude=[], no_links=True, defaults=False)>>"],
            id="all-no-links",
        ),
        pytest.param(
            {"fields": "all", "exclude": ["status"]},
            ['<<meta_all(exclude=["status"], defaults=False)>>'],
            id="all-exclude",
        ),
        pytest.param(
            {"exclude": ["layout", "style"]},
            [
                '<<meta_all(no_links=True, exclude=["layout","style"])>>',
                "<<meta_links_all()>>",
            ],
            id="exclude",
        ),
        pytest.param(
            {"empties": True},
            ["<<meta_all(no_links=True, show_empty=True)>>", "<<meta_links_all()>>"],
            id="empties",
        ),
        pytest.param(
            {"links": False},
            ["<<meta_all(no_links=True)>>"],
            id="no-links",
        ),
        pytest.param(
            {"include": ["status", "tags"]},
            ['<<meta("status")>>', '<<meta("tags")>>', "<<meta_links_all()>>"],
            id="include",
        ),
        pytest.param(
            {"include": ["status"], "empties": True},
            ['<<meta("status", show_empty=True)>>', "<<meta_links_all()>>"],
            id="include-empties",
        ),
        pytest.param(
            {"include": ["status", "tags"], "exclude": ["tags"], "links": False},
            ['<<meta("status")>>'],
            id="include-minus-exclude",
        ),
    ],
)
def test_meta_tier_mapping(meta: dict[str, Any], expected: list[str]) -> None:
    """Each meta tier and switch maps onto the documented ``meta_all`` call."""
    compiled, messages = compile_spec({"meta": meta})
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["meta"] == expected


def test_meta_false_emits_no_meta_section() -> None:
    """``meta = false`` drops the region, and with it the disclosure button."""
    compiled, messages = compile_spec({"header": False, "meta": False})
    assert messages == []
    assert compiled == {"grid": "content", "layout": {}}


@pytest.mark.parametrize(
    ("collapse", "expected_initial"),
    [("honour", "initial=False"), ("closed", "initial=True")],
)
def test_collapse_button_initial(collapse: str, expected_initial: str) -> None:
    """``honour`` starts expanded, ``closed`` starts collapsed."""
    compiled, messages = compile_spec({"collapse": collapse})
    assert messages == []
    assert compiled is not None
    head = compiled["layout"]["head"][0]
    assert "collapse_button" in head
    assert expected_initial in head


def test_collapse_open_emits_no_button() -> None:
    """``open`` pins the meta region open by leaving out the toggle entirely."""
    compiled, messages = compile_spec({"collapse": "open"})
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["head"] == [
        '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>'
    ]


def test_collapse_button_requires_a_meta_region() -> None:
    """No meta row means no collapse button, whatever ``collapse`` says.

    The button targets the ``meta`` row, and the collapse JavaScript does not
    guard against that row being absent.
    """
    compiled, messages = compile_spec({"meta": False, "collapse": "closed"})
    assert messages == []
    assert compiled is not None
    assert "collapse_button" not in "".join(compiled["layout"]["head"])


def test_at_most_one_collapse_button() -> None:
    """A compiled card never carries more than one collapse button."""
    for spec in VALID_SPECS.values():
        compiled, _ = compile_spec(spec)
        assert compiled is not None
        emitted = "".join(
            line for lines in compiled["layout"].values() for line in lines
        )
        assert emitted.count("collapse_button") <= 1


@pytest.mark.parametrize(
    ("spec", "grid"),
    [
        pytest.param({}, "simple", id="header-meta"),
        pytest.param({"meta": False}, "simple", id="header-only"),
        pytest.param({"footer": ["id"]}, "simple_footer", id="header-footer"),
        pytest.param(
            {"side": {"elements": ["id"], "position": "left"}},
            "simple_side_left",
            id="side-left-full",
        ),
        pytest.param(
            {"side": {"elements": ["id"], "position": "right"}},
            "simple_side_right",
            id="side-right-full",
        ),
        pytest.param(
            {"side": {"elements": ["id"], "position": "left", "span": "partial"}},
            "simple_side_left_partial",
            id="side-left-partial",
        ),
        pytest.param(
            {"side": {"elements": ["id"], "position": "right", "span": "partial"}},
            "simple_side_right_partial",
            id="side-right-partial",
        ),
        pytest.param({"header": False, "meta": False}, "content", id="content"),
        pytest.param(
            {"header": False, "meta": False, "footer": ["id"]},
            "content_footer",
            id="content-footer",
        ),
        pytest.param(
            {
                "header": False,
                "meta": False,
                "side": {"elements": ["id"], "position": "left"},
            },
            "content_side_left",
            id="content-side-left",
        ),
        pytest.param(
            {
                "header": False,
                "meta": False,
                "side": {"elements": ["id"], "position": "right"},
            },
            "content_side_right",
            id="content-side-right",
        ),
        pytest.param(
            {
                "header": False,
                "meta": False,
                "footer": ["id"],
                "side": {"elements": ["id"], "position": "left"},
            },
            "content_footer_side_left",
            id="content-footer-side-left",
        ),
        pytest.param(
            {
                "header": False,
                "meta": False,
                "footer": ["id"],
                "side": {"elements": ["id"], "position": "right"},
            },
            "content_footer_side_right",
            id="content-footer-side-right",
        ),
        pytest.param(
            {"side": {"elements": [], "position": "left"}},
            "simple",
            id="empty-side-is-no-side",
        ),
        pytest.param({"side": False}, "simple", id="false-side-is-no-side"),
    ],
)
def test_grid_selection(spec: dict[str, Any], grid: str) -> None:
    """The regions of a specification determine the grid unambiguously."""
    compiled, messages = compile_spec(spec)
    assert messages == []
    assert compiled is not None
    assert compiled["grid"] == grid


@pytest.mark.parametrize(
    "no_side",
    [
        pytest.param(False, id="false"),
        pytest.param({"elements": []}, id="empty-elements"),
    ],
)
@pytest.mark.parametrize(
    "spec",
    [
        pytest.param({}, id="direct"),
        pytest.param({"extends": "clean_l"}, id="extends-side-left"),
        pytest.param({"extends": "clean_rp"}, id="extends-side-right-partial"),
    ],
)
def test_side_opt_out_spellings(spec: dict[str, Any], no_side: Any) -> None:
    """``side = false`` and an empty ``elements`` list both mean "no side region".

    Both spellings are legal, and both must also work as an opt-out from a base
    that does carry a side region -- otherwise a card could inherit a side region
    it has no way to decline.
    """
    compiled, messages = compile_spec({**spec, "side": no_side})
    assert messages == []
    assert compiled is not None
    assert compiled["grid"] == "simple"
    assert "side" not in compiled["layout"]


def test_side_opt_out_leaves_the_rest_of_the_base_intact() -> None:
    """Declining the side region does not decline anything else it inherited."""
    with_side, _ = compile_spec({"extends": "clean_rp"})
    without_side, messages = compile_spec({"extends": "clean_rp", "side": False})
    assert messages == []
    assert with_side is not None
    assert without_side is not None
    assert without_side["layout"]["head"] == with_side["layout"]["head"]
    assert without_side["layout"]["meta"] == with_side["layout"]["meta"]
    assert set(with_side["layout"]) - set(without_side["layout"]) == {"side"}


@pytest.mark.parametrize(
    ("base", "grid"),
    [
        ("clean", "simple"),
        ("clean_l", "simple_side_left"),
        ("clean_lp", "simple_side_left_partial"),
        ("clean_r", "simple_side_right"),
        ("clean_rp", "simple_side_right_partial"),
        # `complete` uses the six column `complex` grid upstream, which the
        # compiler never targets: the same regions land on `simple_footer`
        ("complete", "simple_footer"),
        ("debug", "simple"),
        # `focus` carries the id footer, i.e. upstream's `focus_f`
        ("focus", "content_footer"),
        ("focus_f", "content_footer"),
        ("focus_l", "content_side_left"),
        ("focus_r", "content_side_right"),
        ("test", "simple"),
    ],
)
def test_extends_from_every_builtin(base: str, grid: str) -> None:
    """Every built-in specification works as an ``extends`` base."""
    assert sorted(BUILTIN_CARD_SPECS) == sorted(
        {
            "clean",
            "clean_l",
            "clean_lp",
            "clean_r",
            "clean_rp",
            "complete",
            "debug",
            "focus",
            "focus_f",
            "focus_l",
            "focus_r",
            "test",
        }
    )
    compiled, messages = compile_spec({"extends": base})
    assert messages == []
    assert compiled is not None
    assert compiled["grid"] == grid


def test_extends_inherits_and_overrides() -> None:
    """Keys given by the card win, keys it omits are inherited."""
    compiled, messages = compile_spec(
        {"extends": "clean_rp", "collapse": "closed"},
    )
    assert messages == []
    assert compiled is not None
    assert compiled["grid"] == "simple_side_right_partial"
    assert compiled["layout"]["side"] == ['<<image("field:image", align="center")>>']
    assert "initial=True" in compiled["layout"]["head"][0]


def test_extends_merges_sub_tables() -> None:
    """A partially given ``meta`` merges onto the base's ``meta``."""
    compiled, messages = compile_spec(
        {"extends": "base", "meta": {"empties": True}},
        specs={"base": {"meta": {"exclude": ["status"]}}},
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["meta"][0] == (
        '<<meta_all(no_links=True, exclude=["status"], show_empty=True)>>'
    )


def test_extends_chain_of_user_specs() -> None:
    """``extends`` chains follow user specifications as well as built-ins."""
    compiled, messages = compile_spec(
        {"extends": "middle"},
        name="leaf",
        specs={
            "middle": {"extends": "root", "collapse": "closed"},
            "root": {"footer": ["id"]},
        },
    )
    assert messages == []
    assert compiled is not None
    assert compiled["grid"] == "simple_footer"
    assert "initial=True" in compiled["layout"]["head"][0]


@pytest.mark.parametrize("name", sorted(BUILTIN_CARD_SPECS))
def test_builtin_specs_are_never_mutated(name: str) -> None:
    """Compiling must not touch the shipped specification table."""
    before = copy.deepcopy(BUILTIN_CARD_SPECS[name])
    compile_spec({"extends": name, "collapse": "closed", "meta": {"empties": True}})
    assert BUILTIN_CARD_SPECS[name] == before


def test_resolved_spec_shares_no_state_with_its_base() -> None:
    """A resolved specification must not alias the table it inherited from.

    Reading a resolved specification cannot reveal aliasing, so this writes to it:
    if the ``extends`` base were taken by reference rather than copied, the write
    would land in ``BUILTIN_CARD_SPECS`` — and, through the same class of bug, in
    the layout registry's shared ``LAYOUT_COMMON_SIDE`` object, which four built-in
    layouts alias.
    """
    from sphinx_needs.card_layouts import _resolve_extends

    specs_before = copy.deepcopy(BUILTIN_CARD_SPECS)
    layouts_before = copy.deepcopy(LAYOUTS)

    messages: list[str] = []
    resolved = _resolve_extends("card", {"extends": "clean_l"}, {}, messages.append)
    assert messages == []
    assert resolved is not None
    merged, _ = resolved

    # write through every level of the resolved specification
    merged["collapse"] = "closed"
    merged["side"]["position"] = "right"
    merged["side"]["elements"].append("id")

    assert specs_before == BUILTIN_CARD_SPECS
    assert layouts_before == LAYOUTS


@pytest.mark.parametrize(
    "name",
    ["clean_l", "clean_lp", "clean_r", "clean_rp", "focus_f", "focus_l", "focus_r"],
)
def test_builtin_permutations_round_trip(name: str) -> None:
    """The seven permutations compile back to their upstream definitions.

    This is the fidelity check for the shared vocabulary: the specification of a
    built-in layout must produce exactly that layout again.
    """
    compiled, messages = compile_spec(BUILTIN_CARD_SPECS[name], name=f"card_{name}")
    assert messages == []
    assert compiled == {
        "grid": LAYOUTS[name]["grid"],
        "layout": LAYOUTS[name]["layout"],
    }


def test_clean_round_trip_differs_only_in_whitespace() -> None:
    """``clean`` round-trips to the ``clean_l`` family's spelling of the head line.

    Upstream writes two spaces before the collapse button in ``clean`` but one in
    the ``clean_*`` layouts; the compiler has a single canonical template.
    """
    compiled, _ = compile_spec(BUILTIN_CARD_SPECS["clean"], name="card_clean")
    assert compiled is not None
    upstream = LAYOUTS["clean"]["layout"]
    assert compiled["layout"]["meta"] == upstream["meta"]
    assert compiled["layout"]["head"][0].replace(" ", "") == upstream["head"][
        0
    ].replace(" ", "")


# --------------------------------------------------------------------------
# unit tests: the object form
# --------------------------------------------------------------------------

#: Every string element paired with its object-form spelling.
OBJECT_TWINS: list[tuple[str, dict[str, Any]]] = [
    ("id", {"type": "id"}),
    ("title", {"type": "title"}),
    ("type", {"type": "type"}),
    ("layout_echo", {"type": "layout_echo"}),
    ("style_echo", {"type": "style_echo"}),
    ("field:verified_by", {"type": "field", "field": "verified_by"}),
    ("image:badge", {"type": "image", "field": "badge"}),
]


@pytest.mark.parametrize(
    ("string", "obj"), OBJECT_TWINS, ids=[string for string, _ in OBJECT_TWINS]
)
def test_optionless_object_equals_its_string_shorthand(
    string: str, obj: dict[str, Any]
) -> None:
    """An optionless object compiles byte-identically to its string shorthand.

    This is the hard equivalence requirement of the object form:
    same resolved specification, same compiled layout strings.
    """
    compiled_string, string_messages = compile_spec(
        {"header": False, "meta": False, "footer": [string]}
    )
    compiled_object, object_messages = compile_spec(
        {"header": False, "meta": False, "footer": [obj]}
    )
    assert string_messages == object_messages == []
    assert compiled_string is not None
    assert compiled_string == compiled_object


def test_optionless_object_equivalence_holds_in_the_side_region() -> None:
    """The equivalence guarantee covers ``side.elements`` as well as ``footer``."""
    compiled_string, _ = compile_spec(
        {"side": {"elements": ["image:picture", "id"], "position": "right"}}
    )
    compiled_object, messages = compile_spec(
        {
            "side": {
                "elements": [{"type": "image", "field": "picture"}, {"type": "id"}],
                "position": "right",
            }
        }
    )
    assert messages == []
    assert compiled_string is not None
    assert compiled_string == compiled_object


def test_spellings_mix_freely_in_one_list() -> None:
    """Strings and objects are two spellings of one vocabulary, not two modes."""
    compiled, messages = compile_spec(
        {"footer": ["id", {"type": "field", "field": "status", "label": "State"}]}
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["footer"] == [
        "<<meta_id()>>",
        '<<meta("status", prefix="State: ")>>',
    ]


@pytest.mark.parametrize(
    "label",
    [
        pytest.param("x", id="single-char"),
        pytest.param("Owned by", id="space"),
        pytest.param("A 0_().,/-9", id="all-allowed-chars"),
        pytest.param("a" * 64, id="max-length"),
    ],
)
def test_label_grammar_accepts_its_edges(label: str) -> None:
    """The label grammar's boundary values are all usable."""
    compiled, messages = compile_spec(
        {"footer": [{"type": "field", "field": "status", "label": label}]}
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["footer"] == [f'<<meta("status", prefix="{label}: ")>>']


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("40", id="bare-number-means-px"),
        pytest.param("40.5", id="decimal"),
        pytest.param("40px", id="px"),
        pytest.param("3.5em", id="em"),
        pytest.param("2rem", id="rem"),
        pytest.param("100%", id="percent"),
        pytest.param("12pt", id="pt"),
        pytest.param("1234567890.123px", id="max-length"),
    ],
)
def test_dimension_grammar_accepts_its_edges(value: str) -> None:
    """The height/width grammar's boundary values are all usable."""
    compiled, messages = compile_spec(
        {"footer": [{"type": "image", "field": "badge", "height": value}]}
    )
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["footer"] == [
        f'<<image("field:badge", height="{value}", align="center")>>'
    ]


# --------------------------------------------------------------------------
# unit tests: validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        pytest.param({"nope": 1}, "unknown key(s) 'nope'", id="unknown-key"),
        pytest.param(
            {"meta": {"nope": 1}},
            "unknown key(s) 'nope' in 'meta'",
            id="unknown-meta-key",
        ),
        pytest.param(
            {"side": {"nope": 1}},
            "unknown key(s) 'nope' in 'side'",
            id="unknown-side-key",
        ),
        pytest.param(
            {"meta": {"fields": "some"}}, "'meta.fields' must be one of", id="bad-tier"
        ),
        pytest.param(
            {"collapse": "maybe"}, "'collapse' must be one of", id="bad-collapse"
        ),
        pytest.param(
            {"side": {"elements": ["id"], "position": "top"}},
            "'side.position' must be one of",
            id="bad-position",
        ),
        pytest.param(
            {"side": {"elements": ["id"], "span": "half"}},
            "'side.span' must be one of",
            id="bad-span",
        ),
        pytest.param({"header": "yes"}, "'header' must be a boolean", id="bad-header"),
        pytest.param(
            {"meta": {"links": "yes"}}, "'meta.links' must be a boolean", id="bad-links"
        ),
        pytest.param(
            {"footer": "id"}, "'footer' must be a list of strings", id="bad-footer"
        ),
        pytest.param({"meta": 3}, "'meta' must be a dict or false", id="bad-meta"),
        pytest.param({"side": 3}, "'side' must be a dict or false", id="bad-side"),
        pytest.param({"side": True}, "'side' must be a dict or false", id="side-true"),
        # 0 is falsy but is not False: the opt-out is an identity check, and a
        # truthiness regression would silently accept every falsy value here.
        pytest.param({"side": 0}, "'side' must be a dict or false", id="side-zero"),
        pytest.param(
            {"content": False}, "'content' cannot be disabled", id="content-false"
        ),
        pytest.param(
            {"footer": ["nonsense"]},
            "unknown footer element 'nonsense'",
            id="bad-element",
        ),
        pytest.param(
            {"footer": ["field:bad name"]},
            "invalid field name 'bad name'",
            id="bad-field-identifier",
        ),
        pytest.param(
            {"footer": ["image:../etc"]},
            "invalid field name '../etc'",
            id="bad-image-identifier",
        ),
        pytest.param(
            {"meta": {"include": ["not ok"]}},
            "invalid field name 'not ok' in 'meta.include'",
            id="bad-include-identifier",
        ),
        pytest.param(
            {"extends": "nowhere"}, "unknown 'extends' base", id="unknown-base"
        ),
        pytest.param({"extends": 4}, "'extends' must be a string", id="bad-extends"),
        pytest.param(
            {"footer": ["title"]},
            "the 'title' element is only allowed when 'header' is false",
            id="title-with-header",
        ),
        pytest.param(
            {
                "header": False,
                "meta": False,
                "footer": ["title"],
                "side": {"elements": ["title"]},
            },
            "the 'title' element may only be used in one region",
            id="title-twice",
        ),
        pytest.param(
            {"footer": ["id"], "side": {"elements": ["id"]}},
            "a card with a header, a side region and a footer is not expressible",
            id="header-side-footer",
        ),
        pytest.param(
            {"header": False},
            "a card with a meta region but no header is not expressible",
            id="meta-without-header",
        ),
        # --- object-form elements
        pytest.param(
            {"footer": [{"type": "nonsense"}]},
            "footer element 'type' must be one of",
            id="object-unknown-type",
        ),
        pytest.param(
            {"footer": [{}]},
            "footer element 'type' must be one of",
            id="object-missing-type",
        ),
        pytest.param(
            {"footer": [{"type": "field"}]},
            "'field' is required in a 'field' footer element",
            id="object-field-missing-field",
        ),
        pytest.param(
            {"footer": [{"type": "image"}]},
            "'field' is required in a 'image' footer element",
            id="object-image-missing-field",
        ),
        pytest.param(
            {"side": {"elements": [{"type": "image"}]}},
            "'field' is required in a 'image' side element",
            id="object-side-missing-field",
        ),
        pytest.param(
            {"footer": [{"type": "id", "field": "status"}]},
            "key(s) 'field' not allowed in a 'id' footer element",
            id="object-field-on-id",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "height": "40px"}]},
            "key(s) 'height' not allowed in a 'field' footer element",
            id="object-height-on-field",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "label": "Badge"}]},
            "key(s) 'label' not allowed in a 'image' footer element",
            id="object-label-on-image",
        ),
        pytest.param(
            {"footer": [{"type": "id", "label": "ID"}]},
            "key(s) 'label' not allowed in a 'id' footer element",
            id="object-label-on-id",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "nope": 1}]},
            "key(s) 'nope' not allowed in a 'image' footer element",
            id="object-unknown-key",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "bad name"}]},
            "invalid field name 'bad name'",
            id="object-bad-field-name",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": 3}]},
            "invalid field name 3",
            id="object-non-string-field",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "height": "40 px"}]},
            "'height' must be a number",
            id="object-bad-height",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "width": "-40px"}]},
            "'width' must be a number",
            id="object-bad-width",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "height": 40}]},
            "'height' must be a number",
            id="object-non-string-height",
        ),
        pytest.param(
            {
                "footer": [
                    {"type": "image", "field": "badge", "height": "1234567890.1234px"}
                ]
            },
            "'height' must be a number",
            id="object-height-too-long",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": "bad*label"}]},
            "'label' must be 1-64 characters",
            id="object-label-rst-char",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": " padded"}]},
            "'label' must be 1-64 characters",
            id="object-label-leading-space",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": "padded "}]},
            "'label' must be 1-64 characters",
            id="object-label-trailing-space",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": "-dash"}]},
            "'label' must be 1-64 characters",
            id="object-label-non-alnum-start",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": ""}]},
            "'label' must be 1-64 characters",
            id="object-empty-label",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": "a" * 65}]},
            "'label' must be 1-64 characters",
            id="object-label-too-long",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": 3}]},
            "'label' must be 1-64 characters",
            id="object-non-string-label",
        ),
        pytest.param(
            {"footer": [3]},
            "footer element must be a string or a dict",
            id="object-non-str-non-dict-entry",
        ),
        pytest.param(
            {"side": {"elements": [None]}},
            "side element must be a string or a dict",
            id="object-side-bad-entry",
        ),
        pytest.param(
            {"footer": [{"type": "title"}]},
            "the 'title' element is only allowed when 'header' is false",
            id="object-title-with-header",
        ),
    ],
)
def test_invalid_specs_are_skipped_with_a_warning(
    spec: dict[str, Any], expected: str
) -> None:
    """Every validation failure warns and skips, and never raises."""
    compiled, messages = compile_spec(spec)
    assert compiled is None
    assert any(expected in message for message in messages), messages


def test_extends_cycle_is_detected() -> None:
    """A cyclic ``extends`` chain is reported rather than looping forever."""
    compiled, messages = compile_spec(
        {"extends": "b"},
        name="a",
        specs={"a": {"extends": "b"}, "b": {"extends": "a"}},
    )
    assert compiled is None
    assert any("circular 'extends' chain" in message for message in messages), messages


def test_self_extends_is_a_cycle() -> None:
    """A card extending itself is a cycle too."""
    compiled, messages = compile_spec({"extends": "a"}, name="a", specs={"a": {}})
    assert compiled is None
    assert any("circular 'extends' chain" in message for message in messages), messages


def test_links_back_alone_degrades_with_a_warning() -> None:
    """Back links cannot be suppressed on their own, so the card says so.

    The link types are not yet known when card layouts are compiled, so the meta
    region is realised with back links included.
    """
    compiled, messages = compile_spec({"meta": {"links": True, "links_back": False}})
    assert compiled is not None
    assert compiled["layout"]["meta"] == CLEAN_META
    assert any("'meta.links_back' cannot be disabled" in m for m in messages), messages


def test_links_false_needs_no_degradation_warning() -> None:
    """With all links off there is nothing to degrade."""
    compiled, messages = compile_spec({"meta": {"links": False, "links_back": False}})
    assert messages == []
    assert compiled is not None
    assert compiled["layout"]["meta"] == ["<<meta_all(no_links=True)>>"]


def test_headerless_partial_side_degrades_to_full() -> None:
    """There is no partial side grid without a header, so it becomes full."""
    compiled, messages = compile_spec(
        {
            "header": False,
            "meta": False,
            "side": {"elements": ["id"], "position": "left", "span": "partial"},
        }
    )
    assert compiled is not None
    assert compiled["grid"] == "content_side_left"
    assert any("no partial side grid" in message for message in messages), messages


@pytest.mark.parametrize(
    "spec",
    [
        pytest.param({"footer": ["field:unknown_field"]}, id="field"),
        pytest.param({"footer": ["image:unknown_field"]}, id="image"),
        pytest.param({"side": {"elements": ["image:unknown_field"]}}, id="side-image"),
        pytest.param(
            {"footer": [{"type": "field", "field": "unknown_field"}]},
            id="object-field",
        ),
        pytest.param(
            {"side": {"elements": [{"type": "image", "field": "unknown_field"}]}},
            id="object-side-image",
        ),
    ],
)
def test_unregistered_field_warns_but_still_compiles(spec: dict[str, Any]) -> None:
    """A misspelled field name renders empty, so it is worth a warning."""
    compiled, messages = compile_spec(spec)
    assert compiled is not None
    assert any("not registered" in message for message in messages), messages


def test_builtin_image_field_is_exempt_from_the_field_check() -> None:
    """``clean_l`` and friends reference an ``image`` field nobody has to define.

    That is upstream behaviour, so inheriting it must not produce a warning.
    """
    compiled, messages = compile_spec({"extends": "clean_l"}, known_fields=())
    assert messages == []
    assert compiled is not None


def test_overriding_an_inherited_region_restores_the_field_check() -> None:
    """Once a card writes its own region, its field names are its own."""
    _, messages = compile_spec(
        {"extends": "clean_l", "side": {"elements": ["image:typo"]}}, known_fields=()
    )
    assert any("not registered" in message for message in messages), messages


# --------------------------------------------------------------------------
# unit tests: emission safety
# --------------------------------------------------------------------------


def test_compiler_never_emits_dangerous_constructs() -> None:
    """Sweep the whole matrix for the emissions that break a build.

    ``is_external`` performs a network fetch and writes into the source tree,
    ``{{`` is a need placeholder that raises when it cannot be resolved, and an
    unknown layout function raises out of every ``except Exception`` in Sphinx.
    """
    for spec_name, spec in VALID_SPECS.items():
        compiled, _ = compile_spec(spec)
        assert compiled is not None, spec_name
        for section, lines in compiled["layout"].items():
            for line in lines:
                assert "is_external" not in line, (spec_name, section, line)
                assert "{{" not in line, (spec_name, section, line)
                for call in re.findall(r"<<\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", line):
                    assert call in ALLOWED_FUNCTIONS, (spec_name, section, line)
                assert line.count("<<") == line.count(">>"), (spec_name, section, line)


def test_compiled_sections_are_read_by_their_grid() -> None:
    """A section the chosen grid does not read would be silently dropped."""
    from sphinx_needs.card_layouts import _GRID_SECTIONS

    for spec_name, spec in VALID_SPECS.items():
        compiled, _ = compile_spec(spec)
        assert compiled is not None, spec_name
        assert set(compiled["layout"]) <= _GRID_SECTIONS[compiled["grid"]], spec_name


# --------------------------------------------------------------------------
# end-to-end builds
# --------------------------------------------------------------------------

INDEX = """\
Card layouts
============

.. req:: A requirement
   :id: CARD_1
   :status: open
   :tags: a
   :layout: my_card

   Requirement body.
"""


def conf_py(specs: dict[str, Any], extra: str = "") -> str:
    """Build a ``conf.py`` declaring the given card specifications."""
    return f"extensions = ['sphinx_needs']\nneeds_card_layouts = {specs!r}\n{extra}\n"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py({"my_card": {"footer": ["id", "type"]}}),
                ),
                (Path("index.rst"), INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_compiled_card_renders(test_app: Any) -> None:
    """A compiled card is a first class layout: it renders and warns about nothing."""
    app = test_app
    app.build()
    assert app.warning_list == []

    table = need_table((app.outdir / "index.html").read_text(), "CARD_1")
    assert 'class="need needs_grid_simple_footer needs_layout_my_card' in table
    # head, meta, content and footer rows
    assert '<tr class="need head row-odd"><td class="need head">' in table
    assert '<tr class="need meta row-even"><td class="need meta">' in table
    assert (
        '<tr class="need footer row-even"><td class="need footer" colspan="1">' in table
    )
    # the footer elements, in the order they were declared
    footer = table.split('<td class="need footer"')[1]
    assert footer.index('class="needs-id"') < footer.index('class="needs_type_name"')


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py(
                        {
                            "card_side": {
                                "side": {
                                    "elements": ["id"],
                                    "position": "right",
                                    "span": "partial",
                                }
                            }
                        }
                    ),
                ),
                (
                    Path("index.rst"),
                    INDEX.replace("my_card", "card_side"),
                ),
            ],
        }
    ],
    indirect=True,
)
def test_compiled_side_card_skeleton(test_app: Any) -> None:
    """A partial side region spans the head and meta rows only."""
    app = test_app
    app.build()
    assert app.warning_list == []

    html = scrub((app.outdir / "index.html").read_text())
    assert "needs_grid_simple_side_right_partial needs_layout_card_side" in html
    assert '<td class="need side" rowspan="2">' in html
    assert '<td class="need content" colspan="2">' in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py({"card_focus": {"header": False, "meta": False}}),
                ),
                (Path("index.rst"), INDEX.replace("my_card", "card_focus")),
            ],
        }
    ],
    indirect=True,
)
def test_headerless_card_renders_only_the_content(test_app: Any) -> None:
    """A headerless, meta-less card is a bare content cell."""
    app = test_app
    app.build()
    assert app.warning_list == []

    html = (app.outdir / "index.html").read_text()
    assert "needs_grid_content needs_layout_card_focus" in html
    assert '<tr class="content row-odd"><td class="content">' in html
    assert "needs_head" not in html
    assert "needs_meta" not in html


CONFORMANCE_INDEX = """\
Conformance
===========

.. req:: Full card
   :id: CONF_FULL
   :status: open
   :tags: a
   :verified_by: TEST_1
   :layout: conformance_full

   Full body.

.. req:: Side card
   :id: CONF_SIDE
   :status: open
   :picture: pic.svg
   :layout: conformance_side

   Side body.

.. req:: Headerless card
   :id: CONF_HEADERLESS
   :layout: conformance_headerless

   Headerless body.

.. req:: Object card
   :id: CONF_OBJECT
   :image: pic.svg
   :owner: daniel
   :layout: conformance_object

   Object body.
"""

PIC_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">'
    '<rect width="8" height="8" fill="#123456"/></svg>\n'
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py(
                        CONFORMANCE_SPECS,
                        "needs_fields = {\n"
                        "    'verified_by': {'nullable': True},\n"
                        "    'badge': {'nullable': True},\n"
                        "    'picture': {'nullable': True},\n"
                        "    'image': {'nullable': True},\n"
                        "    'owner': {'nullable': True},\n"
                        "}\n",
                    ),
                ),
                (Path("index.rst"), CONFORMANCE_INDEX),
                (Path("pic.svg"), PIC_SVG),
            ],
        }
    ],
    indirect=True,
)
def test_conformance_specs_build(test_app: Any) -> None:
    """The four shared conformance specifications build end to end.

    They are committed identically to the ubCode implementation of the same
    vocabulary, so that both can be compared against one another.
    """
    app = test_app
    app.build()
    assert app.warning_list == []

    html = scrub((app.outdir / "index.html").read_text())

    for name, grid in CONFORMANCE_GRIDS.items():
        assert f"needs_grid_{grid} needs_layout_{name}" in html

    # conformance_full: a closed disclosure and a six element footer
    assert 'id="target__hide__meta"' in html
    for expected in ("CONF_FULL", "layout:", "style:"):
        assert expected in html

    # conformance_side: partial side on the right
    assert '<td class="need side" rowspan="2">' in html
    assert '<td class="need content" colspan="2">' in html
    assert 'src="_images/pic.svg"' in html

    # conformance_headerless: content plus a footer holding title and id
    headerless = need_table(html, "CONF_HEADERLESS")
    assert '<tr class="footer row-even"><td class="footer">' in headerless
    footer = headerless.split('<td class="footer">')[1]
    assert footer.index('class="needs_title"') < footer.index('class="needs-id"')

    # conformance_object: the height option reaches the side image, and the
    # label option renders as the prefix of the footer's name: value pair
    object_card = need_table(html, "CONF_OBJECT")
    img = object_card[
        object_card.index("<img") : object_card.index(">", object_card.index("<img"))
    ]
    assert 'src="_images/pic.svg"' in img
    assert "40px" in img
    assert "Owned by:" in object_card
    assert object_card.index('class="needs_owner"') < object_card.index(
        'class="needs-id"'
    )


OBJECT_INDEX = """\
Object form
===========

.. req:: Illustrated requirement
   :id: OBJ_SIDE
   :picture: pic.svg
   :layout: object_side

   Side body.

.. req:: Labelled requirement
   :id: OBJ_LABEL
   :owner: daniel
   :layout: object_label

   Label body.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py(
                        {
                            "object_side": {
                                "side": {
                                    "elements": [
                                        {
                                            "type": "image",
                                            "field": "picture",
                                            "height": "40px",
                                        }
                                    ],
                                    "position": "left",
                                }
                            },
                            "object_label": {
                                "footer": [
                                    {
                                        "type": "field",
                                        "field": "owner",
                                        "label": "Owned by",
                                    },
                                    {"type": "id"},
                                ]
                            },
                        },
                        "needs_fields = {\n"
                        "    'picture': {'nullable': True},\n"
                        "    'owner': {'nullable': True},\n"
                        "}\n",
                    ),
                ),
                (Path("index.rst"), OBJECT_INDEX),
                (Path("pic.svg"), PIC_SVG),
            ],
        }
    ],
    indirect=True,
)
def test_object_form_options_render(test_app: Any) -> None:
    """``height`` reaches the rendered image and ``label`` the rendered pair."""
    app = test_app
    app.build()
    assert app.warning_list == []

    html = scrub((app.outdir / "index.html").read_text())

    side = need_table(html, "OBJ_SIDE")
    img = side[side.index("<img") : side.index(">", side.index("<img"))]
    assert 'src="_images/pic.svg"' in img
    assert "40px" in img

    labelled = need_table(html, "OBJ_LABEL")
    footer = labelled.split('<td class="need footer"')[1]
    assert "Owned by:" in footer
    assert 'class="needs_owner"' in footer
    assert footer.index('class="needs_owner"') < footer.index('class="needs-id"')


# --------------------------------------------------------------------------
# end-to-end warnings
# --------------------------------------------------------------------------

SIBLING_INDEX = """\
Warnings
========

.. req:: Good card
   :id: CARD_OK
   :layout: good_card

   Body.
"""


@pytest.mark.parametrize(
    ("bad_spec", "expected"),
    [
        pytest.param({"nope": True}, "unknown key(s) 'nope'", id="unknown-key"),
        pytest.param(
            {"meta": {"fields": "some"}}, "'meta.fields' must be one of", id="bad-enum"
        ),
        pytest.param(
            {"content": False}, "'content' cannot be disabled", id="content-false"
        ),
        pytest.param(
            {"extends": "nowhere"}, "unknown 'extends' base", id="unknown-base"
        ),
        pytest.param(
            {"footer": ["id"], "side": {"elements": ["id"]}},
            "is not expressible",
            id="impossible-grid",
        ),
        pytest.param(
            {"header": False},
            "a card with a meta region but no header",
            id="meta-no-header",
        ),
        pytest.param(
            {"footer": ["field:no such field"]},
            "invalid field name",
            id="bad-identifier",
        ),
        pytest.param(
            {"footer": ["title"]},
            "the 'title' element is only allowed",
            id="title-placement",
        ),
        pytest.param(
            {"footer": [{"type": "image", "field": "badge", "height": "40;px"}]},
            "'height' must be a number",
            id="object-bad-height",
        ),
        pytest.param(
            {"footer": [{"type": "field", "field": "status", "label": "**bold**"}]},
            "'label' must be 1-64 characters",
            id="object-bad-label",
        ),
    ],
)
def test_invalid_card_warns_but_the_build_survives(
    bad_spec: dict[str, Any], expected: str, make_app: Any, sphinx_test_tempdir: Any
) -> None:
    """A bad card is skipped: the build succeeds and its siblings still compile."""
    from tests.conftest import create_src_files_in_tmpdir

    srcdir = create_src_files_in_tmpdir(
        [
            (
                Path("conf.py"),
                conf_py({"bad_card": bad_spec, "good_card": {"footer": ["id"]}}),
            ),
            (Path("index.rst"), SIBLING_INDEX),
        ],
        sphinx_test_tempdir,
    )
    app = make_app(srcdir=srcdir, buildername="html")
    app.build()

    warnings = app._warning.getvalue()
    assert "needs_card_layouts['bad_card']" in warnings
    assert expected in warnings
    assert "needs_card_layouts['good_card']" not in warnings

    # the sibling still compiled and rendered
    html = (Path(app.outdir) / "index.html").read_text()
    assert "needs_layout_good_card" in html
    assert "needs_layout_bad_card" not in html


@pytest.mark.parametrize(
    ("card_name", "extra", "expected"),
    [
        pytest.param("clean", "", "collides with a built-in layout", id="builtin"),
        pytest.param(
            "mine",
            "needs_layouts = {'mine': {'grid': 'simple', 'layout': {}}}\n",
            "collides with an existing needs_layouts entry",
            id="user-layout",
        ),
        pytest.param("not a name", "", "name must match", id="bad-name"),
    ],
)
def test_name_collisions_are_refused(
    card_name: str,
    extra: str,
    expected: str,
    make_app: Any,
    sphinx_test_tempdir: Any,
) -> None:
    """A card never shadows a built-in or a hand written layout."""
    from tests.conftest import create_src_files_in_tmpdir

    srcdir = create_src_files_in_tmpdir(
        [
            (
                Path("conf.py"),
                conf_py({card_name: {"footer": ["id"]}}, extra),
            ),
            (Path("index.rst"), "Title\n=====\n"),
        ],
        sphinx_test_tempdir,
    )
    app = make_app(srcdir=srcdir, buildername="html")
    app.build()

    warnings = app._warning.getvalue()
    assert expected in warnings
    # the built-in / user layout is untouched
    assert app.config.needs_layouts["clean"] == LAYOUTS["clean"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py({"my_card": {"footer": ["image:missing_field"]}}),
                ),
                (Path("index.rst"), INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_unregistered_field_warns_at_build_time(test_app: Any) -> None:
    """An unregistered field is a warning, not a failure: the card still renders."""
    app = test_app
    app.build()

    assert any("not registered" in warning for warning in app.warning_list), (
        app.warning_list
    )
    html = (app.outdir / "index.html").read_text()
    assert "needs_layout_my_card" in html


LAYOUTS_PROBE_CONF = """\
from pathlib import Path

MY_LAYOUTS = {'mine': {'grid': 'simple', 'layout': {}}}
needs_layouts = MY_LAYOUTS


def setup(app):
    def _dump(app, exception):
        Path(app.outdir, 'layouts_probe.txt').write_text(','.join(sorted(MY_LAYOUTS)))

    app.connect('build-finished', _dump)
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    conf_py({"my_card": {"footer": ["id"]}}, LAYOUTS_PROBE_CONF),
                ),
                (Path("index.rst"), INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_user_layouts_object_survives_a_build(test_app: Any) -> None:
    """The dict a ``conf.py`` hands over must not collect generated entries.

    A ``conf.py`` module can outlive a single build, so an entry written into its
    own dict would leak into the next one. The probe holds the reference across
    the build and reports what it ended up containing.
    """
    app = test_app
    app.build()
    assert app.warning_list == []

    # the object conf.py handed over still holds exactly what conf.py put in it
    assert (app.outdir / "layouts_probe.txt").read_text() == "mine"
    # while the configuration did receive the compiled card
    assert {"mine", "my_card"} <= set(app.config.needs_layouts)
    assert "needs_layout_my_card" in (app.outdir / "index.html").read_text()


class _StubConfig:
    """The two configuration values ``compile_card_layouts`` reads and writes."""

    def __init__(self, card_layouts: dict[str, Any], layouts: dict[str, Any]) -> None:
        self.needs_card_layouts = card_layouts
        self.needs_layouts = layouts


def test_compile_card_layouts_rebinds_instead_of_mutating() -> None:
    """The compiler must never write into the layouts mapping it was handed.

    Called through a real build this is masked, because ``merge_default_configs``
    has already rebound ``needs_layouts`` to a fresh dict by the time the compiler
    runs — so the driver is exercised directly here, on a mapping whose identity
    the test owns. The guard matters because that mapping is the user's own
    ``conf.py`` object whenever the upstream ordering changes.
    """
    from sphinx_needs.card_layouts import compile_card_layouts

    existing = {"mine": {"grid": "simple", "layout": {}}}
    config = _StubConfig({"my_card": {"footer": ["id"]}}, existing)

    compile_card_layouts(None, config)  # type: ignore[arg-type]

    assert list(existing) == ["mine"]
    assert config.needs_layouts is not existing
    assert set(config.needs_layouts) == {"mine", "my_card"}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), conf_py({})),
                (Path("index.rst"), INDEX.replace("   :layout: my_card\n", "")),
            ],
        }
    ],
    indirect=True,
)
def test_no_card_layouts_leaves_the_registry_alone(test_app: Any) -> None:
    """Without card specifications, ``needs_layouts`` is exactly the built-in set."""
    app = test_app
    app.build()
    assert app.warning_list == []
    # only the built-in layouts (plus the ones registered by services) are present
    assert LAYOUTS.items() <= app.config.needs_layouts.items()
    assert set(app.config.needs_layouts) - set(LAYOUTS) == {"github"}
