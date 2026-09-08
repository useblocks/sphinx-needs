# The needstable contract

`needstable.js` and `needstable.css` turn a server-rendered needtable into an interactive
one — sortable, searchable, paged, with column visibility and two exports — **in place**,
without re-rendering a single cell. This file is the specification they implement and the
producers emit against.

**Two consumers, one asset.** Sphinx-Needs (`src/sphinx_needs/libs/html/`) and ubCode
(`ubc build html` and the VS Code preview) both render needtables. Sphinx-Needs is the
**repository of record**: the pair is authored here, and ubCode vendors it byte-identical
behind a sha256 fence, as the two repositories already share the needflow and
variant-condition conformance corpora. Edits land here first. `NEEDSTABLE_VERSION` in the
script is the version of *this document*; a change to anything below bumps it.

## 1. The markup a producer emits

```html
<table class="NEEDS_DATATABLES …" id="…-table_node"
       data-needstable-page-size="10" data-needstable-page-sizes="10,25,50,0">
  <colgroup>…</colgroup>
  <thead><tr>
    <th scope="col" class="head needs_col_status" data-col="status" data-type="text">…
  </tr></thead>
  <tbody>
    <tr class="need needs_open"      data-need-id="R_01">
      <td class="needs_id"><p><a href="#R_01">R_01</a></p></td>…
    <tr class="need_part needs_open" data-need-id="R_01.P1" data-parent="R_01">…
  </tbody>
</table>
<p><em>Used filter: …</em></p>
```

- **`NEEDS_DATATABLES` is the selector**: the class Sphinx-Needs has emitted since 2018
  and the one users style against, so it stays although nothing called DataTables is
  involved any more. A table without it is not enhanced — which is what `:style: table`
  (`<table class="NEEDS_TABLE">`) means, and such a table carries none of the options.
- `data-needstable-page-size` — rows per page, `0` for all. Optional; default `10`.
- `data-needstable-page-sizes` — the list offered in the page-size control, `0` = "All".
  Optional; default `10,25,50,0`.
- `data-needstable-labels` — a JSON object overriding any of the script's English labels.
  Optional. **The producer localises**; the script ships no catalogues.
- Unknown `data-needstable-*` attributes are ignored: this is the extension point for
  per-table configuration (sphinx-needs#408, #1425). A new knob is a new attribute here,
  not a new shape of configuration dictionary.
- `data-col` is the **column key** — the option name as the author wrote it (`id`,
  `title`, `outgoing`, a custom field). The visible header text is a display string and
  may be anything; `needs_col_<key>` is a styling hook.
- `data-type` is `text`, `number` or `date`, and is **omitted unless the producer knows**:
  Sphinx-Needs emits it for a field whose schema is `integer` or `number` and for nothing
  else. The script detects the rest from the first fifty non-empty values.
- `need` / `need_part` say what kind of row it is; `:style_row:` adds its class beside
  them, as it always has. `data-parent` appears on a part row only.
- docutils' `row-odd` / `row-even` may stay, but they are stale the moment a sort
  reorders anything and **nothing may depend on them**.
- Cells, their `needs_<key>` classes, the links inside them and the `<colgroup>` are
  untouched. That is the whole point of enhancing in place.
- The `:show_filters:` paragraph goes **after** `</table>`: a `<p>` between `</tbody>` and
  `</table>` is invalid HTML that browsers hoist out again. Order is table, filter
  paragraph, max-items notice. The table `id` is used as the CSV file name.

## 2. The script

`window.needstable` exposes `init(table, options)` (idempotent — a second call returns the
same instance), `initAll(root, options)` over `table.NEEDS_DATATABLES`, and `version`. An
instance exposes `destroy()`, which puts the table back exactly as the producer wrote it:
wrapper and controls removed, every detached row re-attached in the original order, the
`<th>` contents unwrapped, `aria-sort` gone, hidden columns shown. It self-initialises on
`DOMContentLoaded`, or at once when the document is already parsed — which is the case for
the deferred script tag Sphinx-Needs emits.

**Groups.** A `tr.need` and the `tr.need_part` rows that follow it are ONE unit. Rows are
read in document order; anything that is not `tr.need_part` starts a group; a
`tr.need_part` joins the group being built when its `data-parent` names that group's need,
or — carrying no `data-parent` — because it follows it (the adjacency fallback). Groups
are therefore contiguous runs of the source order, which is what lets the unsorted state
restore that order exactly. Sorting orders **groups** by the lead row's cell; filtering
keeps a group when the lead row **or any part row** matches; paging counts groups.

**Sorting.** Click, Enter or Space on a header's button cycles `none → ascending →
descending → none`. There is **no sort at initialisation**: the DOM order is the
producer's `:sort:` order, it is the "none" state, and "none" restores it exactly.
Comparators are typed — `number` (locale-agnostic, tolerating `%` and grouped digits),
`date` (ISO 8601 first, then `Date.parse`), `text` (`Intl.Collator`, `numeric: true`,
`sensitivity: "base"`). Empty cells sort last in both directions; `<td data-sort="…">`
overrides a cell's value. The `<th>` carries `aria-sort`; the button's accessible name is
`"<Header>: sort"`.

**Filtering.** One text input per table, case-insensitive substring over the group's whole
rendered text — **all** columns, including ones the reader switched off, because the data
is still the data. Debounced. An `aria-live="polite"` element reports `Showing 1–10 of 42`
or `No matching rows`.

**Paging — page-only DOM.** Only the current page's rows are attached; the rest are held
in memory, in order. DataTables and every comparable widget already did this, so
find-in-page and `#id` anchors behave no worse than before, and a ten-thousand-row table
initialises in tens of milliseconds rather than seconds. The pager is **hidden entirely**
when there is one page. Sorting or changing the filter resets to page one.

**Column visibility.** A native `<details><summary>` with one checkbox per column. Hiding
a column adds `needstable-hidden` to that column's `<th>` and cells and removes its
`<col>` from the `<colgroup>`, so the remaining widths stay aligned.

**Copy and CSV.** Two buttons, over the header plus **every group the filter matches** —
not only the page — and every row of those groups, so part rows export their own text. A
cell's value is its `textContent`, trimmed, whitespace collapsed. *Copy* writes
tab-separated text through `navigator.clipboard`, falling back to `execCommand("copy")`.
*CSV* is RFC 4180 (fields holding `,`, `"`, CR or LF quoted, embedded quotes doubled) with
CRLF endings and a UTF-8 BOM so Excel opens it correctly, handed over as a `Blob` through
an `<a download>`, which works from `file://`.

**Never:** re-render a cell, use `innerHTML` / `insertAdjacentHTML` / `eval` /
`new Function`, fetch anything, load a module or a worker, name an absolute URL, or depend
on a library. It has to run from `file://`, under `script-src 'self'`, and under a nonce
CSP with no `unsafe-eval`.

## 3. The DOM the script builds, and the CSS contract

```
div.needstable
├── div.needstable-controls   (search, page size, columns, copy, csv)
├── table                     (the producer's table, moved, never rebuilt)
└── div.needstable-footer     (div.needstable-info[aria-live], nav.needstable-pager)
```

Every generated element carries a `needstable-*` class and nothing else, and no inline
styles. The header's own content is wrapped in `button.needstable-sort` — inside the
`<th>`'s `<p>` when there is one, so the markup stays valid; `destroy()` unwraps it.

`needstable.css` is the **structural** sheet and ships beside the script: the two bars, the
pager, the sort glyphs, the hidden column, the focus ring. It is **host-agnostic** — it
names no theme and no host token, and colour reaches it only through custom properties
with self-effacing fallbacks: `--needstable-label-color` (`inherit`),
`--needstable-border-color` and `--needstable-focus-color` (`currentColor`),
`--needstable-hover-bg` and `--needstable-current-bg` (a neutral translucent grey),
`--needstable-popover-bg` / `--needstable-popover-color` (`Canvas` / `CanvasText`). A host
maps its own tokens onto them in its own sheet; Sphinx-Needs does that in
`src/sphinx_needs/css/common/needstable.css`, against `--sn-color-table-*`. The sort
indicators are drawn with CSS borders inheriting `currentColor`, never a Unicode arrow or
an image, so they cannot come out as a different character on a different operating
system. The chrome is deliberately quiet: no border around the widget, small buttons,
little rounding — the table's data is the content.

## 4. Not in version 1

Recorded so nobody has to re-derive that they were considered: Excel and PDF export (CSV
opens in Excel; browsers print), column reordering, a sticky header (an
`overflow-x: auto` wrapper defeats viewport-sticky), responsive column collapse,
multi-column sort, URL state, translation catalogues inside the script (the producer
localises through `data-needstable-labels`), configurable hidden columns or an initial
sort, and virtualised scrolling.
