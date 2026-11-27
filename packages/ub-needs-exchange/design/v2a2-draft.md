# needs.json format "2a2" — a draft, read on opt-in

This document is the specification of the **draft** needs.json format `"2a2"` as this
package reads it: the envelope, the record, its parts, the hop and the link shapes, how a
record is projected to the shape a format-1 record has, and the findings reported on the
way.

**Experimental.** `"2a2"` is the second alpha of the next format (format 2). It may change,
or be removed, in any release while it is a draft, and a file of it is **readable only by
the release that wrote it**: nothing promises that a later release reads a `"2a2"` file,
or that a reader of a later draft does. A reader reads it only when asked to (§1); without
that, a `"2a2"` file is refused exactly as the shared contract refuses every later format
([`exchange-contract.md`](exchange-contract.md) §3.1), so the shared contract and its
corpus are unchanged by it.

**It replaces the first alpha, `"2a1"`**, which ub-needs-exchange 1.2.0 read: this reader
reads `"2a2"` and no other draft, and a `"2a1"` file is refused as every later format is
(§1). Two things changed from `"2a1"`, and nothing else: a need's parts are a section of
the record beside its content, in the need's order, kept where the content is left out
(§3.4), and a link to the empty part is spelled `B.`, the dead link it is (§5.1), where
`"2a1"` read it as a link to the need.

Its executable half is this package's own corpus,
[`tests/fixtures/needs_json_2a2_draft_conformance.toml`](../tests/fixtures/needs_json_2a2_draft_conformance.toml),
run by `tests/test_draft_conformance.py`; "corpus: `name`" below is a case of it, and
`test_reader.py::…` a unit test. It is not the shared reading corpus: it is this
package's own, and ubCode vendors a copy of it, which follows each draft.

Status: describes the implementation as it is (ub-needs-exchange, unreleased: 1.2.0
read `"2a1"`).

## Why a format 2

A needs.json is no longer only a project writing its needs and reading them back. It is
the file other programs hand needs to sphinx-needs in (code traced by sphinx-codelinks,
test results converted by ub-test-reports, requirements exported from other tools), the
file one project imports another's needs from (`needimport`, `needs_external_needs`), and
a build artefact passed between build steps and kept as a baseline. Format 1 was designed
for the first of these, and falls short of the others:

1. **Where a need came from is two keys.** A record says where it is placed (`docname`,
   `lineno`, `sections`), not where its text was written: the file it is written in when
   that is an included fragment, the files it was included through, the code entity a
   marker is attached to, the project that wrote it. A need imported and written again
   by the importing project names the importing page and the `needimport` line, so the
   place it was first written is lost one hop later.
2. **Authored values are mixed with computed ones.** Beside the fields a need was given,
   a default record carries values a reader must know to ignore or recompute: back links
   (`<link type>_back`), `is_import` and `is_external`, the type's configured
   `type_name`, `external_css`, `parent_need`, `is_modified`, `modifications`,
   `constraints_passed` and the other `constraints_*` results, and `has_dead_links`.
3. **Links are strings with a grammar.** A link to a part, or under a condition, is
   written `ID.part[condition]` and parsed back by the reader. The grammar has no escape,
   so an id containing `.` or `[` cannot be written unambiguously.
4. **The file says little about itself.** No format-1 writer writes `format_version`;
   values equal to their default can be left out (`needs_json_remove_defaults`) and are
   restored from the version's one `needs_schema`, not per need type; and
   `versions` holds several snapshots in one file, so every reader has to pick one.

## Design goals

For format 2 as a whole; §§1–7 are how far this draft goes.

1. **Provenance across hops.** Every need records where its text came from, as a list of
   hops, innermost first: the place it is written, each file it was included through,
   the needs.json it was read from, the page it is placed on. A reader appends its own
   hops and never rewrites another project's, so a need passed through several projects
   still names where it was first written, and which project each hop belongs to (§4).
2. **Authored data only.** A record holds what was authored: fields, links, content, and
   its source. Everything a reader can derive is left out: `docname`, `sections`,
   `section_name` and `signature` are derived from the hop a need is placed by (§3.2).
3. **Unambiguous values.** A link with a part or a condition is an object, not a spelling
   to parse (§5); the content is an object, so the markup it is written in can be named
   beside it later.
4. **Self-describing.** The file names its format (`format_version`), the project that
   wrote it and the program; one file is one snapshot of one project version.
5. **Room to grow by adding keys.** Records are an array of objects that each carry their
   `id`, so an id namespace is a key added later, not a reshape; the same holds for the
   pieces left out below.
6. **One contract, read the same everywhere.** Every tool reads the format by this
   specification and its corpus. A reader of format 1 refuses a later format with its own
   message rather than read it wrongly ([`exchange-contract.md`](exchange-contract.md)
   §3.1).
7. **Drafts before a promise.** The format evolves through drafts (`"2a1"`, `"2a2"`,
   `"2b1"`, …) readable only by the release that wrote them, each replacing the one before
   it, then a final `2` that is kept readable.

### What this draft leaves for later ones

- **Id namespaces** (a record's `ns`).
- **A schema block per need type**, and with it defaults left out of records: until then
  a writer writes every value of the fields the need's type declares that is not `null`,
  defaults and typed empties (`[]`, `""`) included, so a record reads the same without a
  schema. A field whose value is `null` is left out, and a reader reads it as unset (§3).
  Whether a type declares a field a record leaves unset is schema information, and
  returns with that block.
- **An origins table** in the envelope (each upstream project's name, URL patterns,
  revision and roots), so URLs are composed on read rather than stored per need.
- **Where a part came from.** A part is an id and its text (§3.4); the key `anchor` of a
  part entry is reserved for a later draft (a span of the content), and a reader ignores
  it. Its absence says nothing: a part its content marks need not have a place in the
  content's text (one written in an included file has none), so a part without an anchor
  is not thereby a part the record states. No other marker of a part's origin is
  written either, and how a reader treats a part its content does not mark is the
  reading tool's (sphinx-needs and ubCode keep it as a stated part).
- **The content's markup** (`doctype` stays as format 1 has it), and the **fields a view
  renders a need by** (layout, style, collapse and the like are fields, as in format 1).
- **Link properties**: a link is an id, a part and a condition (§5), nothing more.
- **Extend records** (what a `needextend` changed, with its own source), **columns** in a
  hop's region, and **hops for items of other systems** (an issue tracker, a
  requirements tool).

## 1. The opt-in — `Document.select_version(requested, *, drafts=())`

1. `drafts` names the drafts the call reads, besides format 1. There is one: `"2a2"`. A
   file whose `format_version` is a draft asked for is read as this document says; any
   other file is read, or refused, exactly as without `drafts` — a format-1 file as the
   shared contract says, any other later format refused (`format_version_unsupported`),
   `"2a1"`, `"2b1"` and `2` included.
   Enforced by: corpus: `a-draft-is-read-on-opt-in`,
   `the-opt-in-reads-only-the-draft-it-names`, `a-2a1-file-is-refused-on-opt-in`,
   `the-opt-in-reads-no-later-integer-format`,
   `a-format-1-file-is-read-as-before-on-opt-in`; `test_reader.py::test_drafts_is_any_collection`,
   `…::test_a_2a1_file_is_refused_exactly_as_without_the_opt_in`.
2. Without `"2a2"` in `drafts`, a `"2a2"` file is refused with the shared contract's code
   and message, and so is a `"2a1"` file.
   Enforced by: corpus: `without-the-opt-in-a-draft-is-refused`,
   `a-2a1-file-is-refused-without-the-opt-in`; the shared corpus's
   `format-version-a-pre-release-is-refused` and
   `format-version-is-checked-whatever-version-is-asked-for`;
   `test_reader.py::test_without_the_opt_in_a_draft_is_refused_exactly_as_before`;
   `test_draft_conformance.py::test_the_shared_corpus_keeps_a_draft_refused`.
3. A `drafts` entry naming a draft this reader does not know is a programming error, not a
   finding about a file: `ValueError`, before the file is looked at — `"2a1"` among them,
   alone or beside `"2a2"`. A string is a collection of its characters, so `drafts="2a2"`
   is one too.
   Enforced by: `test_reader.py::test_an_unknown_draft_is_a_programming_error`.

## 2. The envelope

```json
{
  "format_version": "2a2",
  "project": {"name": "up", "version": "1.0"},
  "creator": {"program": "sphinx_needs", "version": "9.4.0"},
  "created": "2026-11-05T00:00:00",
  "needs": [{"id": "REQ_1", "type": "req", "fields": {"title": "…"}}]
}
```

1. **No `versions` and no `current_version`.** A draft has one version, the document
   itself. A `"2a2"` file that has either key, whatever its value, is refused
   (`draft_has_versions`): a reader of format 1 that does not check `format_version` —
   sphinx-needs 9.0.0 with ub-needs-exchange 1.0.0 is one — reads such a file as format 1,
   silently, so no `"2a2"` file carries them.
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
   the draft writes every field value that is not `null`, defaults included, and leaves
   out a field whose value is `null` (§3).
   Enforced by: corpus: `unknown-envelope-keys-of-a-draft-are-ignored`;
   `test_reader.py::test_a_draft_has_no_schema_defaults`.
6. The refusals are checked in the order `format_version` (the shared contract's),
   `draft_has_versions`, `version_not_found`, `needs_missing`.
   Enforced by: corpus: `versions-are-checked-before-the-draft-s-needs`,
   `the-version-asked-for-is-checked-before-the-draft-s-needs`.
7. `Version.format_version` is `"2a2"` for a draft's version (`1` for every other), and
   `Version.data` is the whole document.
   Enforced by: `test_reader.py::test_a_draft_version_is_marked_as_one`.

## 3. A record — `Version.records`

```json
{
  "id": "REQ_1",
  "type": "req",
  "fields": {"title": "First", "status": "open", "tags": [], "asil": "B"},
  "links": {"links": ["REQ_2", {"id": "REQ_3", "part": "p1"}], "parent_needs": []},
  "content": {"text": "…", "doctype": ".rst"},
  "parts": [{"id": "p1", "text": "the part"}],
  "source": [{"kind": "page", "document": "index", "semantic": [{"kind": "section", "name": "Up"}]}]
}
```

**A `null` field value is left out.** A writer leaves out a field whose value is `null`
(and writes every other value, a default or a typed empty such as `[]` or `""`
included); a reader reads a missing field as unset — the projection has no key for it,
and the reading project applies its own default (sphinx-needs reads a `null` that way
too). A reader still reads a `null` a writer did not leave out, as `null`.
Enforced by: corpus: `a-field-left-out-is-unset-and-a-null-is-read-as-null`;
`test_reader.py::test_a_null_value_of_a_draft_is_read`.

Besides which of two records with one id is read (§3.1) and the order of a record's
parts (§3.4), the order of the records and of keys carries no meaning. sphinx-needs
writes the records in the order of their ids, the envelope's keys and a record's in the
order of the examples above, and a hop's in the
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
   nine keys the projection owns, `id`, `type`, `content`, `doctype`, `parts`, `docname`,
   `sections`, `section_name` and `signature`, which come only from the record itself,
   its `content`, its `parts` and its placement: such a key of `fields` is not read, and each is reported (`field_reserved`,
   path `needs.<index>.fields.<key>`). A `fields` that is not an object is not read
   (`fields_not_object`, path `needs.<index>.fields`).
3. **every link type of `links`**, each a list of format-1 link strings (§5). A `links`
   that is not an object is not read (`links_not_object`, path `needs.<index>.links`).
   A link type replaces a field of its name.
4. from **`content`**, an object: `content` = its `text` and `doctype` = its `doctype` —
   each only where the key is there, so a `content` without `text` gives no `content` key.
   A `content` that is not an object is not read (`content_not_object`, path
   `needs.<index>.content`). The values are not checked here (as format 1's are not). Any
   other key of `content` is ignored, with no finding — `parts` among them, where `"2a1"`
   wrote a need's parts: a `"2a2"` record's parts are its own section.
5. from **`parts`**, the record's section (§3.4): `parts` = `{<part id>: {"id": <part
   id>, "content": <text>}}`, one key per entry read, in the section's order — whether
   the record has a `content` or not. A record with no `parts`, or an empty one, has no
   `parts` key. The shape is the one format 1 writes, less the back links a draft does not
   carry: sphinx-needs' own suite pins it in
   `packages/sphinx-needs/tests/__snapshots__/test_need_parts/test_doc_need_parts[test_app0][output_needs].json`
   (`SP_TOO_001`'s `parts`).
6. from **the placement** — the last valid hop (§4) with a `document` — `docname` = its
   `document` and `sections` = the `name` of each of its `semantic` entries of kind
   `section`, **innermost first**: a hop's `semantic` is outermost first, and format 1's
   `sections` innermost first (sphinx-needs' `project_legacy` in `_need_source.py`, the
   rule that writes format 1's `sections` from the same list). From the same list, as
   format 1 writes them: `section_name` = the first of those `sections` (the innermost),
   or `null` when there is none (sphinx-needs' `NeedItem`, whose `section_name` is
   `sections[0]` or `None`), and `signature` = the `signature` extra of the innermost
   `semantic` entry whose `kind` is not `section` and whose `signature` is not empty, or
   `null` when there is none (`project_legacy`, `_need_source.py` lines 1263–1280 at
   `75267db20`). A placement with no `semantic` has `sections` `[]` and a `null`
   `section_name` and `signature`; a record with no placement has none of the four keys.
   Only the placement gives them: a domain object on another hop (an upstream page)
   gives no `signature`.

What a draft's record does not get: format 1's legacy `description`-as-content rule
(shared contract §6.3) — a field named `description` is a field, and a record with no
`content` has none —, and schema defaults. **Nor does it get any other key a format-1
record can carry**, in two groups:

- the keys **a default format-1 file writes** on every record, which the projection does
  not give: `lineno`, `is_import`, `is_external`, `external_url`, `type_name`,
  `external_css`, the back links (`<link type>_back`), `parent_need`, `is_modified`,
  `modifications`, `constraints_passed`, `constraints_results`, `constraints_error`,
  `has_dead_links`, `has_forbidden_dead_links` and `arch`; and `template`,
  `pre_template`, `post_template`, `pre_content`, `post_content` and `jinja_content`,
  which a draft's writer leaves out (they are read from `fields` only where a writer
  puts them there);
- the keys **a default format-1 file leaves out** (sphinx-needs'
  `needs_json_exclude_fields` default, the core fields marked `exclude_json`), which a
  format-1 file carries only when a project changes that option: `lineno_content`,
  `type_prefix`, `type_color`, `type_style`, `is_need`, `is_part`, `id_parent` and
  `id_complete` — and `collapse` and `hide`, which are fields, and are in a draft's
  `fields` where its writer writes them.

A reader that filters or renders over a record's keys (sphinx-needs' `needimport`
`:filter:`, an external source's `target_url`) finds them absent in a draft's record.

Each record's `fields` is a new object; its values are the document's own (the shared
contract's §6.6), except the link lists and `parts`, which the projection builds — `parts`
and each of its part objects new.

Enforced by: corpus: `a-record-is-projected-to-the-format-1-shape`,
`a-record-with-only-an-id-is-read`, `the-type-is-handed-on-as-written`,
`a-field-named-id-or-type-does-not-replace-them`, `no-key-the-projection-owns-is-read-from-fields`,
`fields-that-are-not-an-object-are-not-read`, `a-link-type-replaces-a-field-of-its-name`,
`links-that-are-not-an-object-are-not-read`, `a-record-without-content-has-no-content-key`,
`content-without-a-doctype-has-no-doctype-key`, `a-content-object-without-text-has-no-content-key`,
`content-parts-are-not-read`, `content-that-is-not-an-object-is-not-read`,
`parts-are-projected-as-format-1-writes-them`, `the-legacy-description-is-not-the-content-in-a-draft`,
`a-record-without-a-placement-has-no-docname`, `a-record-without-a-source-has-no-docname`,
`an-include-chain-has-its-placement-last`,
`of-several-hops-with-a-document-the-last-is-the-placement`,
`the-placement-s-sections-are-innermost-first`, `a-placement-without-semantic-has-no-sections`,
`the-section-name-is-the-innermost-section`, `a-domain-object-of-the-placement-gives-the-signature`,
`the-signature-skips-an-entry-without-one`, `a-signature-extra-on-a-section-is-not-the-signature`,
`only-the-placement-gives-the-signature`,
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

### 3.4 The parts — `parts`

```json
"parts": [{"id": "zeta", "text": "last id first"}, {"id": "alpha", "text": "first id second"}]
```

A key of the record beside `content` — not under it, and not the content's: a record
whose content a writer leaves out keeps its parts, with their texts. An array of the
need's parts, **in the need's order** (sphinx-needs': the parts its content marks in the
order written, then the parts the need states, in the order given), each an object of a
string `id` and a string `text`, the part's text as the need holds it. A writer writes
no `parts` for a need without parts (never `[]`), and sorts nothing.

1. **The order is the section's.** The projection (§3.2) lists the parts in the order of
   the entries read; a reader never sorts them.
   Enforced by: corpus: `parts-keep-the-order-the-file-gives-them`,
   `an-invalid-part-entry-is-dropped`;
   `test_reader.py::test_the_parts_are_projected_in_the_section_s_order`.
2. A `parts` that is not an array — `"2a1"`'s object of part id to text among them, and
   `null`, which is not an array like any other value that is not one — is
   not read (`parts_not_a_list`, path `needs.<index>.parts`): the record has no `parts`
   key, and the rest of it is read. An empty array is no parts: no key and no finding.
   Enforced by: corpus: `parts-that-are-not-an-array-are-not-read`,
   `parts-that-are-null-are-not-read`,
   `an-empty-parts-array-gives-no-parts-key`, `a-record-without-parts-has-no-parts-key`;
   `test_reader.py::test_a_null_parts_is_not_an_array`.
3. An entry that is not an object, or whose `id` or `text` is absent or not a string, is
   dropped (`part_invalid`, path `needs.<index>.parts.<position>`): the other entries and
   the record are read, nothing is turned into text, and a dropped entry claims no id.
   Enforced by: corpus: `an-invalid-part-entry-is-dropped`.
4. **Of two entries with one id the first is read**, at its place, and each later one
   skipped (`duplicate_part_id`, path `needs.<index>.parts.<position>.id`) — as a need
   keeps the first part of an id. Two ids are one id only when they are the same string:
   no case folding, no trimming, no normalisation.
   Enforced by: corpus: `the-first-part-of-an-id-is-read`,
   `part-ids-are-compared-as-written`; `test_reader.py::test_part_ids_are_compared_as_written`.
5. An entry whose `id` is the empty string is well shaped, and projected as any other
   (under the key `""`), with no finding here: a part id cannot be empty, and the reading
   project refuses the need, as it refuses a format-1 record that states an empty part id
   (sphinx-needs: `Part must have a non-empty string ID: ''`, the need not imported).
   Enforced by: corpus: `an-empty-part-id-is-handed-on`; sphinx-needs'
   `tests/test_needs_json_draft_roundtrip.py`, on both routes.
6. Any other key of an entry is ignored, with no finding — `anchor`, which a later draft
   may give a part, among them.
   Enforced by: corpus: `unknown-keys-of-a-part-are-ignored`.
7. A record's `parts` do not depend on its `content`: a record with `parts` and no
   `content` has the `parts` key and no `content` key, as a format-1 record written
   without its content has.
   Enforced by: corpus: `parts-are-read-without-content`.

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
them — so what survives a re-export is what that writer holds: sphinx-needs holds a hop
as its `NeedSourceHop`, and a re-export by it writes only the keys the table below
names, so a hop key another writer added (§4.2) does not survive a sphinx-needs
re-export (in 2a2).

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
   `NeedLink.to_link_string`): a string as it is written, unchanged; an object as its `id`,
   then `.part` where it has a `part`, then the condition, when there is one, in brackets
   one deeper than the longest run of `]` in it — `B`, `B.p1`, `B[c]`, `B.p1[c]`,
   `B[[tags[0] == 'x']]`. **The empty part is a part**: `{"id": "B", "part": ""}` is `B.`,
   and with a condition `B.[c]` — a link to a part no need can have, which the reading
   project reads as the dead link it is, as it reads format 1's `B.` (`"2a1"` spelled it
   `B`, a link to the need).
   A condition that starts with `[` (after any spaces) and ends with `]` is spelled with
   one space after the opening brackets, which the reader drops — `B[[ [x] == a[0]]]`.
   That string reads back as the same link in sphinx-needs, with one exception format 1
   has too: an object whose `id` contains `.` or `[` does not (the string grammar has no
   escape, so the reader reads that `.` as a part and that `[` as a condition). An empty
   condition is spelled `B[]`, which reads as no condition.
   Enforced by: corpus: `a-bare-string-link-is-read-as-written`,
   `a-bare-string-is-handed-on-in-format-1-s-grammar`,
   `a-bare-string-with-brackets-is-handed-on-in-format-1-s-grammar`,
   `a-link-object-of-an-id-alone-is-its-id`, `a-link-to-a-part-is-spelled-id-dot-part`,
   `a-link-with-a-condition-is-spelled-in-brackets`, `a-link-with-a-part-and-a-condition`,
   `a-condition-with-brackets-is-bracketed-one-deeper`, `a-condition-that-ends-in-a-bracket`,
   `a-condition-that-starts-and-ends-with-a-bracket-is-spelled-with-a-space`,
   `an-empty-part-is-the-empty-part`, `an-empty-part-with-a-condition`,
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
| `format_version_unsupported` | the draft is not asked for, or the file is of the draft `"2a1"` it replaces (§1), as for every later format |
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
| `parts_not_a_list` | `needs.<i>.parts` | the record | §3.4.2 |
| `part_invalid` | `needs.<i>.parts.<j>` | the record | §3.4.3 |
| `duplicate_part_id` | `needs.<i>.parts.<j>.id` | the record | §3.4.4 |

Paths are the shared contract's (§8.3), an array's position written as its index.
Enforced by: corpus: `every-finding-of-a-draft-is-reported`;
`test_reader.py::test_a_draft_is_refused`, `…::test_the_draft_findings_messages`,
`…::test_the_draft_parts_findings_messages` (the messages, which are not the contract).

## 7. What the package does not decide

As for format 1 (shared contract §11): which of a record's keys a project takes, coercion,
ids, prefixes, how a record becomes a need. For the draft also: how a hop becomes the
reading tool's own (sphinx-needs builds a `NeedSourceHop`), filling an absent `origin`
(§4), and whether a hop of another project counts as the reading build's own.
