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

# The script is a deferred one, so it runs after parsing but BEFORE `DOMContentLoaded`,
# with `document.readyState === "interactive"`. The `readystatechange` to "interactive"
# fires just before deferred scripts run, which is the last moment at which the untouched
# markup can still be read -- and the only way to capture it without blocking the script,
# which `page.route` cannot do for a `file://` URL.
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

    # `amount` is declared `data-type="number"`: 2 before 10 before 100, not "10, 100, 2"
    _sort(page, INTERACTIVE, 3)
    amounts = [value for value in _column(page, INTERACTIVE, 3) if value]
    assert amounts == [
        "1",
        "2",
        "3",
        "4",
        "4",
        "4",
        "7",
        "8",
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
    assert small.locator("nav.needstable-pager").is_hidden()

    _show_all(page, INTERACTIVE)
    assert len(_need_ids(page, INTERACTIVE)) == 14
    assert _wrapper(page, INTERACTIVE).locator("nav.needstable-pager").is_hidden()

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
    # a second init is a no-op that hands back the same instance
    assert page.evaluate(
        f"""() => {{
            const table = document.getElementById('{INTERACTIVE}');
            return window.needstable.init(table) === table.__needstable;
        }}"""
    )
