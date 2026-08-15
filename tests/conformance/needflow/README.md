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
or README change; `cases` maps case filename → lowercase hex sha256 of the file bytes.
README.md is also checksummed under a `readme` key.

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

config:                                   # portable config, NEUTRAL keys (mapping below)
  direction: up
  legend: types
  link_labels: outgoing
  styles: { warn: { border: "#FF8800", border_width: 2 } }
  engine_config: {}                       # hatch registries; engine-keyed, opaque strings

options:                                  # directive options, portable names, string values
  direction: up
  filter: "True"

expect:
  legend:                                 # engine-INDEPENDENT (ruling D3: one out-of-diagram
    types: [Requirement]                  # implementation everywhere). Lists name EXACTLY the
    links: []                             # entries that must appear, in order (drawn-only rule).
                                          # Key absent => the case must render NO legend.
                                          # An empty list under a present key is a spec error.
  mermaid:                                # consumed by ubcode only
    source: |
      flowchart TB
      ...
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
- `expect.<engine>.source` is the full emitted diagram source for that engine, compared
  byte-exact AFTER normalisation (below). Upstream this is what `:debug:` exposes; in
  ubcode it is the string the mermaid emitter returns.
- `expect.legend` asserts the rendered out-of-diagram legend (which, by design, never
  appears in any `source`): the harness must verify the legend table contains exactly
  the named type rows and link-type rows, in order, and that a case WITHOUT the key
  renders no legend. The identical `source` values across legend cases are themselves
  contract (the legend must not leak into the diagram).
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
contract (exact rows in order when present; no legend rendered when absent) → verify the
manifest checksum of the case file. Cases with `skip` for an engine are skipped there
with the recorded reason. The runner must fail on: unknown top-level keys, unknown
portable option/config keys, tier-1 degradation entries, an empty list under a present
`expect.legend` key, and a case file whose checksum is absent from or different in the
manifest.

## Required initial cases (plan §7 + vocabulary coverage)

1. `baseline-defaults` — two needs, one link, no options: the no-warning fence per engine.
2. `node-id-injectivity` — ids `R-1` and `R=1` must stay two nodes with distinct edges.
3. `edge-empty-label` — a link type with an empty outgoing label under `link_labels`.
4. `percent-neutralisation` — `%%` and mermaid-significant text in titles stays literal.
5. `color-normalisation` — `#RRGGBB` and bare `RRGGBB` in a style class agree.
6. `direction-*` — one per value (down/up/right/left), incl. the plantuml tier-2 cases.
7. `legend-types`, `legend-links`, `legend-both` — drawn-types-only scope asserted via
   `expect.legend` (a configured-but-undrawn type must not appear in its lists).
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
