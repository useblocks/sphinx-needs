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

## Snapshot (expected output) — the real production shape

Each case is run through the extractor and its output is compared to **two**
committed snapshots under `tests/__snapshots__/test_extraction_fixtures/`: one
for the marked content, one for the warnings. These are not a reduced
projection invented for the test — each is the real payload a production run
writes to its own file, taken verbatim (only a temp-path portability rewrite
and one additive field applied; see below):

- **marked content** (the default, unnamed snapshot, `…json`) is exactly
  `SourceAnalyse.dump_marked_content`'s payload: a flat list, in
  `all_marked_content`'s order (sorted by `(filepath, source_map.start.row)`),
  of each entry's own `Metadata.to_dict()` (`analyse/models.py`) —
  `OneLineNeed`'s nested `need` dict, `NeedIdRefs`'s `need_ids` list +
  `marker`, or `MarkedRst`'s `rst` text.
- **warnings** (a second snapshot, named `"warnings"`, saved as
  `…[warnings].json`) is exactly `AnalyseProjects.dump_warnings`'s payload: a
  flat list of `AnalyseWarning.__dict__` records. Production never folds
  warnings into the data stream — `dump_marked_content` and `dump_warnings`
  are two independent files (data vs. warnings, stdout vs. stderr), and CLI
  users additionally get the same warnings via `logger.warning`
  (`cmd.py`) — so the test keeps them as two independent snapshots instead of
  one merged object.

A one-line need, with its need-ref and warning counterparts alongside for
reference (a single case never emits all three at once — shown together here
only to keep this example short):

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
    "source_map": {"start": {"row": 0, "column": 13}, "end": {"row": 0, "column": 32}},
    "tagged_scope": "void f() {}",
    "need_ids": ["REQ_1", "REQ_2", "REQ_3"],
    "marker": "@need-ids:",
    "type": "need-id-refs",
    "tagged_scope_type": "function_definition"
  }
]
```

and the matching `warnings` snapshot for a case that emits one:

```json
[
  {"file_path": "case.cpp", "lineno": 1, "msg": "5 given fields. They shall be less than 4", "type": "need", "sub_type": "too_many_fields"}
]
```

`source_map` rows/columns are 0-indexed, exactly as production computes them.

Common fields on every marked-content entry (mirroring `Metadata`):

- `filepath` — the source file, **relative to the test's `tmp_path`** (e.g.
  `case.cpp`). This is the *only* portability deviation from the real thing:
  production emits an absolute path, but `tmp_path` differs per run and per
  machine, so the harness snapshots it relative to `tmp_path` instead (see
  `_relative_filepath` in `tests/test_extraction_fixtures.py`).
- `remote_url` — always `null` here: the harness forces
  `analyse.git_remote_url`/`git_commit_rev` to `None` before `run()`, so this
  field is deterministic regardless of the host's git configuration.
- `source_map` — the full `{"start": {"row", "column"}, "end": {"row",
  "column"}}` structure production computes.
- `tagged_scope` — the marker's *associated declaration* (computed by
  `find_associated_scope`), as production serialises it: the node's full
  decoded text (`str(node.text.decode("utf-8"))`), or `null` when there is no
  associated scope.
- `type` — the `MarkedContentType` discriminator's real value (`"need"` /
  `"need-id-refs"` / `"rst"`); a need's own `type` field (e.g. `"impl"`) lives
  one level down, inside `need`, so the two never collide.
- `tagged_scope_type` — **the one additive, test-only field.** It is the
  associated node's tree-sitter kind (e.g. `"function_definition"`), or
  `null`. `Metadata.to_dict()` never emits this — it is not part of
  production's output — but it costs nothing to add alongside the real
  `tagged_scope` text: it lets a wrong-scope regression be told apart from a
  same-text coincidence, and gives a second implementation a language-agnostic
  value to compare against. It is always the last key on an entry, so it
  never disturbs the real shape.

Payload-specific fields: `need` (a plain dict — `id`/`title`/`type` as
strings, `links` as a list, exactly as `OneLineNeed.need` holds it — not
decomposed or re-wrapped); `need_ids` (list) + `marker` (string) for a
need-id-reference; `rst` (string) for a marked-rst block. A need-id-reference
entry is **one** record covering every id it references, not exploded per id.

Warning records (`AnalyseWarning.__dict__`): `file_path` (relativized the same
way as `filepath` above), `lineno`, `msg`, `type` (the `MarkedContentType` the
warning occurred while parsing — currently always `"need"`, since only the
one-line-need parser raises these), `sub_type` (the snake_case warning kind,
e.g. `"too_many_fields"`).

Genuinely excluded (the only non-deterministic things): the absolute prefix of
`filepath`/`file_path` (see above), and the raw `SourceComment`/tree-sitter
node objects (production itself drops `source_comment` from `to_dict()`;
`tagged_scope` is captured as full text instead of embedding the node object).

Two known production quirks show up as-is in these snapshots (deliberately
left unfixed — out of scope here):

- a need-id-reference's `source_map` columns are shifted by the width of any
  whitespace between the marker and its ids: `extract_marker`
  (`analyse/analyse.py`) computes `start_column` from the pre-`strip()`
  position but `end_column` from the post-`strip()` length.
- a multi-line `rst` block's `source_map` collapses `start.row`/`end.row` to
  the same row, with the `start`/`end` columns being raw offsets into the
  flattened multi-line comment text rather than a real position past the
  first line.

## Portability guarantees

These snapshots hold real positions (`source_map` rows/columns) and real
captured text (`tagged_scope`, `rst`, ...), so anything that changes a byte
on disk before extraction runs — not just the extractor itself — can shift a
value and break the comparison. The harness (`tests/test_extraction_fixtures.py`)
and the repository make three guarantees so one committed snapshot is valid
on Linux, macOS and Windows alike:

- **LF-pinned inputs.** `.gitattributes` (repository root) forces
  `tests/data/**` and `tests/__snapshots__/**` to check out with LF line
  endings regardless of the platform or the user's `core.autocrlf` (the
  Git-for-Windows default, `true`, rewrites LF to CRLF on checkout
  otherwise). Without this, the fixture YAMLs and the committed snapshots
  themselves could arrive corrupted on Windows before the test even runs.
- **Byte-exact source writing.** The harness writes each case's `source`
  (and, for `libclang` cases, `compile_commands.json`) with
  `Path.write_bytes(text.encode("utf-8"))`, never `Path.write_text(...)`.
  `write_text` opens the file in text mode, which translates every `\n` to
  `os.linesep` on write — on Windows that turns an LF-only fixture into CRLF
  on disk, shifting tree-sitter/libclang column positions at line ends and
  injecting `\r` into any multi-line `tagged_scope` text. Writing exact bytes
  means the file on disk always matches the fixture verbatim, independent of
  platform. `test_extraction_is_crlf_insensitive` pins the consequence: the
  same source, written once as LF and once as genuine CRLF, produces
  identical normalized output.
- **Relative, slash-normalised paths.** `_relative_filepath` renders
  `filepath`/`file_path` with `Path.as_posix()`, so a nested case can never
  render with backslashes (`sub\case.h`) on Windows where every existing
  snapshot uses `/`. `_assert_portable_path` enforces this as an invariant
  rather than a remembered convention: it asserts the value is relative
  (checked against both `PurePosixPath` and `PureWindowsPath`, since neither
  alone recognises every absolute form — POSIX-absolute, drive-absolute, and
  UNC) and contains no backslash, so a non-portable path can never reach a
  committed snapshot silently.

These fixtures and snapshots are also mirrored byte-for-byte into a second
implementation's test suite, so a platform-dependent value breaks that
comparison too, not only Windows CI here.

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
