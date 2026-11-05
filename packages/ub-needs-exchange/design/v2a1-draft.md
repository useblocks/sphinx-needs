# needs.json format "2a1" — a draft, read on opt-in

This document is the specification of the **draft** needs.json format `"2a1"` as this
package reads it: the envelope, the record, the hop and the link shapes, how a record is
projected to the shape a format-1 record has, and the findings reported on the way.

**Experimental.** `"2a1"` is the first alpha of the next format (format 2). It may change,
or be removed, in any release while it is a draft, and a file of it is **readable only by
the release that wrote it**: nothing promises that a later release reads a `"2a1"` file,
or that a reader of a later draft does. A reader reads it only when asked to (§1); without
that, a `"2a1"` file is refused exactly as the shared contract refuses every later format
([`exchange-contract.md`](exchange-contract.md) §3.1), so the shared contract and its
corpus are unchanged by it.

Its executable half is this package's own corpus,
[`tests/fixtures/needs_json_2a1_draft_conformance.toml`](../tests/fixtures/needs_json_2a1_draft_conformance.toml),
run by `tests/test_2a1_draft_conformance.py`; "corpus: `name`" below is a case of it, and
`test_reader.py::…` a unit test. It is not the shared reading corpus, which ubCode
vendors: it becomes one ubCode can vendor once the shape settles.

Status: describes the implementation as it is (ub-needs-exchange, unreleased).

## 1. The opt-in — `Document.select_version(requested, *, drafts=())`

1. `drafts` names the drafts the call reads, besides format 1. There is one: `"2a1"`. A
   file whose `format_version` is a draft asked for is read as this document says; any
   other file is read, or refused, exactly as without `drafts` — a format-1 file as the
   shared contract says, any other later format refused (`format_version_unsupported`),
   `"2b1"` and `2` included.
   Enforced by: corpus: `a-draft-is-read-on-opt-in`,
   `the-opt-in-reads-only-the-draft-it-names`, `the-opt-in-reads-no-later-integer-format`,
   `a-format-1-file-is-read-as-before-on-opt-in`; `test_reader.py::test_drafts_is_any_collection`.
2. Without `"2a1"` in `drafts`, a `"2a1"` file is refused with the shared contract's code
   and message.
   Enforced by: corpus: `without-the-opt-in-a-draft-is-refused`; the shared corpus's
   `format-version-a-pre-release-is-refused` and
   `format-version-is-checked-whatever-version-is-asked-for`;
   `test_reader.py::test_without_the_opt_in_a_draft_is_refused_exactly_as_before`;
   `test_2a1_draft_conformance.py::test_the_shared_corpus_keeps_2a1_refused`.
3. A `drafts` entry naming a draft this reader does not know is a programming error, not a
   finding about a file: `ValueError`, before the file is looked at. A string is a
   collection of its characters, so `drafts="2a1"` is one too.
   Enforced by: `test_reader.py::test_an_unknown_draft_is_a_programming_error`.

## 2. The envelope

```json
{
  "format_version": "2a1",
  "project": {"name": "up", "version": "1.0"},
  "creator": {"program": "sphinx_needs", "version": "9.3.0"},
  "created": "2026-11-05T00:00:00",
  "needs": [{"id": "REQ_1", "type": "req", "fields": {"title": "…"}}]
}
```

1. **No `versions` and no `current_version`.** A draft has one version, the document
   itself. A `"2a1"` file that has either key, whatever its value, is refused
   (`draft_has_versions`): a reader of format 1 that does not check `format_version` —
   sphinx-needs 9.0.0 with ub-needs-exchange 1.0.0 is one — reads such a file as format 1,
   silently, so no `"2a1"` file carries them.
   Enforced by: corpus: `a-draft-with-versions-is-refused`,
   `a-draft-with-a-current-version-is-refused`,
   `versions-are-checked-before-the-draft-s-needs`.
2. **`needs`**, an array of records (§3), in the file's order. Absent or not an array — a
   format-1 `needs` object keyed by id included — the file is refused (`needs_missing`).
   Enforced by: corpus: `a-draft-without-needs-is-refused`,
   `a-draft-whose-needs-is-an-object-is-refused`, `a-draft-with-empty-needs-is-read`.
3. **`project`**, an object of a `name` and a `version`, each a string. The version is
   the document's: `Version.name` is `project.version`, or `""` without one. `project`
   absent or not an object (format 1's `project` string included), or a `name` or
   `version` that is present and not a string, is read as absent and reported (`project_invalid`,
   path `project`, `project.name` or `project.version`) — a finding, not a refusal.
   Enforced by: corpus: `a-draft-without-a-project-version-is-named-empty`,
   `a-draft-without-a-project-is-read-and-reported`,
   `a-draft-whose-project-is-a-string-is-read-and-reported`,
   `a-project-name-or-version-that-is-not-a-string-is-reported`.
4. **Selecting the version.** With none asked for, the one version is read. A version
   asked for by name is read when it is `project.version`, and is `version_not_found`
   otherwise — the empty name too, when the project has no version: a request that cannot
   be met is refused, as in format 1, rather than read as the wrong snapshot.
   Enforced by: corpus: `a-draft-is-selected-by-its-project-version`,
   `a-draft-asked-for-by-another-name-is-not-found`,
   `a-draft-without-a-project-version-has-no-version-to-ask-for`.
5. **`creator`** (`{program, version}`) and **`created`** are informative, and every other
   key of the envelope is ignored, with no finding. A draft has **no schema**: a
   `needs_schema` key is one of those, `Version.schema_defaults()` is `{}`, and
   `records(apply_schema_defaults=...)` gives the same records either way. A writer of
   the draft writes every value, defaults included.
   Enforced by: corpus: `unknown-envelope-keys-of-a-draft-are-ignored`;
   `test_reader.py::test_a_draft_has_no_schema_defaults`.
6. The refusals are checked in the order `format_version` (the shared contract's),
   `draft_has_versions`, `version_not_found`, `needs_missing`.
   Enforced by: corpus: `versions-are-checked-before-the-draft-s-needs`,
   `the-version-asked-for-is-checked-before-the-draft-s-needs`.
7. `Version.format_version` is `"2a1"` for a draft's version (`1` for every other), and
   `Version.data` is the whole document.
   Enforced by: `test_reader.py::test_a_draft_version_is_marked_as_one`.

## 3. A record — `Version.records`

```json
{
  "id": "REQ_1",
  "type": "req",
  "fields": {"title": "First", "status": "open", "tags": [], "asil": "B"},
  "links": {"links": ["REQ_2", {"id": "REQ_3", "part": "p1"}], "parent_needs": []},
  "content": {"text": "…", "doctype": ".rst", "parts": {"p1": "the part"}},
  "source": [{"kind": "page", "document": "index", "semantic": [{"kind": "section", "name": "Up"}]}]
}
```

Besides which of two records with one id is read (§3.1), the order of the records and of
keys carries no meaning. sphinx-needs writes the records in the order of their ids, the
envelope's keys and a record's in the order of the examples above, and a hop's in the
order of its `NeedSourceHop` fields (`kind`, `origin`, `physical`, `semantic`,
`document`, `language`), so that a file reads the same from build to build.

### 3.1 Which records are read

1. A value of `needs` that is not an object is skipped (`record_not_object`, path
   `needs.<index>`); one with no `id` (`id_missing`, path `needs.<index>`) or an `id` that
   is not a string (`id_not_string`, path `needs.<index>.id`) is skipped too. The id is the
   record's key; `type` is beside it, never part of it.
   Enforced by: corpus: `a-record-that-is-not-an-object-is-skipped`,
   `a-record-without-an-id-is-skipped`, `a-record-whose-id-is-not-a-string-is-skipped`.
2. **Of two records with one id the first is read**, and each later one skipped and
   reported (`duplicate_id`, path `needs.<index>.id`) — as sphinx-needs keeps the first of
   two needs with one id. (Format 1's last-wins is an artefact of a JSON object's keys,
   not a choice; a draft's array has no such artefact.)
   Enforced by: corpus: `a-duplicate-id-keeps-the-first-record`.
3. These findings are the version's (`Version.diagnostics`); a finding about a record
   that is read (§3.2–§4) is the record's (`Record.diagnostics`). Records are handed out
   in the file's order.
   Enforced by: corpus: `records-keep-the-file-order`, `every-finding-of-a-draft-is-reported`.

### 3.2 The projection — `Record.fields`

A draft's record is handed out in the shape a format-1 record has, so that a reader of
format 1's records reads it unchanged. `Record.fields` is a new object of:

1. **`id`** and **`type`**, as written (`type` is not checked here, as format 1's is not;
   absent, there is no `type` key).
2. **every key of `fields`**: core and project fields in one name space — except the
   seven keys the projection owns, `id`, `type`, `content`, `doctype`, `parts`, `docname`
   and `sections`, which come only from the record itself, its `content` and its
   placement: such a key of `fields` is not read, and each is reported (`field_reserved`,
   path `needs.<index>.fields.<key>`). A `fields` that is not an object is not read
   (`fields_not_object`, path `needs.<index>.fields`).
3. **every link type of `links`**, each a list of format-1 link strings (§5). A `links`
   that is not an object is not read (`links_not_object`, path `needs.<index>.links`).
   A link type replaces a field of its name.
4. from **`content`**, an object: `content` = its `text`, `doctype` = its `doctype`, and
   `parts` = `{<part id>: {"id": <part id>, "content": <text>}}` from its `parts` (a
   `{<part id>: <text>}` object) — each only where the key is there, so a `content`
   without `text` gives no `content` key. A `content` that is
   not an object is not read (`content_not_object`, path `needs.<index>.content`). The
   values are not checked here (as format 1's are not), and a `parts` that is not an
   object is handed on as it is, for the reading project to refuse as it refuses a
   format-1 record's.
   The `parts` shape is the one format 1 writes, less the back links a draft does not
   carry: sphinx-needs' own suite pins it in
   `packages/sphinx-needs/tests/__snapshots__/test_need_parts/test_doc_need_parts[test_app0][output_needs].json`
   (`SP_TOO_001`'s `parts`).
5. from **the placement** — the last valid hop (§4) with a `document` — `docname` = its
   `document` and `sections` = the `name` of each of its `semantic` entries of kind
   `section`, **innermost first**: a hop's `semantic` is outermost first, and format 1's
   `sections` innermost first (sphinx-needs' `project_legacy` in `_need_source.py`, the
   rule that writes format 1's `sections` from the same list). A placement with no
   `semantic` has `sections` `[]`; a record with no placement has neither key.

What a draft's record does not get: format 1's legacy `description`-as-content rule
(shared contract §6.3) — a field named `description` is a field, and a record with no
`content` has none —, schema defaults, and any key a format-1 record computes (`section_name`,
`signature`, back links, `is_external`, `lineno`, …).

Each record's `fields` is a new object; its values are the document's own (the shared
contract's §6.6), except the link lists and `parts`, which the projection builds.

Enforced by: corpus: `a-record-is-projected-to-the-format-1-shape`,
`a-record-with-only-an-id-is-read`, `the-type-is-handed-on-as-written`,
`a-field-named-id-or-type-does-not-replace-them`, `no-key-the-projection-owns-is-read-from-fields`,
`fields-that-are-not-an-object-are-not-read`, `a-link-type-replaces-a-field-of-its-name`,
`links-that-are-not-an-object-are-not-read`, `a-record-without-content-has-no-content-key`,
`content-without-a-doctype-has-no-doctype-key`, `a-content-object-without-text-has-no-content-key`,
`parts-are-projected-as-format-1-writes-them`, `parts-that-are-not-an-object-are-handed-on-as-they-are`,
`content-that-is-not-an-object-is-not-read`, `the-legacy-description-is-not-the-content-in-a-draft`,
`a-record-without-a-placement-has-no-docname`, `a-record-without-a-source-has-no-docname`,
`an-include-chain-has-its-placement-last`,
`of-several-hops-with-a-document-the-last-is-the-placement`,
`the-placement-s-sections-are-innermost-first`, `a-placement-without-semantic-has-no-sections`,
`the-placement-s-keys-are-not-read-from-fields`;
`test_reader.py::test_a_null_value_of_a_draft_is_read`,
`…::test_a_draft_s_records_do_not_alter_the_document`.

### 3.3 The hops — `Record.source`

`Record.source` is the record's `source` array, **innermost first**, less every hop that
is not valid (§4), each hop **the document's own object** — not copied, as the package
validates a hop's shape but builds nothing from it. A `source` that is not an array is not
read (`source_not_a_list`, path `needs.<index>.source`) and the record has no hops. A
format-1 record's `source` is `()`. Hops are never keys of `fields`.
Enforced by: corpus: `a-source-that-is-not-an-array-is-not-read`, every case stating a
`source`; `test_reader.py::test_hops_are_the_document_s_own_objects`,
`…::test_a_format_1_record_has_no_source`.

## 4. A hop

```json
{"kind": "code", "origin": "up", "language": "cpp",
 "physical": {"root": "srcdir", "path": "src/w.cpp", "start_line": 3, "end_line": 3},
 "semantic": [{"kind": "class", "name": "Widget"},
              {"kind": "method", "name": "draw", "extras": {"qualified_name": "ns::Widget::draw"}}]}
```

One place the need's text passed through, as sphinx-needs' `NeedSourceHop` records it, a
`None` value left out. Innermost first: `source[0]` is where the text is written, the
last hop with a `document` the page the need is placed on. A writer that re-exports a
need it read appends its own hops after the ones it read, and copies those as it holds
them.

| key | shape |
|---|---|
| `kind` | a string, required; an open vocabulary (`page`, `file`, `code`, `external`, `generated`, `report`, …) |
| `origin` | a string, optional: the project the hop belongs to. **Absent, the hop is the writing project's** (the envelope's `project`); a reader that keeps hops across projects fills it so, and never changes a stated one. This package hands the hop on as written: the fill is the reading tool's |
| `document` | a string, optional: the docname, on the hop of the page the need is placed on |
| `language` | a string, optional |
| `physical` | an object, optional: `root` (a string; `"srcdir"` is the WRITER's source directory), `path` (a string, POSIX, relative to `root`), `url` (a string), `start_line` (an integer of 1 or more), `end_line` (an integer of 1 or more, and not before `start_line`), each optional. No columns |
| `semantic` | an array, optional, outermost first, of objects of a string `kind`, a string `name` and, optionally, `extras`: an object of strings |

1. A hop that is not an object, has no string `kind`, or has one of the keys above of
   another shape — `null` included — is dropped and reported (`hop_invalid`, path
   `needs.<index>.source.<position>`); the record and its other hops are read, and a
   dropped hop is not the placement.
   Enforced by: corpus: `a-hop-that-is-not-an-object-or-has-no-kind-is-dropped`,
   `a-hop-with-a-known-key-of-the-wrong-type-is-dropped`,
   `a-hop-with-an-invalid-physical-is-dropped`,
   `a-hop-with-an-invalid-semantic-entry-is-dropped`, `an-invalid-hop-is-not-the-placement`.
2. A key this reader does not know — of a hop, of its `physical`, of a `semantic` entry —
   is kept as written, and any string is a `kind`.
   Enforced by: corpus: `a-hop-of-every-known-key-is-read-as-written`,
   `unknown-hop-keys-are-kept`, `a-hop-kind-is-an-open-vocabulary`.

## 5. A link

`links` maps each link type to an array. An entry is either **a string** or **an object
`{"id", "part"?, "condition"?}`**, each a string — the link to a part, or with a
condition. There are no back links. **A string is handed on as written, and the reading
project reads it in format 1's grammar**: a `.` in it is read as a part and a `[` as the
start of a condition (where its link type parses conditions; with sphinx-needs'
`parse_conditions: False` the `[` stays in the id, as in format 1). So a writer writes a
part or a condition only as an object, and a string is a bare id only when it has
neither character.

1. The projection spells each entry as format 1 writes a link (sphinx-needs'
   `NeedLink.to_link_string`): a string as it is written, unchanged; an object as its `id`, then `.part` when
   the part is not empty, then the condition, when there is one, in brackets one deeper
   than the longest run of `]` in it — `B`, `B.p1`, `B[c]`, `B.p1[c]`, `B[[tags[0] == 'x']]`.
   That string reads back as the same link in sphinx-needs, with one exception format 1
   has too: a condition that ends in `]` does not.
   Enforced by: corpus: `a-bare-string-link-is-read-as-written`,
   `a-bare-string-is-handed-on-in-format-1-s-grammar`,
   `a-bare-string-with-brackets-is-handed-on-in-format-1-s-grammar`,
   `a-link-object-of-an-id-alone-is-its-id`, `a-link-to-a-part-is-spelled-id-dot-part`,
   `a-link-with-a-condition-is-spelled-in-brackets`, `a-link-with-a-part-and-a-condition`,
   `a-condition-with-brackets-is-bracketed-one-deeper`, `an-empty-part-is-no-part`,
   `link-spellings-keep-their-order-in-one-link-type`;
   `test_reader.py::test_a_link_object_is_spelled_as_sphinx_needs_writes_it`,
   `…::test_a_link_object_reads_back_as_the_same_link` (both where sphinx-needs is
   installed).
2. A link type whose value is not an array is not read (`link_invalid`, path
   `needs.<index>.links.<link type>`); an entry that is neither a string nor an object of
   a string `id` — and a string `part` and `condition`, where given — is dropped
   (`link_invalid`, path `needs.<index>.links.<link type>.<position>`). Any other key of a
   link object is ignored.
   Enforced by: corpus: `a-link-type-that-is-not-an-array-is-not-read`,
   `an-invalid-link-entry-is-dropped`, `unknown-keys-of-a-link-object-are-ignored`.

## 6. Refusals and findings

The refusals (`ExchangeError.code`) a draft adds to the shared contract's §8.1, and the
ones it reuses:

| code | when |
|---|---|
| `format_version_unsupported` | the draft is not asked for (§1), as for every later format |
| `draft_has_versions` | the draft has `versions` or `current_version` (§2.1) |
| `version_not_found` | the version asked for is not the draft's `project.version` (§2.4) |
| `needs_missing` | `needs` is absent or not an array (§2.2) |

The findings (`Diagnostic.code`):

| code | path | of | when |
|---|---|---|---|
| `project_invalid` | `project`, `project.name`, `project.version` | the version | §2.3 |
| `record_not_object` | `needs.<i>` | the version | §3.1 |
| `id_missing` | `needs.<i>` | the version | §3.1 |
| `id_not_string` | `needs.<i>.id` | the version | §3.1 |
| `duplicate_id` | `needs.<i>.id` | the version | §3.1 |
| `fields_not_object` | `needs.<i>.fields` | the record | §3.2 |
| `field_reserved` | `needs.<i>.fields.<key>` | the record | §3.2 |
| `links_not_object` | `needs.<i>.links` | the record | §3.2 |
| `link_invalid` | `needs.<i>.links.<t>`, `needs.<i>.links.<t>.<j>` | the record | §5.2 |
| `content_not_object` | `needs.<i>.content` | the record | §3.2 |
| `source_not_a_list` | `needs.<i>.source` | the record | §3.3 |
| `hop_invalid` | `needs.<i>.source.<j>` | the record | §4.1 |

Paths are the shared contract's (§8.3), an array's position written as its index.
Enforced by: corpus: `every-finding-of-a-draft-is-reported`;
`test_reader.py::test_a_draft_is_refused`, `…::test_the_draft_findings_messages` (the
messages, which are not the contract).

## 7. What the package does not decide

As for format 1 (shared contract §11): which of a record's keys a project takes, coercion,
ids, prefixes, how a record becomes a need. For the draft also: how a hop becomes the
reading tool's own (sphinx-needs builds a `NeedSourceHop`), filling an absent `origin`
(§4), and whether a hop of another project counts as the reading build's own.
