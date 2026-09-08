"""The needtable's HTML markup contract, asserted on a built page.

This is the half of ``design/needstable-contract.md`` that sphinx-needs *emits*: the hook
class and the per-table options on the ``<table>``, the column key and sort type on each
``<th>``, the need id (and parent) on each ``<tr>``, and the filter paragraph's place
*after* the table rather than inside it. It is a specification shared with other producers
of needtable markup, so a change here is a change to more than this package.

The behaviour built on top of it is asserted in ``test_needstable_js.py``, which drives a
browser.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import html as html_parser
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import assert_no_warnings, build_warnings

#: the project every test in this module builds
_SRCDIR = "doc_test/doc_needtable_enhancer"

_APP = pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": _SRCDIR}], indirect=True
)


def _tables(app: SphinxTestApp) -> list[html_parser.HtmlElement]:
    """Every ``<table>`` of the built index page, in document order."""
    tree = html_parser.parse(str(Path(app.outdir, "index.html")))
    return tree.xpath("//table")


def _needtables(app: SphinxTestApp) -> list[html_parser.HtmlElement]:
    """The three needtables of the project: two interactive, then the plain one."""
    return [
        table
        for table in _tables(app)
        if {"NEEDS_DATATABLES", "NEEDS_TABLE"} & set(table.get("class", "").split())
    ]


@_APP
def test_table_element(test_app: SphinxTestApp) -> None:
    """The ``<table>`` carries the hook class and the per-table options."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    interactive, small, plain = _needtables(app)

    # the selector is the class it has always been, so a project that styles
    # `.NEEDS_DATATABLES` keeps working
    assert "NEEDS_DATATABLES" in interactive.get("class").split()
    assert interactive.get("id") == "needtable-index-0-table_node"
    assert interactive.get("data-needstable-page-size") == "10"
    assert interactive.get("data-needstable-page-sizes") == "10,25,50,0"

    assert "NEEDS_DATATABLES" in small.get("class").split()
    # `:page_size:` overrides `needs_table_page_size` for this table alone
    assert small.get("data-needstable-page-size") == "5"
    assert small.get("data-needstable-page-sizes") == "10,25,50,0"

    # `:style: table` opts out: no hook class, and none of the options
    assert "NEEDS_TABLE" in plain.get("class").split()
    assert "NEEDS_DATATABLES" not in plain.get("class").split()
    assert plain.get("data-needstable-page-size") is None
    assert plain.get("data-needstable-page-sizes") is None


@_APP
def test_header_cells(test_app: SphinxTestApp) -> None:
    """Each ``<th>`` names its column, and types it where the producer knows the type."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    interactive = _needtables(app)[0]
    headers = interactive.xpath(".//thead//th")

    assert [th.get("data-col") for th in headers] == [
        "id",
        "title",
        "status",
        "amount",
        "due",
        "outgoing",
    ]
    # every header cell is a column header, for assistive technology as much as for the
    # script
    assert {th.get("scope") for th in headers} == {"col"}
    # docutils' own class survives, and the column key joins it
    assert headers[0].get("class").split() == ["head", "needs_col_id"]

    # `amount` is declared `{"type": "integer"}` in the project's `needs_fields`, so the
    # producer types it; nothing else is typed, and the script detects those itself
    assert [th.get("data-type") for th in headers] == [
        None,
        None,
        None,
        "number",
        None,
        None,
    ]

    # the visible header text is unchanged
    assert [th.text_content().strip() for th in headers] == [
        "ID",
        "Title",
        "Status",
        "Amount",
        "Due",
        "Outgoing",
    ]


@_APP
def test_body_rows(test_app: SphinxTestApp) -> None:
    """Each ``<tr>`` names its need, and a part row names its parent."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    interactive = _needtables(app)[0]
    rows = interactive.xpath(".//tbody/tr")

    assert [row.get("data-need-id") for row in rows] == [
        "R_01",
        "R_02",
        "R_03",
        "R_04",
        "R_05",
        "R_06",
        "R_07",
        "R_08",
        "R_09",
        "S_01",
        "S_02",
        "S_02.P1",
        "S_02.P2",
        "S_03",
    ]
    # only the part rows carry a parent, and it is the need they belong to
    assert [row.get("data-parent") for row in rows[-3:]] == ["S_02", "S_02", None]

    # the row kind and `:style_row:` are classes, exactly as before
    first = rows[0]
    assert "need" in first.get("class").split()
    assert "needs_open" in first.get("class").split()
    part = rows[11]
    assert "need_part" in part.get("class").split()

    # the cells are untouched: their classes and their real links
    cells = first.xpath("./td")
    assert [cell.get("class") for cell in cells] == [
        "needs_id",
        "needs_title",
        "needs_status",
        "needs_amount",
        "needs_due",
        "needs_links",
    ]
    assert cells[0].xpath(".//a/@href") == ["#R_01"]


@_APP
def test_show_filters_paragraph_follows_the_table(test_app: SphinxTestApp) -> None:
    """``:show_filters:`` writes a paragraph AFTER the table, not inside it.

    A ``<p>`` between ``</tbody>`` and ``</table>`` is invalid HTML, which browsers hoist
    out of the element again -- and which any client-side enhancer then trips on.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    # asserted on the RAW bytes: an HTML parser (lxml's as much as a browser's) hoists the
    # invalid paragraph out again, so a parsed tree cannot tell the two apart
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    start = html.index('<table class="NEEDS_DATATABLES')
    end = html.index("</table>", start) + len("</table>")
    assert "Used filter" not in html[start:end]
    assert html[end:].lstrip().startswith("<p><em>Used filter")


@_APP
def test_colgroup_and_caption_unchanged(test_app: SphinxTestApp) -> None:
    """``:colwidths:`` still becomes a ``<colgroup>`` and the argument a ``<caption>``."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    interactive = _needtables(app)[0]
    assert [col.get("style") for col in interactive.xpath("./colgroup/col")] == [
        "width: 15.0%",
        "width: 35.0%",
        "width: 10.0%",
        "width: 10.0%",
        "width: 15.0%",
        "width: 15.0%",
    ]
    caption = interactive.xpath("./caption")[0]
    assert caption.text_content().strip().rstrip("\u00b6") == "Every column"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": _SRCDIR}],
    indirect=True,
)
def test_latex_build(test_app: SphinxTestApp) -> None:
    """The three node sub-classes have HTML visitors only.

    Every other builder finds none and falls through the MRO to the ``table`` / ``row`` /
    ``entry`` they derive from, which is what keeps latex (and text, and texinfo) building
    a needtable at all.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    tex = next(Path(app.outdir).glob("*.tex")).read_text(encoding="utf-8")
    assert "R\\_01" in tex


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "singlehtml", "srcdir": _SRCDIR}],
    indirect=True,
)
def test_singlehtml_build(test_app: SphinxTestApp) -> None:
    """The singlehtml builder uses the same translator, so the contract holds there too."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert 'data-need-id="R_01"' in html
    assert 'data-needstable-page-size="10"' in html


@_APP
def test_assets_are_registered_per_page(test_app: SphinxTestApp) -> None:
    """The client pair goes on the pages that have an interactive needtable (#462).

    ``no_table.rst`` holds a need but no needtable, so it must carry neither file.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    def assets(pagename: str) -> list[str]:
        tree = html_parser.parse(str(Path(app.outdir, pagename)))
        return [
            node.attrib["src" if node.tag == "script" else "href"].rsplit("?", 1)[0]
            for node in tree.xpath("/html/head/script") + tree.xpath("/html/head/link")
        ]

    pair = [
        "_static/sphinx-needs/libs/html/needstable.js",
        "_static/sphinx-needs/libs/html/needstable.css",
    ]
    on_index = assets("index.html")
    for asset in pair:
        assert on_index.count(asset) == 1, on_index

    for pagename in ("no_table.html", "search.html", "genindex.html"):
        elsewhere = assets(pagename)
        for asset in pair:
            assert asset not in elsewhere, (pagename, elsewhere)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": _SRCDIR,
            "confoverrides": {
                "needs_table_page_size": 25,
                "needs_table_page_sizes": [25, 100, 0],
            },
        }
    ],
    indirect=True,
)
def test_page_size_configuration(test_app: SphinxTestApp) -> None:
    """``needs_table_page_size`` and ``needs_table_page_sizes`` reach the table."""
    app = test_app
    app.build()
    assert_no_warnings(app)

    interactive, small, _plain = _needtables(app)
    assert interactive.get("data-needstable-page-size") == "25"
    assert interactive.get("data-needstable-page-sizes") == "25,100,0"
    # the directive option still wins for the table that carries it
    assert small.get("data-needstable-page-size") == "5"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": _SRCDIR,
            "confoverrides": {
                # 0 means "all", which is not a page SIZE
                "needs_table_page_size": 0,
                "needs_table_page_sizes": [],
            },
        }
    ],
    indirect=True,
)
def test_page_size_configuration_is_validated(test_app: SphinxTestApp) -> None:
    """A bad value is reported once, at configuration time, and the default is used."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert [warning for warning in warnings if "needs_table_page_size " in warning] == [
        "WARNING: needs_table_page_size must be a positive integer, got 0; "
        "using 10. [needs.config]"
    ], warnings
    assert [
        warning for warning in warnings if "needs_table_page_sizes " in warning
    ] == [
        "WARNING: needs_table_page_sizes must be a non-empty list of non-negative "
        "integers (0 means all), got []; using [10, 25, 50, 0]. [needs.config]"
    ], warnings

    interactive = _needtables(app)[0]
    assert interactive.get("data-needstable-page-size") == "10"
    assert interactive.get("data-needstable-page-sizes") == "10,25,50,0"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable_bad_page_size"}],
    indirect=True,
)
def test_page_size_option_is_validated(test_app: SphinxTestApp) -> None:
    """A bad ``:page_size:`` is reported at the directive and then ignored."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert warnings == [
        "<srcdir>/index.rst:7: WARNING: The 'page_size' option must be a positive "
        "integer, got '0'; ignoring it. [needs.directive]",
        "<srcdir>/index.rst:10: WARNING: The 'page_size' option must be a positive "
        "integer, got 'lots'; ignoring it. [needs.directive]",
    ], warnings

    tree = html_parser.parse(str(Path(app.outdir, "index.html")))
    for table in tree.xpath("//table[contains(@class, 'NEEDS_DATATABLES')]"):
        assert table.get("data-needstable-page-size") == "10"
