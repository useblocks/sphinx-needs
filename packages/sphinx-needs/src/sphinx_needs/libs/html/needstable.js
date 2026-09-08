// @ts-check
/*!
 * needstable.js -- in-place enhancement of a server-rendered needtable.
 *
 * Copyright (c) useblocks GmbH. MIT licence.
 *
 * sphinx-needs is the REPOSITORY OF RECORD for this file. What it reads, what it builds
 * and why it exists at all are specified in `design/needstable-contract.md` in this
 * package; a change to that specification bumps NEEDSTABLE_VERSION below. A consumer that
 * ships this asset vendors it byte-identical and records its sha256 and that version.
 *
 * It never re-renders. Every `<tr>` and `<td>` the server wrote is the same node
 * afterwards, so `:style_row:` classes, the per-cell `needs_*` classes, the links inside
 * cells and the `<colgroup>` all survive sorting, filtering and paging. Rows that are not
 * on the current page are DETACHED rather than hidden -- as every paging table already
 * did -- which is what keeps a ten-thousand-row table usable.
 *
 * Requirements it holds itself to, so that any documentation builder or restrictive host
 * can embed it unchanged: a classic script (no ES modules, no dynamic imports, no
 * workers), no network access, no `eval` and no `innerHTML`, no dependencies, and
 * CSP-clean under a strict `script-src`.
 *
 * Plain ES2020 JavaScript, type-checked through JSDoc; the design document carries the
 * one-line `tsc` recipe.
 */

(function () {
    "use strict";

    /** The version of the markup + DOM contract this file implements. */
    const NEEDSTABLE_VERSION = "1";

    /** The class a `<table>` must carry to be enhanced. */
    const HOOK_CLASS = "NEEDS_DATATABLES";

    /** The class that hides a column the reader switched off. */
    const HIDDEN_CLASS = "needstable-hidden";

    /**
     * Every string the widget shows. A producer overrides any of them through
     * `data-needstable-labels`; this file ships no translation catalogues.
     *
     * @typedef {object} NeedstableLabels
     * @property {string} search
     * @property {string} rowsPerPage
     * @property {string} all
     * @property {string} columns
     * @property {string} copy
     * @property {string} csv
     * @property {string} info `{start}`, `{end}` and `{total}` are substituted
     * @property {string} empty
     * @property {string} pagination
     * @property {string} previous
     * @property {string} next
     * @property {string} sort `{column}` is substituted
     */

    /** @type {NeedstableLabels} */
    const LABELS = {
        search: "Search",
        rowsPerPage: "Rows per page",
        all: "All",
        columns: "Columns",
        copy: "Copy",
        csv: "CSV",
        info: "Showing {start}–{end} of {total}",
        empty: "No matching rows",
        pagination: "Pagination",
        previous: "Previous",
        next: "Next",
        sort: "{column}: sort",
    };

    /**
     * @typedef {object} NeedstableOptions
     * @property {number} pageSize rows per page; `0` means all of them
     * @property {number[]} pageSizes the sizes offered, `0` meaning "All"
     * @property {Partial<NeedstableLabels>} [labels]
     */

    /** @type {NeedstableOptions} */
    const DEFAULTS = {
        pageSize: 10,
        pageSizes: [10, 25, 50, 0],
    };

    /**
     * A need row and the part rows that belong to it: one unit for sorting, filtering
     * and paging alike.
     *
     * @typedef {object} NeedstableGroup
     * @property {HTMLTableRowElement} lead the need row the group sorts by
     * @property {HTMLTableRowElement[]} rows the lead row, then its part rows
     * @property {string | null} needId the lead row's `data-need-id`
     * @property {string} text every row's text, lower-cased, for the filter
     */

    /**
     * A `<table>` that may already carry an instance.
     *
     * @typedef {HTMLTableElement & {__needstable?: NeedsTable}} EnhancedTable
     */

    /**
     * How a column is compared: declared by the producer, or detected from the values.
     *
     * @typedef {"text" | "number" | "date"} ColumnType
     */

    /**
     * Which pager control had focus when the pager was rebuilt, so it can be given back.
     *
     * @typedef {{kind: "previous" | "next" | "number", page: number}} PagerFocus
     */

    /* ----------------------------------------------------------------- helpers */

    /**
     * @template {keyof HTMLElementTagNameMap} K
     * @param {K} tag
     * @param {string} [className]
     * @returns {HTMLElementTagNameMap[K]}
     */
    function element(tag, className) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        return node;
    }

    /**
     * An element's text, trimmed, with runs of whitespace collapsed to one space.
     *
     * @param {Element} node
     * @returns {string}
     */
    function cellText(node) {
        return (node.textContent || "").replace(/\s+/g, " ").trim();
    }

    /**
     * The value a cell sorts and exports by: `data-sort` when given, else its text.
     *
     * @param {HTMLTableCellElement | undefined} cell
     * @returns {string}
     */
    function cellValue(cell) {
        if (!cell) {
            return "";
        }
        const override = cell.getAttribute("data-sort");
        return override === null ? cellText(cell) : override.trim();
    }

    /**
     * Parse a number out of rendered text, without knowing the reader's locale.
     *
     * Whitespace (including non-breaking) and a per-cent sign are dropped. When both a
     * comma and a full stop are present the RIGHTMOST is the decimal mark and the other
     * groups digits; a lone comma groups digits only when the whole string looks like
     * `1,234,567`, and is a decimal mark otherwise.
     *
     * @param {string} text
     * @returns {number} `NaN` when the text is not a number
     */
    function toNumber(text) {
        let value = String(text).replace(/[\s\u00a0\u202f%]/g, "");
        if (!value) {
            return NaN;
        }
        const comma = value.lastIndexOf(",");
        const dot = value.lastIndexOf(".");
        if (comma >= 0 && dot >= 0) {
            value =
                comma > dot
                    ? value.replace(/\./g, "").replace(",", ".")
                    : value.replace(/,/g, "");
        } else if (comma >= 0) {
            value = /^[+-]?\d{1,3}(,\d{3})+$/.test(value)
                ? value.replace(/,/g, "")
                : value.replace(",", ".");
        }
        const number = Number(value);
        return Number.isFinite(number) ? number : NaN;
    }

    /**
     * Parse a date out of rendered text: ISO 8601 first, then whatever the engine takes.
     *
     * @param {string} text
     * @returns {number} milliseconds since the epoch, or `NaN`
     */
    function toDate(text) {
        const value = String(text).trim();
        if (!value) {
            return NaN;
        }
        if (/^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?/.test(value)) {
            return Date.parse(value.length === 10 ? value + "T00:00:00Z" : value);
        }
        return Date.parse(value);
    }

    const collator = new Intl.Collator(undefined, {
        numeric: true,
        sensitivity: "base",
    });

    /**
     * @param {ColumnType} type
     * @returns {(left: string, right: string) => number}
     */
    function comparatorFor(type) {
        if (type === "number") {
            return (left, right) => {
                const a = toNumber(left);
                const b = toNumber(right);
                if (Number.isNaN(a) && Number.isNaN(b)) {
                    return collator.compare(left, right);
                }
                if (Number.isNaN(a)) {
                    return 1;
                }
                if (Number.isNaN(b)) {
                    return -1;
                }
                return a - b;
            };
        }
        if (type === "date") {
            return (left, right) => {
                const a = toDate(left);
                const b = toDate(right);
                if (Number.isNaN(a) && Number.isNaN(b)) {
                    return collator.compare(left, right);
                }
                if (Number.isNaN(a)) {
                    return 1;
                }
                if (Number.isNaN(b)) {
                    return -1;
                }
                return a - b;
            };
        }
        return (left, right) => collator.compare(left, right);
    }

    /**
     * Guess a column's type from up to fifty non-empty values.
     *
     * @param {string[]} values
     * @returns {ColumnType}
     */
    function detectType(values) {
        let seen = 0;
        let numbers = 0;
        let dates = 0;
        for (let index = 0; index < values.length && seen < 50; index += 1) {
            const value = values[index];
            if (!value) {
                continue;
            }
            seen += 1;
            if (!Number.isNaN(toNumber(value))) {
                numbers += 1;
            } else if (!Number.isNaN(toDate(value))) {
                dates += 1;
            }
        }
        if (!seen) {
            return "text";
        }
        if (numbers === seen) {
            return "number";
        }
        if (dates === seen) {
            return "date";
        }
        return "text";
    }

    /**
     * RFC 4180: quote a field that holds a comma, a quote or a line break.
     *
     * @param {string} value
     * @returns {string}
     */
    function csvField(value) {
        return /[",\r\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
    }

    /**
     * Normalise a filter query the way the index it searches was normalised: runs of
     * whitespace collapsed, trimmed, lower-cased. Without this a query typed exactly as
     * the cell reads -- two spaces and all -- would never match.
     *
     * @param {string} text
     * @returns {string}
     */
    function normaliseQuery(text) {
        return text.replace(/\s+/g, " ").trim().toLowerCase();
    }

    /**
     * @param {string} text a label holding `{name}` placeholders
     * @param {Record<string, string | number>} values
     * @returns {string}
     */
    function template(text, values) {
        return text.replace(/\{(\w+)\}/g, (whole, name) =>
            Object.prototype.hasOwnProperty.call(values, name)
                ? String(values[name])
                : whole,
        );
    }

    /**
     * Read a table's `data-needstable-*` options. Anything malformed is ignored, so that
     * a bad attribute degrades to the default rather than to no table at all.
     *
     * @param {HTMLTableElement} table
     * @returns {Partial<NeedstableOptions>}
     */
    function readOptions(table) {
        /** @type {Partial<NeedstableOptions>} */
        const options = {};
        const pageSize = table.getAttribute("data-needstable-page-size");
        if (pageSize !== null) {
            const parsed = parseInt(pageSize, 10);
            if (Number.isFinite(parsed) && parsed >= 0) {
                options.pageSize = parsed;
            }
        }
        const pageSizes = table.getAttribute("data-needstable-page-sizes");
        if (pageSizes !== null) {
            /** @type {number[]} */
            const sizes = [];
            pageSizes.split(",").forEach((entry) => {
                const size = parseInt(entry, 10);
                if (Number.isFinite(size) && size >= 0 && sizes.indexOf(size) === -1) {
                    sizes.push(size);
                }
            });
            if (sizes.length) {
                options.pageSizes = sizes;
            }
        }
        const labels = table.getAttribute("data-needstable-labels");
        if (labels !== null) {
            try {
                const parsedLabels = JSON.parse(labels);
                if (parsedLabels && typeof parsedLabels === "object") {
                    options.labels = parsedLabels;
                }
            } catch (error) {
                /* a malformed label object leaves the English defaults in place */
            }
        }
        return options;
    }

    /**
     * Order page sizes for the control: `0` ("All") comes after every real size.
     *
     * @param {number} left
     * @param {number} right
     * @returns {number}
     */
    function bySize(left, right) {
        if (left === 0 || right === 0) {
            return left === 0 ? 1 : -1;
        }
        return left - right;
    }

    /**
     * Copy through the pre-async-clipboard route, for a browser or an origin that has no
     * usable `navigator.clipboard`.
     *
     * @param {string} text
     */
    function copyWithExecCommand(text) {
        try {
            const area = element("textarea", "needstable-clipboard");
            area.value = text;
            area.setAttribute("aria-hidden", "true");
            document.body.appendChild(area);
            area.select();
            document.execCommand("copy");
            area.remove();
        } catch (error) {
            /* a browser that allows neither route silently copies nothing */
        }
    }

    /* -------------------------------------------------------------- the instance */

    class NeedsTable {
        /**
         * @param {HTMLTableElement} table the server-rendered table, enhanced in place
         * @param {Partial<NeedstableOptions>} [options] overrides for the attributes
         */
        constructor(table, options) {
            /** @type {HTMLTableElement} */
            this.table = table;
            /** @type {NeedstableOptions} */
            this.options = Object.assign(
                {},
                DEFAULTS,
                readOptions(table),
                options || {},
            );
            /** @type {NeedstableLabels} */
            this.labels = Object.assign({}, LABELS, this.options.labels || {});

            const head = table.tHead;
            /** @type {HTMLTableCellElement[]} */
            this.headers = head
                ? Array.from(head.rows[head.rows.length - 1].cells)
                : [];
            /** @type {HTMLTableSectionElement | undefined} */
            this.body = table.tBodies[0];
            /**
             * Every body row, in the order the server wrote them. Never re-ordered: the
             * view is a list of groups, and this is what "unsorted" restores.
             *
             * @type {HTMLTableRowElement[]}
             */
            this.rows = this.body ? Array.from(this.body.rows) : [];
            /** @type {HTMLTableColElement | null} */
            this.colgroup = table.querySelector("colgroup");
            /** @type {Element[]} */
            this.cols = this.colgroup ? Array.from(this.colgroup.children) : [];
            if (this.cols.length !== this.headers.length) {
                /* a colgroup that does not describe these columns is left alone */
                this.cols = [];
            }
            /* every CHILD NODE, not only the elements: the text nodes between them are
               part of the document the server wrote, and `destroy()` owes them back */
            /** @type {ChildNode[]} */
            this.bodyNodes = this.body ? Array.from(this.body.childNodes) : [];
            /** @type {ChildNode[]} */
            this.colgroupNodes = this.colgroup
                ? Array.from(this.colgroup.childNodes)
                : [];

            /** @type {boolean[]} */
            this.hiddenColumns = this.headers.map(() => false);
            /** @type {number} the column being sorted, or `-1` for none */
            this.sortColumn = -1;
            /** @type {number} 0 = unsorted (the server's order), 1 = up, -1 = down */
            this.sortDirection = 0;
            /** @type {string} */
            this.query = "";
            /** @type {number} */
            this.pageSize = this.options.pageSize;
            if (this.options.pageSizes.indexOf(this.pageSize) === -1) {
                /* a producer may name a page size that is not among the offered ones;
                   the control has to be able to show the size the table is using */
                this.options.pageSizes = this.options.pageSizes
                    .concat([this.pageSize])
                    .sort(bySize);
            }
            /** @type {number} */
            this.page = 0;
            /** @type {number | undefined} */
            this.searchTimer = undefined;

            /** @type {NeedstableGroup[]} */
            this.groups = this.buildGroups();
            /** @type {ColumnType[]} */
            this.types = this.detectTypes();
            /** @type {NeedstableGroup[]} what the filter and sort leave, in order */
            this.view = this.groups.slice();

            /* the widget's own elements, created here so that every field this instance
               has is declared in one place; `buildControls` configures and assembles them */
            this.wrapper = element("div", "needstable");
            this.controls = element("div", "needstable-controls");
            this.scroll = element("div", "needstable-scroll");
            this.footer = element("div", "needstable-footer");
            this.searchInput = element("input", "needstable-search-input");
            this.sizeSelect = element("select", "needstable-page-size-select");
            this.columnsDetails = element("details", "needstable-columns");
            this.columnsSummary = element("summary", "needstable-columns-summary");
            /** @type {HTMLInputElement[]} one per column, in column order */
            this.columnCheckboxes = [];
            this.copyButton = element("button", "needstable-button needstable-copy");
            this.csvButton = element("button", "needstable-button needstable-csv");
            this.info = element("div", "needstable-info");
            this.pager = element("nav", "needstable-pager");
            /** @type {HTMLButtonElement[]} */
            this.sortButtons = [];

            this.buildControls();
            /* the last-column guard has to hold from the first paint: with one column the
               reader's first click would otherwise empty the table */
            this.applyColumnVisibility();
            this.update();
        }

        /**
         * A need row and the part rows belonging to it are ONE unit: they sort together,
         * and a filter that matches any of their text keeps all of them.
         *
         * Rows are read in document order. Anything that is not `tr.need_part` starts a
         * group. A `tr.need_part` joins the group being built when its `data-parent`
         * names that group's need, or -- when it carries no `data-parent` -- because it
         * follows it (the adjacency fallback, for a producer that does not emit the
         * attribute). Otherwise it is a group of its own. Groups are therefore contiguous
         * runs of the source order, which is what lets the unsorted state restore that
         * order exactly.
         *
         * @returns {NeedstableGroup[]}
         */
        buildGroups() {
            /** @type {NeedstableGroup[]} */
            const groups = [];
            /** @type {NeedstableGroup | null} */
            let current = null;
            this.rows.forEach((row) => {
                const isPart = row.classList.contains("need_part");
                if (isPart && current) {
                    const parent = row.getAttribute("data-parent");
                    if (parent === null || parent === current.needId) {
                        current.rows.push(row);
                        return;
                    }
                }
                current = {
                    lead: row,
                    rows: [row],
                    needId: row.getAttribute("data-need-id"),
                    text: "",
                };
                groups.push(current);
            });
            groups.forEach((group) => {
                group.text = group.rows
                    .map((row) => cellText(row))
                    .join(" ")
                    .toLowerCase();
            });
            return groups;
        }

        /**
         * The comparator type of each column: what the producer declared, else what the
         * values look like.
         *
         * @returns {ColumnType[]}
         */
        detectTypes() {
            return this.headers.map((header, index) => {
                const declared = header.getAttribute("data-type");
                if (
                    declared === "text" ||
                    declared === "number" ||
                    declared === "date"
                ) {
                    return declared;
                }
                return detectType(
                    this.groups.map((group) => cellValue(group.lead.cells[index])),
                );
            });
        }

        /* ------------------------------------------------------------------ the DOM */

        /** Wrap the table in the two control bars and wire every control up. */
        buildControls() {
            const table = this.table;
            const parent = table.parentNode;
            if (parent) {
                parent.insertBefore(this.wrapper, table);
            }
            this.wrapper.appendChild(this.controls);
            /* the table goes in its own scroll frame: it keeps `display: table`, so
               `:colwidths:` percentages resolve against the full column width, and the
               control bars are siblings of the frame rather than of the table, so they
               never scroll sideways with the data */
            this.scroll.appendChild(table);
            this.wrapper.appendChild(this.scroll);
            this.wrapper.appendChild(this.footer);

            /* search */
            const searchLabel = element("label", "needstable-search");
            const searchText = element("span", "needstable-label");
            searchText.textContent = this.labels.search;
            this.searchInput.type = "search";
            this.searchInput.placeholder = this.labels.search;
            this.searchInput.addEventListener("input", () => {
                if (this.searchTimer !== undefined) {
                    clearTimeout(this.searchTimer);
                }
                this.searchTimer = setTimeout(() => {
                    this.searchTimer = undefined;
                    this.query = normaliseQuery(this.searchInput.value);
                    this.page = 0;
                    this.update();
                }, 100);
            });
            searchLabel.appendChild(searchText);
            searchLabel.appendChild(this.searchInput);
            this.controls.appendChild(searchLabel);

            /* page size */
            const sizeLabel = element("label", "needstable-page-size");
            const sizeText = element("span", "needstable-label");
            sizeText.textContent = this.labels.rowsPerPage;
            this.options.pageSizes.forEach((size) => {
                const option = element("option");
                option.value = String(size);
                option.textContent = size === 0 ? this.labels.all : String(size);
                if (size === this.pageSize) {
                    option.selected = true;
                }
                this.sizeSelect.appendChild(option);
            });
            this.sizeSelect.addEventListener("change", () => {
                this.pageSize = parseInt(this.sizeSelect.value, 10) || 0;
                this.page = 0;
                this.update();
            });
            sizeLabel.appendChild(sizeText);
            sizeLabel.appendChild(this.sizeSelect);
            this.controls.appendChild(sizeLabel);

            /* column visibility -- a native disclosure, so nothing manages a popover */
            this.columnsSummary.textContent = this.labels.columns;
            this.columnsDetails.appendChild(this.columnsSummary);
            const list = element("div", "needstable-columns-list");
            this.columnCheckboxes = this.headers.map((header, index) => {
                const itemLabel = element("label", "needstable-columns-item");
                const checkbox = element("input");
                checkbox.type = "checkbox";
                checkbox.checked = true;
                checkbox.addEventListener("change", () => {
                    this.hiddenColumns[index] = !checkbox.checked;
                    this.applyColumnVisibility();
                    this.update();
                });
                const name = element("span");
                name.textContent = cellText(header);
                itemLabel.appendChild(checkbox);
                itemLabel.appendChild(name);
                list.appendChild(itemLabel);
                return checkbox;
            });
            /* Escape closes the disclosure and hands focus back to the control that
               opened it, which is what a reader who opened it by keyboard expects */
            this.columnsDetails.addEventListener("keydown", (event) => {
                if (event.key === "Escape" && this.columnsDetails.open) {
                    this.columnsDetails.open = false;
                    this.columnsSummary.focus();
                    event.stopPropagation();
                }
            });
            this.columnsDetails.appendChild(list);
            this.controls.appendChild(this.columnsDetails);

            /* export */
            this.copyButton.type = "button";
            this.copyButton.textContent = this.labels.copy;
            this.copyButton.addEventListener("click", () => this.copy());
            this.controls.appendChild(this.copyButton);

            this.csvButton.type = "button";
            this.csvButton.textContent = this.labels.csv;
            this.csvButton.addEventListener("click", () => this.downloadCsv());
            this.controls.appendChild(this.csvButton);

            /* sortable headers: the header's own content becomes the button's label, and
               it goes inside the header's `<p>` where there is one, so that a `<button>`
               never ends up holding block content */
            this.sortButtons = this.headers.map((header, index) => {
                const only = header.firstElementChild;
                const host =
                    header.children.length === 1 && only && only.tagName === "P"
                        ? only
                        : header;
                const button = element("button", "needstable-sort");
                button.type = "button";
                button.setAttribute(
                    "aria-label",
                    template(this.labels.sort, { column: cellText(header) }),
                );
                while (host.firstChild) {
                    button.appendChild(host.firstChild);
                }
                host.appendChild(button);
                header.setAttribute("aria-sort", "none");
                button.addEventListener("click", () => this.toggleSort(index));
                return button;
            });

            /* footer: the live region, then the pager */
            this.info.setAttribute("aria-live", "polite");
            this.pager.setAttribute("aria-label", this.labels.pagination);
            this.footer.appendChild(this.info);
            this.footer.appendChild(this.pager);
        }

        /** Hide or show columns: the headers, and the `<col>`s that size them. */
        applyColumnVisibility() {
            const hidden = this.hiddenColumns;
            this.headers.forEach((header, index) => {
                header.classList.toggle(HIDDEN_CLASS, hidden[index]);
            });
            /* a table cannot be reduced to no columns at all: the last one still showing
               keeps its checkbox, disabled */
            const showing = hidden.filter((isHidden) => !isHidden).length;
            this.columnCheckboxes.forEach((checkbox, index) => {
                checkbox.disabled = showing === 1 && !hidden[index];
            });
            /* the rows on the page are synced by `paint()`; a detached row is synced
               when it is next painted, so there is nothing to walk here */
            if (this.cols.length && this.colgroup) {
                const anyHidden = hidden.some(Boolean);
                const kept = anyHidden
                    ? this.cols.filter((col, index) => !hidden[index])
                    : this.colgroupNodes;
                this.colgroup.replaceChildren(...kept);
            }
        }

        /* --------------------------------------------------------------- behaviours */

        /**
         * Cycle a column: none -> ascending -> descending -> none.
         *
         * @param {number} index
         */
        toggleSort(index) {
            if (this.sortColumn !== index) {
                this.sortColumn = index;
                this.sortDirection = 1;
            } else if (this.sortDirection === 1) {
                this.sortDirection = -1;
            } else {
                this.sortColumn = -1;
                this.sortDirection = 0;
            }
            this.page = 0;
            this.update();
        }

        /** Re-filter, re-sort and repaint. */
        update() {
            const query = this.query;
            this.view = query
                ? this.groups.filter((group) => group.text.indexOf(query) !== -1)
                : this.groups.slice();

            if (this.sortDirection !== 0 && this.sortColumn >= 0) {
                const column = this.sortColumn;
                const direction = this.sortDirection;
                const compare = comparatorFor(this.types[column]);
                /* decorate-sort-undecorate: the comparator sees strings, and the
                   original position keeps the sort stable */
                const decorated = this.view.map((group, position) => ({
                    group,
                    position,
                    value: cellValue(group.lead.cells[column]),
                }));
                decorated.sort((left, right) => {
                    if (left.value === "" || right.value === "") {
                        /* empty cells sort last whichever way the column points */
                        if (left.value === right.value) {
                            return left.position - right.position;
                        }
                        return left.value === "" ? 1 : -1;
                    }
                    const order = compare(left.value, right.value);
                    return order !== 0
                        ? direction * order
                        : left.position - right.position;
                });
                this.view = decorated.map((entry) => entry.group);
            }

            this.headers.forEach((header, index) => {
                let state = "none";
                if (index === this.sortColumn && this.sortDirection === 1) {
                    state = "ascending";
                } else if (index === this.sortColumn && this.sortDirection === -1) {
                    state = "descending";
                }
                header.setAttribute("aria-sort", state);
            });

            this.paint();
        }

        /** Attach only the current page's rows; the rest stay out of the document. */
        paint() {
            const groupCount = this.view.length;
            const size = this.pageSize || groupCount || 1;
            const pageCount = Math.max(1, Math.ceil(groupCount / size));
            if (this.page >= pageCount) {
                this.page = pageCount - 1;
            }
            const from = this.page * size;
            const to = Math.min(groupCount, from + size);

            const fragment = document.createDocumentFragment();
            for (let index = from; index < to; index += 1) {
                this.view[index].rows.forEach((row) => {
                    for (let cell = 0; cell < row.cells.length; cell += 1) {
                        row.cells[cell].classList.toggle(
                            HIDDEN_CLASS,
                            Boolean(this.hiddenColumns[cell]),
                        );
                    }
                    fragment.appendChild(row);
                });
            }
            if (this.body) {
                this.body.replaceChildren(fragment);
            }

            this.info.textContent = groupCount
                ? template(this.labels.info, {
                      start: from + 1,
                      end: to,
                      total: groupCount,
                  })
                : this.labels.empty;
            this.paintPager(pageCount);
        }

        /**
         * Draw the pager: previous, the first and last page, a window around the current
         * one with ellipses for the gaps, next. Hidden entirely when there is one page.
         *
         * @param {number} pageCount
         */
        paintPager(pageCount) {
            /* every button is about to be replaced, including the one the reader just
               activated -- read where focus is BEFORE that happens */
            const focused = this.focusedPagerControl();
            this.pager.replaceChildren();
            this.pager.hidden = pageCount <= 1;
            if (pageCount <= 1) {
                if (focused) {
                    /* the pager is going away while it holds focus. Hand it to the search
                       box -- the control that collapses the table in practice -- rather
                       than dropping the reader back to the top of the document. */
                    this.searchInput.focus();
                }
                return;
            }

            /**
             * @param {string} label
             * @param {number} page
             * @param {boolean} disabled
             * @param {boolean} current
             * @param {string} className
             * @returns {HTMLButtonElement}
             */
            const makeButton = (label, page, disabled, current, className) => {
                const button = element("button", "needstable-page " + className);
                button.type = "button";
                button.textContent = label;
                button.disabled = disabled;
                if (current) {
                    button.setAttribute("aria-current", "page");
                }
                button.addEventListener("click", () => {
                    this.page = page;
                    this.paint();
                });
                return button;
            };
            const addEllipsis = () => {
                const span = element("span", "needstable-ellipsis");
                span.textContent = "…";
                this.pager.appendChild(span);
            };

            this.pager.appendChild(
                makeButton(
                    this.labels.previous,
                    this.page - 1,
                    this.page === 0,
                    false,
                    "needstable-page-previous",
                ),
            );
            const wanted = [0, pageCount - 1];
            for (let page = this.page - 1; page <= this.page + 1; page += 1) {
                if (page >= 0 && page < pageCount && wanted.indexOf(page) === -1) {
                    wanted.push(page);
                }
            }
            wanted.sort((left, right) => left - right);
            let previous = -1;
            wanted.forEach((page) => {
                if (previous >= 0 && page - previous > 1) {
                    addEllipsis();
                }
                this.pager.appendChild(
                    makeButton(
                        String(page + 1),
                        page,
                        false,
                        page === this.page,
                        "needstable-page-number",
                    ),
                );
                previous = page;
            });
            this.pager.appendChild(
                makeButton(
                    this.labels.next,
                    this.page + 1,
                    this.page === pageCount - 1,
                    false,
                    "needstable-page-next",
                ),
            );
            if (focused) {
                this.restorePagerFocus(focused);
            }
        }

        /**
         * Which pager control has focus right now, if any.
         *
         * @returns {PagerFocus | null}
         */
        focusedPagerControl() {
            const active = document.activeElement;
            if (!active || !this.pager.contains(active)) {
                return null;
            }
            if (active.classList.contains("needstable-page-previous")) {
                return { kind: "previous", page: this.page };
            }
            if (active.classList.contains("needstable-page-next")) {
                return { kind: "next", page: this.page };
            }
            return {
                kind: "number",
                page: Number(active.textContent || "1") - 1,
            };
        }

        /**
         * Give focus back to the equivalent control in the rebuilt pager: the same page
         * number if it is still offered, else the nearest one; a prev/next that is now
         * disabled hands focus to the other one.
         *
         * @param {PagerFocus} focused
         */
        restorePagerFocus(focused) {
            /** @type {HTMLButtonElement | null} */
            let target = null;
            if (focused.kind === "previous" || focused.kind === "next") {
                const own = /** @type {HTMLButtonElement | null} */ (
                    this.pager.querySelector("button.needstable-page-" + focused.kind)
                );
                const otherName =
                    focused.kind === "previous" ? "next" : "previous";
                const other = /** @type {HTMLButtonElement | null} */ (
                    this.pager.querySelector("button.needstable-page-" + otherName)
                );
                target = own && !own.disabled ? own : other;
            } else {
                const numbers = /** @type {HTMLButtonElement[]} */ (
                    Array.from(
                        this.pager.querySelectorAll("button.needstable-page-number"),
                    )
                );
                /**
                 * @param {HTMLButtonElement} button
                 * @returns {number}
                 */
                const distance = (button) =>
                    Math.abs(Number(button.textContent || "1") - 1 - focused.page);
                numbers.forEach((button) => {
                    if (!target || distance(button) < distance(target)) {
                        target = button;
                    }
                });
            }
            if (!target) {
                target = /** @type {HTMLButtonElement | null} */ (
                    this.pager.querySelector("button.needstable-page[aria-current]")
                );
            }
            if (target && !target.disabled) {
                target.focus();
            }
        }

        /* ------------------------------------------------------------------ export */

        /**
         * Header plus one line per row of every group the filter matches -- not per page.
         *
         * @returns {string[][]}
         */
        matrix() {
            /**
             * @param {unknown} _value
             * @param {number} index
             * @returns {boolean}
             */
            const keep = (_value, index) => !this.hiddenColumns[index];
            const rows = [this.headers.filter(keep).map((header) => cellText(header))];
            this.view.forEach((group) => {
                group.rows.forEach((row) => {
                    rows.push(
                        Array.from(row.cells)
                            .filter(keep)
                            .map((cell) => cellText(cell)),
                    );
                });
            });
            return rows;
        }

        /** @returns {string} the table as tab-separated text */
        tsv() {
            return this.matrix()
                .map((row) => row.join("\t"))
                .join("\n");
        }

        /** @returns {string} RFC 4180: CRLF endings, quoted fields, doubled quotes */
        csv() {
            return this.matrix()
                .map((row) => row.map(csvField).join(","))
                .join("\r\n");
        }

        /** Put the table on the clipboard as tab-separated text. */
        copy() {
            const text = this.tsv();
            try {
                if (navigator.clipboard) {
                    navigator.clipboard
                        .writeText(text)
                        .catch(() => copyWithExecCommand(text));
                    return;
                }
            } catch (error) {
                /* fall through to the pre-async-clipboard route */
            }
            copyWithExecCommand(text);
        }

        /** Hand the reader the table as a CSV file. */
        downloadCsv() {
            /* the BOM is what makes a spreadsheet read a UTF-8 CSV as UTF-8 */
            const blob = new Blob(["\ufeff" + this.csv()], {
                type: "text/csv;charset=utf-8",
            });
            const url = URL.createObjectURL(blob);
            const link = element("a", "needstable-download");
            link.href = url;
            link.download = (this.table.id || "needtable") + ".csv";
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 0);
        }

        /* ----------------------------------------------------------------- teardown */

        /** Put the table back exactly as the server wrote it. */
        destroy() {
            this.hiddenColumns = this.hiddenColumns.map(() => false);
            this.applyColumnVisibility();
            this.rows.forEach((row) => {
                for (let index = 0; index < row.cells.length; index += 1) {
                    row.cells[index].classList.remove(HIDDEN_CLASS);
                }
            });
            this.headers.forEach((header) => {
                header.classList.remove(HIDDEN_CLASS);
                header.removeAttribute("aria-sort");
            });
            this.sortButtons.forEach((button) => {
                const host = button.parentNode;
                if (!host) {
                    return;
                }
                while (button.firstChild) {
                    host.insertBefore(button.firstChild, button);
                }
                button.remove();
            });
            if (this.body) {
                /* every node goes back, in the order the server wrote them */
                this.body.replaceChildren(...this.bodyNodes);
            }
            if (this.wrapper.parentNode) {
                this.wrapper.parentNode.insertBefore(this.table, this.wrapper);
                this.wrapper.remove();
            }
            if (this.searchTimer !== undefined) {
                clearTimeout(this.searchTimer);
                this.searchTimer = undefined;
            }
            delete (/** @type {EnhancedTable} */ (this.table).__needstable);
        }
    }

    /* -------------------------------------------------------------------- entry */

    /**
     * Enhance one table. Calling it again on the same table returns the same instance.
     *
     * @param {HTMLTableElement} table
     * @param {Partial<NeedstableOptions>} [options]
     * @returns {NeedsTable}
     */
    function init(table, options) {
        const enhanced = /** @type {EnhancedTable} */ (table);
        const existing = enhanced.__needstable;
        if (existing) {
            return existing;
        }
        const instance = new NeedsTable(table, options);
        enhanced.__needstable = instance;
        return instance;
    }

    /**
     * Enhance every needtable under `root` (the document by default).
     *
     * @param {ParentNode} [root]
     * @param {Partial<NeedstableOptions>} [options]
     * @returns {NeedsTable[]}
     */
    function initAll(root, options) {
        const scope = root || document;
        const tables = scope.querySelectorAll("table." + HOOK_CLASS);
        return Array.from(tables).map((table) =>
            init(/** @type {HTMLTableElement} */ (table), options),
        );
    }

    const api = { init: init, initAll: initAll, version: NEEDSTABLE_VERSION };
    /** @type {Window & {needstable?: typeof api}} */ (window).needstable = api;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            initAll();
        });
    } else {
        initAll();
    }
})();
