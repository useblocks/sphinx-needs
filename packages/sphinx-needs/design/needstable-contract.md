# The needstable contract

`needstable.js` and `needstable.css` turn a server-rendered needtable into an interactive
one — sortable, searchable, paged, with column visibility and two exports — **in place**,
without re-rendering a single cell. This file records why they exist and specifies exactly
what they read and build, so that any producer of needtable markup can emit against it.

sphinx-needs is not the only such producer: ubCode, useblocks' Rust-based tooling for needs
projects, renders needtables from the same sources and will ship this asset unchanged
against the same markup contract.

## 0. Decision record

**The problem, as measured.** Until 9.0.0 sphinx-needs vendored DataTables 1.10.16 and
loaded 2.26 MB of JavaScript plus jQuery on **every page of every project** — `search.html`
and `genindex.html` included (#462, open since 2022). The whole tree landed in one commit in
2018 and was never updated: 34 files, 4.72 MB, of which 25 files and 2.43 MB were
unreachable — a second copy of pdfmake, a Flash export shim — and no dependency ecosystem
could see any of it, because raw vendored JavaScript has no manifest for one to read.
About 228 of the ~250 lines of table CSS in the package were overrides of DataTables'
selectors, two of them carrying a `TODO this should not be part of the theme`. There was no
behavioural test of any of it.

**The decisive property: enhance the DOM, never re-render it.** A needtable's features live
in the markup. `:style_row:` is a class on the `<tr>`; each cell carries `needs_<key>`;
every id cell holds a real `<a href="#ID">`; `:colwidths:` becomes a `<colgroup>`. A library
whose data model is a `string[][]` of cell values destroys all four by construction — it
reads the cells, throws the rows away and builds new ones. That is not a bug in any
particular loader; it is what "re-render from data" means.

**The alternatives, one measured line each.**

- **Grid.js** (what #1464 proposed): reads `td.innerHTML` into a `string[][]`, hides the
  source table, and offers one class string for *all* rows — so `:style_row:` cannot
  survive it. No release since 2024-03.
- **DataTables 3**: jQuery-free since 2026-07, in-place, MIT, ~67 KB gzipped — the honest
  fallback. Not chosen: it brings its own control DOM and CSS with fourteen `!important`
  rules that every host theme must fight, it is a six-week-old major from a one-person
  project, and any third-party bundle needs a build toolchain and a manifest in this
  repository that the hand-written file does not.
- **simple-datatables**: in-place and elegant, but LGPL-3.0 — a licence question for a
  minified asset inside an MIT wheel.
- **Tabulator**: deletes the `<table>` element outright and renders need links as escaped
  text.
- **List.js**: in-place, but unreleased since 2021 and it needs producer-side markup of its
  own.
- **tablesort / sortable-tablesort**: tiny and fine, but sorting only — no search, no
  paging, no column visibility.
- **TanStack Table**: headless, so the renderer still has to be written — roll-our-own plus
  a dependency.

**Why one hand-written file.** More than one producer renders needtables from the same
sources, and the same asset has to work in all of them without a bundler, a lockfile or a
supply chain. Being ours, it can be *small* (10 KB gzipped against 968 KB), it emits
controls with our own class names so each host styles them against its own tokens instead
of fighting a library's chrome, and it can do the two things no general table library will:
keep a need's part rows travelling with it, and treat the server's `:sort:` order as the
state the table returns to. The cost, stated plainly: we own a table widget, and its
accessibility and cross-theme tail, for good.

**What was given up, and the vendoring rule.** Excel and PDF export are gone; the CSV
download opens in Excel and browsers print. Column reordering is gone (it was on,
undocumented, and no issue ever mentioned it). A sticky header is not here: the horizontal
scroll container the table needs defeats a viewport-sticky header. sphinx-needs is the
**repository of record**; a consumer vendors the file byte-identical, records its sha256
and `NEEDSTABLE_VERSION`, and edits land here first. An npm package is worth making only if
a third consumer appears. `data-needstable-*` is the extension point for per-table
configuration (#408, #1425).

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

- **`NEEDS_DATATABLES` is the selector**: the class sphinx-needs has emitted since 2018 and
  the one users style against, so it stays although nothing called DataTables is involved
  any more. A table without it is not enhanced — which is what `:style: table`
  (`<table class="NEEDS_TABLE">`) means, and such a table carries none of the options.
- `data-needstable-page-size` — rows per page, `0` for all. Optional; default `10`.
- `data-needstable-page-sizes` — the list offered in the page-size control, `0` = "All".
  Optional; default `10,25,50,0`. The script adds the page size in use to the list when a
  producer names one that is not in it, so that the control can always show it.
- `data-needstable-labels` — a JSON object overriding any of the script's English labels.
  Optional. **The producer localises**; the script ships no catalogues.
- Unknown `data-needstable-*` attributes are ignored: this is the extension point for
  per-table configuration. A new knob is a new attribute here, not a new shape of
  configuration dictionary.
- `data-col` is the **column key** — the option name as the author wrote it (`id`, `title`,
  `outgoing`, a custom field). The visible header text is a display string and may be
  anything; `needs_col_<key>` is a styling hook.
- `data-type` is `text`, `number` or `date`, and is **omitted unless the producer knows**:
  sphinx-needs emits it for a field whose schema is `integer` or `number` and for nothing
  else. The script detects the rest from the first fifty non-empty values.
- `need` / `need_part` say what kind of row it is; `:style_row:` adds its class beside them,
  as it always has. `data-parent` appears on a part row only.
- docutils' `row-odd` / `row-even` may stay, but they are stale the moment a sort reorders
  anything and **nothing may depend on them**.
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
`DOMContentLoaded`, or at once when the document is already parsed. The producer should
emit the tag with `defer`, which makes the second branch the one taken.

> *Corrected 2026-09-08.* This paragraph used to claim that sphinx-needs already emitted a
> deferred tag. Review measured otherwise: the per-page registration went through the
> builder's `add_js_file`, which writes every keyword into the tag verbatim, so the page
> carried an invalid `loading_method="defer"` attribute and a render-blocking script. The
> extension now passes `defer="defer"`, and two tests assert the attribute.

**Groups.** A `tr.need` and the `tr.need_part` rows that follow it are ONE unit. Rows are
read in document order; anything that is not `tr.need_part` starts a group; a
`tr.need_part` joins the group being built when its `data-parent` names that group's need,
or — carrying no `data-parent` — because it follows it (the adjacency fallback). Groups are
therefore contiguous runs of the source order, which is what lets the unsorted state restore
that order exactly. Sorting orders **groups** by the lead row's cell; filtering keeps a
group when the lead row **or any part row** matches; paging counts groups.

**Sorting.** Click, Enter or Space on a header's button cycles `none → ascending →
descending → none`. There is **no sort at initialisation**: the DOM order is the producer's
`:sort:` order, it is the "none" state, and "none" restores it exactly. Comparators are
typed — `number` (locale-agnostic, tolerating `%` and grouped digits), `date` (ISO 8601
first, then `Date.parse`), `text` (`Intl.Collator`, `numeric: true`, `sensitivity: "base"`).
Empty cells sort last in both directions; `<td data-sort="…">` overrides a cell's value. The
`<th>` carries `aria-sort`; the button's accessible name is `"<Header>: sort"`.

**Filtering.** One text input per table, case-insensitive substring over the group's whole
rendered text — **all** columns, including ones the reader switched off, because the data is
still the data. Debounced. An `aria-live="polite"` element reports `Showing 1–10 of 42` or
`No matching rows`.

**Paging — page-only DOM.** Changing the page rebuilds the pager, so the control the reader
just activated is removed from the document; focus is given back to the equivalent control
(the same page number if it is still offered, else the nearest; a prev/next that has become
disabled hands focus to the other one). Only the current page's rows are attached; the rest
are held in memory, in order. Every comparable widget already did this, so find-in-page and `#id`
anchors behave no worse than before, and a ten-thousand-row table initialises in tens of
milliseconds rather than seconds. The pager is **hidden entirely** when there is one page.
Sorting or changing the filter resets to page one.

**Column visibility.** A native `<details><summary>` with one checkbox per column. Hiding a
column adds `needstable-hidden` to that column's `<th>` and cells and removes its `<col>`
from the `<colgroup>`, so the remaining widths stay aligned.

**Copy and CSV.** Two buttons, over the header plus **every group the filter matches** — not
only the page — and every row of those groups, so part rows export their own text. A cell's
value is its `textContent`, trimmed, whitespace collapsed. *Copy* writes tab-separated text
through `navigator.clipboard`, falling back to `execCommand("copy")`. *CSV* is RFC 4180
(fields holding `,`, `"`, CR or LF quoted, embedded quotes doubled) with CRLF endings and a
UTF-8 BOM so a spreadsheet opens it correctly, handed over as a `Blob` through an
`<a download>`, which needs no server.

**Requirements the asset holds itself to**, so that any documentation builder or restrictive
host can embed it unchanged: a classic script (no ES modules, no dynamic imports, no
workers), no network access, no `eval` and no `innerHTML`, no dependencies, and CSP-clean
under a strict `script-src`. It must never re-render a cell or name an absolute URL.

## 3. The DOM the script builds, and the CSS contract

```text
div.needstable
├── div.needstable-controls   (search, page size, columns, copy, csv)
├── div.needstable-scroll     (overflow-x: auto -- the horizontal scroll frame)
│   └── table                 (the producer's table, moved, never rebuilt)
└── div.needstable-footer     (div.needstable-info[aria-live], nav.needstable-pager)
```

The scroll frame is a box of the widget's own, and the table inside it keeps
`display: table; width: 100%`.

> *Corrected 2026-09-08.* An earlier draft made the `<table>` itself the scroll container
> (`div.needstable > table { display: block; overflow-x: auto }`) and said so here. Review
> measured that wrong twice over: a `display: block` table re-wraps its rows in an anonymous
> table box that shrink-to-fits, so a table narrower than its column rendered up to 22 %
> narrower still (555 px in a 708 px column) and `:colwidths:` percentages resolved against
> the shrunken width; and in a host whose own script wraps every `<table>` in a `<div>`, the
> child combinator stopped matching at all, so the rule was dead code exactly where scrolling
> mattered. An inner box the host does not know about has neither problem.

Every generated element carries a `needstable-*` class and nothing else, and no inline
styles. The header's own content is wrapped in `button.needstable-sort` — inside the `<th>`'s
`<p>` when there is one, so the markup stays valid; `destroy()` unwraps it.

`needstable.css` is the **structural** sheet and ships beside the script: the two bars, the
pager, the sort glyphs, the hidden column, the focus ring. It is **host-agnostic** — it names
no theme and no host token, and colour reaches it only through custom properties with
self-effacing fallbacks: `--needstable-label-color` (`inherit`), `--needstable-border-color`
and `--needstable-focus-color` (`currentColor`), `--needstable-hover-bg` and
`--needstable-current-bg` (a neutral translucent grey), `--needstable-popover-bg` /
`--needstable-popover-color` (`Canvas` / `CanvasText`). A host maps its own tokens onto them
in its own sheet; sphinx-needs does that in `src/sphinx_needs/css/common/needstable.css`,
against `--sn-color-table-*`. The sort indicators are drawn with CSS borders inheriting
`currentColor`, never a Unicode arrow or an image, so they cannot come out as a different
character on a different operating system. The chrome is deliberately quiet: no border
around the widget, small buttons, little rounding — the table's data is the content.

## 4. Type-checking the script

The script is plain ES2020 JavaScript — one artefact, no build step, readable in the tree
and in `view-source`, and vendored verbatim. It is nevertheless fully typed, through
`// @ts-check` and JSDoc, and the types are checked with one command and no `package.json`:

```console
$ npx -y -p typescript tsc --allowJs --checkJs --noEmit --strict --target es2020 \
      --lib dom,es2020 packages/sphinx-needs/src/sphinx_needs/libs/html/needstable.js
$ echo $?
0
```

It is not a CI gate here — this package's CI has no node — so run it by hand after editing
the file. A consumer with a JavaScript toolchain can run the same check on its vendored copy.

Why not TypeScript source: it would need a node toolchain, committed compiled output and a
re-compile fence in a Python repository — exactly the machinery rolling our own avoided —
and the compiled file, not the source, would be what reviewers read. Revisit if the asset
ever grows into several modules.

## 5. Not in version 1

Recorded so nobody has to re-derive that they were considered: Excel and PDF export (CSV
opens in Excel; browsers print), column reordering, a sticky header (the horizontal scroll
container defeats viewport-sticky), responsive column collapse, multi-column sort, URL
state, translation catalogues inside the script (the producer localises through
`data-needstable-labels`), configurable hidden columns or an initial sort, and virtualised
scrolling.
