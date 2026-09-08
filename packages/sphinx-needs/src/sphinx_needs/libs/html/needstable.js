/*!
 * needstable.js -- in-place enhancement of a server-rendered needtable.
 *
 * Copyright (c) useblocks GmbH. MIT licence.
 *
 * sphinx-needs is the REPOSITORY OF RECORD for this file; ubCode vendors it
 * byte-identical behind a sha256 fence. Edits land here first. The markup this script
 * reads, the DOM it builds and the classes it uses are specified in
 * `packages/sphinx-needs/design/needstable-contract.md`; a change to that specification
 * bumps NEEDSTABLE_VERSION below.
 *
 * It never re-renders. Every `<tr>` and `<td>` the server wrote is the same node
 * afterwards, so `:style_row:` classes, the per-cell `needs_*` classes, the links inside
 * cells and the `<colgroup>` all survive sorting, filtering and paging. Rows that are not
 * on the current page are DETACHED rather than hidden -- as DataTables and every other
 * paging table already did -- which is what keeps a ten-thousand-row table usable.
 *
 * No dependencies, no network, no `innerHTML`, no `eval`. It runs from `file://` and
 * under `script-src 'self'` or a nonce.
 */

(function () {
    "use strict";

    /** The version of the markup + DOM contract this file implements. */
    var NEEDSTABLE_VERSION = "1";

    /** The class a `<table>` must carry to be enhanced. */
    var HOOK_CLASS = "NEEDS_DATATABLES";

    /** Where the instance is parked on the table element, for idempotent init. */
    var INSTANCE_KEY = "__needstable";

    /** English defaults; `data-needstable-labels` (a JSON object) overrides any of them. */
    var LABELS = {
        search: "Search",
        rowsPerPage: "Rows per page",
        all: "All",
        columns: "Columns",
        copy: "Copy",
        csv: "CSV",
        info: "Showing {start}–{end} of {total}",
        empty: "No matching rows",
        pagination: "Pagination",
        first: "First",
        previous: "Previous",
        next: "Next",
        last: "Last",
        sort: "{column}: sort",
    };

    var DEFAULTS = {
        pageSize: 10,
        pageSizes: [10, 25, 50, 0],
    };

    /* ----------------------------------------------------------------- helpers */

    function element(tag, className) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        return node;
    }

    /** An element's text, trimmed, with runs of whitespace collapsed to one space. */
    function cellText(node) {
        return (node.textContent || "").replace(/\s+/g, " ").trim();
    }

    /** The value a cell sorts and exports by: `data-sort` when given, else its text. */
    function cellValue(cell) {
        if (!cell) {
            return "";
        }
        var override = cell.getAttribute("data-sort");
        return override === null ? cellText(cell) : override.trim();
    }

    /**
     * Parse a number out of rendered text, without knowing the reader's locale.
     *
     * Whitespace (including non-breaking) and a per-cent sign are dropped. When both a
     * comma and a full stop are present the RIGHTMOST is the decimal mark and the other
     * groups digits; a lone comma groups digits only when the whole string looks like
     * `1,234,567`, and is a decimal mark otherwise.
     */
    function toNumber(text) {
        var value = String(text).replace(/[\s\u00a0\u202f%]/g, "");
        if (!value) {
            return NaN;
        }
        var comma = value.lastIndexOf(",");
        var dot = value.lastIndexOf(".");
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
        var number = Number(value);
        return Number.isFinite(number) ? number : NaN;
    }

    /** Parse a date out of rendered text: ISO 8601 first, then whatever the engine takes. */
    function toDate(text) {
        var value = String(text).trim();
        if (!value) {
            return NaN;
        }
        if (/^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?/.test(value)) {
            return Date.parse(value.length === 10 ? value + "T00:00:00Z" : value);
        }
        var parsed = Date.parse(value);
        return Number.isNaN(parsed) ? NaN : parsed;
    }

    var collator = new Intl.Collator(undefined, {
        numeric: true,
        sensitivity: "base",
    });

    function comparatorFor(type) {
        if (type === "number") {
            return function (left, right) {
                var a = toNumber(left);
                var b = toNumber(right);
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
            return function (left, right) {
                var a = toDate(left);
                var b = toDate(right);
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
        return function (left, right) {
            return collator.compare(left, right);
        };
    }

    /** Guess a column's type from up to 50 non-empty values. */
    function detectType(values) {
        var seen = 0;
        var numbers = 0;
        var dates = 0;
        for (var index = 0; index < values.length && seen < 50; index += 1) {
            var value = values[index];
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

    /** RFC 4180: quote a field that holds a comma, a quote or a line break. */
    function csvField(value) {
        return /[",\r\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
    }

    function template(text, values) {
        return text.replace(/\{(\w+)\}/g, function (whole, name) {
            return Object.prototype.hasOwnProperty.call(values, name)
                ? String(values[name])
                : whole;
        });
    }

    /** Read this table's `data-needstable-*` options. */
    function readOptions(table) {
        var options = {};
        var pageSize = table.getAttribute("data-needstable-page-size");
        if (pageSize !== null) {
            var parsed = parseInt(pageSize, 10);
            if (Number.isFinite(parsed) && parsed >= 0) {
                options.pageSize = parsed;
            }
        }
        var pageSizes = table.getAttribute("data-needstable-page-sizes");
        if (pageSizes !== null) {
            var sizes = [];
            pageSizes.split(",").forEach(function (entry) {
                var size = parseInt(entry, 10);
                if (Number.isFinite(size) && size >= 0 && sizes.indexOf(size) === -1) {
                    sizes.push(size);
                }
            });
            if (sizes.length) {
                options.pageSizes = sizes;
            }
        }
        var labels = table.getAttribute("data-needstable-labels");
        if (labels !== null) {
            try {
                var parsedLabels = JSON.parse(labels);
                if (parsedLabels && typeof parsedLabels === "object") {
                    options.labels = parsedLabels;
                }
            } catch (error) {
                /* a malformed label object leaves the English defaults in place */
            }
        }
        return options;
    }

    function assign(target) {
        for (var index = 1; index < arguments.length; index += 1) {
            var source = arguments[index];
            if (!source) {
                continue;
            }
            Object.keys(source).forEach(function (key) {
                target[key] = source[key];
            });
        }
        return target;
    }

    /* -------------------------------------------------------------- the instance */

    /**
     * @param {HTMLTableElement} table the server-rendered table, enhanced in place
     * @param {object} [options] overrides for the `data-needstable-*` options
     */
    function NeedsTable(table, options) {
        this.table = table;
        this.options = assign({}, DEFAULTS, readOptions(table), options || {});
        this.labels = assign({}, LABELS, this.options.labels || {});

        this.head = table.tHead;
        this.headers = this.head
            ? Array.prototype.slice.call(this.head.rows[this.head.rows.length - 1].cells)
            : [];
        this.body = table.tBodies[0];
        /** every body row, in the order the server wrote them -- never re-ordered */
        this.rows = this.body ? Array.prototype.slice.call(this.body.rows) : [];
        this.colgroup = table.querySelector("colgroup");
        this.cols = this.colgroup
            ? Array.prototype.slice.call(this.colgroup.children)
            : [];
        if (this.cols.length !== this.headers.length) {
            /* a colgroup that does not describe these columns is left alone */
            this.cols = [];
        }
        /* every CHILD NODE, not only the elements: the text nodes between them are part
           of the document the server wrote, and `destroy()` owes them back */
        this.bodyNodes = this.body
            ? Array.prototype.slice.call(this.body.childNodes)
            : [];
        this.colgroupNodes = this.colgroup
            ? Array.prototype.slice.call(this.colgroup.childNodes)
            : [];

        this.hiddenColumns = this.headers.map(function () {
            return false;
        });
        this.sortColumn = -1;
        /** 0 = unsorted (the server's `:sort:` order), 1 = ascending, -1 = descending */
        this.sortDirection = 0;
        this.query = "";
        this.pageSize = this.options.pageSize;
        this.page = 0;
        this.searchTimer = null;

        this.groups = this.buildGroups();
        this.types = this.detectTypes();
        this.view = this.groups.slice();

        this.buildControls();
        this.update();
    }

    /**
     * A need row and the part rows belonging to it are ONE unit: they sort together, and
     * a filter that matches any of their text keeps all of them.
     *
     * Rows are read in document order. Anything that is not `tr.need_part` starts a
     * group. A `tr.need_part` joins the group being built when its `data-parent` names
     * that group's need, or -- when it carries no `data-parent` -- because it follows it
     * (the adjacency fallback, for a producer that does not emit the attribute).
     * Otherwise it is a group of its own. Groups are therefore contiguous runs of the
     * source order, which is what lets the unsorted state restore that order exactly.
     */
    NeedsTable.prototype.buildGroups = function () {
        var groups = [];
        var current = null;
        this.rows.forEach(function (row) {
            var isPart = row.classList.contains("need_part");
            if (isPart && current) {
                var parent = row.getAttribute("data-parent");
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
        groups.forEach(function (group) {
            var text = group.rows
                .map(function (row) {
                    return cellText(row);
                })
                .join(" ");
            group.text = text.toLowerCase();
        });
        return groups;
    };

    NeedsTable.prototype.detectTypes = function () {
        var self = this;
        return this.headers.map(function (header, index) {
            var declared = header.getAttribute("data-type");
            if (declared) {
                return declared;
            }
            return detectType(
                self.groups.map(function (group) {
                    return cellValue(group.lead.cells[index]);
                }),
            );
        });
    };

    /* ------------------------------------------------------------------ the DOM */

    NeedsTable.prototype.buildControls = function () {
        var self = this;
        var table = this.table;

        this.wrapper = element("div", "needstable");
        table.parentNode.insertBefore(this.wrapper, table);
        this.controls = element("div", "needstable-controls");
        this.footer = element("div", "needstable-footer");
        this.wrapper.appendChild(this.controls);
        this.wrapper.appendChild(table);
        this.wrapper.appendChild(this.footer);

        /* search */
        var searchLabel = element("label", "needstable-search");
        var searchText = element("span", "needstable-label");
        searchText.textContent = this.labels.search;
        this.searchInput = element("input", "needstable-search-input");
        this.searchInput.type = "search";
        this.searchInput.placeholder = this.labels.search;
        this.searchInput.addEventListener("input", function () {
            if (self.searchTimer !== null) {
                clearTimeout(self.searchTimer);
            }
            self.searchTimer = setTimeout(function () {
                self.searchTimer = null;
                self.query = self.searchInput.value.trim().toLowerCase();
                self.page = 0;
                self.update();
            }, 100);
        });
        searchLabel.appendChild(searchText);
        searchLabel.appendChild(this.searchInput);
        this.controls.appendChild(searchLabel);

        /* page size */
        var sizeLabel = element("label", "needstable-page-size");
        var sizeText = element("span", "needstable-label");
        sizeText.textContent = this.labels.rowsPerPage;
        this.sizeSelect = element("select", "needstable-page-size-select");
        this.options.pageSizes.forEach(function (size) {
            var option = element("option");
            option.value = String(size);
            option.textContent = size === 0 ? self.labels.all : String(size);
            if (size === self.pageSize) {
                option.selected = true;
            }
            self.sizeSelect.appendChild(option);
        });
        this.sizeSelect.addEventListener("change", function () {
            self.pageSize = parseInt(self.sizeSelect.value, 10) || 0;
            self.page = 0;
            self.update();
        });
        sizeLabel.appendChild(sizeText);
        sizeLabel.appendChild(this.sizeSelect);
        this.controls.appendChild(sizeLabel);

        /* column visibility -- a native disclosure, so nothing has to manage a popover */
        this.columnsDetails = element("details", "needstable-columns");
        var summary = element("summary", "needstable-columns-summary");
        summary.textContent = this.labels.columns;
        this.columnsDetails.appendChild(summary);
        var list = element("div", "needstable-columns-list");
        this.headers.forEach(function (header, index) {
            var itemLabel = element("label", "needstable-columns-item");
            var checkbox = element("input");
            checkbox.type = "checkbox";
            checkbox.checked = true;
            checkbox.addEventListener("change", function () {
                self.hiddenColumns[index] = !checkbox.checked;
                self.applyColumnVisibility();
                self.update();
            });
            var name = element("span");
            name.textContent = cellText(header);
            itemLabel.appendChild(checkbox);
            itemLabel.appendChild(name);
            list.appendChild(itemLabel);
        });
        this.columnsDetails.appendChild(list);
        this.controls.appendChild(this.columnsDetails);

        /* export */
        this.copyButton = element("button", "needstable-button needstable-copy");
        this.copyButton.type = "button";
        this.copyButton.textContent = this.labels.copy;
        this.copyButton.addEventListener("click", function () {
            self.copy();
        });
        this.controls.appendChild(this.copyButton);

        this.csvButton = element("button", "needstable-button needstable-csv");
        this.csvButton.type = "button";
        this.csvButton.textContent = this.labels.csv;
        this.csvButton.addEventListener("click", function () {
            self.downloadCsv();
        });
        this.controls.appendChild(this.csvButton);

        /* sortable headers: the header's own content becomes the button's label */
        this.sortButtons = this.headers.map(function (header, index) {
            var host =
                header.children.length === 1 &&
                header.firstElementChild.tagName === "P"
                    ? header.firstElementChild
                    : header;
            var button = element("button", "needstable-sort");
            button.type = "button";
            var name = cellText(header);
            button.setAttribute(
                "aria-label",
                template(self.labels.sort, { column: name }),
            );
            while (host.firstChild) {
                button.appendChild(host.firstChild);
            }
            host.appendChild(button);
            header.setAttribute("aria-sort", "none");
            button.addEventListener("click", function () {
                self.toggleSort(index);
            });
            return button;
        });

        /* footer: the live region, then the pager */
        this.info = element("div", "needstable-info");
        this.info.setAttribute("aria-live", "polite");
        this.pager = element("nav", "needstable-pager");
        this.pager.setAttribute("aria-label", this.labels.pagination);
        this.footer.appendChild(this.info);
        this.footer.appendChild(this.pager);
    };

    /** Hide or show a column: the header, every cell, and the `<col>` that sizes it. */
    NeedsTable.prototype.applyColumnVisibility = function () {
        var hidden = this.hiddenColumns;
        this.headers.forEach(function (header, index) {
            header.classList.toggle("needstable-hidden", hidden[index]);
        });
        /* the rows on the page are synced by `paint()`; a detached row is synced when
           it is next painted, so there is nothing to walk here */
        if (this.cols.length) {
            var anyHidden = hidden.some(Boolean);
            var kept = anyHidden
                ? this.cols.filter(function (col, index) {
                      return !hidden[index];
                  })
                : this.colgroupNodes;
            this.colgroup.replaceChildren.apply(this.colgroup, kept);
        }
    };

    /* --------------------------------------------------------------- behaviours */

    /** none -> ascending -> descending -> none. */
    NeedsTable.prototype.toggleSort = function (index) {
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
    };

    NeedsTable.prototype.update = function () {
        var self = this;
        var query = this.query;
        this.view = query
            ? this.groups.filter(function (group) {
                  return group.text.indexOf(query) !== -1;
              })
            : this.groups.slice();

        if (this.sortDirection !== 0 && this.sortColumn >= 0) {
            var column = this.sortColumn;
            var direction = this.sortDirection;
            var compare = comparatorFor(this.types[column]);
            /* decorate-sort-undecorate keeps the sort stable and the comparator cheap */
            var decorated = this.view.map(function (group, position) {
                return {
                    group: group,
                    position: position,
                    value: cellValue(group.lead.cells[column]),
                };
            });
            decorated.sort(function (left, right) {
                if (left.value === "" || right.value === "") {
                    /* empty cells sort last whichever way the column is pointing */
                    if (left.value === right.value) {
                        return left.position - right.position;
                    }
                    return left.value === "" ? 1 : -1;
                }
                var order = compare(left.value, right.value);
                if (order !== 0) {
                    return direction * order;
                }
                return left.position - right.position;
            });
            this.view = decorated.map(function (entry) {
                return entry.group;
            });
        }

        this.headers.forEach(function (header, index) {
            var state = "none";
            if (index === self.sortColumn && self.sortDirection === 1) {
                state = "ascending";
            } else if (index === self.sortColumn && self.sortDirection === -1) {
                state = "descending";
            }
            header.setAttribute("aria-sort", state);
        });

        this.paint();
    };

    /** Attach only the current page's rows; the rest stay out of the document. */
    NeedsTable.prototype.paint = function () {
        var self = this;
        var groupCount = this.view.length;
        var size = this.pageSize || groupCount || 1;
        var pageCount = Math.max(1, Math.ceil(groupCount / size));
        if (this.page >= pageCount) {
            this.page = pageCount - 1;
        }
        var from = this.page * size;
        var to = Math.min(groupCount, from + size);

        var fragment = document.createDocumentFragment();
        var shownRows = 0;
        for (var index = from; index < to; index += 1) {
            this.view[index].rows.forEach(function (row) {
                for (var cell = 0; cell < row.cells.length; cell += 1) {
                    row.cells[cell].classList.toggle(
                        "needstable-hidden",
                        Boolean(self.hiddenColumns[cell]),
                    );
                }
                fragment.appendChild(row);
                shownRows += 1;
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
        return shownRows;
    };

    NeedsTable.prototype.paintPager = function (pageCount) {
        var self = this;
        this.pager.replaceChildren();
        /* one page needs no pager at all */
        this.pager.hidden = pageCount <= 1;
        if (pageCount <= 1) {
            return;
        }

        var makeButton = function (label, page, disabled, current, className) {
            var button = element("button", "needstable-page " + className);
            button.type = "button";
            button.textContent = label;
            button.disabled = Boolean(disabled);
            if (current) {
                button.setAttribute("aria-current", "page");
            }
            button.addEventListener("click", function () {
                self.page = page;
                self.paint();
            });
            return button;
        };
        var addEllipsis = function () {
            var span = element("span", "needstable-ellipsis");
            span.textContent = "…";
            self.pager.appendChild(span);
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
        var wanted = [0, pageCount - 1];
        for (var page = this.page - 1; page <= this.page + 1; page += 1) {
            if (page >= 0 && page < pageCount && wanted.indexOf(page) === -1) {
                wanted.push(page);
            }
        }
        wanted.sort(function (left, right) {
            return left - right;
        });
        var previous = -1;
        wanted.forEach(function (page) {
            if (previous >= 0 && page - previous > 1) {
                addEllipsis();
            }
            self.pager.appendChild(
                makeButton(
                    String(page + 1),
                    page,
                    false,
                    page === self.page,
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
    };

    /* ------------------------------------------------------------------ export */

    /** Header plus one line per row of every group the filter matches -- not per page. */
    NeedsTable.prototype.matrix = function () {
        var self = this;
        var keep = function (_value, index) {
            return !self.hiddenColumns[index];
        };
        var rows = [
            this.headers
                .filter(keep)
                .map(function (header) {
                    return cellText(header);
                }),
        ];
        this.view.forEach(function (group) {
            group.rows.forEach(function (row) {
                rows.push(
                    Array.prototype.slice
                        .call(row.cells)
                        .filter(keep)
                        .map(function (cell) {
                            return cellText(cell);
                        }),
                );
            });
        });
        return rows;
    };

    NeedsTable.prototype.tsv = function () {
        return this.matrix()
            .map(function (row) {
                return row.join("\t");
            })
            .join("\n");
    };

    /** RFC 4180: CRLF line endings, quoted fields, doubled embedded quotes. */
    NeedsTable.prototype.csv = function () {
        return this.matrix()
            .map(function (row) {
                return row.map(csvField).join(",");
            })
            .join("\r\n");
    };

    NeedsTable.prototype.copy = function () {
        var text = this.tsv();
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text);
                return;
            }
        } catch (error) {
            /* fall through to the pre-async-clipboard route below */
        }
        try {
            var area = element("textarea", "needstable-clipboard");
            area.value = text;
            area.setAttribute("aria-hidden", "true");
            document.body.appendChild(area);
            area.select();
            document.execCommand("copy");
            area.remove();
        } catch (error) {
            /* a browser that allows neither route silently copies nothing */
        }
    };

    NeedsTable.prototype.downloadCsv = function () {
        /* the BOM is what makes Excel open a UTF-8 CSV as UTF-8 */
        var blob = new Blob(["\ufeff" + this.csv()], {
            type: "text/csv;charset=utf-8",
        });
        var url = URL.createObjectURL(blob);
        var link = element("a", "needstable-download");
        link.href = url;
        link.download = (this.table.id || "needtable") + ".csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () {
            URL.revokeObjectURL(url);
        }, 0);
    };

    /* ----------------------------------------------------------------- teardown */

    /** Put the table back exactly as the server wrote it. */
    NeedsTable.prototype.destroy = function () {
        var self = this;

        this.hiddenColumns = this.hiddenColumns.map(function () {
            return false;
        });
        this.applyColumnVisibility();
        this.rows.forEach(function (row) {
            for (var index = 0; index < row.cells.length; index += 1) {
                row.cells[index].classList.remove("needstable-hidden");
            }
        });
        this.headers.forEach(function (header) {
            header.classList.remove("needstable-hidden");
            header.removeAttribute("aria-sort");
        });
        this.sortButtons.forEach(function (button) {
            var host = button.parentNode;
            while (button.firstChild) {
                host.insertBefore(button.firstChild, button);
            }
            button.remove();
        });
        if (this.body) {
            /* every node goes back, in the order the server wrote them */
            this.body.replaceChildren.apply(this.body, this.bodyNodes);
        }
        if (this.wrapper && this.wrapper.parentNode) {
            this.wrapper.parentNode.insertBefore(this.table, this.wrapper);
            this.wrapper.remove();
        }
        if (this.searchTimer !== null) {
            clearTimeout(this.searchTimer);
            this.searchTimer = null;
        }
        try {
            delete self.table[INSTANCE_KEY];
        } catch (error) {
            self.table[INSTANCE_KEY] = undefined;
        }
    };

    /* -------------------------------------------------------------------- entry */

    /**
     * Enhance one table. Calling it again on the same table returns the same instance.
     *
     * @param {HTMLTableElement} table
     * @param {object} [options]
     * @returns {NeedsTable}
     */
    function init(table, options) {
        if (table[INSTANCE_KEY]) {
            return table[INSTANCE_KEY];
        }
        var instance = new NeedsTable(table, options);
        table[INSTANCE_KEY] = instance;
        return instance;
    }

    /**
     * Enhance every needtable under `root` (the document by default).
     *
     * @param {ParentNode} [root]
     * @param {object} [options]
     * @returns {NeedsTable[]}
     */
    function initAll(root, options) {
        var scope = root || document;
        var tables = scope.querySelectorAll("table." + HOOK_CLASS);
        return Array.prototype.map.call(tables, function (table) {
            return init(table, options);
        });
    }

    window.needstable = {
        init: init,
        initAll: initAll,
        version: NEEDSTABLE_VERSION,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initAll();
        });
    } else {
        initAll();
    }
})();
