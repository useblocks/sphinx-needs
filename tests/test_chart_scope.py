"""Tests for the selection options of ``needpie`` and ``needbar``.

``:status:``, ``:tags:``, ``:types:`` and ``:filter:`` do not select what a chart
shows -- a chart shows whatever its content says -- they select the needs it
counts over. The scope is resolved once per chart and every content line is then
counted as its own result intersected with that scope, so the numbers of a scoped
chart are the numbers of the unscoped chart, restricted to the scope.

The oracle these tests assert is the corpus of ``doc_test/doc_chart_scope``:
six needs of three types with two statuses and the tags ``a``/``b``, one of which
carries the part ``TEST_1.P1``, so that seven objects can be counted.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from docutils import nodes
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFilteredBaseType, SphinxNeedsData
from sphinx_needs.filter_common import filter_scope_ids, process_filters
from tests.util import bar_sum_labels, chart_images, pie_slice_counts

CHART_SCOPE = pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_chart_scope",
            # the fixture needs no diagrams, so the suite-wide plantuml override
            # would only add an "unknown config value" warning to assert around
            "no_plantuml": True,
        }
    ],
    indirect=True,
)

INVALID_FILTER_WARNING = (
    "<srcdir>/invalid.rst:8: WARNING: Filter 'xxx' not valid. "
    "Error: name 'xxx' is not defined. [needs.filter]"
)
"""The only warning the fixture is expected to emit, from its one invalid scope."""

PIE_ORACLE = {
    # every pie of the fixture counts the same four content lines:
    #   status == 'open' / type == 'req' / 'a' in tags / the literal 3
    "pie unscoped": [5, 3, 5, 3],
    "pie status": [5, 2, 4, 3],
    "pie tags": [4, 2, 5, 3],
    "pie types": [2, 3, 2, 3],
    # ``:types:`` matches the human-readable type title as well as the directive
    # name, so this pie must count exactly what ``:types: req`` counts
    "pie types by title": [2, 3, 2, 3],
    "pie status and tags": [4, 1, 4, 3],
    "pie filter": [2, 3, 2, 3],
    "pie status and filter": [2, 2, 1, 3],
    # a scope that selects nothing zeroes every filter line, but a literal line
    # is not counted over the scope and so is left alone
    "pie scope selects nothing": [0, 0, 0, 3],
}

BAR_ORACLE = {
    # every bar of the fixture counts one row of three cells:
    #   status == 'open' / type == 'req' / 'a' in tags
    "bar unscoped": ["5", "3", "5"],
    "bar status": ["5", "2", "4"],
    "bar filter": ["2", "3", "2"],
    # unlike a pie, a bar chart has no empty state: it draws all zeros
    "bar scope selects nothing": ["0", "0", "0"],
    # a comma in the option value is not a cell separator, so this filter
    # arrives whole and selects the two closed needs
    "bar filter with a comma": ["0", "1", "1"],
}

SCOPES: list[dict[str, object]] = [
    {"status": ["open"], "tags": [], "types": [], "filter": None},
    {"status": [], "tags": ["a"], "types": [], "filter": None},
    {"status": [], "tags": [], "types": ["req"], "filter": None},
    {"status": [], "tags": [], "types": ["Requirement"], "filter": None},
    {"status": ["open"], "tags": ["a"], "types": [], "filter": None},
    {"status": [], "tags": [], "types": [], "filter": "type == 'req'"},
    {"status": ["open"], "tags": [], "types": [], "filter": "type == 'req'"},
    {"status": ["nonexistent"], "tags": [], "types": [], "filter": None},
]
"""The scopes of the oracle, as the four option values a directive collects."""


def _warnings(app: SphinxTestApp) -> list[str]:
    return (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )


@CHART_SCOPE
def test_scope_intersects_every_content_line(test_app: SphinxTestApp):
    """A scoped chart counts each content line over the scope only.

    This is the whole oracle: nine pies and five bars whose content is identical
    and whose selection options are not, so every number that moves is the scope
    at work and nothing else.
    """
    app = test_app
    app.build()
    assert _warnings(app) == [INVALID_FILTER_WARNING]

    images = chart_images(Path(app.outdir, "index.html").read_text())
    # the two empty-state pies write no image, so they are not in here, and the
    # filter-func pie has its own test
    assert set(images) == set(PIE_ORACLE) | set(BAR_ORACLE) | {"pie filter func"}

    def svg(title: str) -> str:
        return Path(app.outdir, "_images", images[title]).read_text()

    assert {title: pie_slice_counts(svg(title)) for title in PIE_ORACLE} == PIE_ORACLE
    assert {
        title: bar_sum_labels(svg(title), title, 3) for title in BAR_ORACLE
    } == BAR_ORACLE


@CHART_SCOPE
def test_scope_selecting_nothing_keeps_each_directives_empty_state(
    test_app: SphinxTestApp,
):
    """A scope that selects nothing does not introduce a new empty state.

    A pie of only filter lines then counts nothing and is replaced by the "no
    needs" paragraph it already used for a filter that matches nothing, including
    the ``:filter_warning:`` text. A pie that also has a literal line still has a
    value and is still drawn, and a bar chart, which has no such paragraph, draws
    all zeros -- see ``BAR_ORACLE``.
    """
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    assert html.count('<p class="needs_filter_warning"') == 2
    assert "No needs passed the filters" in html
    assert "nothing is in this scope" in html

    images = chart_images(html)
    assert "pie all filters and no scope members" not in images
    assert "pie all filters and no scope members warned" not in images
    assert "pie scope selects nothing" in images


@CHART_SCOPE
def test_invalid_scope_filter_warns_once_and_selects_nothing(test_app: SphinxTestApp):
    """An unevaluable scope ``:filter:`` is warned by the filter engine.

    It is the same warning the same expression gives on a content line, and it is
    given once for the chart rather than once per line, because the scope is
    resolved once. The scope is then empty, so every filter line counts zero.
    """
    app = test_app
    app.build()
    assert _warnings(app) == [INVALID_FILTER_WARNING]

    images = chart_images(Path(app.outdir, "invalid.html").read_text())
    svg = Path(app.outdir, "_images", images["pie invalid scope filter"]).read_text()
    assert pie_slice_counts(svg) == [0, 0, 0, 3]


@CHART_SCOPE
def test_scope_restricts_the_input_of_a_filter_func(test_app: SphinxTestApp):
    """A ``:filter-func:`` is handed the needs of the scope, not the project.

    The scope restricts what the function sees, not what it returns: the numbers
    of the chart are whatever the function appends. The fixture's function returns
    the size of the ``needs`` it was given, which is 5 for ``:status: open`` and
    would be 7 -- the whole corpus, parts included -- without the scope.
    """
    app = test_app
    app.build()

    images = chart_images(Path(app.outdir, "index.html").read_text())
    svg = Path(app.outdir, "_images", images["pie filter func"]).read_text()
    assert pie_slice_counts(svg) == [5, 1]


@CHART_SCOPE
def test_scope_membership_equals_the_filter_options_of_a_view_directive(
    test_app: SphinxTestApp,
):
    """The scope holds exactly what the same options select on a view directive.

    ``filter_scope_ids`` does not call ``process_filters`` -- a chart has no
    single filter to give it, and its content is not filter code -- so the two
    can drift apart. This pins them together for every scope of the oracle.
    """
    app = test_app
    app.build()

    data = SphinxNeedsData(app.env)
    config = NeedsSphinxConfig(app.env.config)
    location = nodes.paragraph()

    for scope in SCOPES:
        scope_ids = filter_scope_ids(
            data.get_needs_view(),
            config,
            status=scope["status"],
            tags=scope["tags"],
            types=scope["types"],
            filter=scope["filter"],
            location=location,
            origin_docname="index",
        )
        filter_data: NeedsFilteredBaseType = {
            "docname": "index",
            "lineno": 1,
            "target_id": "equivalence",
            "status": scope["status"],
            "tags": scope["tags"],
            "types": scope["types"],
            "filter": scope["filter"],
            "sort_by": None,
            # a chart's content is one filter per line, never filter code, so the
            # comparison is against the option-only branch of process_filters
            "filter_code": [],
            "filter_func": None,
            "filter_warning": None,
        }
        found = process_filters(
            app, data.get_needs_view(), filter_data, "needpie", location
        )
        assert scope_ids == frozenset(need["id_complete"] for need in found), scope


@CHART_SCOPE
def test_no_selection_option_means_no_scope(test_app: SphinxTestApp):
    """No selection option is not an empty scope, it is no scope at all.

    An empty scope would zero every filter line; no scope must leave a chart
    counting over the whole project, exactly as it did before the options
    existed. ``None`` is what carries that difference.
    """
    app = test_app
    app.build()

    assert (
        filter_scope_ids(
            SphinxNeedsData(app.env).get_needs_view(),
            NeedsSphinxConfig(app.env.config),
            status=[],
            tags=[],
            types=[],
            filter=None,
            location=nodes.paragraph(),
            origin_docname="index",
        )
        is None
    )
