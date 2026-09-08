// @ts-check
/*!
 * sphinx_needs_collapse.js -- the collapse control on a need's meta box.
 *
 * Copyright (c) useblocks GmbH. MIT licence.
 *
 * Plain ES2020, no dependencies -- it drove jQuery until #1922, which was the last thing
 * in this extension that did. Type-checked through `// @ts-check` and JSDoc with the
 * one-line `tsc` recipe in `design/needstable-contract.md` (section 4).
 *
 * The markup it drives is written by `layout.py`, one block per need:
 *
 *     <div id="SNCB-1a2b3c4d" class="need_container">
 *       <table class="need">
 *         <tr class="meta"> ... </tr>            the rows the control governs
 *         <span class="needs needs_collapse" id="target__<show|hide>__<row class>...">
 *           <span class="needs collapsed"> ... </span>   one of the two is displayed;
 *           <span class="needs visible"> ... </span>     the other carries HIDE_CLASS
 *
 * The `id` on the control is NOT an identifier: docutils writes the same one on every
 * need of a page (`target__show__meta`, forty-four times over in one of the test
 * projects), and what it actually carries is the state the page was written in plus the
 * row classes, joined by `__`. So every lookup here is scoped to the control's own
 * `SNCB-` container instead, which is what the `#<container id> table ...` selectors this
 * file used to build did.
 *
 * The server already hides the right ICON, so on load the only state this script has to
 * establish is the metadata ROWS'. A click then flips all three.
 */

(function () {
    "use strict";

    /** The class that hides an icon or a metadata row; `css/common/need_core.css` styles it. */
    const HIDE_CLASS = "collapse_is_hidden";

    /**
     * The elements one control governs, inside the need's own container.
     *
     * Each lookup takes the FIRST match, as the selectors it replaces did -- a need has one
     * table, with one icon of each kind and one row per named class.
     *
     * @param {Element} container the `div[id^=SNCB-]` around one need
     * @param {string[]} rowClasses the metadata row classes named in the control's id
     * @returns {{collapsedIcon: Element | null, visibleIcon: Element | null, rows: Element[]}}
     */
    function governed(container, rowClasses) {
        /** @type {Element[]} */
        const rows = [];
        for (const rowClass of rowClasses) {
            if (!rowClass) {
                continue; // an empty `target` would build the invalid selector `table tr.`
            }
            const row = container.querySelector("table tr." + rowClass);
            if (row) {
                rows.push(row);
            }
        }
        return {
            collapsedIcon: container.querySelector("table span.needs.collapsed"),
            visibleIcon: container.querySelector("table span.needs.visible"),
            rows: rows,
        };
    }

    /**
     * @param {Element | null} element
     * @param {boolean} hidden
     */
    function setHidden(element, hidden) {
        if (element) {
            element.classList.toggle(HIDE_CLASS, hidden);
        }
    }

    /** @param {Element | null} element */
    function flipHidden(element) {
        if (element) {
            element.classList.toggle(HIDE_CLASS);
        }
    }

    /**
     * Give one control the state its page was written in, and the click that flips it.
     *
     * @param {Element} control a `span.needs.needs_collapse` inside a `table.need`
     */
    function initControl(control) {
        const id = control.getAttribute("id");
        if (!id) {
            return;
        }
        const [, mode, ...rowClasses] = id.split("__");
        const table = control.closest("table");
        const container = table && table.closest('div[id^="SNCB-"]');
        if (!container) {
            return;
        }

        const showRows = mode === "show";
        const parts = governed(container, rowClasses);
        setHidden(parts.visibleIcon, showRows);
        setHidden(parts.collapsedIcon, !showRows);
        for (const row of parts.rows) {
            setHidden(row, !showRows);
        }

        const icons = control.querySelectorAll(
            "span.needs.collapsed, span.needs.visible",
        );
        for (const icon of Array.from(icons)) {
            icon.addEventListener("click", function () {
                // looked up again on every click, as before, so that the control still
                // governs whatever is in the container at that moment
                const current = governed(container, rowClasses);
                for (const row of current.rows) {
                    flipHidden(row);
                }
                flipHidden(current.collapsedIcon);
                flipHidden(current.visibleIcon);
            });
        }
    }

    function run() {
        const controls = document.querySelectorAll(
            "table.need span.needs.needs_collapse",
        );
        for (const control of Array.from(controls)) {
            initControl(control);
        }

        // an anchor that must not navigate. The extension's own layouts do not emit one
        // today, but a project's `needs_layouts` may, and this has always been here
        for (const anchor of Array.from(document.querySelectorAll("a.no_link"))) {
            anchor.addEventListener("click", function (event) {
                event.preventDefault();
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
    } else {
        run();
    }
})();
