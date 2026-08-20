# Declarative extraction-test fixtures

Marker extraction (comment → one-line need / need-id-reference / marked-rst) is
tested declaratively: each case is a **fixture** (the input) plus a **snapshot**
(the captured expected output). This keeps the inputs language-agnostic and the
expected output reviewable, and lets us cover the whole language matrix without a
bespoke test function per case.

## Fixture format

Each `*.yaml` file in this directory is a map of `case_name → case`:

```yaml
default_oneliner_cpp:
  lang: cpp                 # cpp | c | python | csharp | rust | yaml | go | jsonc | bash
  config: default          # "default", or an inline config block (see below)
  source: |
    // @My Title, IMPL_1, impl, [REQ_1]
    void f() {}

custom_brackets_c:
  lang: c
  config:
    start_sequence: "[["
    end_sequence: "]]"
    field_split_char: ","
    needs_fields:
      - {name: title, type: str}
      - {name: id, type: str}
      - {name: type, type: str, default: impl}
      - {name: links, type: "list[str]", default: []}
    need_id_markers: ["@need-ids:"]   # optional; default ["@need-ids:"]
  source: |
    /* [[A Title, ID_1, impl, [REQ_1]]] */
```

- `config: default` uses the built-in `OneLineCommentStyle` default
  (`@` / newline / `,` with fields `title, id, type(default "impl"), links(list)`).
- Field `type` is `str` or `list[str]`.
- `extract` (optional): which extractors to run — a subset of
  `[oneline, need_refs, rst]` (default: all three). Narrow it to keep a case
  focused: a need-reference case sets `extract: [need_refs]` so the `@`-prefixed
  `@need-ids:` marker isn't also parsed as a one-line need.
- `engine` (optional): `treesitter` (default) sees every comment; `libclang`
  evaluates the preprocessor and excludes markers in inactive `#if`/`#ifdef`
  branches. libclang cases are skipped when the `clang` bindings are unavailable.
- `defines` (optional, libclang only): preprocessor defines, e.g.
  `["VARIANT_A=1", "PROTOCOL_VERSION=3"]`.

## Snapshot (expected output) — normalized contract

Each case is run through the extractor and the result is normalized to this JSON
shape, then compared to a committed snapshot under
`tests/__snapshots__/extraction/`. The snapshot mirrors the real per-marker
payload the extractor produces (`analyse/models.py:Metadata.to_dict` and its
`OneLineNeed` / `NeedIdRefs` / `MarkedRst` subclasses) rather than a reduced
projection of it, so a regression in any field production actually emits is
caught here too:

```json
{
  "needs": [
    {
      "id": "IMPL_1",
      "title": "My Title",
      "type": "impl",
      "links": {"links": ["REQ_1"]},
      "metadata": {},
      "line": 1,
      "filepath": "case.cpp",
      "remote_url": null,
      "source_map": {"start": {"row": 0, "column": 4}, "end": {"row": 0, "column": 35}},
      "content_type": "need",
      "scope": {"scope_type": "function_definition", "scope_text": "void f() {}"}
    }
  ],
  "need_refs":  [{"need_id": "", "line": 1, "marker": "@need-ids:", "filepath": "case.cpp", "remote_url": null, "source_map": {"start": {"row": 0, "column": 0}, "end": {"row": 0, "column": 0}}, "content_type": "need-id-refs", "scope": null}],
  "marked_rst": [{"content": "", "start_line": 1, "end_line": 1, "filepath": "case.cpp", "remote_url": null, "source_map": {"start": {"row": 0, "column": 0}, "end": {"row": 0, "column": 0}}, "content_type": "rst", "scope": null}],
  "warnings":   [{"kind": "too_many_fields", "line": 1}]
}
```

Lines are 1-indexed. `needs`/`warnings` are sorted by line; `need_refs` by
`(line, need_id)`.

Per-entry fields common to `needs`, `need_refs` and `marked_rst` (mirroring
`Metadata`):

- `filepath` — the source file, **relative to the test's `tmp_path`** (e.g.
  `case.cpp`). Production emits an absolute path; the temp directory differs
  per run and per machine, so only the relative part is stable and snapshotted.
- `remote_url` — always `null` in these fixtures: the harness forces
  `analyse.git_remote_url`/`git_commit_rev` to `None` before `run()`, so this
  field is deterministic here regardless of the host's git configuration.
- `source_map` — the full `{"start": {"row", "column"}, "end": {"row",
  "column"}}` structure production computes (0-indexed). The pre-existing
  `line` (and, for `marked_rst`, `start_line`/`end_line`) keys are kept
  alongside it rather than dropped, since they duplicate the start row but a
  second implementation's comparison tooling may already rely on them.
- `content_type` — the `MarkedContentType` discriminator (`"need"` /
  `"need-id-refs"` / `"rst"`). Named `content_type` rather than `type` because
  a `needs` entry already has a `type` key for the need's own field (e.g.
  `"impl"`).
- `scope` — the marker's *associated declaration* (`tagged_scope`, computed by
  `find_associated_scope`): `{"scope_type", "scope_text"}`, or `null` when
  there is no associated scope. `scope_text` is the node's full decoded text,
  exactly as production serialises it (`str(node.text.decode("utf-8"))`).
  `scope_type` (the node's tree-sitter kind) is not part of production's
  output, but it is cheap, deterministic, and useful for cross-language/
  cross-implementation comparison, so it rides along.

`need_refs` entries additionally carry `marker` (the matched marker string,
e.g. `"@need-ids:"`), which production attaches to `NeedIdRefs` but earlier
revisions of this fixture dropped.

`needs` keep the id/title/type/links/metadata decomposition instead of
production's raw `need` dict: the same data either way, but the decomposition
is what makes the payload comparable against a second implementation whose
needs are a typed struct rather than a dict.

Genuinely excluded (the only non-deterministic things): the absolute prefix of
`filepath` (see above), and the raw `SourceComment`/tree-sitter node objects
(production itself drops `source_comment` from `to_dict()`; `tagged_scope` is
captured as full text instead of embedding the node object).

## Running / updating

```bash
# run the declarative extraction tests
python -m pytest tests/test_extraction_fixtures.py

# review + accept snapshot changes after editing fixtures or the extractor
python -m pytest tests/test_extraction_fixtures.py --snapshot-update
```

Adding a case is just a new entry in a `*.yaml` file here, then
`--snapshot-update` to capture its snapshot (review the diff before committing).
