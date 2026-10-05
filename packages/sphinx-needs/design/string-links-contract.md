# The string-links contract

A *string link* turns a need field's value — `AB-1`, a commit URL — into a hyperlink, by
searching the value with a regular expression and rendering the named groups into a URL
template and a name template. Two engines render string links from the same sources:
sphinx-needs (`needs_string_links` in `conf.py`, or `[needs.string_links.<name>]` in
`ubproject.toml`) and ubCode, useblocks' Rust-based tooling for needs projects
(`[needs.string_links.<name>]`). This file records why a string link is moving onto the field
it applies to, specifies the per-field model both engines implement, and lists, row by row,
where the two engines agree and where they do not.

sphinx-needs is the repository of record for this file; ubCode's design documents cite it by
path, as they cite `needstable-contract.md`. The issue is useblocks/sphinx-needs#2048.

## 0. Decision record

**A string link is per-field in everything but its syntax.** Each `needs_string_links` entry
names the fields it applies to in `options`, and a renderer only ever uses the FIRST declared
entry naming a field (sphinx-needs: `matching_link_confs[0]` in `match_string_link`; ubCode:
`rules.iter().find(…)` in `StringLinkRegistry::link`). So one field has at most one effective
rule — a per-field property stored in a global table under an arbitrary name.

**The precedent is `needs_global_options` → `default`.** `needs_global_options` held per-field
defaults in a global table keyed by field name; sphinx-needs folded each entry onto the field
definition (`FieldSchema.default`, `FieldSchema.predicate_defaults`, set after construction in
`create_schema`), deprecated the table, and the field definition became the one place to read
what a field is. A string link is the presentation half of the same object, and joins the
same family of sibling keys (`default`, `nullable`, `allow_extend`, `parse_variants`,
`parse_dynamic_functions`, `predicate_defaults`, `directive_option`).

**The rule lives on the field definition object, never in a side table** (user ruling,
2026-10-05). A name-keyed side table would keep today's behaviour for names that have no
field definition, but it defeats the purpose — the rule would not travel with the field — and
it would be blind to a future per-type field schema, where the same field name can carry a
different definition per need type. A field that has no definition object cannot carry a rule:
in sphinx-needs that is the 35 core fields outside the field schema (`id`, `docname`,
`type_name`, `section_name`, `content`, …) and every link type; ubCode already refused all of
them. No use of a string link on any of the 35 was found; `external_url`, a URL-valued core
field, is the one residual, and is claimable in ubCode. Where one was linked it now renders as
plain text — in need cards (every default layout's heading shows `type_name`), in needtables
and in custom layouts.

**The stages.**

- **Stage 0** (this contract's first version): at configuration resolution each field acquires
  at most one rule — the first declared table entry naming it — and the renderers read the
  field's rule instead of scanning the table. The table stays the only input; there is no new
  key, no deprecation, no documentation announcing anything, and rendering is byte-identical
  except for the disclosed changes in §2. Stage 0 leaves the seam for stage 1: every rule
  carries its provenance.
- **Stage 1**: a field may declare its own rule (`link` beside `schema` in `needs_fields` /
  `[needs.fields.<name>]`, and `add_field(…, link=…)`), validated at configuration load. A
  field-sourced rule links "per item for arrays, whole value for strings": it never splits.
- **Stage 2**: each table entry is converted onto the fields its `options` name, with a
  deprecation warning; a field that also declares its own rule keeps it, and that is warned.
- **Stage 3** (next major): the table, and the `,`/`;` splitting that exists only for it, are
  removed.

## 1. The per-field model

Both engines implement exactly this.

1. **The rule is an attribute of the field definition object**: sphinx-needs
   `FieldSchema.string_link` (`StringLinkRule | None`), ubCode `NeedField.string_link`
   (`Option<FieldStringLinkR>`). `LinkSchema` has no such attribute.
2. **A rule is source strings only** — `regex`, `link_url`, `link_name` — **plus its
   provenance**: the name of the table entry that supplied it. Every warning about a rule names
   that entry. `options` does not survive on the rule: the field it sits on is the key. (The
   sphinx-needs `regex` may be an already-compiled `re.Pattern`, as validated; a compiled
   pattern pickles. A compiled template does not, and is never stored.)
3. **First declared wins.** Walk the validated table in authored order; for each surviving
   `options` name, set the field's rule only if the field has none (sphinx-needs: or only the
   rule of an entry that does not compile, item 5). An entry none of whose options survive
   claims nothing; a field no entry names has no rule.
4. **Claimable names are exactly the fields that have a definition object**: sphinx-needs'
   field schema (its core fields with `add_to_field_schema`, and the extra fields), ubCode's
   resolved field registry. The check runs where the definitions exist — sphinx-needs: in the
   fold, so a field registered after the table is validated is claimable and not warned about;
   ubCode: at resolution — and any other name in `options` is warned about once and ignored.
5. **Validation is otherwise untouched.** The fold is a post-pass over the table. For the
   entries in the validated table, besides the name check of item 4 (sphinx-needs moved it
   from `config-inited` into the fold, where the field schema exists; a name an entry lists
   twice now warns once), no warning, code, path, message or emission time moves. An entry
   written after validation (sphinx-needs only) is checked, compiled and reported at the fold
   (`env-before-read-docs`): its compile failure is reported once there instead of at the
   first rendered need; a source of the wrong type (a `regex` that is neither a string nor a
   string pattern, a template that is not a string) is refused with its own message — a bytes
   pattern once, instead of a warning per rendered value — and that entry claims nothing, so a
   field only it names is no longer split; and a bare-string `options` warns once per
   character. The fold compiles each entry through the memo validation filled: the field's
   rule is the first entry naming it that compiles, and an entry that does not compile still
   claims a field nobody else names — the field splits, but nothing links — as both
   renderers did before.
6. **Split iff the field has a rule.** In stage 0 every rule is table-sourced, so every claimed
   field's string value is split on `,` and `;`, each item stripped, empty items dropped, and
   the items re-joined exactly as before. The provenance is what stage 1 keys its no-split rule
   on.
7. **Compiled forms live only in render-time caches** — sphinx-needs' `_compile_string_link`
   memo, ubCode's `StringLinkRegistry` — never in anything pickled, persisted or hashed.

## 2. Parity

The union of both engines' parity surveys, as measured at sphinx-needs `db7683a2` and ubCode
`2e5d3d55`. sphinx-needs paths are relative to `packages/sphinx-needs/src/sphinx_needs/`; ubCode
paths to its repository root. "Measured" rows were built with probe projects (sphinx-needs:
`sphinx-build -b html`, serial and `-j 2`; ubCode: `ubc build html`). Stage 0 resolves no
DIVERGES row: each engine keeps its own behaviour.

| aspect | sphinx-needs @ `db7683a2` | ubCode @ `2e5d3d55` | verdict |
|---|---|---|---|
| rule shape | entry `{regex, link_url, link_name, options}` under a name; `regex` may be a compiled `re.Pattern`, keeping its flags (`string_links.py:203-221`) | `StringLinkR {regex, link_url, link_name, options}` under a name, strings only (`rust/ubc_config/src/needs/string_link.rs:61-73`) | SAME shape; a compiled pattern is a Python-only spelling (TOML cannot carry one) |
| where the rule lives after stage 0 | `FieldSchema.string_link` | `NeedField.string_link` | SAME |
| first declared wins, no fallthrough (an entry that does not compile is skipped for linking, and still splits a field nobody else names) | `matching_link_confs[0]` over dict order (`utils.py:527-529`); measured: `ticket = "T-1, X-9; T-2"`, entries `first` (`^T-\d+$`) then `second` (`.+`) → `FIRST T-1; X-9; FIRST T-2` in the meta area and the needtable | `rules.iter().find(…)` over `IndexMap` order (`string_link.rs:575-581`); measured: a later rule naming the same field draws zero labels, card and needtable | SAME |
| claimable names | before stage 0: any name — the 11 schema core fields, the 35 core fields outside the schema and the extra fields silently (`string_links.py:295`); a link type or unknown name warned but its entry was kept, and a custom layout's `<<meta("links")>>` still linked it (measured `LNK REQ_002`). After stage 0: only the field schema — `title status tags collapse hide layout style template pre_template post_template constraints` plus the extra fields | the resolved field registry: core `title status tags collapse hide layout style doctype external_url` (`rust/ubc_config/src/needs/resolved.rs:936-948,1182,1222`) plus the declared extra fields; link types live in a separate map | SAME rule (only fields with a definition object). Residual difference in the populations: `template`, `pre_template`, `post_template`, `constraints` are claimable only in sphinx-needs (ubCode does not implement those features, `resolved.rs:944-948`); `doctype` and `external_url` only in ubCode |
| a name that is not claimable | warns `needs.string_link` once per entry when the schema is built (`env-before-read-docs`; before stage 0 at `config-inited` 551), keeps the entry, the name is inert | warns `config.string_link_unknown_field`, drops the name, keeps the rule's other names (`string_link.rs:223-240`); measured with `nosuch`, `owner_typo` | SAME outcome (the name never links); DIVERGES in code and in whether the name stays in the stored table |
| an extra field registered after validation | links, without a warning: the GitHub service fields (`services/config/github.py:3-9`) are registered by `prepare_env` (`needs.py:941-955`, `env-before-read-docs`, before `create_schema`) in every project, and get a `FieldSchema` before the fold runs; likewise an `add_field` at `config-inited` after 551 | does not link: the codelinks auto-registration runs after `resolve_string_links`, so the name is dropped as unknown (useblocks/ubcode#3840) | DIVERGES (ubCode bug, preserved by stage 0, fixed separately) |
| split a claimed field's STRING value | `re.split(r",\|;")`, strip, drop empties (`string_links.py:153-163`) | `split([',', ';'])`, trim, drop empties (`string_link.rs:555-566`) | SAME — ubCode's comment at `string_link.rs:546-550` describing a "phantom third item" upstream is stale: sphinx-needs strips before dropping (`packages/sphinx-needs/docs/changelog.rst:772 @ db7683a2`) |
| re-join separator, string value, meta area and needtable | `"; "` between items only (`layout.py:540-542`, `utils.py:211-212`) | `"; "` (`rust/ubc_ast/src/render_html/special.rs:3227-3262`, both surfaces) | SAME |
| no match → still split and re-joined | yes; measured `X-9` plain between two links | yes ("alice, bob → alice; bob") | SAME |
| LIST value, needtable | per element, `"; "`; measured `TAG alpha; TAG beta` | per element, `"; "` | SAME |
| LIST value, meta area | per element, `", "` spacer (`layout.py:550-554`); measured `TAG alpha, TAG beta` | per element, `"; "`; measured `CP 1</a>; <a …>CP 2` | **DIVERGES** (separator) |
| empty list element | rendered as empty text with its separator (meta guard `layout.py:561`, table guard `utils.py:141`) | dropped (`rust/ubc_parser_ctrl/src/hydration.rs:2128-2131`) | DIVERGES in shape (byte level unmeasured: the directive parser already drops empty items, so only a field default reaches the guard) |
| empty `options` | warns, keeps the entry (`string_links.py:234-235`) | `config.string_link_incomplete`, rule refused | DIVERGES (no rendering effect) |
| unknown key in an entry | warns, keeps the entry (`string_links.py:190-196`) | `deny_unknown_fields` on `StringLinkI` (`rust/ubc_config/src/needs/input.rs:661`): a configuration parse error | DIVERGES |
| unusable entry (missing key, bad regex, bad template) | warns and skips the whole entry, one code `needs.string_link` | warns and skips the whole rule, codes `config.string_link_incomplete` / `_regex_invalid` / `_template_invalid` (`string_link.rs:39-45`) | SAME posture, DIVERGES in codes |
| regex dialect | Python `re` (look-around, back-references) | Rust `regex` (neither; a named error) | DIVERGES (engine) |
| a named group that did not participate | renders the literal `None`; measured `NG None Second` | renders empty (`string_link.rs:590-600`) | DIVERGES (documented by ubCode) |
| empty rendered label | plain text (`utils.py:540-545`) | plain text (`string_link.rs:619`) | SAME |
| template fails at render time | `needs.layout` warning per value, with the need's location; the value as plain text (`utils.py:547-557`) | `build.need_string_link_invalid`, aggregated per rule; plain text | SAME fallback, DIVERGES in code and aggregation |
| href grammar | none: any rendered URL is emitted | only `http(s)://`, `mailto:` and scheme-less relative targets; others refused | DIVERGES (ubCode security posture) |
| `needs_render_context` | merged over the groups, so it shadows a same-named group (`utils.py:530-538`) | not merged, deliberately | **DIVERGES** |
| needtable ID and link-type columns | never string-linked (`make_ref` / `ref_lookup`) | never string-linked (link columns answered first) | SAME |
| needtable TITLE column | goes through `row_col_maker`, linked if claimed | goes through the rules | SAME |
| validation time | `config-inited` priority 551 | configuration resolution | SAME stage |
| fold time | the end of `create_schema` (`env-before-read-docs`), over the table as validated at 551 plus any entry written after validation and before the fold | immediately after `resolve_string_links` | SAME stage relative to validation |
| a table entry written after the fold | not rendered (stage 0 change: an `env-before-read-docs` handler after `create_schema`, or a directive at read time — the latter already did not render under `-j N`); an entry written at `config-inited` after 551 is folded unvalidated: it renders if it compiles; if it does not, it is reported once and links nothing, but still splits a field nobody else names; if a source has the wrong type, it is reported once and claims nothing, so a field only it names is no longer split | not possible (configuration is resolved once) | n/a |

## 3. Open for stage 1

Stage 0 decides none of these; each is a stage-1 decision, and each is a DIVERGES row above or
a seam this contract leaves.

1. **List-value separator in the meta area**: sphinx-needs `", "`, ubCode `"; "`.
2. **`needs_render_context`**: merge over the groups (sphinx-needs), or not at all (ubCode).
3. **A name that is not claimable**: keep it in the stored table (sphinx-needs), or drop it
   (ubCode). Both now agree the name never links.
4. **A non-participating group**: `None` (sphinx-needs) or empty (ubCode).
5. **Diagnostic code families**: one `needs.string_link` subtype, or ubCode's four
   `config.string_link_*` codes plus `build.need_string_link_invalid`.
6. **Splitting for field-sourced rules**: the issue proposes "per item for arrays, whole value
   for strings", with the `,`/`;` split kept only for table-sourced rules during the
   deprecation window; the provenance carried by every stage-0 rule is the key it would use.
