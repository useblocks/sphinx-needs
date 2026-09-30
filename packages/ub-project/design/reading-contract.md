# The `ubproject.toml` reading contract

This document is the **normative** specification of how the parts of `ubproject.toml`
that more than one tool reads are read: finding and loading the file, selecting a table,
anchoring a relative path, the `[variants]` table and its `[needs]` fallback, and the
variant-data merge.

It exists because the file is read by five readers in two languages — sphinx-needs,
sphinx-mounts, sphinx-codelinks, sphinx-test-reports and ubCode — and a rule that is only
written down in one of them is a rule the others will diverge from. The Python half of the
contract is this package; the executable half is the corpus
[`tests/fixtures/ubproject_reading_conformance.toml`](../tests/fixtures/ubproject_reading_conformance.toml),
which this repository holds canonically and ubCode is to vendor (its reader does not read
`[variants]` yet).

Audience: implementers of a second reader, and anyone changing this package.

Status: describes the implementation as it is. When behaviour changes, this document, the
corpus and the tests change in the same commit. Every rule names the test that enforces it;
"corpus: `name`" means the conformance case of that name, run by
`tests/test_conformance.py::test_case`.

## 1. Scope, and what is deliberately out

1. This package provides **mechanisms and no policy.** Discovery (walk up, or read a Sphinx
   `confdir`), whether a finding is worth a warning, and how a command line (`-D` in Sphinx,
   `-c` in ubCode) interacts with the file are each consumer's decision.
   Enforced by: the API itself — no function takes a logger, a Sphinx object or an
   override; §6 findings are returned (`tests/test_variants.py::TestDiagnostics`).
2. The variant-**condition** grammar (`var.edition == 'pro'`) is not here. It has its own
   corpus, `packages/sphinx-mounts/tests/fixtures/variant_condition_conformance.toml`.
3. The package imports **the standard library and nothing else**: no Sphinx, no docutils,
   no workspace member.
   Enforced by: `tests/test_imports.py::test_no_sphinx_docutils_or_sibling_is_imported`,
   `tests/test_imports.py::test_only_the_standard_library_is_imported`, and CI's
   `toolchain-free` job, which runs this suite where Sphinx is not installed.
4. Every hard failure is an `ProjectConfigError` whose message names the file (or the dotted
   path inside the data) and the rule broken. Nothing else is raised for a problem with
   the file's bytes, syntax or values. Pathological depth (input nested ~1 000 levels,
   which Python's recursion limit refuses) is out of contract.
   Enforced by: `tests/test_variants.py::TestRefusals`, `tests/test_project.py::TestLoadToml`,
   `tests/test_variant_data.py::TestValidate::test_invalid_shapes_name_the_path_and_the_rule`.

## 2. Finding the file — `find_project_config`

1. The search starts at the given directory, made absolute **without** resolving symlinks,
   and moves up one parent at a time. The first directory holding a *file* of the given
   name (default `ubproject.toml`) ends it successfully; a directory of that name is not
   the file.
   Enforced by: `tests/test_project.py::TestFindProjectConfig::test_finds_the_file_in_the_starting_directory`,
   `…::test_walks_up_to_the_repository_root`,
   `…::test_a_directory_named_like_the_file_is_not_the_file`,
   `…::test_a_relative_start_is_searched_from_the_working_directory`,
   `…::test_an_explicit_filename_is_searched_for`,
   `…::test_a_symlinked_start_walks_the_link_s_parents`.
2. The search never passes the **project boundary**: the nearest ancestor holding `.git`
   (a directory or a file); only when no ancestor holds `.git`, the nearest ancestor
   holding `pyproject.toml`; with neither, the filesystem root. The boundary directory
   itself is still searched.
   Enforced by: `…::test_stops_at_a_nested_repository_without_the_file`,
   `…::test_stops_at_the_distribution_root_without_a_repository`,
   `…::test_the_file_at_the_distribution_root_is_still_found`,
   `…::test_the_file_wins_over_the_marker_in_one_directory`.
3. Inside a repository, a `pyproject.toml` on the way up does **not** end the search: it
   marks a Python distribution (a `docs/` dependency set, a workspace member), not the
   project.
   Enforced by: `…::test_a_pyproject_toml_beside_conf_py_does_not_end_the_search`,
   `…::test_walks_past_a_workspace_member_pyproject_toml`.
4. A fruitless search calls `report` exactly once, naming the start and the boundary that
   ended it; a successful one never calls it.
   Enforced by: `…::test_a_fruitless_search_reports_where_it_ended`,
   `…::test_a_fruitless_search_reports_the_distribution_root`,
   `…::test_a_successful_search_reports_nothing`,
   `…::test_an_explicit_filename_that_is_absent_is_reported`.

Whether a consumer walks at all is its own decision (§1.1). The walk is test-reports'
existing behaviour, moved here unchanged.

## 3. Loading — `load_toml`

1. The file is parsed as UTF-8 TOML 1.0. Invalid TOML, bytes that are not UTF-8, a
   missing file, a directory and an unreadable file are each an `ProjectConfigError` naming
   the file.
   Enforced by: `tests/test_project.py::TestLoadToml` (all six tests, including
   `test_a_non_utf8_file_names_the_file`).

## 4. Selecting a table — `select_table`

1. A table path is dotted (`"tool.acme.needs"`) or a sequence of keys (for a key that
   itself contains a dot). An empty path or an empty segment is the caller's mistake
   (`ValueError`), not the file's.
   Enforced by: `tests/test_project.py::TestSelectTable::test_a_dotted_path`,
   `…::test_a_sequence_path_can_hold_a_dotted_key`,
   `…::test_a_malformed_path_is_the_callers_mistake`.
2. A segment that is **absent** makes the whole path absent (`None`). A segment that is
   present but **not a table** is an `ProjectConfigError` naming the dotted path so far — never
   read as absent. A path is spelled as TOML spells it: a segment that is not a bare key
   is quoted by the rule in §7.2 (`tool."acme.docs".needs`), in messages and in diagnostic
   paths.
   Enforced by: `…::test_an_absent_table_is_none`,
   `…::test_a_segment_that_is_not_a_table_is_an_error`,
   `…::test_the_last_segment_not_a_table_is_an_error`; corpus:
   `prefix-segment-not-a-table`.

## 5. Anchoring — `anchor`

1. A relative path read from the file is anchored at **the directory of the file that
   declared it** — not a consumer's `confdir`, not the working directory.
   Enforced by: `tests/test_project.py::TestAnchor::test_a_relative_value_is_joined_onto_the_base`,
   `tests/test_variants.py::TestAnchoring::test_a_relative_data_file_is_anchored_at_the_toml_directory`;
   corpus: `relative-file-anchors-at-the-toml-directory`,
   `legacy-relative-file-anchors-at-the-toml-directory`.
2. Anchoring **joins** and does nothing else: symlinks are not resolved and `..` is not
   folded away. Whether to normalise is the consumer's decision (mounts resolves, for
   symlink confinement; test-reports keeps the form it was handed).
   Enforced by: `tests/test_project.py::TestAnchor::test_a_symlinked_base_is_not_resolved`,
   `tests/test_project.py::TestAnchor::test_a_parent_segment_is_kept`,
   `tests/test_variants.py::TestAnchoring::test_a_symlinked_toml_directory_is_not_resolved`;
   corpus: `relative-file-with-parent-segment-is-joined`.
3. An absolute path is returned untouched — a `..` in it is kept, and a symlink in it is
   not resolved.
   Enforced by: `tests/test_project.py::TestAnchor::test_an_absolute_value_is_untouched`,
   `tests/test_project.py::TestAnchor::test_an_absolute_value_with_a_parent_segment_is_untouched`,
   `tests/test_project.py::TestAnchor::test_an_absolute_value_through_a_symlink_is_untouched`;
   corpus: `absolute-file-is-untouched`.

## 6. The `[variants]` table — `read_variants`

```toml
[variants]
data_file = "variants.json"   # ONE path, a string
[variants.data]               # an inline table, deep-merged over the file
edition = "pro"
```

1. **Keys.** `[variants]` defines exactly two keys: `data`, a table, and `data_file`, one
   non-empty path string. A list of paths is refused, not read as its first entry.
   Enforced by: `tests/test_variants.py::TestRefusals` (`data-not-a-table`,
   `data-file-a-list`, `data-file-empty`); corpus: `data-not-a-table`,
   `data-file-is-one-string-not-a-list`, `data-file-empty-string`.
2. **The legacy location** is `[needs] variant_data` (a table) and
   `[needs] variant_data_file` (one path), held to the same types. The `[needs]` table's
   path is a parameter, so a consumer that nests it (`[tool.acme.needs]`) reads it there;
   `[variants]` is always read from the top level of the table given. The prefix is a
   Python consumer's option (sphinx-needs' `needs_from_toml_table`); ubCode's `[needs]` is
   always top-level, so the corpus cases that carry `needs_table` are Python-only (§9.4).
   Enforced by: `tests/test_variants.py::TestPrefix`, `TestRefusals`
   (`legacy-data-not-a-table`, `legacy-data-file-not-a-string`); corpus:
   `needs-under-a-dotted-prefix`, `prefix-ignores-a-top-level-needs`,
   `prefix-with-variants-set`, `legacy-data-not-a-table`.
3. **Declaring.** A location is *declared* when at least one of its two keys is set to a
   value — including `data = {}`. A `[variants]` table holding neither (empty, or only
   unknown keys) declares nothing, so it can never switch a project's `[needs]` data off.
   (TOML has no null; a Python caller's `None` is absent, as it is in `select_table`.)
   Enforced by: `tests/test_variants.py::TestPrecedence::test_an_empty_variants_table_declares_nothing`,
   `…::test_an_empty_inline_table_is_a_declaration`,
   `…::test_a_none_value_declares_nothing`,
   `TestDiagnostics::test_unknown_keys_do_not_declare_variants`; corpus:
   `empty-variants-table-alone`, `empty-variants-table-falls-back`,
   `empty-inline-table-declares-variants`, `unknown-keys-only-fall-back`.
4. **Precedence is whole-location.**

   | declared | read | findings |
   | --- | --- | --- |
   | `[variants]` only | `[variants]` | — |
   | `[needs]` only | `[needs]` | `variant_data_legacy_location` per key read |
   | both | `[variants]` | `variant_data_location` per `[needs]` key ignored |
   | neither | nothing: `{}`, no file | — |

   Both keys always come from ONE table; a `[needs]` file is never merged under a
   `[variants]` inline table, nor the reverse. The ignored location's keys are not read,
   so a missing or malformed file there is no error; its table must still be a table
   (§4.2).
   Enforced by: `tests/test_variants.py::TestPrecedence` (the whole class); corpus: the seven
   `neither-location` … `needs-file-and-data` cases, the nine `both-*` cases (every
   combination of keys on each side), and `ignored-location-is-not-read`.
5. **`[variants]` is refused if it is not a table.** The name is this contract's; reading
   `variants = [...]` as "no variant data" would be exactly the silent vanishing the table
   exists to end.
   Enforced by: `tests/test_variants.py::TestRefusals` (`variants-not-a-table`); corpus:
   `variants-not-a-table`.
6. **Unknown keys inside `[variants]` are tolerated**, each reported as
   `variants_unknown_key`, never an error: several tool versions read this table at once,
   and one that aborted on a key from a newer version would take the whole build down.
   The legacy spelling `variant_data` inside `[variants]` is such an unknown key.
   Enforced by: `tests/test_variants.py::TestDiagnostics::test_an_unknown_key_in_variants_is_reported_not_raised`;
   corpus: `unknown-key-beside-data`, `legacy-spelling-inside-variants-is-unknown`.
7. The result carries `data` (the merged map, §8.4), `data_file` (the anchored file of the
   location read, or `None`), `location` (`"variants"`, `"needs"` or `None`) and
   `diagnostics`.

## 7. Diagnostics

1. Findings are **returned**, never logged, as `Diagnostic(code, path, message, severity)`.
   `code`, `path` and `message` are those of ubCode's `ConfigResolutionDiagnostic`;
   `severity` is this package's. Hard failures are never diagnostics (§1.4).
2. The codes are fixed, and they are the **bare subcodes**. ubCode is to carry them under
   its own `config.` prefix (`config.variant_data_location`), by its convention for
   fine-grained configuration diagnostics (`code` is optional there, and its variant-data
   diagnostics carry none today); the corpus compares the bare subcode, and ubCode's
   runner strips `config.` before comparing.

   | code | severity | `path` | when |
   | --- | --- | --- | --- |
   | `variant_data_location` | warning | the ignored key, e.g. `needs.variant_data_file` | both locations declared; one per ignored `[needs]` key |
   | `variant_data_legacy_location` | info | the key read, e.g. `needs.variant_data` | the data came from `[needs]`; one per key read |
   | `variants_unknown_key` | warning | `variants.<key>` | an unknown key in `[variants]`; one per key |

   `variant_data_legacy_location` is **informational and takes no side**: sphinx-needs
   will warn on it to move its users, ubCode will not because it supports several
   sphinx-needs versions at once. A path under a prefix carries the prefix
   (`tool.acme.needs.variant_data`).

   **Path spelling, for every reader.** A `path` is dotted, one segment per key. A segment
   matching `[A-Za-z0-9_-]+` is written as a TOML bare key; any other is written as a TOML
   basic string with TOML's escapes — `"` and `\` backslash-escaped, control characters as
   `\b \t \n \f \r` or `\uXXXX` — and every other character as itself: `variants."a.b"`,
   `variants."café"`, `tool."acme.docs".needs.variant_data`. A rendered segment is TOML
   that names the same key again. ubCode is to render the same.
   Enforced by: `tests/test_variants.py::TestDiagnostics` (codes, paths, severities;
   `test_a_non_bare_key_is_a_toml_basic_string_in_the_path` for the examples,
   `test_a_rendered_path_reads_back_as_the_same_key` for the escapes); corpus:
   `unknown-keys-are-rendered-as-toml`;
   corpus: every non-refusal case compares codes and paths.
3. Order is stable — unknown keys sorted, then location findings in `variant_data`,
   `variant_data_file` order — but a second reader need not reproduce it: the corpus
   compares findings as a multiset. Message wording is not part of the contract.
   Enforced by: `tests/test_variants.py::TestDiagnostics::test_an_unknown_key_in_variants_is_reported_not_raised`,
   `…::test_both_set_names_every_ignored_key`,
   `…::test_unknown_keys_do_not_declare_variants`.

## 8. Variant data

1. **Shape.** A variant map is a table with string keys whose values are `str`, `bool`,
   `int` or `float`; arrays that are empty or hold scalars of ONE exact type (`[1, true]`
   and `[1, 1.5]` are mixed); or tables of the same shape. Anything else — `null`, a
   date-time, an array of tables or of arrays — is refused, naming the dotted path
   (`var.build.opt`).
   Enforced by: `tests/test_variant_data.py::TestValidate`; corpus: `valid-every-shape`,
   `invalid-mixed-array`, `invalid-bool-int-array`, `invalid-int-float-array`,
   `invalid-array-of-tables`, `invalid-datetime-value`, `invalid-null-in-file`.
2. **The data file** is JSON, UTF-8, holding an object of that shape, validated ON ITS
   OWN before the merge: an inline value cannot rescue an invalid file value. A missing
   file, a directory (reported as one), undecodable content and a non-object are each
   refused, naming the file.
   Enforced by: `tests/test_variant_data.py::TestLoad`; corpus: `missing-data-file`,
   `missing-legacy-data-file`, `invalid-file-not-json`, `invalid-file-not-an-object`,
   `invalid-file-value-overridden-by-valid-inline`.
3. **The merge** (`deep_merge`) recurses only where BOTH sides hold a table under the same
   key; everywhere else the override replaces the base wholesale — an array replaces an
   array, a scalar a table and a table a scalar. `false` is a value, not an absence.
   Neither input is modified. The merge is idempotent:
   `deep_merge(base, deep_merge(base, override)) == deep_merge(base, override)`.
   The result is plain tables (Python: `dict`) at every level the merge builds, whatever
   mapping type came in — an input TOML or JSON can express only as plain tables anyway.
   Enforced by: `tests/test_variant_data.py::TestDeepMerge` (including
   `test_does_not_mutate_either_side` and `test_is_idempotent` over every merge shape);
   corpus: the eight `merge-*` cases.
4. **Resolution** (`resolve_variant_data`) loads the file, validates the inline table, and
   deep-merges the inline table over the file. It always returns a **new** mapping —
   never the caller's inline table, even when there is no file — so a consumer may store
   and change the result without changing its own configuration.
   (Not normative, and not reproducible by a second reader: in this implementation a
   nested value taken whole from one side is that side's object.)
   Enforced by: `tests/test_variant_data.py::TestResolve::test_returns_a_fresh_mapping_with_no_file`,
   `…::test_returns_a_fresh_mapping_with_an_empty_inline_table`,
   `…::test_is_idempotent_over_an_already_merged_inline_map`.

## 9. The corpus

1. `tests/fixtures/ubproject_reading_conformance.toml` is canonical **here**; ubCode is
   to vendor it byte-for-byte with a provenance block prepended. Its header states the
   case format and the rules for every runner. A change to it is a change to this
   contract and owes ubCode a re-vendor.
2. Its bytes are protected: `.gitattributes` pins LF line endings, and the taplo and
   yamlfmt hooks exclude it — taplo, measured, would otherwise rewrap eleven expectation
   lines.
3. `tests/test_conformance.py` runs every case and pins the case COUNT, so a trimmed
   corpus is a red test.
   Enforced by: `tests/test_conformance.py::test_the_corpus_still_has_every_case`,
   `…::test_every_case_has_a_complete_expectation`,
   `…::test_the_corpus_header_records_where_it_is_canonical`.
4. **Rules for every runner** (stated in the header too): a case writes only inside its
   own directory; a case carrying `needs_table` is Python-only and ubCode's runner skips
   it; codes compare as the bare subcode; integers beyond the signed 64-bit range are
   unspecified. A refusal is compared as a refusal, not by its reason — two rows
   (`data-file-empty-string`, `invalid-file-not-an-object`) would refuse for another
   reason too, and the unit tests pin their actual rule.
   Enforced by: `tests/test_conformance.py::test_a_case_cannot_write_outside_its_directory`.

## 10. For consumers

What a consumer has to do that this package deliberately does not:

1. **Map `""` to `None` before calling.** On the `conf.py` / `-D` route both sphinx-needs
   (`needs_variant_data_file = ""`) and sphinx-mounts read an empty data-file value as "no
   file". This package takes `Path | None` and refuses an empty `data_file` in the TOML
   (§6.1), so a consumer keeps its own route's meaning by mapping `""` to `None` itself.
2. **Decide what each finding is worth** (§7): warn, log at a verbose level, or drop.
3. **Re-raise `ProjectConfigError` in its own vocabulary** (§1.4): a Sphinx configuration
   error, a non-zero exit.
