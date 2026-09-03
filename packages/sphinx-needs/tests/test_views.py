"""Unit tests for the read-only need views of ``sphinx_needs.views``.

These views are part of the published Python API (``docs/api.rst``) and are the
objects a filter string or a filter function is handed, so their narrowing
methods are exercised here directly, without a Sphinx build.
"""

from __future__ import annotations

from sphinx_needs.need_item import NeedItem, NeedPartData, NeedsContent
from sphinx_needs.views import NeedsAndPartsListView, NeedsView

CORE_BASE = {
    "id": "abc",
    "type": "type",
    "type_name": "type title",
    "type_prefix": "type prefix",
    "type_color": "#000000",
    "type_style": "node",
    "status": None,
    "tags": [],
    "constraints": (),
    "title": "title",
    "collapse": False,
    "arch": {},
    "style": None,
    "layout": None,
    "hide": False,
    "external_css": "external_link",
    "has_dead_links": False,
    "has_forbidden_dead_links": False,
    "sections": (),
    "signature": None,
}


def _parts_view() -> NeedsAndPartsListView:
    """A need without parts and a need with two, so a sibling part can be left out.

    Two parts is the shape that tells an exact selection from an approximate one:
    ``TEST_1.P1`` and ``TEST_1.P2`` share a need id, so anything that selects by
    need id cannot address one of them alone.
    """
    needs = [
        NeedItem(
            core=CORE_BASE | {"id": "REQ_1", "type": "req", "type_name": "Requirement"},
            extras={},
            links={},
            source=None,
            content=NeedsContent(content="", doctype=".rst"),
            parts=(),
        ),
        NeedItem(
            core=CORE_BASE | {"id": "TEST_1", "type": "test", "type_name": "Test Case"},
            extras={},
            links={},
            source=None,
            content=NeedsContent(content="", doctype=".rst"),
            parts=(
                NeedPartData(id="P1", content="Part one"),
                NeedPartData(id="P2", content="Part two"),
            ),
        ),
    ]
    return NeedsView._from_needs({n["id"]: n for n in needs}).to_list_with_parts()


def _ids(view: NeedsAndPartsListView) -> list[str]:
    return sorted(item["id_complete"] for item in view)


def test_the_corpus_holds_the_needs_and_every_part():
    """The premise of the tests below: parts are members in their own right."""
    assert _ids(_parts_view()) == ["REQ_1", "TEST_1", "TEST_1.P1", "TEST_1.P2"]


def test_filter_id_complete_selects_exactly_the_given_items():
    """A part is selected on its own -- without its need and without its sibling.

    This is what ``filter_ids`` cannot do, and it is why a chart's scope, which is
    a set of ``id_complete`` values, needs its own method: selecting the parent
    need or the sibling part would silently widen a scope.
    """
    view = _parts_view().filter_id_complete(["REQ_1", "TEST_1.P1"])
    assert _ids(view) == ["REQ_1", "TEST_1.P1"]


def test_filter_id_complete_can_select_a_need_without_its_parts():
    """Selecting a need does not bring its parts along."""
    assert _ids(_parts_view().filter_id_complete(["TEST_1"])) == ["TEST_1"]


def test_filter_id_complete_of_nothing_is_an_empty_view():
    """An empty selection is an empty view, not an unfiltered one.

    A chart's scope relies on this: a scope that selected nothing must count
    nothing, which is a different thing from a chart that has no scope at all.
    """
    view = _parts_view().filter_id_complete([])
    assert _ids(view) == []
    assert len(view) == 0
    assert not view


def test_filter_id_complete_ignores_values_that_are_not_in_the_view():
    """Unknown ids are ignored, and so are ids the view has already filtered out."""
    assert _ids(_parts_view().filter_id_complete(["REQ_1", "NOPE", "TEST_1.P9"])) == [
        "REQ_1"
    ]
    narrowed = _parts_view().filter_types(["test"])
    assert _ids(narrowed.filter_id_complete(["REQ_1", "TEST_1.P2"])) == ["TEST_1.P2"]


def test_filter_id_complete_returns_a_view_that_can_be_narrowed_further():
    """The result is a view, so every other narrowing method still applies.

    A filter function is handed one of these, and the published API says so, so
    the result of an exact selection has to keep those methods reachable.
    """
    view = _parts_view().filter_id_complete(["REQ_1", "TEST_1", "TEST_1.P2"])
    assert isinstance(view, NeedsAndPartsListView)
    assert _ids(view.filter_types(["test"])) == ["TEST_1", "TEST_1.P2"]
    assert _ids(view.filter_types(["Requirement"], or_type_names=True)) == ["REQ_1"]


def test_filter_ids_is_not_id_complete():
    """Why ``filter_id_complete`` exists, pinned rather than described.

    ``filter_ids`` matches a need id or a bare part id, so an ``id_complete``
    value never matches, and a need id brings its parts along once the view has
    been narrowed. Both behaviours are fine for its own callers and wrong for a
    scope.
    """
    fresh = _parts_view()
    assert _ids(fresh.filter_ids(["TEST_1.P1"])) == []
    assert _ids(fresh.filter_ids(["P1"])) == ["TEST_1.P1"]
    narrowed = _parts_view().filter_types(["test"])
    assert _ids(narrowed.filter_ids(["TEST_1"])) == [
        "TEST_1",
        "TEST_1.P1",
        "TEST_1.P2",
    ]


def test_filter_id_complete_keeps_the_order_of_the_view():
    """The result iterates in the view's own order, not in the order of ``values``.

    A ``:filter-func:`` used to be handed a plain list built by iterating the
    unscoped view, so its needs arrived in document order; the view it is handed
    now must iterate the same way, or a function that relies on that order (the
    first need, a running total) changes its answer when a scope is added.
    """
    view = _parts_view()
    selected = view.filter_id_complete(["TEST_1.P2", "REQ_1", "TEST_1"])
    assert [item["id_complete"] for item in selected] == [
        "REQ_1",
        "TEST_1",
        "TEST_1.P2",
    ]
    assert [item["id_complete"] for item in selected] == [
        item["id_complete"] for item in view if item["id_complete"] != "TEST_1.P1"
    ]
