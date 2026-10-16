# The needs.json exchange contract

This document is the **normative** specification of the needs exchange file,
`needs.json`, as it is read: the envelope, the selection of a version, the records a
version holds, the schema defaults merged under them, and the findings reported on the way.

It exists because the file is written by two writers (sphinx-needs' `needs` builder and
ubCode) and read for its records by six readers in two languages (sphinx-needs' `needimport`
and `needs_external_needs`, which read through this package; ubCode's import, external,
config-free and diff readers), and a rule that is only written down in one of them is a rule
the others will diverge from. (sphinx-needs has a seventh: the `needs` builder's
`needs_file`, see §13.) The
Python half of the contract is this package; the executable half is the corpus
[`tests/fixtures/needs_json_reading_conformance.toml`](../tests/fixtures/needs_json_reading_conformance.toml),
which this repository holds canonically and ubCode is to vendor.

Audience: implementers of a second reader, and anyone changing this package.

Status: describes the implementation as it is (version 1.0.0). When behaviour changes, this
document, the corpus and the tests change in the same commit. Every rule names what
enforces it: "corpus: `name`" is the conformance case of that name, run by
`tests/test_conformance.py::test_case` (and, from a file, `::test_case_read_from_a_file`);
`test_reader.py::…` is a unit test, for what the corpus cannot state (messages, bytes,
object identity). A rule marked **(not pinned)** has neither.

## 1. Scope, and what is deliberately out

1. This package reads the **document**: the text, the envelope, a version, its records.
   It provides **mechanisms and no policy**: which of a record's keys a project takes, how
   a value is coerced to a project's field, which ids are accepted, the prefix a reader
   adds, how a record becomes a need, and whether a finding is worth a warning are each
   consumer's decision (§11).
   Enforced by: the API itself — no function takes a logger, a project or a configuration.
2. The package imports **the standard library and nothing else**: no Sphinx, no docutils,
   no `jsonschema`, no `requests`, no workspace member.
   Enforced by: `tests/test_imports.py::test_no_toolchain_validator_or_sibling_is_imported`,
   `tests/test_imports.py::test_only_the_standard_library_is_imported`, and CI's
   `toolchain-free` job, which runs this suite where Sphinx is not installed.
3. A file **no record can be read from** is refused: one `ExchangeError` with a `code`
   (§8.1) and a `message`, and nothing else is raised for a problem with the file's bytes,
   syntax or values. A file that is read but carries something worth knowing gives
   `Diagnostic` values (§8.2) — a `code`, a `path` and a `message` — returned, never
   logged. Codes and paths are the contract; messages are not.
   Enforced by: every corpus case (a refusal states only its code; a read states its
   findings as code + path); `test_reader.py::test_parse_refuses_bytes_that_are_not_utf8`.
4. How a file is obtained — a path, a URL, a cache, a revalidation window — is each
   reader's own. The package reads text (`parse`) or a local file (`load`).
5. The **writer** (`NeedsList` in sphinx-needs' `needsfile.py`) is not here yet; §10 describes the one property of its output another feature depends on.

## 2. The text — `parse`, `load`

1. The file is UTF-8 JSON whose top level is an object. Text that is not JSON is
   `invalid_json`; a top level of any other JSON type is `not_an_object`.
   A byte order mark is not JSON: text that starts with U+FEFF is `invalid_json`, given as
   text, as UTF-8 bytes or in a file, and so are UTF-16 bytes.
   Enforced by: corpus: `not-json`, `top-level-array`, `top-level-string`,
   `a-byte-order-mark-is-not-json`, `unicode-text-is-read`;
   `test_reader.py::test_a_byte_order_mark_is_invalid_json`,
   `…::test_utf16_bytes_are_invalid_json`.
2. A key written twice in one object keeps its last value, at every level — a record of
   `needs`, a version of `versions`, a key of the envelope.
   Enforced by: corpus: `a-duplicated-key-keeps-its-last-value` (a record of `needs`),
   and for the envelope `a-duplicated-envelope-key-keeps-its-last-value`;
   `test_reader.py::test_a_duplicated_key_keeps_its_last_value` (`versions`, the envelope).
3. `parse` takes text or bytes; bytes are decoded as UTF-8, and bytes that are not UTF-8
   are `invalid_json`. `load` reads a file as UTF-8; a file that cannot be read (absent, a
   directory, unreadable) or is not UTF-8 is `invalid_json`.
   Enforced by: `test_reader.py::test_parse_reads_utf8_bytes`,
   `…::test_parse_refuses_bytes_that_are_not_utf8`, `…::test_load_reads_utf8`,
   `…::test_load_of_a_missing_file_is_invalid_json`,
   `…::test_load_of_a_file_that_is_not_utf8_is_invalid_json`; every corpus case through
   `test_case_read_from_a_file`.
4. Out of contract **(not pinned)**: pathological input (nesting ~1 000 levels deep, which
   Python's recursion limit refuses; integers beyond 64 bits), and what is not JSON but
   Python's `json` accepts — the three constants `NaN`, `Infinity` and `-Infinity`, and lone
   surrogate escapes (`"\ud800"`). This reader reads them; a strict reader refuses the file.
   A file meant for every reader carries none of them.

## 3. The envelope

```json
{
  "format_version": 1,
  "project": "demo",
  "created": "2026-01-01T00:00:00",
  "current_version": "1.0",
  "versions": {"1.0": {"needs": {"REQ_1": {"id": "REQ_1", "type": "req", "title": "…"}}}}
}
```

1. **`format_version`**, an integer of 1 or more: the format the file is written in.
   Absent, the file is format 1 — every file written before the key existed is. Format 1
   is the only one there is. A value above 1 is read as format 1 and reported
   (`format_version_unsupported`, path `format_version`): a later format is to stay
   readable as this one, or it is not a later version of this format. Any other value — a
   string, even `"1"`; `0` or a negative number; any number written with a fraction or an exponent, even `1.0` or `1e0`;
   `true`; `null` — refuses the file (`format_version_invalid`). It is checked before
   anything else in the envelope. No writer writes the key yet.
   Enforced by: corpus: `format-version-1`, `format-version-absent-is-1`,
   `format-version-above-1-is-read-as-1`, `format-version-a-string`,
   `format-version-zero`, `format-version-negative`, `format-version-a-fraction`,
   `format-version-a-boolean`, `format-version-null`, `format-version-is-checked-first`;
   `test_reader.py::test_a_later_format_version_is_read_as_the_first` (the message).
2. **`versions`**, an object: each key a version's name, each value a version (§5).
   Absent or not an object, the file is refused (`versions_missing`).
   Enforced by: corpus: `versions-absent`, `versions-not-an-object`.
3. **`current_version`**, a string: the name of the version read when none is asked for
   (§4).
4. **`project`**, **`created`** and **`creator`** are informative: the reader reads none of
   them. Every other key of the envelope is ignored too, with no finding — so a later
   writer can add one without breaking a reader of this contract.
   Enforced by: corpus: `unknown-envelope-keys-are-ignored`.

## 4. Selecting a version — `Document.select_version`

1. A version **asked for** by name is read. It need not be `current_version`, and the file
   need not have a `current_version` at all. A name that is not a key of `versions` is
   `version_not_found`.
   Enforced by: corpus: `requested-version-is-read`,
   `requested-version-needs-no-current-version`, `requested-version-not-in-the-file`.
2. With none asked for, **`current_version`** is read. Absent, not a string, or empty is
   `current_version_missing` — with one exception: an empty `current_version` names the
   version called `""` when the file has one (sphinx-needs writes exactly that for a
   project whose `version` is unset). A `current_version` naming no version of the file,
   an empty `versions` included, is `version_not_found`.
   Enforced by: corpus: `current-version-is-read`,
   `empty-current-version-names-the-empty-version`, `current-version-absent`,
   `current-version-empty-and-no-empty-version`, `current-version-a-number`,
   `current-version-not-in-the-file`, `versions-empty`.
3. The selected version must be an object with a `needs` object; otherwise the file is
   `needs_missing`. Only the selected version is checked: another version's faults are
   neither a refusal nor a finding.
   Enforced by: corpus: `needs-absent`, `needs-not-an-object`, `version-not-an-object`,
   `only-the-selected-version-is-checked`.

## 5. A version

1. **`needs`**, an object: each key a need's id, each value its record (§6).
2. **`needs_schema`**, a JSON schema of one need, whose `properties` carry the defaults
   (§7). Optional.
3. **`needs_defaults_removed`**: `true` says the writer left out every value equal to its
   default, to be restored from `needs_schema` (§7.3). Any other value, or none, says
   nothing was left out.
4. **`needs_amount`**, **`created`** and **`creator`** are informative: not read, and a
   `needs_amount` that disagrees with `needs` is not a finding. Every other key of a version
   is ignored too.
   Enforced by: corpus: `needs-amount-is-not-checked`, `unknown-envelope-keys-are-ignored`.

## 6. A record — `Version.records`

1. **A value of `needs` that is not an object is not a record**: it is skipped and
   reported (`record_not_object`, path `versions.<version>.needs.<key>`); the other records
   are read.
   Enforced by: corpus: `record-not-an-object-is-skipped`,
   `record-values-of-every-other-type-are-skipped`; `test_reader.py::test_a_record_that_is_not_an_object_is_skipped` (the message).
2. **The key is the need's id.** A record's `fields["id"]` is always its key. A record
   without an `id` gets the key; one whose `id` differs from the key — another string, a
   number, `null` — is reported (`id_mismatch`, path `versions.<version>.needs.<key>.id`)
   and the stated `id` is ignored.
   Enforced by: corpus: `id-equal-to-the-key`, `id-absent-is-the-key`,
   `id-other-than-the-key`, `id-a-number`, `id-null`,
   `id-mismatch-names-the-version-it-is-in`; `test_reader.py::test_the_key_is_the_id` (the messages).
3. **The legacy `description` is the `content`** when the record's `content` is absent,
   or is `null`, `""`, `0`, `false`, `[]` or `{}` — any value Python treats as false
   (sphinx-needs before 4.0 wrote `description`): the key is renamed, not copied. A record
   with any other `content` keeps both. The mapping runs after the schema
   defaults are merged (§7), so an empty default `content` does not hide a `description`.
   Enforced by: corpus: `description-is-the-content`, `description-fills-an-empty-content`,
   `description-fills-a-null-content`, `description-fills-a-false-content`,
   `description-fills-a-zero-content`, `description-fills-an-empty-array-content`,
   `description-fills-an-empty-object-content`,
   `content-wins-over-description`,
   `a-content-default-does-not-hide-the-description`;
   `test_reader.py::test_map_legacy_keys_in_place`.
4. **Every other key is handed on as written**, known or not — `parts`, `links_back`,
   `type_name`, a key no project defines. Which keys a reading project takes, and what it
   checks of their values (sphinx-needs refuses `parts` that is not a mapping of mappings,
   a missing or non-string `title`, a non-string `type` or `content`), is the ingest
   layer's (§11).
   Enforced by: corpus: `record-keys-are-carried-verbatim`, `parts-are-carried-verbatim`.
5. Records are handed out **in the file's order**.
   Enforced by: corpus: `records-keep-the-file-order`, `empty-needs-is-read`.
6. Each record's `fields` is a new object, but its **values are the document's own** — a
   list or object value, and a default, is the same object in every record it fills. A
   reader replaces a value rather than changing it in place. (Copying them would cost more
   than reading the file: about a second for twenty thousand needs.)
   Enforced by: `test_reader.py::test_records_do_not_alter_the_document`,
   `…::test_a_default_is_one_object_in_every_record`.

## 7. Schema defaults

1. A version's defaults are the `default` of each property of `needs_schema.properties`
   that has one. Of a property only `default` is read: its `field_type` (`core`, `links`,
   `backlinks`, `extra`, or anything else), its `type`, `readOnly` and the rest decide
   nothing here. A `needs_schema` or `properties` that is not an object, and a property
   that is not an object, give no defaults and no finding.
   Enforced by: corpus: `only-default-is-read-from-a-property`,
   `a-schema-that-is-not-an-object-merges-nothing`,
   `schema-properties-not-an-object-merge-nothing`,
   `a-property-that-is-not-an-object-is-ignored`.
2. The defaults are **merged under each record**: a default fills a field the record does
   not have, a stated value wins, and a property without a default adds nothing. A default
   is any JSON value, `null` included; a default for `id` never replaces the key (§6.2).
   They are merged whether or not `needs_defaults_removed` is set. A reader may ask for
   the records without them (`records(apply_schema_defaults=False)`).
   Enforced by: corpus: `schema-defaults-are-merged-under-each-record`,
   `schema-defaults-are-merged-without-defaults-removed`,
   `a-default-of-any-json-type-is-merged`, `a-schema-default-does-not-replace-the-key`,
   `without-a-schema-nothing-is-merged`; `test_reader.py::test_a_null_default_is_merged`,
   `…::test_schema_defaults_can_be_left_out`.
3. A version whose `needs_defaults_removed` is `true` and which has **no `needs_schema`
   key** is read and reported (`defaults_removed_without_schema`, path
   `versions.<version>.needs_defaults_removed`): its defaults are gone and nothing here can
   restore them; the reading project's own defaults are the reader's fallback. A
   `needs_schema` key of any value, `null` included, counts as present.
   Enforced by: corpus: `defaults-removed-without-a-schema`,
   `defaults-removed-false-without-a-schema`, `defaults-removed-not-a-boolean`,
   `defaults-removed-with-a-schema-that-is-not-an-object`;
   `test_reader.py::test_defaults_removed_without_a_schema` (the message).
4. **The writer's half of the merge.** A writer that leaves defaults out
   (`needs_defaults_removed`) leaves out a value exactly where it equals the `default` its
   field's property carries in the version's own `needs_schema`, as a JSON value of the
   same type (`1.0` is not `1`, `[1.0]` not `[1]`): never a need type's default, which
   `needs_schema` does not carry. A need holding its type's default, its own type's or one
   it inherits, writes it wherever it differs from that `default`. A reader restores a
   left-out value from the version's own `needs_schema` (2.), not from the reading
   project's declarations, which fill only a field to which the schema gives no default.
   So a version read with its defaults left out gives the same records as the same version
   written in full.
   Enforced by: sphinx-needs' field-declaration corpus,
   `packages/sphinx-needs/tests/fixtures/field_declaration_conformance.toml`:
   `defaults-left-out-equal-the-field-default` (the writer),
   `defaults-left-out-restored-from-the-file` (the reader).

## 8. Refusals and findings

### 8.1 Error codes (`ExchangeError.code`): no record can be read

| code | when |
|---|---|
| `invalid_json` | the text is not JSON; bytes or a file that are not UTF-8; a file that cannot be read (§2) |
| `not_an_object` | the top level is not a JSON object (§2) |
| `format_version_invalid` | `format_version` is present and not an integer of 1 or more (§3.1) |
| `versions_missing` | `versions` is absent or not an object (§3.2) |
| `current_version_missing` | none asked for, and `current_version` is absent, not a string, or empty with no `""` version (§4.2) |
| `version_not_found` | the version asked for, or the current one, is not a key of `versions` (§4) |
| `needs_missing` | the selected version is not an object, or has no `needs` object (§4.3) |

They are checked in that order, so a file is refused for the first rule it breaks.
Enforced by: corpus: `format-version-is-checked-first`,
`versions-are-checked-before-current-version`.

### 8.2 Diagnostic codes (`Diagnostic.code`): read, and reported

| code | path | when |
|---|---|---|
| `format_version_unsupported` | `format_version` | `format_version` above 1 (§3.1) |
| `record_not_object` | `versions.<version>.needs.<key>` | a value of `needs` is not an object (§6.1) |
| `defaults_removed_without_schema` | `versions.<version>.needs_defaults_removed` | §7.3 |
| `id_mismatch` | `versions.<version>.needs.<key>.id` | §6.2 |

The first three are the version's (`Version.diagnostics`), the last each record's
(`Record.diagnostics`); a reader reports both, and the corpus compares them together, as
a multiset.
Enforced by: corpus: `every-finding-of-a-file-is-reported`.

### 8.3 Paths

**A path** is the keys from the top-level object down to what was found, each spelled
   as the file spells it, joined by `.`. A key that itself contains a `.` (a version named
   `1.0`) is not escaped, so a path names its place for a person rather than
   unambiguously for a program **(the form is pinned by every corpus case with a finding;
   its ambiguity is known)**.

## 9. What v1 must still read

sphinx-needs' changelog dates the shapes: `needs_schema` (with the defaults it lets a
writer remove) arrived in 3.0.0; `creator`, and `content` in place of `description`, in
4.0.0 (#1311, #1312).

1. **The pre-3.0 shape**, which most of sphinx-needs' own fixtures have: no `creator`, no
   `needs_schema`, no `needs_defaults_removed`, `description` where `content` is meant,
   and commonly `created` at both levels and a `needs_amount`.
   Enforced by: corpus: `a-pre-3-0-file`.
2. **The 3.x shape**: a `needs_schema` (with `field_type` on each property) and
   `needs_defaults_removed`, but no `creator`, and `description` where `content` is meant —
   a schema `description` default is merged under each record and then mapped (§6.3, §7) —
   and, in the large export ubCode's tests carry, no `created` either and the legacy
   `full_title` on every record.
   Enforced by: corpus: `a-3-x-file`.
3. **The 4.x shape** sphinx-needs writes today: `creator`, `created`, `needs_schema`,
   `needs_defaults_removed`, `needs_amount`.
   Enforced by: corpus: `a-4-x-file`.

## 10. The value serialisation another feature reads

sphinx-needs' `hash` derive kind (`_rule_hash` in `sphinx_needs/functions/common.py`)
digests a need's fields "each value as `needs.json` writes it", so the WRITER's value
model is a contract another feature depends on, and the writer that moves here later must
keep it byte-stable. Today the writer is `NeedsList.write_json` / `dump_json`
(`sphinx_needs/needsfile.py`, the two `json.dump(s)(self.needs_list, …, sort_keys=True)`
calls): keys sorted, Python's default separators (`", "` and `": "`), non-ASCII escaped
(`ensure_ascii=True`), numbers as Python writes them (`3.0`, `1e+16`), link lists sorted.
The hash itself serialises the values it reads as one compact JSON array
(`separators=(",", ":")`, `ensure_ascii=False`) and takes its SHA-256, so it depends on
the values and their types, not on the file's bytes. sphinx-needs'
`tests/__snapshots__/test_needs_builder.ambr` pins the written bytes **(not pinned
here: the writer is a later slice)**.

## 11. What the package does not decide

As `ub-project`'s contract says of discovery, each of these stays with each consumer:

- **which of a record's keys a project takes**: sphinx-needs' ten-field table (the core
  fields `needimport` keeps and `needs_external_needs` drops, and the reverse), its
  unknown-keys warnings, and ubCode's equivalents;
- **coercion** of a value to a project's field type, and the per-record checks of
  `title`, `type`, `content`, `id` and `parts` (sphinx-needs' `_record_params`);
- **`needs_id_regex`** (sphinx-needs applies it to neither reader);
- **`id_prefix`**, and **the file's ids as its namespace**: the ids a file contains are
  its own, and a reference to one of them — a link, or the id written in a need's
  `content` — names that need of the file, whether a reader takes the need or not; a
  reference to an id the file does not contain names something outside it. A reader that
  adds a prefix therefore rewrites every reference to one of the file's ids, and no other
  (a link given as a string holding a dynamic function or a variant is left for the
  reader to resolve first), and the reading project references those needs by their
  prefixed ids. `content` is opaque markup: every whole-word occurrence of a file id in it
  is such a reference, inside code blocks and file names too **(not pinned here: the
  ingest layer, pinned by sphinx-needs' `tests/test_exchange_readers.py`)**;
- **`:ids:`, `:filter:`, `:tags:`**, duplicates across sources, and where a need is
  recorded (`docname`, `lineno`);
- **whether a finding is worth a warning**, and its wording.

## 12. Divergences from ubCode

ubCode is to be held to this contract through the corpus. A behaviour ubCode diverges from
deliberately is a row of its `design/divergence-register.md`, and a corpus case it
diverges on carries `divergent = { ubcode = "design/divergence-register.md#…" }`. **No
document-layer case does**: none of the register's needs.json rows is a document-layer
behaviour. The rows about the file, by subject (as of ubCode `51eb4f4784`):

- remote sources and their revalidation (transport; out of scope, §1.4);
- what the export carries — no `<link>_back` keys, link conditions collapsed, no
  `created`, no dead-link flags (the writer, a later slice);
- what an import makes of a record — `:id_prefix:` at resolution, an imported need's
  `parent_needs`, content parsed in its `doctype`, the winner of a duplicate id, `sections`
  on an imported need (the ingest layer, §11).

Where a reader of ubCode's differs from a document-layer rule today and no row registers
it, the corpus case is the specification, and ubCode's runner fails it until ubCode
follows.

## 13. For consumers

sphinx-needs' two readers of a needs.json read it through this package — `needimport` (a
directive's file or URL) and `needs_external_needs` (each configured source) — and report each
refusal as one warning that refuses that source (`needs.needimport`,
`needs.external_needs`) and each finding as a warning naming the source and the path. What
it then does with each record is its own (§11). `sphinx_needs.exchange`, where 9.0.0
shipped this reader, is a deprecated alias of this package until sphinx-needs 10.0.
The `needs` builder's `needs_file` (`NeedsList.load_json`) and `check_needs_file` still read the file with `json.load`; they move with the writer, a later slice.
