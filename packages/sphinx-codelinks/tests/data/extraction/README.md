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
  lang: cpp                 # cpp | c | python | csharp | rust | yaml | go | jsonc
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
`tests/__snapshots__/extraction/`:

```json
{
  "needs":      [{"id": "", "title": "", "type": "", "links": {"field": ["..."]}, "line": 1}],
  "need_refs":  [{"need_id": "", "line": 1}],
  "marked_rst": [{"content": "", "start_line": 1, "end_line": 1}],
  "warnings":   [{"kind": "too_many_fields", "line": 1}]
}
```

Lines are 1-indexed. `needs`/`warnings` are sorted by line; `need_refs` by
`(line, need_id)`. Volatile data (file paths, columns, URLs, tagged scope) is
omitted so snapshots are stable.

## Running / updating

```bash
# run the declarative extraction tests
python -m pytest tests/test_extraction_fixtures.py

# review + accept snapshot changes after editing fixtures or the extractor
python -m pytest tests/test_extraction_fixtures.py --snapshot-update
```

Adding a case is just a new entry in a `*.yaml` file here, then
`--snapshot-update` to capture its snapshot (review the diff before committing).
