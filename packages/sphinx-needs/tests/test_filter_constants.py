"""A filter that is a constant alone is refused on every tier, and nothing else is.

A filter is read for its truth, need by need, and a constant -- ``"x"``, ``0``, ``-5``,
``None``, a display such as ``[1]`` or ``("x",)``, an f-string with no placeholder,
parenthesised or not, after any leading spaces -- has the same truth on every need, so
it says nothing about one. The engine refuses it before any tier runs, reports it once
per use, and selects nothing (#2355); ``:filter: "x"`` used to select every need.
``True`` and ``False`` are the exception: they are the spelling of "every need" and "no
need". A constant inside a larger filter, or a constant expression, is read like any
other filter (#1773: by its truth).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from sphinx_needs import filter_common
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    _filter_tier,
    _is_constant_filter,
    apply_default_predicate,
    filter_import_item,
    filter_needs_and_parts,
    filter_single_need,
)
from sphinx_needs_testkit import build_warnings
from tests.test_ubquery import _make_need
from tests.util import bar_sum_labels, chart_images, needs_by_id, pie_slice_counts

#: One filter of every shape a bare constant takes.
CONSTANTS = ['"x"', '""', "0", "-5", "1.5", "None", '("x")', "+5", 'b"x"']

#: A constant after leading spaces or a tab, which Python's ``eval`` reads past: a
#: filter configured outside a document keeps them (a directive option or a role does
#: not).
INDENTED = [" 1", '\t"x"', ' "x"']

#: A display, whatever it holds, and an f-string with no placeholder: each is true or
#: false on every need alike, as a literal is.
DISPLAYS = ['status == "open",', "[1]", '("x",)', "{}", "[]", "()", 'f"x"', 'f""']

#: Filters that are no bare constant: each is read for its truth, none is refused.
NOT_CONSTANTS = [
    "True",
    "False",
    "(True)",
    "-True",
    "--5",
    "not 1",
    "1 == 1",
    "1 and status",
    'True and "a" in tags',
    '"x" and status == "open"',
    "tags",
    "len(tags)",
    "title.lower()",
    "True and owner",
    "var.platform",
    "[t for t in tags]",
    "{t for t in tags}",
    "{t: 1 for t in tags}",
    "(t for t in tags)",
    'f"{status}"',
    "set()",
    " tags",
    " True",
    "this ( is bad",
]


@pytest.mark.parametrize("filter_string", [*CONSTANTS, *INDENTED, *DISPLAYS])
def test_a_constant_is_refused_by_every_tier(filter_string: str) -> None:
    """The decision is the string's alone, and every entry point of the engine takes it:
    the need-by-need ones raise, the list one reports once and selects nothing."""
    assert _is_constant_filter(filter_string)
    assert _filter_tier(filter_string) == ("refused", None)
    config = Mock()
    config.filter_data = {}
    config.variant_data_proxy = None
    refusal = (
        f"Filter {filter_string!r} not valid. Error: it is a constant, which says "
        "nothing about a need, so it selects none."
    )
    with pytest.raises(NeedsInvalidFilter) as raised:
        filter_single_need(_make_need(), config, filter_string)
    assert str(raised.value) == refusal
    with pytest.raises(NeedsInvalidFilter) as raised:
        filter_import_item({"id": "REQ_001"}, config, filter_string)
    assert str(raised.value) == refusal
    with pytest.raises(NeedsInvalidFilter) as raised:
        apply_default_predicate(filter_string, config, {}, {}, {})
    assert str(raised.value) == refusal.replace("Filter", "Predicate", 1)


@pytest.mark.parametrize("filter_string", NOT_CONSTANTS)
def test_nothing_else_is_a_constant(filter_string: str) -> None:
    """True and False alone, a constant inside a larger filter, a constant expression, a
    comprehension, an f-string with a placeholder, a call and a string that does not
    parse are no constant: a tier answers each."""
    assert not _is_constant_filter(filter_string)
    assert _filter_tier(filter_string)[0] != "refused"


def test_a_constant_is_reported_once_per_call() -> None:
    """Over many needs, the list entry point reports the constant once, not per need."""
    config = Mock()
    config.filter_data = {}
    config.variant_data_proxy = None
    needs = [_make_need(id=f"REQ_00{i}") for i in range(1, 4)]
    with patch.object(filter_common, "log_warning") as warn:
        assert (
            filter_needs_and_parts(needs, config, '"x"', append_warning="(here)") == []
        )
    assert warn.call_count == 1
    _, message, code = warn.call_args.args
    assert code == "filter"
    assert message.startswith("""Filter '"x"' not valid. Error: it is a constant""")
    assert message.endswith(" (here)")


# --- every consumer, in one project ---------------------------------------------------

NEEDS_JSON = json.dumps(
    {
        "current_version": "1",
        "versions": {
            "1": {"needs": {"IMP_A": {"id": "IMP_A", "type": "req", "title": "A"}}}
        },
    }
)


def _quoted(filter_string: str) -> str:
    """A filter as a Python string literal in a function call."""
    return repr(filter_string)


#: A ``needs_warnings`` entry and a field with a default predicate per constant.
WARNINGS = {f"constant_{n}": s for n, s in enumerate(CONSTANTS)}
FIELDS = {
    f"by_predicate_{n}": {"default": "plain", "predicates": [(s, "matched")]}
    for n, s in enumerate(CONSTANTS)
}

CONF = "\n".join(
    [
        'extensions = ["sphinx_needs"]',
        "needs_build_json = True",
        f"needs_warnings = {WARNINGS!r}",
        f"needs_fields = {FIELDS!r}",
        "",
    ]
)

INDEX = "\n".join(
    [
        "Constants",
        "=========",
        "",
        ".. req:: Alpha",
        "   :id: REQ_001",
        "   :status: open",
        "   :tags: a",
        "",
        ".. req:: Beta",
        "   :id: REQ_002",
        "",
        *(f".. needlist::\n   :filter: {s}\n" for s in CONSTANTS),
        *(f"Count {n}: :need_count:`{s}`\n" for n, s in enumerate(CONSTANTS)),
        ".. needpie:: pie",
        "",
        "   10",
        *(f"   {s}" for s in CONSTANTS),
        "",
        ".. needbar:: bar",
        "   :show_sum:",
        "",
        "   " + ",".join(["10", *CONSTANTS]),
        "",
        *(f'.. needextend:: "{s}"\n   :status: extended\n' for s in CONSTANTS),
        *(
            f".. needimport:: needs.json\n   :filter: {s}\n   :id_prefix: I{n}_\n"
            for n, s in enumerate(CONSTANTS)
        ),
        *(
            f".. spec:: Linker {n}\n   :id: LINKER_{n}\n"
            f"   :links: [[links_from_filter({_quoted(s)})]]\n"
            for n, s in enumerate(CONSTANTS)
        ),
    ]
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("needs.json"), NEEDS_JSON),
            ],
        }
    ],
    indirect=True,
)
def test_every_consumer_refuses_a_constant(test_app: Any) -> None:
    """Views, need_count, needpie lines, needbar cells, needextend, needs_warnings,
    needimport, default predicates and ``links_from_filter`` each refuse every constant
    with one warning naming it, and select nothing; the build goes on."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    codes = Counter(
        m[1] if (m := re.search(r"\[needs\.([a-z_]+)\]$", w)) else w for w in warnings
    )
    shapes = len(CONSTANTS)
    # views, need_count, pie lines, bar cells, needextend, needs_warnings; a chart
    # reads a non-negative integer (`0`) as a static value, not as a filter
    assert codes == {
        "filter": 6 * shapes - 2,
        "needimport": shapes,
        "config": shapes,
        "dynamic_function": shapes,
    }, warnings
    for filter_string in CONSTANTS:
        naming = [w for w in warnings if f"{filter_string!r} not valid" in w]
        assert len(naming) == (7 if filter_string.isdigit() else 9), naming
        assert all(
            "it is a constant, which says nothing about a need" in w for w in naming
        ), naming

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    for n in range(shapes):
        assert f"Count {n}: 0" in html
    # every needlist is empty
    assert html.count("No needs passed the filters") == shapes
    images = chart_images(html)
    pie = Path(app.outdir, "_images", images["pie"]).read_text()
    assert pie_slice_counts(pie) == [10] + [0] * shapes
    bar = Path(app.outdir, "_images", images["bar"]).read_text()
    assert bar_sum_labels(bar, "bar") == ["10"] + ["0"] * shapes

    needs = needs_by_id(app)
    # no needimport imported its need
    assert set(needs) == {"REQ_001", "REQ_002"} | {f"LINKER_{n}" for n in range(shapes)}
    assert needs["REQ_001"]["status"] == "open"
    assert needs["REQ_002"]["status"] is None
    for n in range(shapes):
        assert needs["REQ_001"][f"by_predicate_{n}"] == "plain"
        assert needs[f"LINKER_{n}"]["links"] == []


# --- a constant configured outside a document, after leading whitespace --------------

INDENTED_WARNINGS = {f"indented_{n}": s for n, s in enumerate(INDENTED)}
INDENTED_FIELDS = {
    f"by_indented_{n}": {"default": "plain", "predicates": [(s, "matched")]}
    for n, s in enumerate(INDENTED)
}
INDENTED_INDEX = (
    "Indented\n========\n\n"
    ".. req:: Alpha\n   :id: REQ_001\n   :tags: a\n\n"
    ".. req:: Beta\n   :id: REQ_002\n"
)


def _indented_project(setting: str) -> dict[str, Any]:
    conf = f'extensions = ["sphinx_needs"]\nneeds_build_json = True\n{setting}\n'
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), INDENTED_INDEX)],
    }


@pytest.mark.parametrize(
    "test_app",
    [_indented_project(f"needs_fields = {INDENTED_FIELDS!r}")],
    indirect=True,
)
def test_a_default_predicate_after_leading_whitespace_is_refused(
    test_app: Any,
) -> None:
    """A predicate in the configuration keeps its leading spaces, which ``eval`` reads
    past: ``" 1"`` would match every need, so it is refused as ``1`` is, with one
    warning each, and matches none."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(INDENTED), warnings
    assert all(w.endswith("[needs.config]") for w in warnings), warnings
    assert all(
        "it is a constant, which says nothing about a need" in w for w in warnings
    )
    needs = needs_by_id(app)
    for n in range(len(INDENTED)):
        assert needs["REQ_001"][f"by_indented_{n}"] == "plain"
        assert needs["REQ_002"][f"by_indented_{n}"] == "plain"


@pytest.mark.parametrize(
    "test_app",
    [_indented_project(f"needs_warnings = {INDENTED_WARNINGS!r}")],
    indirect=True,
)
def test_a_warnings_filter_after_leading_whitespace_is_refused(test_app: Any) -> None:
    """A ``needs_warnings`` filter with leading spaces is a constant all the same: one
    ``needs.filter`` warning each, where the view path stopped the build on the
    indentation."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(INDENTED), warnings
    assert all(w.endswith("[needs.filter]") for w in warnings), warnings
    assert all(
        "it is a constant, which says nothing about a need" in w for w in warnings
    )


# --- a value that is no boolean, on the two eval tails no other test reaches ---------

TRUTH_JSON = json.dumps(
    {
        "current_version": "1",
        "versions": {
            "1": {
                "needs": {
                    "IMP_TAGGED": {
                        "id": "IMP_TAGGED",
                        "type": "req",
                        "title": "Tagged",
                        "tags": ["t"],
                    },
                    "IMP_PLAIN": {
                        "id": "IMP_PLAIN",
                        "type": "req",
                        "title": "Plain",
                        "tags": [],
                    },
                }
            }
        },
    }
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\n'
                    "needs_build_json = True\n"
                    "needs_fields = {'by_tags': {'default': 'plain', "
                    "'predicates': [('tags', 'matched')]}}\n",
                ),
                (
                    Path("index.rst"),
                    "Truth\n=====\n\n"
                    ".. req:: Alpha\n   :id: REQ_001\n   :tags: a\n\n"
                    ".. req:: Beta\n   :id: REQ_002\n\n"
                    ".. needimport:: needs.json\n   :filter: tags\n",
                ),
                (Path("needs.json"), TRUTH_JSON),
            ],
        }
    ],
    indirect=True,
)
def test_a_predicate_and_an_import_filter_are_read_for_their_truth(
    test_app: Any,
) -> None:
    """A default predicate and a needimport filter are evaluated by ``eval`` alone, and
    read for their truth as every filter is (#1773): ``tags`` matches the needs that
    have tags, and nothing is reported."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_001"]["by_tags"] == "matched"
    assert needs["REQ_002"]["by_tags"] == "plain"
    assert "IMP_TAGGED" in needs
    assert "IMP_PLAIN" not in needs
