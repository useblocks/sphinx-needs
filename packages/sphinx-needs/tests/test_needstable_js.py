"""Browser tests for ``src/sphinx_needs/libs/html/needstable.js``.

The page is built by the ordinary ``test_app`` fixture and opened straight off disk over
``file://`` -- the script fetches nothing, so no server is involved. What is asserted is
the behaviour half of ``design/needstable-contract.md``: in-place enhancement, typed
sorting with a three-state cycle, part rows travelling with their need, a filter over the
whole table rather than the page, paging, column visibility, the two exports, keyboard
operation and ``destroy()``.

Every case rebuilds and re-opens the page, so no case can leave state for the next.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sphinx.testing.util import SphinxTestApp

# the browser driver is the `js` dependency group, which the CI matrix cells deliberately
# do not install: without this the module fails at COLLECTION there, which fails the whole
# run even though `-m "not jstest"` would deselect these tests
_playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="the browser tests need the `js` dependency group (`uv sync --group js`)",
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

#: the ids `needtable.py` gives the three tables of `doc_test/doc_needtable_enhancer`
INTERACTIVE = "needtable-index-0-table_node"
SMALL = "needtable-index-1-table_node"
PLAIN = "needtable-index-2-table_node"

_APP = pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable_enhancer"}],
    indirect=True,
)

# The script is deferred, so it runs after parsing but BEFORE `DOMContentLoaded`, with
# `document.readyState === "interactive"`. The `readystatechange` to "interactive" fires
# just before deferred scripts run, which is the last moment at which the untouched markup
# can still be read -- and the only way to capture it without blocking the script, which
# `page.route` cannot do for a `file://` URL.
#
# This comment used to describe a tag that was not in fact deferred (review measured
# `loading_method="defer"`, a literal attribute, on every page). The capture happened to
# work anyway, because an UNdeferred script's `DOMContentLoaded` listener runs later still
# than this event; it is correct in both worlds, and correct for the stated reason now.
_CAPTURE_PRISTINE = """
document.addEventListener('readystatechange', function () {
    if (document.readyState !== 'interactive' || window.__pristine) {
        return;
    }
    var pristine = {};
    document.querySelectorAll('table').forEach(function (table) {
        if (table.id) {
            pristine[table.id] = table.outerHTML;
        }
    });
    window.__pristine = pristine;
});
"""


@pytest.fixture
def opened(test_app: SphinxTestApp, page: Page):
    """Build the project, open its index page and hand back ``(page, page_errors)``."""
    app = test_app
    app.build()

    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(error.message))
    page.add_init_script(_CAPTURE_PRISTINE)
    page.goto(Path(app.outdir, "index.html").as_uri())
    # the script self-initialises, so by the time `goto` returns the widget is there
    assert page.locator(f"#{INTERACTIVE}").evaluate("t => !!t.__needstable")
    yield page, page_errors
    assert not page_errors, f"the page raised: {page_errors}"


def _column(page: Page, table_id: str, index: int) -> list[str]:
    """The text of one column, over the rows currently attached to ``table_id``."""
    return page.evaluate(
        """([id, index]) => Array.from(
            document.getElementById(id).tBodies[0].rows,
        ).map((row) => (row.cells[index] || {}).textContent.trim())""",
        [table_id, index],
    )


def _need_ids(page: Page, table_id: str) -> list[str]:
    return page.evaluate(
        """(id) => Array.from(
            document.getElementById(id).tBodies[0].rows,
        ).map((row) => row.getAttribute('data-need-id'))""",
        table_id,
    )


def _wrapper(page: Page, table_id: str) -> Any:
    return page.locator(f"#{table_id}").locator(
        "xpath=ancestor::div[@class='needstable'][1]"
    )


def _show_all(page: Page, table_id: str) -> None:
    """Switch a table to the "All" page size, so every row is attached."""
    _wrapper(page, table_id).locator(
        "select.needstable-page-size-select"
    ).select_option("0")


def _sort(page: Page, table_id: str, column: int, times: int = 1) -> None:
    button = _wrapper(page, table_id).locator("th button.needstable-sort").nth(column)
    for _ in range(times):
        button.click()


def _pager_display(page: Page, table_id: str) -> str:
    """The pager's COMPUTED display -- `none` is the only value that really hides it."""
    return page.evaluate(
        """(id) => {
            const wrapper = document.getElementById(id).closest('div.needstable');
            const pager = wrapper.querySelector('nav.needstable-pager');
            return getComputedStyle(pager).display;
        }""",
        table_id,
    )


def _aria_sort(page: Page, table_id: str) -> list[str | None]:
    return page.evaluate(
        """(id) => Array.from(
            document.getElementById(id).tHead.rows[0].cells,
        ).map((cell) => cell.getAttribute('aria-sort'))""",
        table_id,
    )


@pytest.mark.jstest
@_APP
def test_enhancement_is_in_place(opened) -> None:
    """t1 -- the server's own nodes are what get sorted and filtered.

    Every ``<tr>`` and ``<td>`` is stamped with a property no serialisation carries, so
    a node that survives sorting and filtering is provably the same object -- and its
    ``:style_row:`` class, its ``data-need-id``, its cell classes and the ``<a href>``
    inside it survive with it.
    """
    page, _ = opened
    _show_all(page, INTERACTIVE)

    page.evaluate(
        """(id) => {
            Array.from(document.getElementById(id).tBodies[0].rows).forEach(
                (row, index) => {
                    row.__stamp = 'row-' + index;
                    Array.from(row.cells).forEach((cell, position) => {
                        cell.__stamp = 'cell-' + index + '-' + position;
                    });
                },
            );
        }""",
        INTERACTIVE,
    )
    before = _need_ids(page, INTERACTIVE)
    assert len(before) == 14

    _sort(page, INTERACTIVE, 0, times=2)  # id, descending
    _wrapper(page, INTERACTIVE).locator("input.needstable-search-input").fill("R_0")
    page.wait_for_timeout(250)

    state = page.evaluate(
        """(id) => Array.from(
            document.getElementById(id).tBodies[0].rows,
        ).map((row) => ({
            stamp: row.__stamp,
            needId: row.getAttribute('data-need-id'),
            classes: row.className,
            cellStamps: Array.from(row.cells).map((cell) => cell.__stamp),
            cellClasses: Array.from(row.cells).map((cell) => cell.className),
            href: row.cells[0].querySelector('a').getAttribute('href'),
        }))""",
        INTERACTIVE,
    )
    assert state, "the filter matched nothing"
    for row in state:
        assert row["stamp"] is not None, "a row was re-created rather than moved"
        assert all(stamp is not None for stamp in row["cellStamps"])
        assert row["needId"] in before
        classes = set(row["classes"].split())
        assert classes & {"need", "need_part"}
        if "need" in classes:
            # `:style_row:` put this class here and nothing has taken it away
            assert classes & {"needs_open", "needs_closed"}
        assert row["cellClasses"][0].startswith("needs_id")
        assert row["href"] == "#" + row["needId"]


@pytest.mark.jstest
@_APP
def test_typed_sort_and_three_state_cycle(opened) -> None:
    """t2 -- numbers sort as numbers, dates as dates, text naturally; empty last."""
    page, _ = opened
    _show_all(page, INTERACTIVE)

    original = _need_ids(page, INTERACTIVE)
    assert _aria_sort(page, INTERACTIVE) == ["none"] * 6

    # `amount` is declared `data-type="number"`, so a number comparator runs: 2 before 10
    # before 100, not "10, 100, 2" -- and -20 before -5, which a text collator gets wrong
    # even with `numeric: true` (measured: it orders "-5" before "-20")
    _sort(page, INTERACTIVE, 3)
    amounts = [value for value in _column(page, INTERACTIVE, 3) if value]
    assert amounts == [
        "-20",
        "-5",
        "1",
        "2",
        "4",
        "4",
        "4",
        "7",
        "10",
        "15",
        "25",
        "42",
        "100",
    ]
    # the need with no amount is last, whichever way the column points
    assert _column(page, INTERACTIVE, 3)[-1] == ""
    assert _aria_sort(page, INTERACTIVE)[3] == "ascending"

    _sort(page, INTERACTIVE, 3)
    assert _aria_sort(page, INTERACTIVE)[3] == "descending"
    descending = [value for value in _column(page, INTERACTIVE, 3) if value]
    assert descending == list(reversed(amounts))
    assert _column(page, INTERACTIVE, 3)[-1] == ""

    # the third click is "none": the server's `:sort:` order, restored exactly
    _sort(page, INTERACTIVE, 3)
    assert _aria_sort(page, INTERACTIVE) == ["none"] * 6
    assert _need_ids(page, INTERACTIVE) == original

    # `due` carries no `data-type`; the script detects a date column and orders it
    _sort(page, INTERACTIVE, 4)
    dates = [value for value in _column(page, INTERACTIVE, 4) if value]
    assert dates == sorted(dates)
    assert _column(page, INTERACTIVE, 4)[-1] == ""
    _sort(page, INTERACTIVE, 4, times=2)

    # `title` is text, compared with a natural-order collator. Only the LEAD row of a
    # group carries the need's own title; a part row carries the part's text and travels
    # with its need rather than sorting on its own.
    _sort(page, INTERACTIVE, 1)
    titles = page.evaluate(
        """(id) => Array.from(document.getElementById(id).tBodies[0].rows)
            .filter((row) => row.classList.contains('need'))
            .map((row) => row.cells[1].textContent.trim())""",
        INTERACTIVE,
    )
    assert titles[0].startswith("Alpha")
    assert titles == sorted(titles, key=str.lower)


@pytest.mark.jstest
@_APP
def test_part_rows_travel_with_their_need(opened) -> None:
    """t3 -- a need and its parts are one unit, in both sort directions."""
    page, _ = opened
    _show_all(page, INTERACTIVE)

    for clicks in (1, 2):
        _sort(page, INTERACTIVE, 0, times=clicks)
        ids = _need_ids(page, INTERACTIVE)
        position = ids.index("S_02")
        assert ids[position : position + 3] == ["S_02", "S_02.P1", "S_02.P2"], ids
        _sort(page, INTERACTIVE, 0, times=3 - clicks)


@pytest.mark.jstest
@_APP
def test_filter_matches_a_part_beyond_the_first_page(opened) -> None:
    """t4 -- the filter reads the whole table, and a match keeps the whole group."""
    page, _ = opened
    wrapper = _wrapper(page, INTERACTIVE)
    search = wrapper.locator("input.needstable-search-input")
    info = wrapper.locator("div.needstable-info")

    # `S_02` is the eleventh group, so it is NOT attached while page one is shown; the
    # word only ever appears in its part rows
    assert "S_02" not in _need_ids(page, INTERACTIVE)
    search.fill("zebracrossing")
    page.wait_for_timeout(250)

    assert _need_ids(page, INTERACTIVE) == ["S_02", "S_02.P1", "S_02.P2"]
    assert info.text_content().strip() == "Showing 1\u20131 of 1"

    search.fill("no such need anywhere")
    page.wait_for_timeout(250)
    assert _need_ids(page, INTERACTIVE) == []
    assert info.text_content().strip() == "No matching rows"

    # the count is announced, not merely displayed
    assert info.get_attribute("aria-live") == "polite"
    assert wrapper.locator("nav.needstable-pager").get_attribute("aria-label") == (
        "Pagination"
    )


@pytest.mark.jstest
@_APP
def test_filter_query_whitespace_is_normalised(opened) -> None:
    """t14 -- a query typed exactly as the cell reads matches it.

    The index the filter searches collapses runs of whitespace, so the query has to as
    well; otherwise a cell rendered with two spaces is found by typing one and not by
    typing what is on the screen.
    """
    page, _ = opened

    page.evaluate(
        """(id) => {
            const table = document.getElementById(id);
            table.__needstable.destroy();
            table.tBodies[0].rows[0].cells[1].textContent = 'gamma  spaced';
            window.needstable.init(table);
        }""",
        INTERACTIVE,
    )
    search = _wrapper(page, INTERACTIVE).locator("input.needstable-search-input")

    search.fill("gamma  spaced")
    page.wait_for_timeout(250)
    assert _need_ids(page, INTERACTIVE) == ["R_01"]

    # and the collapsed spelling still matches, as it always did
    search.fill("gamma spaced")
    page.wait_for_timeout(250)
    assert _need_ids(page, INTERACTIVE) == ["R_01"]


@pytest.mark.jstest
@_APP
def test_paging(opened) -> None:
    """t5 -- ten groups a page, a hidden pager when there is one page, "All", and reset."""
    page, _ = opened
    wrapper = _wrapper(page, INTERACTIVE)
    pager = wrapper.locator("nav.needstable-pager")

    assert len(_need_ids(page, INTERACTIVE)) == 10
    assert pager.is_visible()
    assert wrapper.locator("div.needstable-info").text_content().strip() == (
        "Showing 1\u201310 of 12"
    )

    # the second page carries the last two groups, which is four rows: S_02 and its two
    # parts, then S_03
    pager.locator("button.needstable-page-number", has_text="2").click()
    assert _need_ids(page, INTERACTIVE) == ["S_02", "S_02.P1", "S_02.P2", "S_03"]

    # the small table holds three GROUPS -- `S_01`, `S_02` with the two part rows the
    # filter matched, and `S_03` -- so it is one page, and the pager is not there at all
    small = _wrapper(page, SMALL)
    assert _need_ids(page, SMALL) == ["S_01", "S_02", "S_02.P1", "S_02.P2", "S_03"]
    assert small.locator("div.needstable-info").text_content().strip() == (
        "Showing 1\u20133 of 3"
    )
    # `hidden` alone is not enough: an author `display` rule beats the user agent's
    # `[hidden] { display: none }`, and an element that is `hidden` but still displayed
    # stays in the accessibility tree. Assert the thing that actually removes it.
    assert _pager_display(page, SMALL) == "none"

    # the small table asks for `:page_size: 5`, which is not one of the offered sizes;
    # the control has to be able to show the size the table is actually using
    assert small.locator(
        "select.needstable-page-size-select option"
    ).all_text_contents() == [
        "5",
        "10",
        "25",
        "50",
        "All",
    ]
    assert small.locator("select.needstable-page-size-select").input_value() == "5"

    _show_all(page, INTERACTIVE)
    assert len(_need_ids(page, INTERACTIVE)) == 14
    assert _pager_display(page, INTERACTIVE) == "none"

    # back to ten a page, on page two, then filter: the view resets to page one
    wrapper.locator("select.needstable-page-size-select").select_option("10")
    pager.locator("button.needstable-page-number", has_text="2").click()
    wrapper.locator("input.needstable-search-input").fill("requirement")
    page.wait_for_timeout(250)
    assert (
        wrapper.locator("div.needstable-info")
        .text_content()
        .strip()
        .startswith("Showing 1\u2013")
    )


@pytest.mark.jstest
@_APP
def test_scroll_frame(opened, test_app: SphinxTestApp) -> None:
    """t11 -- the table fills its column, and the scroll frame is what scrolls.

    The `<table>` keeps ``display: table``, so ``:colwidths:`` percentages resolve against
    the whole column; the horizontal scrolling is a box of the widget's own, outside which
    the control bars sit. A `<table>` set to ``display: block`` would shrink-to-fit instead,
    and a rule targeting the table through its parent would stop matching in any host whose
    own script wraps the `<table>`.
    """
    page, _ = opened

    def geometry(table_id: str) -> dict[str, float]:
        return page.evaluate(
            """(id) => {
                const table = document.getElementById(id);
                const wrapper = table.closest('div.needstable');
                const scroll = table.closest('div.needstable-scroll');
                const controls = wrapper.querySelector('div.needstable-controls');
                return {
                    wrapper: wrapper.getBoundingClientRect().width,
                    controls: controls.getBoundingClientRect().width,
                    scrollClient: scroll.clientWidth,
                    scrollWidth: scroll.scrollWidth,
                    table: table.getBoundingClientRect().width,
                    display: getComputedStyle(table).display,
                    overflowX: getComputedStyle(scroll).overflowX,
                };
            }""",
            table_id,
        )

    # (a) a table that fits fills the frame exactly -- it does not shrink-to-fit
    narrow = geometry(SMALL)
    assert narrow["display"] == "table"
    assert abs(narrow["table"] - narrow["scrollClient"]) <= 1, narrow
    assert abs(narrow["scrollClient"] - narrow["wrapper"]) <= 1, narrow

    # (b) a table too wide for the page scrolls INSIDE the frame, and the control bar is
    # not dragged wider with it. `wide.html` holds a ten-column table for exactly this.
    page.goto(Path(test_app.outdir, "wide.html").as_uri())
    wide_id = page.evaluate("() => document.querySelector('table.NEEDS_DATATABLES').id")
    wide = geometry(wide_id)
    assert wide["overflowX"] == "auto", wide
    assert wide["scrollWidth"] > wide["scrollClient"], wide
    assert abs(wide["controls"] - wide["wrapper"]) <= 1, wide


@pytest.mark.jstest
@_APP
def test_the_last_column_is_guarded_from_the_first_paint(
    opened, test_app: SphinxTestApp
) -> None:
    """t16 -- a one-column table cannot be emptied by the reader's first click.

    The guard is applied whenever the visibility changes, which for two or more columns
    means the first click engages it in time. With exactly one column that click is already
    the fatal one, so the guard has to hold before the reader touches anything.
    """
    page, _ = opened

    def disabled_flags() -> list[bool]:
        return page.evaluate(
            """() => Array.from(
                document.querySelectorAll('label.needstable-columns-item input'),
            ).map((box) => box.disabled)"""
        )

    # six columns and three: nothing is disabled, because nothing is at stake yet
    assert disabled_flags() == [False] * 9

    page.goto(Path(test_app.outdir, "one_column.html").as_uri())
    assert disabled_flags() == [True]

    # and the guard means what it says: clicking it changes nothing
    box = page.locator("label.needstable-columns-item input")
    page.locator("details.needstable-columns > summary").click()
    assert box.is_enabled() is False
    assert box.is_checked() is True
    assert page.evaluate(
        "() => document.querySelector('colgroup') === null"
        " || document.querySelectorAll('colgroup > col').length"
    )


@pytest.mark.jstest
def test_the_vendored_pair_lays_out_on_its_own(page: Page) -> None:
    """t15 -- `needstable.css` + `needstable.js`, with no host stylesheet at all.

    This is what a consumer that vendors the pair byte-identical actually ships, and it is
    the only thing that can fence the STRUCTURAL sheet: sphinx-needs' own host sheet also
    gives the table `width: 100%`, so every other test in this module passes whether or not
    the shipped pair does. Without the rule the table shrink-to-fits -- measured at 378 px
    in an 800 px frame, with the `<colgroup>` percentages resolving against the shrunken
    width, which is the defect the scroll frame was introduced to fix.

    It needs no sphinx build: the fixture references the two files in the package tree.
    """
    fixture = Path(__file__).parent / "fixtures" / "needstable_pair.html"
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(error.message))
    page.goto(fixture.as_uri())

    measured = page.evaluate(
        """() => {
            const table = document.getElementById('pair-table');
            const frame = table.closest('div.needstable-scroll');
            return {
                enhanced: Boolean(table.__needstable),
                host: document.getElementById('host').clientWidth,
                frame: frame ? frame.clientWidth : null,
                table: table.getBoundingClientRect().width,
                controls: document
                    .querySelector('div.needstable-controls')
                    .getBoundingClientRect().width,
            };
        }"""
    )
    assert not page_errors, page_errors
    assert measured["enhanced"], "the pair did not enhance its own markup"
    assert measured["frame"] == measured["host"], measured
    assert abs(measured["table"] - measured["frame"]) <= 1, measured
    assert abs(measured["controls"] - measured["host"]) <= 1, measured


@pytest.mark.jstest
@_APP
def test_column_visibility_reaches_the_export(opened) -> None:
    """t6 -- hiding a column removes it from the table AND from what is exported."""
    page, _ = opened
    wrapper = _wrapper(page, INTERACTIVE)

    def csv_header() -> str:
        return page.evaluate(
            f"() => document.getElementById('{INTERACTIVE}')"
            ".__needstable.csv().split('\\r\\n')[0]"
        )

    assert csv_header() == "ID,Title,Status,Amount,Due,Outgoing"

    wrapper.locator("details.needstable-columns > summary").click()
    wrapper.locator("label.needstable-columns-item input").nth(2).uncheck()

    assert wrapper.locator("thead th").nth(2).is_hidden()
    # the `<col>` that sized the hidden column goes with it, so the widths stay aligned
    assert (
        page.evaluate(
            f"() => document.getElementById('{INTERACTIVE}')"
            ".querySelector('colgroup').children.length"
        )
        == 5
    )
    assert csv_header() == "ID,Title,Amount,Due,Outgoing"

    # and a PART row loses the column too -- `matrix()` filters every row of every group
    # by the same index, not only the leads
    part_line = page.evaluate(
        f"""() => document.getElementById('{INTERACTIVE}')
            .__needstable.csv()
            .split('\\r\\n')
            .find((line) => line.startsWith('\u2192 S_02.P1'))"""
    )
    assert part_line is not None, "the part row is not in the export"
    assert part_line.count(",") == 4, part_line

    # `copy()` writes the same matrix, tab-separated
    tsv_header = page.evaluate(
        f"() => document.getElementById('{INTERACTIVE}')"
        ".__needstable.tsv().split('\\n')[0]"
    )
    assert tsv_header == "ID\tTitle\tAmount\tDue\tOutgoing"

    # a table cannot be reduced to no columns: switch every column off but one, and the
    # last one still showing keeps its checkbox, disabled
    boxes = wrapper.locator("label.needstable-columns-item input")
    for index in (1, 3, 4, 5):
        boxes.nth(index).uncheck()
    assert boxes.nth(0).is_enabled() is False
    assert [boxes.nth(index).is_checked() for index in range(6)] == [
        True,
        False,
        False,
        False,
        False,
        False,
    ]

    # Escape closes the disclosure and hands focus back to the control that opened it
    page.keyboard.press("Escape")
    assert wrapper.locator("details.needstable-columns").get_attribute("open") is None
    assert page.evaluate("() => document.activeElement.className") == (
        "needstable-columns-summary"
    )


@pytest.mark.jstest
@_APP
def test_csv_download_bytes(opened) -> None:
    """t7 -- a UTF-8 BOM, CRLF line endings and RFC 4180 quoting."""
    page, _ = opened
    _show_all(page, INTERACTIVE)

    with page.expect_download() as downloaded:
        _wrapper(page, INTERACTIVE).locator("button.needstable-csv").click()
    download = downloaded.value
    assert download.suggested_filename == f"{INTERACTIVE}.csv"
    raw = Path(download.path()).read_bytes()

    assert raw.startswith(b"\xef\xbb\xbf"), "Excel needs the BOM to read it as UTF-8"
    text = raw.decode("utf-8-sig")
    assert text.split("\r\n")[0] == "ID,Title,Status,Amount,Due,Outgoing"
    assert "\r\n" in text
    assert text.count("\n") == text.count("\r\n"), "a bare LF got in"
    # the title holds both a comma and a quote, so the field is quoted and the quotes
    # are doubled
    assert '"Comma, and ""quotes"" in a title"' in text


@pytest.mark.jstest
@_APP
def test_keyboard_sorting(opened) -> None:
    """t8 -- the header control is a real button, so Tab reaches it and Enter sorts."""
    page, _ = opened
    button = _wrapper(page, INTERACTIVE).locator("th button.needstable-sort").first
    button.focus()
    assert page.evaluate("() => document.activeElement.className") == "needstable-sort"
    assert button.get_attribute("aria-label") == "ID: sort"

    page.keyboard.press("Enter")
    assert _aria_sort(page, INTERACTIVE)[0] == "ascending"
    page.keyboard.press("Enter")
    assert _aria_sort(page, INTERACTIVE)[0] == "descending"

    # paging rebuilds every pager button, including the one the reader just activated.
    # Focus has to land back inside the pager, or a keyboard reader is returned to <body>
    # and has to Tab from the top of the document after every page change.
    pager = _wrapper(page, INTERACTIVE).locator("nav.needstable-pager")
    before = _need_ids(page, INTERACTIVE)
    pager.locator("button.needstable-page-next").focus()
    page.keyboard.press("Enter")
    assert _need_ids(page, INTERACTIVE) != before, "the page did not change"
    assert page.evaluate(
        "() => document.activeElement.closest('nav.needstable-pager') !== null"
    ), page.evaluate("() => document.activeElement.tagName")
    # "Next" is disabled on the last page, so focus goes to the control that is not
    assert (
        page.evaluate("() => document.activeElement.className")
        == "needstable-page needstable-page-previous"
    )

    # and when the pager goes away entirely while it holds focus -- which only a script can
    # arrange, since every control that collapses the table takes focus itself first -- the
    # reader lands on the search box rather than on <body>
    landed = page.evaluate(
        """(id) => {
            const table = document.getElementById(id);
            const wrapper = table.closest('div.needstable');
            wrapper.querySelector('button.needstable-page-number').focus();
            const instance = table.__needstable;
            instance.query = 'zebracrossing';
            instance.page = 0;
            instance.update();
            const pager = wrapper.querySelector('nav.needstable-pager');
            return {
                display: getComputedStyle(pager).display,
                active: document.activeElement.className,
            };
        }""",
        INTERACTIVE,
    )
    assert landed["display"] == "none", landed
    assert landed["active"] == "needstable-search-input", landed


@pytest.mark.jstest
@_APP
def test_destroy_restores_the_original_dom(opened) -> None:
    """t9 -- after ``destroy()`` the table is byte-for-byte what the server wrote."""
    page, _ = opened

    # do enough to make a restoration non-trivial: sort, hide a column, page and filter
    _sort(page, INTERACTIVE, 3)
    wrapper = _wrapper(page, INTERACTIVE)
    wrapper.locator("details.needstable-columns > summary").click()
    wrapper.locator("label.needstable-columns-item input").nth(1).uncheck()
    wrapper.locator("input.needstable-search-input").fill("requirement")
    page.wait_for_timeout(250)

    restored, pristine = page.evaluate(
        """(id) => {
            const table = document.getElementById(id);
            table.__needstable.destroy();
            return [table.outerHTML, window.__pristine[id]];
        }""",
        INTERACTIVE,
    )
    assert pristine, "the pristine markup was never captured"
    assert restored == pristine
    # and the widget is gone from around it
    assert page.locator(f"#{INTERACTIVE}").evaluate("t => !t.__needstable")
    assert (
        page.evaluate("() => document.querySelectorAll('div.needstable').length") == 1
    )


@pytest.mark.jstest
@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        # the DEFAULT theme, which is what a project that never sets `needs_css` gets
        (
            {
                "buildername": "html",
                "srcdir": "doc_test/doc_needtable_enhancer",
                "confoverrides": {"needs_css": "modern.css"},
            },
            ("rgb(255, 255, 255)", "rgb(51, 51, 51)"),
        ),
        (
            {
                "buildername": "html",
                "srcdir": "doc_test/doc_needtable_enhancer",
                "confoverrides": {"needs_css": "dark.css"},
            },
            ("rgb(51, 51, 51)", "rgb(238, 238, 238)"),
        ),
    ],
    indirect=["test_app"],
)
def test_columns_popover_follows_the_theme(opened, expected) -> None:
    """t12 -- the one opaque surface the widget paints takes its colours from the host.

    Everything else the widget draws is transparent and inherits the page. The columns
    disclosure cannot be: it overlays the table. Its structural fallbacks are the system
    colours, which follow the USER AGENT's colour scheme rather than the page's, so on a
    site whose own switch says dark they come out white on a dark page.
    """
    page, _ = opened
    wrapper = _wrapper(page, INTERACTIVE)
    wrapper.locator("details.needstable-columns > summary").click()

    colours = page.evaluate(
        """() => {
            const list = document.querySelector('div.needstable-columns-list');
            const style = getComputedStyle(list);
            return {bg: style.backgroundColor, fg: style.color};
        }"""
    )
    # the point is that a token answered at all -- in BOTH themes, including the default
    # one, whose mapping nothing would otherwise notice the loss of -- and so that the
    # surface is never the user agent's `Canvas`
    assert (colours["bg"], colours["fg"]) == expected, colours


@pytest.mark.jstest
@_APP
def test_producer_extension_points(opened) -> None:
    """t13 -- the two extension points the contract publishes but sphinx-needs never uses.

    ``<td data-sort>`` and ``data-needstable-labels`` are for a producer that knows more
    than the rendered text does, or that speaks another language. sphinx-needs emits
    neither today, so without this the only thing standing between them and a silent
    regression is the design document's prose. They are set here on the built page, and the
    widget re-initialised over it.
    """
    page, _ = opened

    result = page.evaluate(
        """(id) => {
            const table = document.getElementById(id);
            table.__needstable.destroy();
            // `Alpha requirement` sorts first by text; `zzz` sends it to the end
            const first = table.tBodies[0].rows[0];
            first.cells[1].setAttribute('data-sort', 'zzz');
            table.setAttribute(
                'data-needstable-labels',
                JSON.stringify({copy: 'Kopieren', empty: 'Nichts gefunden'}),
            );
            const instance = window.needstable.init(table);
            instance.pageSize = 0;
            instance.toggleSort(1);
            const wrapper = table.closest('div.needstable');
            const ids = Array.from(table.tBodies[0].rows).map(
                (row) => row.getAttribute('data-need-id'),
            );
            instance.query = 'no such need anywhere';
            instance.update();
            return {
                ids: ids,
                copyLabel: wrapper.querySelector('button.needstable-copy').textContent,
                emptyLabel: wrapper.querySelector('div.needstable-info').textContent,
            };
        }""",
        INTERACTIVE,
    )

    # `data-sort` beat the cell's own text: the row that sorts first by title is last
    assert result["ids"][0] != "R_01", result["ids"]
    assert result["ids"][-1] == "R_01", result["ids"]
    # and the producer's labels reached the DOM
    assert result["copyLabel"] == "Kopieren"
    assert result["emptyLabel"] == "Nichts gefunden"


@pytest.mark.jstest
@_APP
def test_plain_table_is_untouched(opened) -> None:
    """t10 -- `:style: table` opts out, and nothing on the page throws."""
    page, _ = opened

    assert page.locator(f"#{PLAIN}").evaluate("t => !t.__needstable")
    assert page.evaluate(
        """(id) => {
            const table = document.getElementById(id);
            return table.closest('div.needstable') === null
                && table.querySelector('button.needstable-sort') === null
                && table.outerHTML === window.__pristine[id];
        }""",
        PLAIN,
    )
    # the two interactive tables on the page each got their own widget
    assert (
        page.evaluate("() => document.querySelectorAll('div.needstable').length") == 2
    )
    assert page.evaluate("() => window.needstable.version") == "1"

    # every control on the bar is one typeface and one size. A host theme that styles
    # `<summary>` or a form control -- and several do, one of them as an admonition with
    # an injected icon and a chevron -- must not leave one of them a different size from
    # its neighbours. This runs against the default theme only, but it fences the
    # `font: inherit` rules that stop it happening.
    sizes = page.evaluate(
        """() => {
            const bar = document.querySelector('div.needstable-controls');
            const of = (selector) =>
                getComputedStyle(bar.querySelector(selector)).fontSize;
            return {
                copy: of('button.needstable-copy'),
                summary: of('details.needstable-columns > summary'),
                search: of('input.needstable-search-input'),
                size: of('select.needstable-page-size-select'),
            };
        }"""
    )
    assert len(set(sizes.values())) == 1, sizes
    # a second init is a no-op that hands back the same instance
    assert page.evaluate(
        f"""() => {{
            const table = document.getElementById('{INTERACTIVE}');
            return window.needstable.init(table) === table.__needstable;
        }}"""
    )
