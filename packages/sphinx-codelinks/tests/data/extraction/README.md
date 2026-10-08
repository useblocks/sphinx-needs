# Declarative extraction-test fixtures

Marker extraction (comment → one-line need / need-id-reference / multi-line need) is
tested declaratively: each case is a **fixture** (the input) plus a **snapshot**
(the captured expected output). This keeps the inputs language-agnostic and the
expected output reviewable, and lets us cover the whole language matrix without a
bespoke test function per case.

## Shared with ubCode

The YAML files of this directory that ubCode's `sync_codelinks_expected.py`
names in `SHARED_FIXTURES` are copied byte for byte into ubCode
(`rust/ubc_codelinks/tests/fixtures/extraction/`), and ubCode takes their
snapshots in `tests/__snapshots__/test_extraction_fixtures/` as the expected
output of its parity test. A change to a case or a snapshot is therefore a
contract change, which the ubCode side re-syncs. useblocks/ubcode#3014 points
that tooling at this repository; useblocks/ubcode#3928 tracks projecting the
production shape below back to ubCode's normalized one.

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
- `config.multiline_needs` (optional): the multi-line need markers and markups,
  `{start_sequence, end_sequence, default_markup, markups}` (defaults `@need`,
  `@endneed`, `rst`, `{rst: ".rst", md: ".md"}`).
- `extract` (optional): which extractors to run — a subset of
  `[oneline, need_refs, multiline]` (default: all three). Narrow it to keep a case
  focused: a need-reference case sets `extract: [need_refs]` so the `@`-prefixed
  `@need-ids:` marker isn't also parsed as a one-line need.
- `engine` (optional): `treesitter` (default) sees every comment; `libclang`
  evaluates the preprocessor and excludes markers in inactive `#if`/`#ifdef`
  branches. libclang cases are skipped when the `clang` bindings are unavailable.
- `line_endings` (optional): `lf` (default), `crlf` or `cr`. The `source` is
  written with that line ending, and the case is also run with LF endings and
  must produce the same output.
- `defines` (optional, libclang only): preprocessor defines, e.g.
  `["VARIANT_A=1", "PROTOCOL_VERSION=3"]`.

## Snapshots: the production shape

Each case has two snapshots under `tests/__snapshots__/test_extraction_fixtures/`,
one per output production produces:

- **marked content** (`…].json`): `SourceAnalyse.dump_marked_content`'s
  payload — the flat list `all_marked_content` holds, sorted by
  `(filepath, source_map.start.row)`, one `Metadata.to_dict()`
  (`analyse/models.py`) per entry.
- **warnings** (`…][warnings].json`): the `AnalyseWarning.__dict__` records of
  `SourceAnalyse.warnings`. Production reports them apart from the
  marked content (the `src-trace` directive as `codelinks.oneline` build
  warnings, `codelinks analyse` through `logger.warning`), so they are a
  separate snapshot.

Three deviations from production output, all deliberate:

- `filepath` and `file_path` are relative to the test's `tmp_path` and
  `/`-separated (`_relative_filepath`, `Path.as_posix()`); production writes an
  absolute path, which differs per run and per machine.
- `tagged_scope_type`, the last key of every marked-content entry, is
  test-only: the associated node's tree-sitter kind (e.g.
  `"function_definition"`) or `null`, so a wrong scope cannot pass on matching
  text, and one construct can be compared across languages.
- The warnings are sorted by `(file_path, lineno, type, sub_type, msg)`:
  production reports them in tree-sitter capture order, which differs between
  two runs of the same input.

A need and a need-id-reference entry (shown together for brevity, not the
output of one case):

```json
[
  {
    "filepath": "case.cpp",
    "remote_url": null,
    "source_map": {"start": {"row": 0, "column": 4}, "end": {"row": 0, "column": 35}},
    "tagged_scope": "void f() {}",
    "need": {"title": "My Title", "id": "IMPL_1", "type": "impl", "links": ["REQ_1"]},
    "type": "need",
    "tagged_scope_type": "function_definition"
  },
  {
    "filepath": "case.cpp",
    "remote_url": null,
    "source_map": {"start": {"row": 0, "column": 14}, "end": {"row": 0, "column": 33}},
    "tagged_scope": "void f() {}",
    "need_ids": ["REQ_1", "REQ_2", "REQ_3"],
    "marker": "@need-ids:",
    "type": "need-id-refs",
    "tagged_scope_type": "function_definition"
  }
]
```

and a `warnings` snapshot, for a case that emits one:

```json
[
  {"file_path": "case.cpp", "lineno": 1, "msg": "5 given fields, maximum is 4", "type": "need", "sub_type": "too_many_fields"}
]
```

The fields of a marked-content entry, as `Metadata.to_dict()` writes them:

- `remote_url` — always `null`: the harness sets `git_remote_url` and
  `git_commit_rev` to `None` before `run()`.
- `source_map` — `{"start": {"row", "column"}, "end": {"row", "column"}}`,
  0-indexed; a column counts the characters before it on its line. A one-line
  need starts at its title, a reference at its first id and ends after its last.
- `tagged_scope` — the full text of the declaration `find_associated_scope`
  associates with the marker, or `null`.
- `type` — `"need"`, `"need-id-refs"` or `"multiline-need"`; a need's own `type` (e.g.
  `"impl"`) is inside `need`.
- the payload — `need` (the `OneLineNeed.need` dict as is), `need_ids` and
  `marker` (one record for all the ids of a marker, not one per id), or a
  multi-line need's `need`, `markup` and `source` (below).

A multi-line need (`"type": "multiline-need"`, the cases of `multiline_needs.yaml`)
carries `need` (`type`, `title`, the options in the order written as directive
strings, `content`, `doctype`), `markup` (the resolved tag) and `source`: here
always `project` `""`, `path` `case.<ext>` with `root` `"src_dir"` and `commit` `null`, the
`start`/`end`/`content_start` positions (1-based `line`, 0-based character
`col`; `content_start` `null` without a body), `option_lines` and `scope`
(`{kind, start, end}` or `null`). Its refusals and notes are warning records
with `type` `"multiline-need"` and a `multiline_need_*` `sub_type`.

A warning record has `file_path`, `lineno`, `msg`, `type` (the
`MarkedContentType` being parsed: `"need"` from the one-line parser,
`"multiline-need"` from the multi-line one) and `sub_type` (the kind, e.g. `"too_many_fields"`).
No `SourceComment` or tree-sitter node object is snapshotted: production's
`to_dict()` drops the comment and writes the scope as its text.

No case puts two entries of one kind on one row: production orders them by row
only, so they keep tree-sitter's capture order, which differs between runs
(#2150). On a row, references come before needs.

## Portability

One committed snapshot holds on Linux, macOS and Windows:

- The root `.gitattributes` checks this directory and `tests/__snapshots__/`
  out with LF on every platform, because ubCode copies their bytes.
- The harness writes each case's `source` (and a libclang case's
  `compile_commands.json`) as exact bytes (`_write_exact`): `Path.write_text`
  would turn every `\n` into `\r\n` on Windows. The `line_endings.yaml` cases
  pin that CRLF and a lone CR extract as LF does.
- Paths are `/`-separated (see above).

A value that still differed per platform would fail the Windows CI cell.

## Running / updating

```bash
# run the declarative extraction tests
python -m pytest tests/test_extraction_fixtures.py

# review + accept snapshot changes after editing fixtures or the extractor
python -m pytest tests/test_extraction_fixtures.py --snapshot-update
```

Adding a case is just a new entry in a `*.yaml` file here, then
`--snapshot-update` to capture its two snapshots (review the diff before
committing).
