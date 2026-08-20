# needflow conformance corpus — format spec v1

Orchestrator-authored spec implementing plan §7 (`/home/user/ubcode/planning/needflow-portable-options.md`).
This document ships INSIDE the corpus as `conformance/needflow/README.md`, so it travels with both copies.
Consumers: S3 builder (sphinx-needs copy + pytest harness), U1b builder (ubcode copy + Rust harness + sync check).

## Purpose and mechanism

The corpus is the only structural mitigation for dual-implementation drift of the portable
needflow vocabulary. It is a set of language-neutral fixture cases, each mapping
`(needs data, portable config, directive options)` to the expected emitted diagram source
per engine plus the expected degradations. The corpus is **duplicated verbatim into both
repos** with a shared manifest stamp:

- **Repo of record: ubcode** (`useblocks/ubcode`). All edits land there first; the
  sphinx-needs copy is a verbatim re-sync. The sync check script lives in ubcode.
- Each repo's harness independently verifies `sha256(case file) == manifest entry` for its
  own copy, so any local edit that skips the manifest is a red test in that repo.
- Drift between repos becomes visible at re-sync time (differing `corpus_version` or
  checksums). Honest limitation (per plan): no cross-repo CI guard exists; the manifest
  makes drift visible, not impossible.

## Directory layout (identical in both repos)

```
conformance/needflow/
  README.md            # this spec, verbatim
  manifest.json        # {"corpus_version": <int>, "cases": {"<file>": "<sha256>"}}
  cases/
    <case-id>.yaml
```

Repo anchoring (each slice wires its own): sphinx-needs under `tests/conformance/needflow/`;
ubcode under the crate that owns the mermaid emitter, e.g.
`rust/ubc_parser_ctrl/tests/conformance/needflow/` (U1b builder decides the exact test-crate
path; the layout below `conformance/needflow/` is fixed).

`manifest.json`: `corpus_version` is a monotonically increasing integer, bumped on ANY case
or README change; `cases` maps case filename → lowercase hex sha256 of the file CONTENT.
README.md is also checksummed under a `readme` key.

**Checksums are over LINE-ENDING-NORMALISED bytes**: replace CRLF and lone CR with LF
before hashing. The manifest stamps content, not transport encoding — a corpus checked out
on Windows (git's `text=auto` rewrites LF to CRLF) must produce the same checksum as the
same corpus on Linux, in either repo. Each repo SHOULD additionally pin the corpus to LF in
`.gitattributes` (`<corpus path>/** text eol=lf`) so the working-tree bytes stay canonical
and a re-sync between the two repos cannot carry a platform's line endings across; the
normalisation in the hash is what makes the contract hold even when that pin is missing.

## Case file schema (YAML)

One case per file; filename is `<id>.yaml`. Top-level keys:

```yaml
id: direction-up-degrades-on-plantuml     # == filename stem; stable slug
title: ":direction: up degrades to down on plantuml with a warn-once"
purpose: >                                # WHY the case exists (testing-philosophy rule)
  Tier-2 degradation: plantuml has no bottom-up primitive; the axis-mate
  fallback must fire exactly one warning per project.

needs:                                    # minimal neutral need records
  - id: REQ_1
    type: req                             # must exist in `types`
    title: Requirement one
    status: open                          # optional
    tags: [a, b]                          # optional
    links: { links: [REQ_2] }             # map: link-type name -> list of target ids
  - id: REQ_2
    type: req
    title: Requirement two

types:                                    # portable needs_types subset; omit for defaults
  - directive: req
    title: Requirement
    prefix: "R_"
    color: "#BFD8D2"                      # optional
    shape: rectangle                      # optional; portable enum only

links:                                    # portable needs_links subset; omit for default `links`
  - option: links
    incoming: "is linked by"
    outgoing: "links to"
    line: dashed                          # optional; portable enum
    arrow: open                           # optional; portable enum
    color: "#00AA00"                      # optional

legends:                                  # named legend configs (the mapping a case may pin)
  compact:
    parts: [types]                          # LIST of sections, in RENDER ORDER (types, links).
                                            # A list only — a bare string is a spec error.
    placement: external                      # preference: internal where the engine can, else
                                            # external. UNSET takes the ENGINE's default placement
                                            # (internal on plantuml/graphviz, external on mermaid).

config:                                   # portable config, NEUTRAL keys (mapping below)
  direction: up
  show_legend: compact                    # names an entry in `legends`; unset => engine default
  link_labels: outgoing
  styles: { warn: { border: "#FF8800", border_width: 2 } }
  engine_config: {}                       # hatch registries; engine-keyed, opaque strings

options:                                  # directive options, portable names, string values
  direction: up
  show_legend: compact                    # a KEY into `legends` (never an inline value)
  filter: "True"

expect:
  mermaid:                                # consumed by ubcode only
    source: |
      flowchart TB
      ...
    legend:                               # the EXTERNAL (out-of-diagram) legend, per engine.
      types: [Requirement]                # Lists name EXACTLY the entries that must appear, in
                                          # order (drawn-only rule). Omit a section that must not
                                          # render (here: links). Key absent for an engine =>
                                          # that engine must render NO external legend.
                                          # A present-but-empty section is a spec error.
  plantuml:                               # consumed by sphinx-needs only
    source: |
      @startuml
      ...
      @enduml
    degradations:
      - id: direction-vertical-unsupported
        tier: 2
        once: true
  graphviz:
    source: |
      digraph needflow {
      ...
      }
  # an engine key may instead be: `skip: "<reason>"` when a case is inapplicable there
```

Rules:

- `config`/`options` use ONLY the portable vocabulary (plan §3) with neutral spellings —
  never `needs_flow_*` conf.py names, never legacy/deprecated spellings, never
  engine-specific blobs outside `engine_config`. Legacy-alias behaviour is each repo's own
  unit-test business, not corpus business.
- Every case must state `purpose`.
- An omitted `types:` means the CORPUS default — a single `req` / `Requirement` / `R_`
  type — never the repository's own built-in types, which differ between the two tools
  and would make the copies structurally unable to agree.
- `expect.<engine>.source` is the full emitted diagram source for that engine, compared
  byte-exact AFTER normalisation (below). Upstream this is what `:debug:` exposes; in
  ubcode it is the string the mermaid emitter returns.
- **Two kinds of legend, asserted in two places.** An INTERNAL legend is drawn inside the
  diagram, so it is already asserted byte-exactly by that engine's `source` — it needs no
  key of its own, and adding one would duplicate the contract. An EXTERNAL legend is
  out-of-diagram document content, so it is asserted by `expect.<engine>.legend`: exactly
  the named type rows and link-type rows, in order; key absent for an engine means that
  engine must render no external legend.
- `legend` is per-engine, NOT shared, because the default legend is engine-specific
  (an engine that can draw a good internal legend does; one that cannot renders the
  external table). Where a case pins an explicit legend config the expectations will
  usually be identical across engines — write them out per engine anyway. This mirrors
  how `source` is already handled, and it avoids any merge or precedence rule: a reader
  sees exactly what each engine must produce without resolving an override in their head.
  (This supersedes an earlier revision of this spec in which `legend` was a single shared
  top-level key. That assumed one out-of-diagram implementation everywhere, which the
  engine-specific default deliberately breaks.)
- `degradations` lists the degradation events the harness must observe for that engine:
  neutral `id` (registry below), `tier` (1–3; tier 1 is silent so it never appears here —
  listing a tier-1 entry is a spec error), `once: true` for warn-once-per-project.
  Absent list = the case must produce NO warnings on that engine (the fence).

## Normalisation (each harness applies to both sides before comparing)

1. Node hyperlink URLs are repo-specific: replace the harness's own computed URL for a
   need with the token `<NODE_URL:need_id>` (upstream: the `[[...]]`/`URL=` values;
   ubcode: the `click ... href "..."` target).
2. Trailing whitespace stripped per line; exactly one trailing newline.
3. Nothing else — indentation, ordering, and quoting are contract.

## Degradation-id registry (neutral → per-repo mapping)

The corpus uses neutral ids; each harness owns a small mapping table to its native
warning subtype / diagnostic code. Initial registry (extend as cases need; extending the
registry bumps `corpus_version`):

| id | meaning |
|---|---|
| `direction-vertical-unsupported` | engine cannot draw `up` (falls back `down`) |
| `direction-horizontal-unsupported` | engine cannot draw `left` (falls back `right`) |
| `shape-unmapped` | portable shape has no engine mapping (falls back default) |
| `arrow-unsupported` | arrow beyond the engine's set (falls back `normal`) |
| `style-class-unknown` | `:styles:` names a class not in config (rule skipped) |
| `option-conflict-direction` | `:direction:` disagrees with an `engine_config`-derived direction |

sphinx-needs mapping: sphinx-needs warning subtypes (e.g. `needs.diagram_*` — S3 builder
fixes the exact names and documents the table in its harness).
ubcode mapping: `needs.option_*` diagnostic codes (U1b builder likewise).

## Harness contract (what each repo's runner must do)

For every case file: load → build a minimal project from `needs`/`types`/`links`/`config`
(portable keys mapped to the repo's config surface) → run the needflow directive with
`options` → capture emitted source per applicable engine + emitted warnings →
normalise → assert source equality, the exact degradation set, and the `expect.legend`
contract for that engine (exact rows in order when present; no external legend rendered
when absent) → verify the manifest checksum of the case file (over line-ending-normalised
bytes, as defined above). Cases with `skip` for an engine are skipped there
with the recorded reason. The runner must fail on: unknown top-level keys, unknown
portable option/config keys, tier-1 degradation entries, an empty list under a present
`expect.<engine>.legend` section, and a case file whose checksum is absent from or
different in the manifest.

## Required initial cases (plan §7 + vocabulary coverage)

1. `baseline-defaults` — two needs, one link, no options: the no-warning fence per engine.
2. `node-id-injectivity` — ids `R-1` and `R=1` must stay two nodes with distinct edges.
3. `edge-empty-label` — a link type with an empty outgoing label under `link_labels`.
4. `percent-neutralisation` — `%%` and mermaid-significant text in titles stays literal.
5. `color-normalisation` — `#RRGGBB` and bare `RRGGBB` in a style class agree.
6. `direction-*` — one per value (down/up/right/left), incl. the plantuml tier-2 cases.
7. `legend-types`, `legend-links`, `legend-both` — each pinning an explicit legend config
   key so every engine renders the same external legend; drawn-types-only scope asserted via
   `expect.<engine>.legend` (a configured-but-undrawn type must not appear in its lists).
   Plus `legend-engine-default` — no key named, exercising the deliberate engine-specific
   default: an engine that draws an internal legend has it in `source` and NO `legend` key;
   an engine that cannot has a `legend` key and no legend in its `source`.
8. `link-labels-*` — none/outgoing/incoming/type.
9. `styles-cascade` — two matching rules, later wins per property; plus built-in
   `highlight` byte-parity case.
10. `link-line-arrow-color` — one link type exercising line/arrow/color together.
11. `shape-enum-sample` — 2–3 portable shapes incl. one `shape-unmapped` degradation.
12. One case per remaining degradation-registry id not covered above.

## Versioning discipline

Any change (case, README, registry) → bump `corpus_version`, recompute checksums, land in
ubcode first, re-sync to sphinx-needs in the paired PR. The two copies must be
byte-identical below `conformance/needflow/`.
