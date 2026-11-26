"""``needs_views_include_parts``: what a view's filter selects.

``True`` tests a view's filter on every need and every need part, as 9.x always did;
``False`` on the needs alone, a part being listed only where the view asks for it
(``:show_parts:`` on a needtable). Unset is ``True`` in 9.x, and each view, chart line
or cell and ``:need_count:`` whose result holds a part, and each needflow that will draw
a link to a part to the part's need, reports ``needs.views_include_parts`` once, where
it is written.

One project, built with the value ``True``, ``False`` and unset: eight needs, five of them
``open``, and five parts (two of ``REQ_A``, one of the nested ``SPEC_N``, one imported,
one external), every part ``open`` with its need. Each consumer sits in a container
named after it on ``views.rst``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from docutils import nodes
from lxml import html as html_parser
from sphinx.testing.util import SphinxTestApp
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needflow import _model as needflow_model
from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs.directives.needflow._model import collect_edges
from sphinx_needs.filter_common import _report_parts_in_view, filter_scope_ids
from sphinx_needs_testkit import build_warnings
from tests.util import (
    bar_sum_labels,
    chart_images,
    pie_slice_counts,
    serial_and_parallel,
)

CONF = """\
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_flow_engine = "graphviz"
needs_build_json = True
needs_reproducible_json = True
needs_fields = {"duration": {"schema": {"type": "integer"}, "nullable": True}}
needs_links = {
    "lff": {},
    "lff_parts": {},
    "d_parts": {
        "derive": {
            "kind": "links",
            "where": "id_parent == 'REQ_A'",
            "include_parts": True,
        }
    },
}
needs_warnings = {"w_is_part": "is_part"}
needs_external_needs = [
    {"base_url": "http://example.org/", "json_path": "external.json"},
]
"""

#: The line each arm adds to ``conf.py``.
VALUES = {
    "true": "needs_views_include_parts = True\n",
    "false": "needs_views_include_parts = False\n",
    "unset": "",
}

FILTER_FUNC = """\
def open_only(needs, results, **kwargs):
    for need in needs:
        if need["status"] == "open":
            results.append(need)


def with_parts(needs, results, **kwargs):
    for need in needs:
        if need["id"] == "REQ_A":
            results.append(need)
            results.extend(need.iter_part_items())
"""

IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "status": "open",
                    "duration": 1,
                    "content": "Marks :np:`(ip) imported part`.",
                }
            }
        }
    },
}

EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_1": {
                    "id": "EXT_1",
                    "type": "req",
                    "title": "External",
                    "status": "open",
                    "duration": 1,
                    "content": "",
                    "parts": {"e1": {"id": "e1", "content": "external part"}},
                }
            }
        }
    },
}

INDEX = """\
Parts
=====

.. toctree::

   views

.. req:: Alpha
   :id: REQ_A
   :status: open
   :duration: 2

   First :np:`(p1) brake fast` and :np:`(p2) steer well`.

   .. spec:: Nested
      :id: SPEC_N
      :status: open
      :duration: 1

      :np:`(n1) nested part`

.. req:: Beta
   :id: REQ_B
   :status: closed

.. test:: Test one
   :id: TEST_1
   :status: open
   :duration: 1
   :links: REQ_A.p1, REQ_B

.. spec:: Collector
   :id: COLL_1
   :status: draft
   :lff: [[links_from_filter("status == 'open'")]]
   :lff_parts: [[links_from_filter("status == 'open'", include_parts=True)]]

.. test:: Checker
   :id: TEST_2
   :status: done
   :links: REQ_A.p1, SPEC_N

.. needimport:: imported.json

.. needextend:: status == 'open'
   :+tags: extended
"""

VIEWS = """\
Views
=====

.. container:: nt-all

   .. needtable::
      :columns: id;title;status
      :style: table

.. container:: nt-open

   .. needtable::
      :filter: status == 'open'
      :columns: id;title;status
      :style: table

.. container:: nt-open-show-parts

   .. needtable::
      :filter: status == 'open'
      :columns: id;title;status
      :show_parts:
      :style: table

.. container:: nt-status

   .. needtable::
      :status: open
      :columns: id;title;status
      :style: table

.. container:: nt-is-part

   .. needtable::
      :filter: is_part
      :columns: id;title;status
      :style: table

.. container:: nt-content

   .. needtable::
      :filter: "brake" in content
      :columns: id;title;status
      :style: table

.. container:: nt-code

   .. needtable::
      :columns: id;title;status
      :style: table

      results = [n for n in needs if n["status"] == "open"]

.. container:: nt-func

   .. needtable::
      :filter-func: viewfuncs.open_only
      :columns: id;title;status
      :style: table

.. container:: nl-open

   .. needlist::
      :status: open

.. container:: nf-open

   .. needflow::
      :filter: status == 'open'
      :link_types: links

.. container:: nf-all

   .. needflow::
      :link_types: links

.. container:: pie

   .. needpie:: pie
      :labels: open, part, all

      status == 'open'
      is_part
      True

.. container:: bar

   .. needbar:: bar
      :xlabels: open, part
      :ylabels: row
      :show_sum:

      status == 'open', is_part

.. container:: scoped-bar

   .. needbar:: scoped bar
      :filter: id_parent == 'REQ_A'
      :xlabels: all, part
      :ylabels: row
      :show_sum:

      True, is_part

.. container:: gantt

   .. needgantt:: gantt
      :filter: status == 'open'

.. container:: extract

   .. needextract::
      :filter: status == 'open' and not is_external

.. container:: count-open

   :need_count:`status == 'open'`

.. container:: count-is-part

   :need_count:`is_part`

.. container:: count-is-need

   :need_count:`is_need`

.. container:: count-true

   :need_count:`True`

.. container:: count-ratio

   :need_count:`status == 'open' ? True`

.. container:: count-id

   :need_count:`id == "p1"`

.. container:: scoped-pie

   .. needpie:: scoped pie
      :filter: is_need

      True

.. container:: nf-is-need

   .. needflow::
      :filter: is_need
      :link_types: links

.. container:: count-ratio-parts

   :need_count:`is_need ? is_part`

.. container:: nt-show-parts-mixed

   .. needtable::
      :filter: id == "REQ_A" or id_complete in ["REQ_A.p1", "SPEC_N.n1"]
      :columns: id;title;status
      :show_parts:
      :style: table
"""


def files(value: str, *, views: str = VIEWS, conf: str = "") -> list[tuple[Path, str]]:
    """The project, with the line of the arm *value* added to ``conf.py``."""
    return [
        (Path("conf.py"), CONF + VALUES[value] + conf),
        (Path("index.rst"), INDEX),
        (Path("views.rst"), views),
        (Path("viewfuncs.py"), FILTER_FUNC),
        (Path("imported.json"), json.dumps(IMPORTED)),
        (Path("external.json"), json.dumps(EXTERNAL)),
    ]


def project(value: str, **kwargs: Any) -> dict[str, Any]:
    return {"buildername": "html", "files": files(value), **kwargs}


ARMS = pytest.mark.parametrize(
    "test_app",
    [project(value) for value in VALUES],
    indirect=True,
    ids=list(VALUES),
)


def _page(app: SphinxTestApp, docname: str = "views") -> Any:
    return html_parser.fromstring(
        Path(app.outdir, f"{docname}.html").read_text(encoding="utf-8")
    )


def _container(app: SphinxTestApp, name: str, docname: str = "views") -> Any:
    (container,) = _page(app, docname).xpath(
        f'//div[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'
    )
    return container


def rows(app: SphinxTestApp, name: str, docname: str = "views") -> list[str]:
    """The need ids of the rows of the table in the container *name*."""
    return [
        row.get("data-need-id")
        for row in _container(app, name, docname).xpath(".//tr[@data-need-id]")
    ]


def lines(app: SphinxTestApp, name: str) -> list[str]:
    """The lines of the needlist in the container *name*."""
    return [
        " ".join(line.text_content().split())
        for line in _container(app, name).xpath('.//div[@class="line"]')
    ]


def text(app: SphinxTestApp, name: str) -> str:
    return " ".join(_container(app, name).text_content().split())


def extracted(app: SphinxTestApp, name: str) -> list[str]:
    """The ids of the needs a needextract in the container *name* writes."""
    return [
        table.get("id")
        for table in _container(app, name).xpath(".//table[@id]")
        if table.get("id")
    ]


def capture_diagrams(app: SphinxTestApp) -> dict[str, str]:
    """The diagram source of each needflow and needgantt, by the class of its
    container, captured where the page is written."""
    sources: dict[str, str] = {}

    def collect(_app: Any, doctree: nodes.document, _docname: str) -> None:
        for container in doctree.findall(nodes.container):
            for node in container.findall(NeedflowGraphiz):
                sources[container["classes"][0]] = node["resolved_content"]
            for node in container.findall(plantuml):
                sources[container["classes"][0]] = node["uml"]

    app.connect("doctree-resolved", collect, priority=900)
    return sources


_DOT_NODE = re.compile(r'^\s*"([^"]+)" \[label=', re.M)
_DOT_CLUSTER = re.compile(r'^\s*subgraph "cluster_([^"]+)"', re.M)
_DOT_EDGE = re.compile(r'^"([^"]+)" -> "([^"]+)" \[(.*)\];$', re.M)


def drawn(dot: str) -> list[str]:
    """Every need and part a graphviz needflow draws, a need holding others as a
    cluster."""
    return sorted(_DOT_NODE.findall(dot) + _DOT_CLUSTER.findall(dot))


def edges(dot: str) -> list[tuple[str, str, bool]]:
    """Every edge of a graphviz needflow: its ends, and whether it is dotted (a part
    edge)."""
    return sorted(
        (source, target, "dotted" in attributes)
        for source, target, attributes in _DOT_EDGE.findall(dot)
    )


def gantt_elements(uml: str) -> list[str]:
    """The aliases of the elements a needgantt declares."""
    return re.findall(r"^\[.*\] as \[(.+)\] lasts", uml, re.M)


def charts(app: SphinxTestApp) -> dict[str, list[Any]]:
    """The numbers each chart draws: a pie's slices, a bar's sums."""
    images = chart_images(Path(app.outdir, "views.html").read_text(encoding="utf-8"))

    def svg(title: str) -> str:
        return Path(app.outdir, "_images", images[title]).read_text(encoding="utf-8")

    return {
        "pie": pie_slice_counts(svg("pie")),
        "bar": bar_sum_labels(svg("bar"), "bar"),
        "scoped bar": bar_sum_labels(svg("scoped bar"), "scoped bar"),
        "scoped pie": pie_slice_counts(svg("scoped pie")),
    }


def reports(app: SphinxTestApp) -> list[str]:
    """The build's ``needs.views_include_parts`` reports."""
    return [
        warning
        for warning in build_warnings(app)
        if warning.endswith("[needs.views_include_parts]")
    ]


def others(app: SphinxTestApp) -> list[str]:
    """Every other warning of the build."""
    return [
        warning
        for warning in build_warnings(app)
        if not warning.endswith("[needs.views_include_parts]")
    ]


OPEN_NEEDS = ["EXT_1", "IMP_1", "REQ_A", "SPEC_N", "TEST_1"]
OPEN_WITH_PARTS = [
    "EXT_1",
    "EXT_1.e1",
    "IMP_1",
    "IMP_1.ip",
    "REQ_A",
    "REQ_A.p1",
    "REQ_A.p2",
    "SPEC_N",
    "SPEC_N.n1",
    "TEST_1",
]
ALL_NEEDS = ["COLL_1", "EXT_1", "IMP_1", "REQ_A", "REQ_B", "SPEC_N", "TEST_1", "TEST_2"]
PARTS = ["EXT_1.e1", "IMP_1.ip", "REQ_A.p1", "REQ_A.p2", "SPEC_N.n1"]

#: What each consumer gives with parts as candidates (``True``, and unset in 9.x) and
#: without (``False``): the recon's measured numbers, on this project.
WITH_PARTS: dict[str, Any] = {
    "nt-all": sorted(ALL_NEEDS + PARTS),
    "nt-open": OPEN_WITH_PARTS,
    "nt-open-show-parts": OPEN_WITH_PARTS,
    "nt-status": OPEN_WITH_PARTS,
    "nt-is-part": PARTS,
    "nt-content": ["REQ_A", "REQ_A.p1"],
    "nt-code": OPEN_WITH_PARTS,
    "nt-func": OPEN_WITH_PARTS,
    "nl-open": 10,
    "pie": [10, 5, 13],
    "bar": ["10", "5"],
    "scoped bar": ["3", "2"],
    # the scope drops the parts the line holds, so it counts no part and reports none
    "scoped pie": [8],
    "gantt": 10,
    "count-open": "10",
    "count-is-part": "5",
    "count-is-need": "8",
    "count-true": "13",
    "count-ratio": "76.9",
    "count-id": "1",
    "count-ratio-parts": "160.0",
    # REQ_A.p1 under its need, as is REQ_A.p2, which the filter does not select;
    # SPEC_N.n1 on a row of its own, its need not being one
    "nt-show-parts-mixed": ["REQ_A", "REQ_A.p1", "REQ_A.p2", "SPEC_N.n1"],
}
NEEDS_ONLY: dict[str, Any] = {
    "nt-all": ALL_NEEDS,
    "nt-open": OPEN_NEEDS,
    "nt-open-show-parts": OPEN_WITH_PARTS,
    "nt-status": OPEN_NEEDS,
    "nt-is-part": [],
    "nt-content": ["REQ_A"],
    "nt-code": OPEN_NEEDS,
    "nt-func": OPEN_NEEDS,
    "nl-open": 5,
    "pie": [5, 0, 8],
    "bar": ["5", "0"],
    "scoped bar": ["1", "0"],
    "scoped pie": [8],
    "gantt": 5,
    "count-open": "5",
    "count-is-part": "0",
    "count-is-need": "8",
    "count-true": "8",
    "count-ratio": "62.5",
    "count-id": "0",
    "count-ratio-parts": "inf",
    "nt-show-parts-mixed": ["REQ_A", "REQ_A.p1", "REQ_A.p2"],
}
EXPECTED = {"true": WITH_PARTS, "unset": WITH_PARTS, "false": NEEDS_ONLY}


def consumers(app: SphinxTestApp, diagrams: dict[str, str]) -> dict[str, Any]:
    """What each consumer of the project gives, in the shape of :data:`WITH_PARTS`."""
    found: dict[str, Any] = {
        name: sorted(rows(app, name))
        for name in ("nt-all", "nt-open", "nt-status", "nt-is-part", "nt-content")
    }
    # the show_parts table and the code and function tables in their own order
    for name in ("nt-open-show-parts", "nt-code", "nt-func", "nt-show-parts-mixed"):
        found[name] = rows(app, name)
    found["nl-open"] = len(lines(app, "nl-open"))
    found.update(charts(app))
    found["gantt"] = len(gantt_elements(diagrams["gantt"]))
    for name in (
        "count-open",
        "count-is-part",
        "count-is-need",
        "count-true",
        "count-ratio",
        "count-id",
        "count-ratio-parts",
    ):
        found[name] = text(app, name)
    return found


@ARMS
def test_each_view_selects_by_the_value(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """Every consumer of a view's filter, under each value: ``True`` and unset list,
    draw and count the parts a filter matches, ``False`` the needs alone; a table with
    ``:show_parts:`` lists each part once, under its need, either way."""
    value = request.node.callspec.id
    diagrams = capture_diagrams(test_app)
    test_app.build()
    assert others(test_app) == []
    assert consumers(test_app, diagrams) == EXPECTED[value]


@ARMS
def test_needextract_does_not_change(test_app: SphinxTestApp) -> None:
    """needextract drops the parts its filter matches, so it extracts the same needs
    under every value, and is never reported."""
    test_app.build()
    # SPEC_N twice: on its own, and nested in REQ_A's extract
    assert extracted(test_app, "extract") == [
        "REQ_A",
        "SPEC_N",
        "SPEC_N",
        "TEST_1",
        "IMP_1",
    ]
    assert not any("needextract" in report for report in reports(test_app))


@ARMS
def test_needflow_draws_by_the_value(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """With parts as candidates a part is a node inside its need, and a link to it an
    edge to that node; with the needs alone, a link naming a part of a drawn need ends
    on that need, styled as a part edge. A needflow whose filter selects needs alone
    draws no edge for a link to a part with parts as candidates, as every release so
    far: the link ends on the part's need under ``False`` only."""
    value = request.node.callspec.id
    diagrams = capture_diagrams(test_app)
    test_app.build()
    opened, every, needs_only = (
        diagrams["nf-open"],
        diagrams["nf-all"],
        diagrams["nf-is-need"],
    )
    assert drawn(needs_only) == ALL_NEEDS
    if value == "false":
        assert drawn(opened) == ["EXT_1", "IMP_1", "REQ_A", "SPEC_N", "TEST_1"]
        assert edges(opened) == [("TEST_1", "REQ_A", True)]
        assert drawn(every) == ALL_NEEDS
        assert edges(every) == [
            ("TEST_1", "REQ_A", True),
            ("TEST_1", "REQ_B", False),
            ("TEST_2", "REQ_A", True),
            ("TEST_2", "SPEC_N", False),
        ]
        assert edges(needs_only) == edges(every)
    else:
        assert drawn(opened) == sorted(OPEN_WITH_PARTS)
        assert edges(opened) == [("TEST_1", "REQ_A.p1", True)]
        assert drawn(every) == sorted(ALL_NEEDS + PARTS)
        assert edges(every) == [
            ("TEST_1", "REQ_A.p1", True),
            ("TEST_1", "REQ_B", False),
            ("TEST_2", "REQ_A.p1", True),
            ("TEST_2", "SPEC_N", False),
        ]
        assert edges(needs_only) == [
            ("TEST_1", "REQ_B", False),
            ("TEST_2", "SPEC_N", False),
        ]


def test_needs_json_is_the_same_under_every_value(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The value reaches the views alone: no function, rule, needextend or warning
    check, so the needs.json of the three builds is the same, byte for byte."""
    written: dict[str, bytes] = {}
    for value in VALUES:
        srcdir = tmp_path / value
        for path, content in files(value):
            (srcdir / path).parent.mkdir(parents=True, exist_ok=True)
            (srcdir / path).write_text(content, encoding="utf-8")
        app = make_app("html", srcdir=srcdir, freshenv=True)
        app.build()
        written[value] = Path(app.outdir, "needs.json").read_bytes()
    assert written["true"] == written["false"] == written["unset"]
    data = json.loads(written["true"])
    needs = data["versions"][data["current_version"]]["needs"]
    # the functions and the rule asked for parts, and still have them
    assert needs["COLL_1"]["lff"] == OPEN_NEEDS
    assert needs["COLL_1"]["lff_parts"] == OPEN_WITH_PARTS
    assert needs["TEST_1"]["d_parts"] == ["REQ_A", "REQ_A.p1", "REQ_A.p2"]


@pytest.mark.parametrize("test_app", [project("false")], indirect=True, ids=["false"])
def test_a_scoped_chart_counts_over_needs_alone(test_app: SphinxTestApp) -> None:
    """With the needs alone, a chart's scope holds no part: what a line or a cell
    counts, and what a filter-func of the chart is handed, is a need of the scope."""
    test_app.build()
    config = NeedsSphinxConfig(test_app.config)
    scope = filter_scope_ids(
        SphinxNeedsData(test_app.env).get_needs_view(),
        config,
        status=["open"],
        tags=[],
        types=[],
        filter="id_parent == 'REQ_A' or is_part",
        location=nodes.Element(),
        origin_docname="views",
    )
    assert scope == frozenset({"REQ_A"})
    # the public method keeps its meaning: needs and parts, whatever the value says
    every = SphinxNeedsData(test_app.env).get_needs_view().to_list_with_parts()
    assert sorted(item["id_complete"] for item in every) == sorted(ALL_NEEDS + PARTS)


BUILT_BY_THE_FUNC = """
.. container:: built-by-the-func

   .. needtable::
      :filter-func: viewfuncs.with_parts
      :columns: id;title
      :style: table
"""

FUNC_VIEWS = "Views\n=====\n" + BUILT_BY_THE_FUNC


@pytest.mark.parametrize(
    "test_app,expected",
    [
        (
            {
                "buildername": "html",
                "files": files("false", views=FUNC_VIEWS),
            },
            ["REQ_A"],
        ),
        (
            {
                "buildername": "html",
                "files": files(
                    "false",
                    views=FUNC_VIEWS,
                    conf="needs_allow_unsafe_filters = True\n",
                ),
            },
            ["REQ_A", "REQ_A.p1", "REQ_A.p2"],
        ),
        (
            {"buildername": "html", "files": files("true", views=FUNC_VIEWS)},
            ["REQ_A", "REQ_A.p1", "REQ_A.p2"],
        ),
    ],
    indirect=["test_app"],
    ids=["false", "false-unsafe", "true"],
)
def test_a_filter_func_building_parts_itself(
    test_app: SphinxTestApp, expected: list[str]
) -> None:
    """Under ``False`` a filter-func is handed needs alone, and its result is mapped
    back over them: a part it builds itself is dropped, unless unsafe filters are
    allowed, which take its result as it is."""
    test_app.build()
    assert others(test_app) == []
    assert rows(test_app, "built-by-the-func") == expected


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": files("false", conf="needs_allow_unsafe_filters = True\n"),
        }
    ],
    indirect=True,
)
def test_filter_code_and_func_are_handed_needs_alone(test_app: SphinxTestApp) -> None:
    """Under ``False`` filter code and a filter-func are handed needs alone: with unsafe
    filters allowed their result is taken as it is, so a part they were handed would
    be a row."""
    test_app.build()
    assert others(test_app) == []
    assert rows(test_app, "nt-code") == OPEN_NEEDS
    assert rows(test_app, "nt-func") == OPEN_NEEDS


@pytest.mark.parametrize("test_app", [project("false")], indirect=True, ids=["false"])
def test_a_link_to_a_part_the_need_lacks_draws_nothing(test_app: SphinxTestApp) -> None:
    """A link naming a part ends on its need only when the need has the part: a dead
    part address draws no edge, as with parts as candidates."""
    test_app.build()
    data = SphinxNeedsData(test_app.env)
    links = data.get_schema().get_link_field("links")
    assert links is not None
    source: Any = {"id_complete": "SRC", "links": ["REQ_A.nope", "REQ_A.p1"]}
    found = [data.get_needs_view()["REQ_A"], source]
    drawn_ids = {"REQ_A", "SRC"}
    assert [
        (edge.source_id, edge.target_id, edge.is_part, edge.target_drawn)
        for edge in collect_edges(found, [links], drawn_ids, part_links_to_needs=True)
    ] == [("SRC", "REQ_A", True, True)]


# --- the report, while the value is unset ---------------------------------------------


def _report(
    line: int,
    what: str,
    count: int,
    *,
    links: int = 0,
    page: str = "views.rst",
    show_parts: bool = False,
) -> str:
    """The report of the place *what* at *line*: its filter selects *count* need parts
    (for a needtable with ``:show_parts:``, parts whose need it does not list) and, for
    a needflow, the needs it draws hold *links* links to parts of its needs."""

    def parts(n: int) -> str:
        return f"{n} need part{'' if n == 1 else 's'}"

    set_ = "Set needs_views_include_parts = True to keep"
    if what == "needflow" and links:
        drawn = f"{links} link{'' if links == 1 else 's'} to " + (
            "a need part as an edge to the part's need"
            if links == 1
            else "need parts as edges to the parts' needs"
        )
        head = (
            f"This needflow's filter selects {parts(count)}, and from Sphinx-Needs "
            f"10.0 it draws {drawn}"
            if count
            else f"From Sphinx-Needs 10.0 this needflow draws {drawn}, which it draws "
            "no edge for now"
        )
        text = (
            f"{head}: a view's filter then selects needs only, and a needflow draws a "
            "link to a part of a need it shows as an edge to that need. "
            f"{set_} the needflow as it is, or False to draw "
            + ("needs only" if count else "those edges")
            + " now"
        )
    else:
        counts = what.startswith(("needpie", "needbar", "need_count"))
        verb = (
            ("counting", "count")
            if counts
            else ("drawing", "draw")
            if what in ("needflow", "needgantt")
            else ("listing", "list")
        )
        asks = (
            ", and a needtable lists a need's parts under it only with :show_parts:"
            if what == "needtable"
            else ""
        )
        head = (
            f"This {what} counts {parts(count)}"
            if counts
            else f"This {what}'s filter selects {parts(count)}"
            + (" whose need it does not list" if show_parts else "")
        )
        text = (
            f"{head}: from Sphinx-Needs 10.0 a view's filter selects needs only{asks}. "
            f"{set_} {verb[0]} them, or False to {verb[1]} needs only now"
        )
    return (
        f"<srcdir>/{page}:{line}: WARNING: {text}; or suppress "
        "needs.views_include_parts. [needs.views_include_parts]"
    )


#: Each place of the project whose result holds a part, and each needflow whose needs
#: link to parts of its needs (the edges it gains under ``False``: one for ``nf-open``,
#: two for ``nf-all`` and ``nf-is-need``, as :func:`test_needflow_draws_by_the_value`
#: draws them), in the order the page is written, and what it reports: never the table
#: whose matched parts are each listed under their need, never needextract, never a
#: count without a part.
UNSET_REPORTS = [
    _report(6, "needtable", 5),
    _report(12, "needtable", 5),
    _report(27, "needtable", 5),
    _report(34, "needtable", 5),
    _report(41, "needtable", 1),
    _report(48, "needtable", 5),
    _report(56, "needtable", 5),
    _report(63, "needlist", 5),
    _report(68, "needflow", 5, links=1),
    _report(74, "needflow", 5, links=2),
    _report(79, "needpie line \"status == 'open'\"", 5),
    _report(79, "needpie line 'is_part'", 5),
    _report(79, "needpie line 'True'", 5),
    _report(88, "needbar cell \"status == 'open'\"", 5),
    _report(88, "needbar cell 'is_part'", 5),
    _report(97, "needbar cell 'True'", 2),
    _report(97, "needbar cell 'is_part'", 2),
    _report(107, "needgantt", 5),
    _report(117, "need_count \"status == 'open'\"", 5),
    _report(121, "need_count 'is_part'", 5),
    _report(129, "need_count 'True'", 5),
    _report(133, "need_count \"status == 'open' ? True\"", 5),
    _report(137, "need_count 'id == \"p1\"'", 1),
    _report(148, "needflow", 0, links=2),
    _report(154, "need_count 'is_need ? is_part'", 5),
    # of the two parts its filter selects, the one on a row of its own
    _report(158, "needtable", 1, show_parts=True),
]


@pytest.mark.parametrize("test_app", serial_and_parallel(files("unset")), indirect=True)
def test_unset_reports_each_place_whose_result_holds_a_part(
    test_app: SphinxTestApp,
) -> None:
    """One report per place, located there, naming the value and what to set; a
    needflow whose result holds parts and gains edges reports once, saying both."""
    test_app.build()
    assert sorted(reports(test_app)) == sorted(UNSET_REPORTS)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": files(
                value,
                views=VIEWS + BUILT_BY_THE_FUNC,
                conf="needs_allow_unsafe_filters = True\n",
            ),
        }
        for value in ("true", "false")
    ],
    indirect=True,
    ids=["true", "false"],
)
def test_a_value_set_either_way_reports_nothing(test_app: SphinxTestApp) -> None:
    """Set either way, nothing is reported, though a result holds parts: under
    ``False`` too, as a filter function that builds parts itself, with unsafe filters
    allowed, has them taken as it gives them."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert rows(test_app, "built-by-the-func") == ["REQ_A", "REQ_A.p1", "REQ_A.p2"]


INCLUDED = """\
.. needtable::
   :filter: is_part
   :columns: id
   :style: table
"""

TWICE = [
    (Path("conf.py"), CONF),
    (
        Path("index.rst"),
        INDEX.replace("   views\n", "   first\n   second\n   third\n   fourth\n"),
    ),
    (Path("first.rst"), "First\n=====\n\n.. include:: table.rst.inc\n"),
    (Path("second.rst"), "Second\n======\n\n.. include:: table.rst.inc\n"),
    (Path("table.rst.inc"), INCLUDED),
    # a table of each page's own, at the same line of both
    (Path("third.rst"), "Third\n=====\n\n" + INCLUDED),
    (Path("fourth.rst"), "Fourth\n======\n\n" + INCLUDED),
    (Path("viewfuncs.py"), FILTER_FUNC),
    (Path("imported.json"), json.dumps(IMPORTED)),
    (Path("external.json"), json.dumps(EXTERNAL)),
]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "files": TWICE}], indirect=True
)
def test_a_place_is_reported_once_whatever_pages_show_it(
    test_app: SphinxTestApp,
) -> None:
    """One table, included by two documents: one place, one report. Two tables, each
    written on a page of its own at the same line: two places, two reports."""
    test_app.build()
    assert rows(test_app, "body", "first") == rows(test_app, "body", "second") == PARTS
    assert rows(test_app, "body", "third") == rows(test_app, "body", "fourth") == PARTS
    assert sorted(reports(test_app)) == [
        _report(4, "needtable", 5, page="fourth.rst"),
        _report(1, "needtable", 5, page="table.rst.inc"),
        _report(4, "needtable", 5, page="third.rst"),
    ]


def test_each_build_of_one_application_reports_again(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """What was reported is forgotten at each build: one application built twice, its
    views page changed in between, reports every place of it both times."""
    for path, content in files("unset"):
        (tmp_path / path).write_text(content, encoding="utf-8")
    app = make_app("html", srcdir=tmp_path)
    app.build()
    first = reports(app)
    (tmp_path / "views.rst").write_text(VIEWS + "\nA changed line.\n", encoding="utf-8")
    app.build()
    second = reports(app)[len(first) :]
    assert sorted(first) == sorted(second) == sorted(UNSET_REPORTS)


#: A need linking two parts of ``REQ_A``, a part ``REQ_A`` lacks and a part of ``SPEC_N``,
#: by a link type that allows dead links; a need linking its own part; and a needflow
#: over those three needs alone, which does not show ``SPEC_N``.
LINKED_PARTS_VIEWS = """\
Views
=====

.. test:: Loose
   :id: TEST_L
   :status: done
   :loose: REQ_A.p1, REQ_A.p2, REQ_A.nope, SPEC_N.n1

.. req:: Self
   :id: REQ_S
   :status: done
   :loose: REQ_S.s1

   :np:`(s1) self part`

.. container:: linked-parts

   .. needflow::
      :filter: id in ["TEST_L", "REQ_A", "REQ_S"]
      :link_types: loose
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": files(
                value,
                views=LINKED_PARTS_VIEWS,
                conf='needs_links["loose"] = {"allow_dead_links": True}\n',
            ),
        }
        for value in VALUES
    ],
    indirect=True,
    ids=list(VALUES),
)
def test_a_needflow_reports_each_link_it_will_draw_to_a_parts_need(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """One need linking two parts of a need the needflow shows, a part that need lacks
    and a part of a need it does not show, and a need linking its own part: unset
    reports three links, which the needflow draws under ``False`` as two edges (the two
    links to parts of one need as one edge, and a need's edge to itself), and the dead
    part address and the part of the need it does not show none, as it draws none for
    them."""
    value = request.node.callspec.id
    diagrams = capture_diagrams(test_app)
    test_app.build()
    assert others(test_app) == []
    gained = [
        ("REQ_S", "REQ_S", True),
        ("TEST_L", "REQ_A", True),
    ]
    assert edges(diagrams["linked-parts"]) == (gained if value == "false" else [])
    assert reports(test_app) == (
        [_report(18, "needflow", 0, links=3)] if value == "unset" else []
    )


#: Two capped needflows over needs alone: the first keeps ``REQ_A`` and ``REQ_B``, so
#: ``TEST_1``, linking a part of ``REQ_A``, falls beyond its cap; the second keeps
#: ``REQ_A`` and ``TEST_1``, so of the two needs linking a part of ``REQ_A`` (``TEST_1``
#: and ``TEST_2``), one is drawn. The third holds parts and links: its cap keeps ``REQ_A``
#: and ``REQ_A.p1``, and over needs alone ``REQ_A`` and ``TEST_1``. The fourth gives no
#: ``:max_items:``, and the project's ``needs_views_max_items`` caps it as the second.
#: The fifth keeps ``TEST_2`` alone (``done`` sorts before ``open``), whose link to a part
#: of ``REQ_A`` names a need beyond its cap.
CAPPED_LINKS_VIEWS = """\
Views
=====

.. container:: capped-beyond

   .. needflow::
      :filter: id in ["REQ_A", "REQ_B", "TEST_1"]
      :max_items: 2
      :link_types: links

.. container:: capped-one-of-two

   .. needflow::
      :filter: id in ["REQ_A", "TEST_1", "TEST_2"]
      :max_items: 2
      :link_types: links

.. container:: capped-parts-and-links

   .. needflow::
      :filter: id_parent == "REQ_A" or id in ["TEST_1", "TEST_2"]
      :max_items: 2
      :link_types: links

.. container:: capped-by-project

   .. needflow::
      :filter: id in ["REQ_A", "TEST_1", "TEST_2"]
      :link_types: links

.. container:: capped-target-beyond

   .. needflow::
      :filter: id in ["REQ_A", "TEST_2"]
      :sort_by: status
      :max_items: 1
      :link_types: links
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": files(
                value, views=CAPPED_LINKS_VIEWS, conf="needs_views_max_items = 2\n"
            ),
        }
        for value in VALUES
    ],
    indirect=True,
    ids=list(VALUES),
)
def test_a_capped_needflow_reports_the_links_its_window_draws(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """The links counted are those of the needs the cap keeps: a needflow whose linking
    need falls beyond its cap draws the same under ``True`` and ``False`` and is not
    reported; one whose cap keeps one of two linking needs reports one link, the one
    edge it gains under ``False``. The window is the one over needs alone, whatever
    the result holds, and the project's cap makes one as the option does. A link of a
    need of the window to a part of a need beyond it is not counted, as it is not
    drawn."""
    value = request.node.callspec.id
    diagrams = capture_diagrams(test_app)
    test_app.build()
    assert drawn(diagrams["capped-beyond"]) == ["REQ_A", "REQ_B"]
    assert edges(diagrams["capped-beyond"]) == []
    assert drawn(diagrams["capped-one-of-two"]) == ["REQ_A", "TEST_1"]
    assert edges(diagrams["capped-one-of-two"]) == (
        [("TEST_1", "REQ_A", True)] if value == "false" else []
    )
    assert drawn(diagrams["capped-parts-and-links"]) == (
        ["REQ_A", "TEST_1"] if value == "false" else ["REQ_A", "REQ_A.p1"]
    )
    assert edges(diagrams["capped-parts-and-links"]) == (
        [("TEST_1", "REQ_A", True)] if value == "false" else []
    )
    assert drawn(diagrams["capped-by-project"]) == ["REQ_A", "TEST_1"]
    assert edges(diagrams["capped-by-project"]) == (
        [("TEST_1", "REQ_A", True)] if value == "false" else []
    )
    assert drawn(diagrams["capped-target-beyond"]) == ["TEST_2"]
    assert edges(diagrams["capped-target-beyond"]) == []
    assert [
        warning for warning in others(test_app) if "needs.max_items" not in warning
    ] == []
    assert reports(test_app) == (
        [
            _report(13, "needflow", 0, links=1),
            _report(20, "needflow", 2, links=1),
            _report(27, "needflow", 0, links=1),
        ]
        if value == "unset"
        else []
    )


#: Views whose filter names ids in an order that is not the document's: a needlist with
#: no part in its result; a capped needflow whose window, in the list's order, holds two
#: needs linking a part of ``REQ_A``; and one whose window leaves ``REQ_A`` out, so it
#: links no part of a need it shows.
ORDERED_VIEWS = """\
Views
=====

.. container:: listed-in-order

   .. needlist::
      :filter: id in ["TEST_1", "REQ_A"]

.. container:: capped-in-order

   .. needflow::
      :filter: id in ["REQ_A", "TEST_1", "TEST_2", "REQ_B"]
      :max_items: 3
      :link_types: links

.. container:: capped-in-order-no-part

   .. needflow::
      :filter: id in ["TEST_2", "TEST_1", "REQ_B", "REQ_A"]
      :max_items: 3
      :link_types: links
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "html", "files": files(value, views=ORDERED_VIEWS)}
        for value in VALUES
    ],
    indirect=True,
    ids=list(VALUES),
)
def test_needs_alone_come_in_the_order_they_come_with_parts(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """Under ``False`` a view's result is the result under ``True`` with its parts left
    out, in the same order: a needlist with no part lists the same lines in the order
    of its filter under every value, unreported; a capped needflow keeps the same
    window, so under ``False`` it gains the edges to the parts' needs its report counts,
    and one that is not reported gains none."""
    value = request.node.callspec.id
    diagrams = capture_diagrams(test_app)
    test_app.build()
    assert [
        warning for warning in others(test_app) if "needs.max_items" not in warning
    ] == []
    assert lines(test_app, "listed-in-order") == ["TEST_1: Test one", "REQ_A: Alpha"]
    assert drawn(diagrams["capped-in-order"]) == ["REQ_A", "TEST_1", "TEST_2"]
    assert edges(diagrams["capped-in-order"]) == (
        [("TEST_1", "REQ_A", True), ("TEST_2", "REQ_A", True)]
        if value == "false"
        else []
    )
    assert drawn(diagrams["capped-in-order-no-part"]) == ["REQ_B", "TEST_1", "TEST_2"]
    assert edges(diagrams["capped-in-order-no-part"]) == [("TEST_1", "REQ_B", False)]
    assert reports(test_app) == (
        [_report(11, "needflow", 0, links=2)] if value == "unset" else []
    )


@pytest.mark.parametrize("value", [True, False])
def test_the_link_count_is_asked_only_while_the_value_is_unset(value: bool) -> None:
    """A needflow's link count is a callable the report calls only while the value is
    unset: with the value set either way it is never asked."""

    def part_links() -> int:
        pytest.fail("the link count was asked with the value set")

    _report_parts_in_view(
        Mock(views_include_parts=value),
        [],
        "needflow",
        nodes.Element(),
        part_links=part_links,
    )
    asked: list[bool] = []

    def asking() -> int:
        asked.append(True)
        return 0

    _report_parts_in_view(
        Mock(views_include_parts=None),
        [],
        "needflow",
        nodes.Element(),
        part_links=asking,
    )
    assert asked == [True], "the premise: while unset it is asked"


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "html", "files": files(value, views=ORDERED_VIEWS)}
        for value in VALUES
    ],
    indirect=True,
    ids=list(VALUES),
)
def test_a_needflow_counts_its_links_only_while_the_value_is_unset(
    test_app: SphinxTestApp,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where a needflow hands the report its link count: nothing of it is computed with
    the value set either way, and once per needflow while it is unset."""
    value = request.node.callspec.id
    counted: list[str] = []
    count = needflow_model.count_part_links_to_needs

    def counting(*args: Any) -> int:
        counted.append(value)
        return count(*args)

    monkeypatch.setattr(needflow_model, "count_part_links_to_needs", counting)
    test_app.build()
    assert len(counted) == (2 if value == "unset" else 0)


#: A needflow whose ``max_items`` hides every part its filter selects.
CAPPED_VIEWS = """\
Views
=====

.. container:: capped

   .. needflow::
      :filter: id_parent == 'REQ_A'
      :max_items: 1
      :link_types: links
"""


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "files": files("unset", views=CAPPED_VIEWS)}],
    indirect=True,
)
def test_a_needflow_reports_what_its_filter_selects_before_its_cap(
    test_app: SphinxTestApp,
) -> None:
    """The cap keeps the first item alone, the need, but the parts it hides are what
    the filter selects, and from 10.0 the cap's window holds needs alone: reported."""
    diagrams = capture_diagrams(test_app)
    test_app.build()
    assert drawn(diagrams["capped"]) == ["REQ_A"]
    assert reports(test_app) == [_report(6, "needflow", 2)]


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            "unset", confoverrides={"suppress_warnings": ["needs.views_include_parts"]}
        )
    ],
    indirect=True,
)
def test_the_report_can_be_suppressed(test_app: SphinxTestApp) -> None:
    test_app.build()
    assert build_warnings(test_app) == []
    assert rows(test_app, "nt-open") == OPEN_WITH_PARTS


# --- how the value is set -----------------------------------------------------------


@pytest.mark.parametrize(
    "test_app,expected",
    [
        (
            project("unset", confoverrides={"needs_views_include_parts": "0"}),
            OPEN_NEEDS,
        ),
        (
            project("unset", confoverrides={"needs_views_include_parts": "1"}),
            OPEN_WITH_PARTS,
        ),
    ],
    indirect=["test_app"],
    ids=["0", "1"],
)
def test_the_command_line_reaches_the_value(
    test_app: SphinxTestApp, expected: list[str]
) -> None:
    """``-D needs_views_include_parts=0`` (and ``=1``) sets the value, so nothing is
    reported."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert sorted(rows(test_app, "nt-open")) == expected


TOML_CONF = 'needs_from_toml = "ubproject.toml"\n'


@pytest.mark.parametrize(
    "test_app,expected",
    [
        (
            {
                "buildername": "html",
                "files": [
                    *files("unset", conf=TOML_CONF),
                    (Path("ubproject.toml"), "[needs]\nviews_include_parts = false\n"),
                ],
            },
            OPEN_NEEDS,
        ),
        (
            {
                "buildername": "html",
                "files": [
                    *files("unset", conf=TOML_CONF),
                    (Path("ubproject.toml"), "[needs]\nviews_include_parts = true\n"),
                ],
            },
            OPEN_WITH_PARTS,
        ),
    ],
    indirect=["test_app"],
    ids=["false", "true"],
)
def test_ubproject_toml_reaches_the_value(
    test_app: SphinxTestApp, expected: list[str]
) -> None:
    test_app.build()
    assert build_warnings(test_app) == []
    assert sorted(rows(test_app, "nt-open")) == expected


@pytest.mark.parametrize(
    "test_app,kind,expected",
    [
        (
            project("unset", confoverrides={"needs_views_include_parts": "no"}),
            "str",
            OPEN_WITH_PARTS,
        ),
        (
            {
                "buildername": "html",
                "files": files("unset", conf='needs_views_include_parts = "no"\n'),
            },
            "str",
            OPEN_WITH_PARTS,
        ),
        (
            {
                "buildername": "html",
                "files": files("unset", conf="needs_views_include_parts = 0\n"),
            },
            "int",
            OPEN_NEEDS,
        ),
    ],
    indirect=["test_app"],
    ids=["command-line-text", "conf-text", "conf-number"],
)
def test_a_value_of_another_type_is_reported_and_read_by_its_truth(
    test_app: SphinxTestApp, kind: str, expected: list[str]
) -> None:
    """A text or a number is no boolean: Sphinx reports its type, as it does for the
    other boolean settings, and it is read by its truth, as those are (``"no"`` is a
    text, so true; ``0`` false). It is set either way, so nothing else is reported."""
    test_app.build()
    (warning,) = build_warnings(test_app)
    assert f"`needs_views_include_parts' has type `{kind}'" in warning
    assert sorted(rows(test_app, "nt-open")) == expected


def test_a_flip_rewrites_the_views_and_reads_nothing(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Changing the value between two incremental builds re-reads no document, and
    each view follows it, both ways; the build after the flip back has nothing left of
    the flip."""
    for path, content in files("true"):
        (tmp_path / path).write_text(content, encoding="utf-8")
    steps = []
    for value in (True, False, True):
        app = make_app(
            "html",
            srcdir=tmp_path,
            confoverrides={"needs_views_include_parts": value},
        )
        app.build()
        status = app._status.getvalue()
        read = re.search(r"(\d+) added, (\d+) changed, (\d+) removed", status)
        assert read is not None, status
        steps.append(
            (
                tuple(int(n) for n in read.groups()),
                sorted(rows(app, "nt-open")),
                text(app, "count-is-part"),
            )
        )
    first, flipped, back = steps
    assert first == ((2, 0, 0), OPEN_WITH_PARTS, "5")
    assert flipped == ((0, 0, 0), OPEN_NEEDS, "0")
    assert back == ((0, 0, 0), OPEN_WITH_PARTS, "5")
