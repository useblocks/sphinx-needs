# The directives contract: presets, declared templates, `ub-template`

This document is the **normative** specification of three directive mechanisms that a
project declares in `ubproject.toml`, and that two implementations read: this package
(the Sphinx half) and ubCode. It is re-derived from the measured behaviour of both
(the `ubdir` recon), not transcribed from either implementation's notes.

- **Directive presets** (`[parse.directive_presets.<name>]`, §3): a directive name that is
  an existing directive with preset options, or project-wide defaults for an existing one.
- **Declared template directives** (`[parse.directive_templates.<name>]`, §5): a directive
  of the project's own whose output is a Jinja template, with a closed signature.
- **`ub-template`** (§6): the generic template directive, switched on by
  `[parse] ub_template_enabled`.

Both template forms read **template contexts** (`[parse.template_contexts.<name>]`, §4)
and the variant data as `var`.

The executable half of the contract is two corpora, both canonical in THIS repository and
vendored by ubCode:
[`tests/fixtures/directive_presets_conformance.toml`](../tests/fixtures/directive_presets_conformance.toml)
and
[`tests/fixtures/template_directives_conformance.toml`](../tests/fixtures/template_directives_conformance.toml).
"corpus: `name`" below means the case of that name, run by
`tests/test_presets_conformance.py` or `tests/test_templates_conformance.py`; "test:"
means a unit test of this package.

Status: describes the contract both implementations are held to. When behaviour changes,
this document, the corpora and the tests change in the same commit, and the pull request
says that ubCode owes a re-vendor.

## 1. The parity promise

1. **What is promised: the rendered text and the needs data.** A project built by both
   implementations gives, for every use of a preset or a template directive, the same
   expansion text (templates), the same needs with the same field values and types
   (`sections` included), and the same findings by code.
2. **What is never promised: diagnostic locations.** A conforming implementation reports
   every finding about a use at a position inside that use (the directive's first line at
   least), and a render error names the template and the line the engine reports.
   Implementations may be more precise: ubCode reports the body line, the rendered line
   and the template line; the Sphinx half reports at the directive's line. Messages and
   severities are not part of the contract either.
3. **How findings are compared: by code and attribution.** A finding is its contract code
   (§8), plus the `ubproject.toml` path a configuration finding is reported at, or the
   directive a finding at a use is attributed to. The corpora compare findings as a
   multiset of these, never by line.
4. **Each tool's page form is its own.** The two tools render through different writers
   and node vocabularies, so pages are never compared across tools. What a corpus case
   may pin instead is an `equivalent` page: the same page written without the mechanism
   (the base written out, the output written out), which must give the same products as
   the case's page WITHIN each implementation.

Enforced by: every case of both corpora (expansions, needs, findings); the `equivalent`
cases (corpus: `identity-note-rst`, `host-content-continues-in-the-last-section`, …).

## 2. Reading the configuration

1. **One file.** The tables are read from the project's `ubproject.toml` only: the file
   sphinx-needs reads (`needs_from_toml`) when it is set, else the one
   `ub_project.find_project_config` finds from the Sphinx `confdir`. No `extend` chain is
   resolved: ub-project does not resolve one, and neither does sphinx-needs, so the whole
   Sphinx family reads one file today. ubCode resolves `extend` for itself; a project
   that relies on it for these tables builds differently with Sphinx.
   When the file has an `extend` key and any `[parse.directive_presets]`,
   `[parse.directive_templates]` or `[parse.template_contexts]` table, the Sphinx half
   warns once (`ub_directives.extend_unsupported`). The corpora have no `extend` case.
   Enforced by: test `test_config.py::test_an_extend_key_warns_once`.
2. **When.** The tables are read at `config-inited` into the confval
   `ub_directives_resolved` (registered `rebuild="env"`), so a change to them re-reads
   every document; presets are registered at `builder-inited`, after every extension's
   `config-inited` (need types, sphinx-design) and before any document is read.
   Enforced by: test `test_config.py::test_the_tables_are_a_rebuild_env_confval`.
3. **Keys.** `[parse.directive_presets.<name>]`, `[parse.directive_templates.<name>]`,
   `[parse.template_contexts.<name>]`, and the bool `[parse] ub_template_enabled`
   (default `false`). There is no top-level `[directives]` table and no alias for any
   earlier name.
4. **Path anchoring: the source root.** Template and context paths are anchored at the
   project's SOURCE ROOT (the Sphinx `srcdir`), as content is, like `.. include::` —
   a named exception to ub-project's reading contract §5.1, which anchors a path at the
   directory of the file that declared it. A leading `/` is the source root too. A path
   whose real path (symlinks resolved) is outside the source root is refused, and never
   read.
   Enforced by: corpus `include-is-from-the-source-root`, `context-refused-outside-the-root`,
   `declared-template-outside-the-root`, `ub-template-file-outside-the-root`.

## 3. Directive presets

### 3.1 The entry

```toml
[parse.directive_presets.req-draft]
base = "req"                         # required: the directive it is
description = "A requirement that starts as a draft"
argument = "Untitled requirement"    # the argument of a use that writes none
options = { status = "draft" }       # defaults: a written value replaces one
append_options = { class = "x" }     # class options only: preset tokens go first
force_options = { collapse = true }  # a use cannot change these
```

1. **Scalars.** A value is a TOML string, boolean, integer or float, converted to option
   TEXT: a string as written; `true` → `""` for a flag option, else `"true"`; `false` for a
   flag is refused, else `"false"`; a number → its decimal text. An array, table or
   date-time is `directive_preset_invalid_value`. `description` and `argument` equal to
   `""` (after stripping, for `argument`) are unset.
   Enforced by: corpus `flag-default`, `number-is-its-decimal-text`,
   `true-for-a-non-flag-is-the-text-true`, `refused-flag-switched-off`,
   `refused-array-value`, `refused-table-argument`, `description-and-empty-argument`.
2. **Unknown keys** of an entry are each `directive_preset_unknown_key`, and the preset is
   KEPT. Enforced by: corpus `unknown-key-keeps-the-preset`.
3. **Shape.** An entry that is not a table, a `base` or `description` that is not a
   string, or an option table that is not a table is `directive_preset_invalid_value` at the
   entry. `[parse] directive_presets` itself must be a table of entries.
   Enforced by: corpus `refused-entry-not-a-table`, `refused-base-not-a-string`,
   `refused-description-not-a-string`, `refused-options-not-a-table`.

### 3.2 Resolution (once per build; each failure one finding at its path; the preset is left out)

1. **Names compare case-insensitively.** Two entries whose names differ only in case are
   one name: ONE `directive_preset_name_taken` at the later spelling (in key order), and the
   first is used. A use is looked up case-insensitively, as every directive is.
   Enforced by: corpus `refused-case-duplicate-names`, `use-is-case-insensitive`.
2. A missing or blank `base` is `directive_preset_unknown_base` at the entry.
   Enforced by: corpus `refused-missing-base`, `refused-blank-base`.
3. A **self-preset** is an entry whose name equals its base (case-insensitively): it gives
   that directive project-wide defaults.
   Enforced by: corpus `self-preset-gives-project-defaults`, `self-preset-of-a-need-type`.
4. A base naming another (accepted, non-self) preset is `directive_preset_base_is_preset`:
   presets do not chain. Enforced by: corpus `refused-base-is-preset`.
5. **The base** is the need type of that name (case-insensitively; need types are lower
   case, see 3.2.6), else the directive registered under that name (docutils, Sphinx, any
   domain, any loaded extension). Nothing found is `directive_preset_unknown_base` at
   `….base`. Enforced by: corpus `refused-unknown-base`, `base-is-case-insensitive`,
   `identity-confval-rst`.
6. **A need type spelled with upper-case letters is refused as a base**
   (`directive_preset_unknown_base`, saying why): a Sphinx build registers such a type
   verbatim but looks every directive up in lower case, so the type is unusable there, and
   a preset would make it usable under another name only. The corpora use lower-case need
   types only. Enforced by: test `test_presets.py::test_a_capitalised_need_type_is_refused_as_a_base`.
7. A new (non-self) name that is already a directive — built in, a need type, any loaded
   extension's — is `directive_preset_name_taken` at the entry.
   Enforced by: corpus `refused-name-taken`, `refused-name-taken-by-a-need-type`.

### 3.3 Option checks (every problem reported; the preset is left out if any)

The tables are checked in the order `options`, `append_options`, `force_options`, keys
sorted; the path is `….<name>.<table>.<key>`.

1. A key already seen in an earlier table is `directive_preset_option_conflict` (at the
   later one). Enforced by: corpus `refused-option-in-two-verbs`.
2. An identity option — the base's `name`, or a need's `id` — is
   `directive_preset_identity_option`. Enforced by: corpus `refused-identity-option-name`,
   `refused-identity-option-id`.
3. A key the base does not take is `directive_preset_unknown_option`. For a need-type base
   the options are the type's fields and links plus the need directive's own options.
   Enforced by: corpus `refused-unknown-option`, `refused-unknown-need-option`.
4. An `append_options` key other than `class` or `class-*` is
   `directive_preset_append_not_list`. Enforced by: corpus `refused-append-to-a-scalar`.
5. A value the base's option rejects is `directive_preset_invalid_value`. The Sphinx half
   runs the base's own option converter; ubCode runs its own validators, which check at
   least what the converter checks and may check more (an implementation MAY refuse at
   load a value the base would refuse at every use: corpus `refused-wrong-field-type` and
   `refused-bad-line-spec` are ubCode's). Enforced by: corpus `refused-flag-given-a-value`,
   `refused-outside-the-choices`, `refused-bad-measure`, `refused-bad-integer`,
   `refused-bad-table-widths`, `refused-bad-highlight-threshold`.
6. `argument` for a base that takes none is `directive_preset_argument_not_accepted`.
   Enforced by: corpus `refused-argument-for-a-base-without-one`.
7. Every problem of an entry is reported, and a refused entry costs only that entry.
   Enforced by: corpus `every-problem-of-an-entry-is-reported`,
   `a-refused-preset-costs-only-its-entry`.

### 3.4 A use

1. **A use is its base with the options merged in**: it renders, is checked and is
   indexed exactly as the base written with those options. A need-type base gives the
   need that type. The output carries no trace of the preset.
   Enforced by: every `identity-*` and `options-*` corpus case (the `equivalent` page).
2. **Precedence**, highest first: a forced value; what the use writes (for an appended
   option, the preset's tokens first, then the written ones); the preset's default; the
   base's own defaults (a field's `default`, `needs.global_options`).
   Enforced by: corpus `default-option-yields-to-the-written-one`,
   `precedence-over-a-field-default`, `appended-class-goes-first-rst`,
   `appended-class-alone`, `forced-need-option`.
3. **The default argument** fills a use written without one, even for a base that
   requires one; a written argument replaces it whole.
   Enforced by: corpus `default-argument-fills-an-absent-one-rst`,
   `written-argument-replaces-the-default`, `default-argument-of-a-need-is-its-title`.
4. **A forced option** a use writes is reported (`preset_forced_option`, attributed to the
   preset) and the preset's value is used; the written value is never converted, so a
   value the base would reject is reported as forced, not as an error.
   Enforced by: corpus `forced-option-wins-and-is-reported-rst`,
   `forced-option-value-is-never-converted`, `forced-option-not-written-is-quiet`.
5. **A preset of a directive that also has a self-preset is the ORIGINAL directive**:
   it does not take the self-preset's values, whatever the order of registration.
   Enforced by: corpus `preset-of-a-self-preset-base-takes-the-original`.
6. A default flag cannot be switched off by a use (there is no `:no-<option>:`).

### 3.5 The Sphinx half (informative: how this package meets §3)

- Each accepted preset is a subclass of the base's class, registered with
  `app.add_directive(name, cls, override=<self-preset>)`, every base class snapshotted
  before the first registration (3.4.5).
- With a default argument, `required_arguments = 0` and `optional_arguments =
  max(1, required + optional)` of the base: docutils (and MyST) check the argument count
  BEFORE `run()`.
- `option_spec` is a subclass of `type(base.option_spec)` that maps the forced keys to
  `unchanged` and defers every other lookup to the base's mapping, so sphinx-needs'
  `DummyOptionSpec` keeps accepting any key (a plain `dict` copy of it is empty, and turns
  every need option into an "unknown option" error).
- `run()` merges the options as §3.4 says (options are already converted there, so an
  appended class is the preset's converted tokens plus the written list), sets
  `self.name` to the base, and calls the base's `run()`.
- The forced-option warning is located at `(env.docname, self.lineno)`: a plain docutils
  directive has no `get_location()`.
- MyST drops an unknown option with a warning, and reads a flag's value leniently, where
  docutils refuses the directive: a refusal at a use is compared by code, never by "the
  directive rendered nothing".

## 4. Template contexts and `var`

1. **An entry** `[parse.template_contexts.<name>]` is a table whose ONLY key is a string
   `file` (the file form: a JSON or TOML file under the source root, §2.4) or any other
   table (inline data). Enforced by: corpus `declared-sees-every-context`,
   `needs-from-a-json-file`.
2. **The data model** is ub-project's variant-data shape rule (reading contract §8.1),
   extended to arrays of tables: string keys; values that are strings, booleans, integers
   or floats; arrays that are empty, hold scalars of ONE exact type, or hold only tables;
   and tables of the same shape. A null, a date-time, a float that is not finite (TOML's
   `inf`, `nan`), an array of mixed scalars (`[1, 1.5]` and `[1, true]` are mixed) and an
   array of arrays are `template_context_invalid`, as is a file whose top level is not a
   table. Enforced by: corpus `context-refused-json-null`,
   `context-refused-toml-datetime`, `context-refused-inline-datetime`,
   `context-refused-mixed-array`, `context-refused-int-float-array`,
   `context-refused-array-of-arrays`, `context-refused-not-a-mapping`,
   `context-array-of-tables`, `context-values-keep-their-types`.
3. **Formats: JSON and TOML only** (by extension, `.json` and `.toml`); there are no YAML
   contexts in v0.1, so a `.yaml` or `.yml` file is `template_context_invalid` saying so,
   and so is any other extension, a missing file, and a file that does not parse.
   Enforced by: corpus `context-refused-yaml-file`, `context-refused-yml-file`,
   `context-refused-other-extension`, `context-refused-missing-file`,
   `context-refused-invalid-json`.
4. **Map order is FILE order.** A mapping iterates in the order its data writes it, for a
   file and an inline table alike; a mapping a template builds keeps insertion order; only
   `dictsort` sorts. Enforced by: corpus `map-order-is-file-order-json-file`,
   `map-order-is-file-order-toml-file`, `map-order-is-file-order-inline`,
   `map-order-literal-and-dictsort`.
5. **Context data is the engine's own data.** It reaches a template as engine-native
   values: read-only (a method that would change it — `pop`, `append`, `clear` — is a
   render error, and no render changes the data another sees), iterated in file order,
   and printed as the engine prints its values (`{{ rows }}` is `[1, "a"]`).
   Enforced by: corpus `context-is-read-only`, `dialect-values-render-pythonically`,
   `context-data-prints-as-the-engine-prints`.

   *The Sphinx half (informative):* minijinja-py hands a Python `dict` or `list` to a
   template as a Python object — printed as Python's `repr` (`{'a': [1, 2]}`), with
   Python's own `items()` and `pop()` — and freezing it into a `MappingProxyType` keeps the
   `repr` (measured on 2.24). So the context is written into the template as one line of
   `{% set %}` statements of literals in front of it: JSON is minijinja's literal syntax
   once null is excluded, which the data model guarantees, and one line moves no
   template line.
6. **`var`** is in every template context: the project's merged variant data (the map
   `.. if::` evaluates against — reading contract §8), read-only, by attribute or by key.
   A key it does not define is undefined, and undefined is an error (`is defined` tests
   it). On the Sphinx side it is `app.config.needs_variant_data` when sphinx-needs is
   loaded, else `ub_project.read_variants(...).data`; the data file is a dependency.
   Enforced by: corpus `var-is-the-variant-data`, `var-merges-the-data-file`,
   `var-missing-key-is-undefined`, `var-is-defined-test`, `ub-template-sees-var`.
7. **`var` is reserved.** A context NAMED `var` is `template_context_reserved` at
   `parse.template_contexts.var` and is not read; for `ub-template`, whose context keys
   are top-level variables, a named context or `:ctx:` with a top-level `var` key is
   `template_context_invalid`. Enforced by: corpus `context-named-var-is-reserved`,
   `ub-template-context-with-a-var-key-is-refused`, `ub-template-ctx-refused-var-key`.

## 5. Declared template directives

### 5.1 The declaration

```toml
[parse.directive_templates.req-row]
template = "_templates/req_row.rst.j2"   # under the source root; or body = "…"
markup = "rst"                            # "rst" | "md"; default from the file name
description = "One requirement row"
argument = { required = true, description = "Requirement id" }
content = false                           # whether it takes a body

[parse.directive_templates.req-row.options]
owner = { required = true, description = "Who owns it" }
status = { choices = ["open", "closed"], default = "open" }
draft = { flag = true }
```

1. A declaration is refused at load (`directive_template_invalid` at its entry) and ignored
   when its name, in any case, is already a directive (built in, a need type); when it
   differs only in case from another declaration (the later in key order is refused);
   when it gives both or neither of `template` and `body`; when `markup` is not `"rst"` or
   `"md"`; or when `markup` contradicts its template file's name.
   Enforced by: corpus `declaration-refused-builtin-name`,
   `declaration-refused-builtin-name-in-capitals`, `declaration-refused-need-type-name`,
   `declaration-refused-case-duplicate`, `declaration-refused-template-and-body`,
   `declaration-refused-neither`, `declaration-refused-bad-markup`,
   `declaration-refused-markup-contradicts-the-file`,
   `declaration-refused-builtin-keeps-the-builtin`.
2. **Markup** is `markup`, else the template file's name (`*.rst.j2`, `*.md.j2`; also
   `.rst.jinja`, `.md.jinja`), else reStructuredText.

### 5.2 What the template sees — exactly this

- `argument`: the use's argument, or none;
- `options`: every declared option — the written value, else its `default`, else none; a
  flag is `true` or `false`;
- `body`: the use's body text, when `content` is true;
- `contexts`: every context (§4), by name;
- `var` (§4.6).

Enforced by: corpus `declared-file-template`, `declared-options-surface`,
`declared-content-is-body`, `declared-sees-every-context`, `declared-env-is-unavailable`.

### 5.3 The closed signature

An option that is not declared, a missing required option or argument, a value outside
`choices`, a flag written with a value, an argument to a directive that declares none, or
a body on a directive without `content` is `template_signature` at the use, which renders
nothing. Enforced by: corpus `signature-undeclared-option`,
`signature-missing-required-option`, `signature-bad-choice`, `signature-missing-argument`,
`signature-argument-not-declared`, `signature-unexpected-body`,
`signature-flag-given-a-value`.

## 6. `ub-template`

1. **The switch.** `[parse] ub_template_enabled = true` turns it on; off (the default) a
   use is `template_switched_off` and renders nothing.
   Enforced by: corpus `ub-template-is-off-by-default`, `ub-template-switched-off-explicitly`.
2. **The context**: the named context's keys (the optional argument names it;
   `template_context_unknown` when no context has that name), overridden by `:ctx:` (an
   inline JSON object under §4.2), plus `var`. Enforced by: corpus
   `ub-template-named-context`, `ub-template-ctx-overrides-the-named-context`,
   `ub-template-unknown-context`, `ub-template-ctx-refused-invalid-json`,
   `ub-template-ctx-refused-not-an-object`, `ub-template-ctx-refused-null-value`.
3. **The template**: the body, or `:file:` (relative to the page, or to the source root
   with a leading `/`; `template_missing`, `template_outside_root`). A `:file:` and a body
   together is `template_option_invalid`, and the file is rendered. A `:file:` named
   `*.rst.j2` / `*.md.j2` is that markup; any other template is the page's.
   Enforced by: corpus `ub-template-file-relative-to-the-page`,
   `ub-template-file-from-the-source-root`, `ub-template-file-missing`,
   `ub-template-file-outside-the-root`, `ub-template-file-and-body`,
   `ub-template-file-of-the-other-markup`.
4. `:raw: <format>` emits the output as raw content of that format, unparsed (an empty
   `:raw:` is `template_option_invalid`); `:debug:` also shows the rendered text as a
   literal block after the output. Enforced by: corpus `ub-template-raw`,
   `ub-template-raw-needs-a-format`, `ub-template-debug`.

## 7. Rendering, and joining the page (both template forms)

1. **The dialect** is minijinja 2.x, configured identically on both sides — these and only
   these differences from the engine's bare defaults:
   - undefined is strict (`is defined` tests it); no autoescaping; the standard delimiters;
     one trailing newline of a template dropped;
   - `debug()` removed; Python-compatible methods on values (`pycompat`);
   - `break` / `continue` (minijinja's `loop_controls`);
   - `filesizeformat`, `urlencode`, `truncate`, `pluralize`, `striptags`, `joiner()`,
     `cycler()` (minijinja-contrib's, and minijinja's `urlencode`): present on both sides
     (ubCode enables them; none adds a dependency);
   - `wordwrap` with a positional width (`|wordwrap(7)`) as well as `width=`;
   - no clock, randomness or I/O: `now`, `random`, `lipsum`, `datetimeformat` are unknown.
   The Python-only string methods ubCode's docs once listed (`center`, `ljust`, `rjust`,
   `zfill`, `expandtabs`) do not exist on either side.
   Enforced by: corpus `dialect-*` (one case per name above),
   `render-error-debug-is-removed`, `render-error-undefined-attribute-test`.
2. **`env` is unavailable.** A template that names `env` as a free variable is
   `template_context_unavailable` (sphinx-jinja2 handed a template the live build
   environment; neither implementation has one to give).
   Enforced by: corpus `ub-template-env-is-unavailable`, `declared-env-is-unavailable`.
3. **Includes** (`include`, `import`, `extends`) name files relative to the source root; one
   that would leave it is not read (a render error). Templates are read as UTF-8.
   Enforced by: corpus `include-is-from-the-source-root`,
   `include-outside-the-root-is-an-error`.
4. **Recursion** is minijinja's default limit on both sides; no corpus case pins it.
5. **Limits are bounds, not semantics.** A template that stays under them renders
   identically on both sides; one that exceeds a limit is non-conforming, and an
   implementation reports it as a limit finding and renders nothing — but WHICH templates
   exceed a limit, how fast that is said, and how much memory is used first are
   implementation-defined. The corpus pins only "an output over 1 MiB is refused"
   (`template_output_limit`), which both sides check after the render. The Sphinx half
   bounds a render by fuel and checks the output after it; it does not bound
   intermediate values, and it has NO live output cap: a minijinja-py `finalizer` changes
   how every value it sees prints (measured on 2.24: `1.0` prints `1`, a list prints as
   Python's `repr`), which would break §7.1. ubCode keeps its byte budget and value limit
   (`template_value_limit`, `template_compute_limit`, never pinned).
   Enforced by: corpus `output-over-1-mib-is-refused`, `output-of-1-mib-is-rendered`.
6. **The per-page breaker.** In one page, once a template has hit a limit with three
   different inputs, its later uses there with yet other inputs are not rendered
   (`template_disabled`); a use with inputs that already failed reports its limit again.
   An input-keyed render memo is NOT required (it is ubCode's optimisation); determinism
   is. Enforced by: corpus `breaker-disables-a-runaway-template-for-the-page`.
7. **A render error** (undefined, syntax, unknown filter) is `template_render_error`, and
   the use renders nothing; the rest of the page renders.
   Enforced by: corpus `render-error-undefined`, `render-error-syntax`,
   `var-missing-key-is-undefined`.
8. **Splice: textual semantics.** Output in the page's own markup is inserted as if it
   had been written in place of the directive (docutils' `insert_input`): its headings
   join the page's hierarchy, and host content AFTER the directive continues in the
   output's last open section. Enforced by: corpus `heading-joins-the-page`,
   `host-content-continues-in-the-last-section`,
   `host-content-continues-in-the-last-section-md`,
   `output-without-a-heading-stays-in-the-host-section`, `ub-template-heading-joins-the-page`.
9. **Cross-markup output** (a template of the other markup) is parsed in the TEMPLATE's
   markup and allowed without headings: a section title anywhere in it is
   `template_markup_heading`, and the use renders nothing.
   Enforced by: corpus `rst-template-in-an-md-page`,
   `rst-template-with-a-heading-in-an-md-page`, `md-template-in-an-rst-page`,
   `md-template-with-a-heading-in-an-rst-page`, `md-template-in-an-md-page`.
10. **Depth 1, and only declared inputs.** Output may not hold a directive that expands a
    template (`template_nested_expansion`) or one that reads content outside the
    template's declared inputs (`template_output_reads_file`). Such a directive renders
    nothing and is reported; **the rest of the output renders**. The reads-a-file list is
    normative — these and only these:

    | directive | refused when |
    |---|---|
    | `autoattribute`, `autoclass`, `autodata`, `autodecorator`, `autoexception`, `autofunction`, `automethod`, `automodule`, `autoproperty` | always |
    | `csv-table`, `raw` | with `:file:` or `:url:` |
    | `graphviz`, `mermaid`, `plantuml`, `uml` | with an argument (a file) |
    | `include`, `literalinclude`, `needimport`, `needservice`, `src-trace` | always |
    | `needreport` | with `:template:` |
    | the sphinx-test-reports directives the project configures | always |
    | a need directive (any need type) | with `:template:`, `:pre_template:`, `:post_template:` or `:jinja_content:` |
    | `ub-template`, every declared template directive | always (`template_nested_expansion`) |

    The property behind the list: a directive that reads content the template did not
    declare. An inline diagram, an `image` and a `figure` read nothing into the page (an
    image is linked, as on any page). A third-party directive neither tool knows is the
    project's responsibility: ubCode never runs one, and the Sphinx half additionally
    warns when such a directive notes a dependency while it runs from output
    (`ub_directives.template_reads_dependency`, Sphinx only, never in the corpus).
    Enforced by (the backstop): test `test_templates.py::test_a_third_party_directive_noting_a_dependency_is_reported`.

    *The Sphinx half (informative):* refusal happens during the real parse of the output,
    at the directive LOOKUP: every line a template inserts carries the directive's own
    `(source, line)` (and nested bodies inherit it), so a lookup is on output exactly when
    the document's current position is one a template inserted; output of the other
    markup, and a Markdown page's output, are parsed synchronously under a context
    variable instead. Output of the other markup is first parsed with every directive
    inert, to look for a heading without side effects (§7.9).
    Enforced by: corpus `output-reads-file-*` (one per row), `output-nested-*`,
    `output-allows-*` (the allowed twins).
11. **Dependencies.** Every template, context and `:file:` a use reads — including a
    missing or refused one — is a dependency of the page, so creating or editing it
    re-reads the page. Enforced by: test `test_templates.py::test_every_input_is_a_dependency`.

## 8. Codes

The corpus spells every code bare. ubCode carries them under its own prefixes; the Sphinx
half reports each as the warning type `ub_directives` with the code as its subtype
(`[ub_directives.<code>]`), so `suppress_warnings = ["ub_directives.<code>"]` silences one.

| corpus code | ubCode | when |
|---|---|---|
| `directive_preset_unknown_base` | `config.directive_preset_unknown_base` | §3.2.2, 3.2.5, 3.2.6 |
| `directive_preset_base_is_preset` | `config.directive_preset_base_is_preset` | §3.2.4 |
| `directive_preset_name_taken` | `config.directive_preset_name_taken` | §3.2.1, 3.2.7 |
| `directive_preset_unknown_option` | `config.directive_preset_unknown_option` | §3.3.3 |
| `directive_preset_invalid_value` | `config.directive_preset_invalid_value` | §3.1, 3.3.5 |
| `directive_preset_option_conflict` | `config.directive_preset_option_conflict` | §3.3.1 |
| `directive_preset_append_not_list` | `config.directive_preset_append_not_list` | §3.3.4 |
| `directive_preset_argument_not_accepted` | `config.directive_preset_argument_not_accepted` | §3.3.6 |
| `directive_preset_identity_option` | `config.directive_preset_identity_option` | §3.3.2 |
| `directive_preset_unknown_key` | `config.directive_preset_unknown_key` | §3.1.2 |
| `preset_forced_option` | `directive.preset_forced_option` | §3.4.4 |
| `directive_template_invalid` | `config.directive_template_invalid` | §5.1 |
| `template_context_reserved` | `config.template_context_reserved` | §4.7 |
| `template_switched_off` | `template.switched_off` | §6.1 |
| `template_signature` | `template.signature` | §5.3 |
| `template_option_invalid` | `template.option_invalid` | §6.3, 6.4 |
| `template_context_unknown` | `template.context_unknown` | §6.2 |
| `template_context_invalid` | `template.context_invalid` | §4.2, 4.3, 4.7, 6.2 |
| `template_context_unavailable` | `template.context_unavailable` | §7.2 |
| `template_missing` | `template.template_missing` | §6.3 |
| `template_outside_root` | `template.template_outside_root` | §2.4 |
| `template_render_error` | `template.render_error` | §7.3, 7.7 |
| `template_output_limit` | `template.output_limit` | §7.5 |
| `template_disabled` | `template.template_disabled` | §7.6 |
| `template_nested_expansion` | `template.nested_expansion` | §7.10 |
| `template_output_reads_file` | `template.output_reads_file` | §7.10 |
| `template_markup_heading` | `template.markup_heading` | §7.9 |

The rule behind the template rows: a ubCode code `template.<sub>` is the corpus code
`<sub>` when `<sub>` already starts with `template_`, else `template_<sub>`. The codes
never in a corpus: ubCode's `template.value_limit`, `template.compute_limit`,
`template.cancelled` (§7.5), and the Sphinx half's `extend_unsupported` (§2.1),
`template_reads_dependency` (§7.10) and `template_markup_unsupported` (a Markdown
template in a project that does not load myst-parser).

## 9. The corpora

1. Both corpora are canonical here; ubCode vendors each byte-for-byte with a provenance
   block prepended, pinned by a digest and a case-count fence
   (`rust/ubc_parser_ctrl/tests/conformance/mod.rs`). A change to a corpus is a change to
   this contract and owes ubCode a re-vendor.
2. Their bytes are protected: `.gitattributes` pins LF, and the taplo and yamlfmt hooks
   exclude them.
3. Each runner pins its case COUNT, the uniqueness of names, a complete expectation per
   case and the header's "canonical" line. Enforced by:
   `tests/test_presets_conformance.py::test_the_corpus_still_has_every_case`,
   `…::test_every_case_has_a_complete_expectation`,
   `…::test_the_corpus_header_records_where_it_is_canonical`, and the same three in
   `tests/test_templates_conformance.py`.
4. **The engine version is part of the template corpus.** Its header records the
   minijinja version it was recorded against. A lock check alone is not enough — the two
   sides compile different FEATURES of one version — so the dialect cases are the feature
   check, and the version check is `tools/check_minijinja_version.py` (and
   `tests/test_minijinja_version.py`): the monorepo's locked minijinja equals the
   version the header records. ubCode's runner records its own `Cargo.lock` version.
