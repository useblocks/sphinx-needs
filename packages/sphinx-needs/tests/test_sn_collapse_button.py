"""Browser tests for the need table's collapse button.

The page under test is built by the ordinary ``test_app`` fixture and then opened straight
off disk over ``file://`` -- nothing in it fetches, so no server is involved. What is
asserted is ``src/sphinx_needs/libs/html/sphinx_needs_collapse.js``: on load it hides one of
the two icons (and, in ``hide`` mode, the metadata rows) by adding ``collapse_is_hidden``,
and a click on the control toggles all of them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sphinx.testing.util import SphinxTestApp

# the browser driver is the `js` dependency group, which the CI matrix cells deliberately do
# not install: without this the module fails at COLLECTION there, which fails the whole run
# even though `-m "not jstest"` would deselect these tests
_playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="the browser tests need the `js` dependency group (`uv sync --group js`)",
)
expect = _playwright.expect

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

#: the class ``sphinx_needs_collapse.js`` adds and removes
HIDE_CLASS = "collapse_is_hidden"


def _has_class(name: str) -> re.Pattern[str]:
    """A word-boundary match for ONE class name.

    ``class`` holds several names, so equality on the whole attribute would assert the
    other classes too and break whenever the markup around it changes.
    """
    return re.compile(rf"(^|\s){re.escape(name)}($|\s)")


def _expect_hide_class(locator: Locator, *, present: bool) -> None:
    """Assert every element ``locator`` matches carries (or lacks) :data:`HIDE_CLASS`."""
    count = locator.count()
    assert count, f"selector matched no element: {locator}"
    for index in range(count):
        element = locator.nth(index)
        if present:
            expect(element).to_have_class(_has_class(HIDE_CLASS))
        else:
            expect(element).not_to_have_class(_has_class(HIDE_CLASS))


def _check_collapse_buttons(app: SphinxTestApp, page: Page) -> set[str]:
    """Build the project, open its index page and exercise every collapse control.

    :return: the modes (``show`` / ``hide``) actually met on the page, so a caller can
        assert which branch of the script it covered.
    """
    app.build()

    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(error.message))

    page.goto(Path(app.outdir, "index.html").as_uri())

    controls = page.locator("table.need span.needs.needs_collapse")
    control_count = controls.count()
    assert control_count, "the built page has no collapse control to test"
    modes_seen: set[str] = set()

    for index in range(control_count):
        control = controls.nth(index)

        # the control's id is `<need id>__<show|hide>__<row class>__<row class>...`:
        # the mode it starts in, then the metadata rows it governs
        control_id = control.get_attribute("id")
        assert control_id, "a collapse control has no id"
        _, mode, *rows = control_id.split("__")
        assert mode in {"show", "hide"}, f"unexpected collapse mode in {control_id!r}"
        assert rows, f"no rows named in {control_id!r}"
        modes_seen.add(mode)

        # the enclosing need container -- `ancestor::…[1]` on a reverse axis is the
        # NEAREST one, i.e. the `closest()` the script itself uses to scope its lookups
        container = control.locator("xpath=ancestor::div[starts-with(@id, 'SNCB-')][1]")
        container_id = container.get_attribute("id")
        assert container_id, "the collapse control has no SNCB- container"

        icon_visible = control.locator("span.needs.visible")
        icon_collapsed = control.locator("span.needs.collapsed")
        row_locators = [page.locator(f"#{container_id} table tr.{row}") for row in rows]

        # (a) the state the script leaves on load
        if mode == "show":
            _expect_hide_class(icon_visible, present=True)
        else:
            _expect_hide_class(icon_collapsed, present=True)
            for row_locator in row_locators:
                _expect_hide_class(row_locator, present=True)

        # (b) a click flips every one of them
        control.click()
        # `show` starts expanded, so its click hides the rows; `hide` starts collapsed
        hidden_after_click = mode == "show"
        for row_locator in row_locators:
            _expect_hide_class(row_locator, present=hidden_after_click)
        _expect_hide_class(icon_collapsed, present=hidden_after_click)
        _expect_hide_class(icon_visible, present=not hidden_after_click)

    # nothing on THESE pages throws (the three test projects use the default theme), so
    # this is an unconditional assertion -- there is no allowance for "<x> is not defined"
    # like the retired JS harness's support file carried. It is not true of every theme: a
    # docs build with `sphinx_immaterial` raises `DOCUMENTATION_OPTIONS is not defined` from
    # sphinx-copybutton on every page (the theme emits no documentation_options.js), so a
    # case on such a page needs an allowance that matches that exact message and says why
    assert not page_errors, f"the page raised: {page_errors}"

    return modes_seen


@pytest.mark.jstest
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/variant_doc",
            "tags": ["tag_a"],
        }
    ],
    indirect=True,
)
def test_collapse_button_in_variant_doc(test_app: SphinxTestApp, page: Page) -> None:
    """Check the Sphinx-Needs collapse button works in the variant documentation source."""
    _check_collapse_buttons(test_app, page)


@pytest.mark.jstest
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_basic",
        }
    ],
    indirect=True,
)
def test_collapse_button_in_doc_basic(test_app: SphinxTestApp, page: Page) -> None:
    """Check the Sphinx-Needs collapse button works in the basic documentation source."""
    _check_collapse_buttons(test_app, page)


@pytest.mark.jstest
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/import_doc",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_collapse_button_in_import_doc(test_app: SphinxTestApp, page: Page) -> None:
    """Check the collapse button in a project that renders *collapsed* needs too.

    The other two projects emit only ``show`` controls, so on their own they never run the
    script's ``hide`` branch -- neither did the JavaScript specs they replace. This project's
    index imports one set of needs with ``:collapse: True``, so it carries both.
    """
    modes = _check_collapse_buttons(test_app, page)
    assert {"show", "hide"} <= modes, (
        f"expected both collapse modes, met {sorted(modes)}"
    )
