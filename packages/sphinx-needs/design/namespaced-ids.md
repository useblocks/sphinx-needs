# Namespaced need ids

This file records the design of namespaced ids in sphinx-needs: what a namespace is, how
sphinx-needs reads one out of an id, what it stores, how a filter reads it, and what is
deliberately left for later. The user's documentation is `docs/namespaced_ids.rst` (with
`needs_namespaced_ids` in `docs/configuration.rst` and the filter names in
`docs/filter.rst`, section "Filtering by namespace"). The executable halves are the
need-id corpus of ub-needs-exchange (the grammar), the "namespaced ids" section of
`tests/fixtures/filter_conformance.toml` (the filter names, in both tiers) and
`tests/test_namespaced_ids.py` (the rest).

Status: describes the implementation as it is (unreleased). The filter names and the
need attributes are **experimental**; the configuration value is not, nor is the
`namespace` of an import (section 10).

## 1. The model

A need's identity is a namespace (zero or more segments) and a local id, and its `id` is
the text of that pair, `seg::seg::LOCAL`. **Whether an id is namespaced is a function of
its text and ONE rule of the project**, `needs_namespaced_ids`: nothing else (who created
the need, which file it came from, a declaration elsewhere) decides it. So two needs with
the same id always have the same namespace, a link target can be split without resolving
it, and a reader applies its own rule to every id whatever wrote the file.

**The joined string is the key.** `id` is unchanged everywhere: the key of every mapping
(`NeedsView`, the environment), `need["id"]`, the HTML anchor, the `needs.json` id, what a
link and a `:need:` role name. `need["id"]` is a string in the public Python contract, and
a structured key is the slower lookup: a dict keyed by `(segments, local id)` tuples is
slower to look up than one keyed by the joined strings, because a tuple's hash is computed
on every lookup while a string caches its own.

## 2. The grammar, and the composition order

The grammar is not sphinx-needs': it is section 14 of
`packages/ub-needs-exchange/design/exchange-contract.md`, implemented once in
`ub_needs_exchange.need_id` and pinned by that package's need-id corpus. In short: split
at the LAST `::`; the text before it, cut at every `::`, must give segments of ASCII
letters, digits, `_` and `-`, and the local id must not be empty; otherwise the id is a
plain id with a problem of one of three classes (`EMPTY_LOCAL`, `EMPTY_SEGMENT`,
`SEGMENT_CHARACTER`). Splitting never fails.

sphinx-needs calls that module for every split, join, parse and format: no string constant
equal to `"::"` appears under `src/sphinx_needs`
(`tests/test_namespaced_ids.py::test_only_the_exchange_package_spells_the_separator`).

**The composition order, stated once.** A link target is not an id. Its `[condition]` is
stripped first, then its part is split off at the FIRST `.`, and only then is the
namespace split at the LAST `::` (`nc::m2::REQ_1.p1[status == "open"]` is the need
`nc::m2::REQ_1`, its part `p1`, the condition `status == "open"`). The link grammar is not
changed. One consequence predates namespaces: a local id holding `.` cannot be named by a
link without its tail being read as a part.

## 3. The switch

`needs_namespaced_ids` (`[needs] namespaced_ids`), a boolean, **off by default in the 9.x
series and on by default from 10.0** (section 3.1), rebuild `"env"` (flipping it re-reads
every document). It is read where a need is created, in the
creation funnel (`api.need._generate_need`, which every route passes: a directive, the API,
`list2need`, `needservice`, `needimport`, `needs_external_needs`, and the family's
producers), and by `needextract` to classify an argument naming an id that does not exist.
Nothing else reads it but the warning of section 9: the filters and the hints read what the
funnel stored. Off, no id is
split and every need is plain; the filter names stay defined and read `""` and the whole id,
and no hint is offered, as no need is in a namespace. "No namespaces" is the empty rule,
not a second mode of the code.

### 3.1 The default (ruled 2026-11-17)

The feature ships whole in a minor release (9.3.0), but OFF by default there, and ON by
default from 10.0. Turned on, two of its rules can change what an existing project gets:
the warning for an authored id that does not split cleanly can fail a `-W` build, and the
local-id rule of the id patterns means a pattern can no longer refuse a namespace. Neither
should reach a project that did not ask for it in a minor release. With the switch on, the
behaviour is the one this record describes; with nothing set, a project builds as before
(one re-read of its sources aside, for the stored values). The switch itself is not
experimental; its default changes once, at 10.0.

## 4. What does not split, and why it is never refused

With the switch on, an id that holds `::` but does not split cleanly (`A::::B`, `NS::`,
`std::vector<int>::size`) is a **plain id**. It is never refused: with the rule on (by
default from 10.0), refusing would break projects whose ids hold `::` for another reason,
and every import of such a file. An id the project writes or generates is reported at the need, once
per need directive (a duplicate of such an id, refused as a duplicate, is reported for its
id too), as `needs.id_namespace`, with the class of the problem and the three ways out
(correct the id; `needs_namespaced_ids = False`; suppress the warning type). It does not
name the offending segment: finding it would mean cutting the id outside the one module.
An imported or external need is the data of the project that wrote it and is not
reported, as it is not checked against the id patterns. The report is the funnel's last
act: a need an id pattern or a value refuses is reported for that refusal, not for its id.

## 5. Id patterns

With the switch on, `needs_id_regex` and a need type's `id_regex` accept an id whose LOCAL id matches, or
which matches as a whole (each with `re.match`, as before). The local id keeps a project's
pattern meaning what it means (`nc::REQ_00001` passes the default through `REQ_00001`), and
"or as a whole" keeps every id a pattern accepted before accepted (`REQ_1::A`, whose local
id `A` fails the default). One seam reads both: `_namespaced_ids.id_matched_by_patterns`,
which `needextract`'s test of an argument naming a missing id reads too (with
`re.fullmatch`, as before). With the switch off, and for a plain id, local and whole are
one text. A refusal keeps its wording and names the local id too.

## 6. The stored structure, and why it is not a field

Each `NeedItem` stores its namespace (a tuple of segments, shared by the needs of one
namespace within a reading process: a `-j` read's workers and a loaded environment each
start their own)
and its local id in two slots that are **not mapping keys**, set once in the funnel and
kept by every copy, pickle, parallel merge and needtable row: the id never changes after
creation, so they cannot go stale. Read-only attributes expose them: `id_ns` (text),
`id_ns_segments` (the tuple), `id_local`; a part answers with its need's.

A key of the need's mapping (a `_computed` key, a `NeedsCoreFields` entry) would have
been a root filter name, a `needs_schema` property, a `needs.json` key and a reserved field
name at once. None of those is wanted: `needs.json` format 1 and its draft `"2a2"` are
byte-identical with the switch on and off, and the names `ns`, `local_id`, `id_ns` and
`id_local` stay free for a project's fields. `ENV_DATA_VERSION` 28 records the two slots.

## 7. The filter names, and why they live under `c.`

`c.id.ns` (the namespace as text, `""` for none), `c.id.local` (the local id, the whole id
for a plain id), and `c.in_namespace("<ns>")` (the namespace or below it, by segments). Text
rather than the tuple, because the portable language has no list equality or subscripts,
and in `eval` a tuple never equals a string. An empty argument, or one that is no
namespace, is an error of the filter in both tiers, never "every need"; "in no namespace"
is `c.id.ns == ""`; in a derived field's `where` such a literal is the rule's problem,
`needs.derive_invalid`. `c.id` itself holds the facets, not the id: compared with a value
(`c.id == "nc::REQ_1"`, `!=`, `c.id in [...]`) it is an error of the filter, naming what
to compare instead (`id`, `c.id.local`, `c.id.ns`). `c.in_namespace` takes its argument
positionally.

They live under the check context `c`, beside `c.source`, because `c` is set over every
field: no name a project declares can shadow them, and none is reserved. They are added
through the same mechanism as `c.source` (`_id_facets.py` and one table of the check
context's facets, `_source_facets.CHECK_FACETS`, read by the eval object, the portable
tier's `c.<group>.<facet>` chain, the did-you-mean of an unknown facet, the explanation
where there is no check context, and a derived field's whitelist). `c.in_namespace` is
compiled in the portable tier for one string literal, as `c.is_a`; anything else is
answered by `eval`. The order of the dynamic functions records them as reading `id`.

## 8. Hints

With the switch on, a dead outgoing link (an external need's too: it explains why the target is not found
here), or a `:need:` role naming no need, gains ` (did you mean 'nc::REQ_2'?)` after its
unchanged text when its target, condition and part stripped: names no need, holds no `::`,
and is the local id of exactly one need in a non-empty namespace; and, where the target
names a part, that need has the part (which the hint re-attaches). Otherwise the message is
as it was; nothing changes in what resolves. The index of local ids is built lazily, when
the first such target is met, and shared by the links and the roles of a build: one per
build, made when the needs are post-processed and kept on the application object the two
callers hold (`_namespaced_ids.reset_local_id_hints` / `local_id_hints`), never in the
environment, which Sphinx pickles. An application that builds twice (a server rebuilding on
change) gets a new one for each build, and neither build's pickled environment holds one
(`tests/test_namespaced_ids.py::test_the_hint_index_is_one_builds_and_never_pickled`).

## 9. The warning for a namespace filter with the switch off

**The rule.** With the switch off, a filter string that reads `c.id.ns`, `c.id.local` or
`c.in_namespace()` is answered as written (every need plain: `""`, the whole id, false) and
reported as `needs.namespaced_ids_off`, naming what it reads, what each is with the switch
off, and the two ways out (turn the switch on; suppress the warning type). The reason: such
a filter gets an answer that means nothing, `c.in_namespace("nc")` selecting no need and
`not c.in_namespace("nc")` every need, and no word that it does. With the switch on it never
fires, and no answer changes either way.

**Where it is detected.** By the filter's text as parsed (`_source_facets.namespace_reads`,
which `_check_reads` gates), in `filter_common._report_namespaced_ids_off`, which the two
entries every filter string evaluated over needs passes call before either tier:
`filter_needs_and_parts` and `filter_single_need`, beside the report of a `c.is_a` literal
naming no need type. The switch is read first, so with it on no text is read; the text is
walked with an explicit stack, never recursively, so a filter nested past the interpreter's
recursion limit is checked like any other. The text names the filter. A string the text
shows refused has its refusal and nothing beside it: one that does not parse, a
`c.in_namespace` call that is not one positional argument or whose literal names no
namespace (`namespace_argument` judges it), a facet that is none, `c.id` compared or hashed,
each judged only where evaluation reaches it unconditionally (not a later operand of `and` /
`or`, not a branch of a conditional, not a lambda or comprehension body). **Where the text
cannot settle whether a filter is refused, the warning is given**: a filter may then get
both findings, and none at all is the outcome this rule exists to prevent. Once per build
per place: the key is the string, where it is written and the origin its caller appends (a
`needs_warnings` entry, the builder filter, an external need's link condition), so a place
with no location is reported once per string per build; the keys are emptied where the need
types are set. A `needextend` filter, evaluated once per document, is reported again for
each further place in that document it is written; a `needflow` highlight, a `needgantt`
milestone filter and a `needsequence` filter, evaluated need by need, are reported once at
their directive before any need is tested. A quiet pre-pass (the one ordering the dynamic
functions evaluates a `copy` or `calc_sum` filter first) runs under
`filter_common.quiet_filters`, which restores the reported keys, so it does not use up the
real place's report (nor that of a `c.is_a` naming no need type). A directive's filter is
evaluated where its page is resolved, and a `needextend`, a constraint, a dynamic function's
filter and a derived field's `where` where the needs are post-processed (`write-started`);
both run in the main process of a `-j` build too, so a parallel build reports what a serial
one does.

**What it cannot see.** A name reached dynamically (`getattr(c.id, "ns")`, which `eval`
answers); a filter function or a directive's filter code, which are Python, not filter
strings; where a filter is data or configuration evaluated need by need (a link condition,
a constraint, a dynamic function's filter, a derived field's `where`), a filter tested on no
need, as nothing reads it there; and a refusing construct the text sees in a first operand
that evaluation happens not to raise (`c.id in [] or c.id.ns == ""`: an empty list compares
nothing), which keeps such a filter unreported. Where there is no check context (a
`needimport` filter, a field's predicate, a variant condition) a read of `c` is refused
already, and that refusal stands alone.

## 10. The namespace of an import

**The rule.** `needimport`'s `:namespace:` and a `needs_external_needs` source's
`namespace` key are the `id_prefix` of the namespace's text followed by the separator, with
the value checked: `namespace = SUP` is `id_prefix = SUP::`. The value is resolved ONCE, at
the option's boundary, into that prefix text (`_namespaced_ids.import_prefix`, through
`ub_needs_exchange.namespace_prefix(parse_namespace(text))`; no consumer spells the
separator), and below it the existing prefix path runs unchanged: ids, links to the file's
own ids, parts, conditions, the file schema's link defaults, the content rewrite, external
URLs, duplicates. The two spellings give the same needs, field for field, the same
`needs.json` and the same pages (`tests/test_import_namespace.py` builds both and compares).
Every reader of an external source's prefix -- the loader, and the set a part's external
URL is computed from, read by `:need:` and `:need_outgoing:` -- reads it through one
helper, `external_needs.source_id_prefix`. Nothing is stored: the option is its prefix,
and `ENV_DATA_VERSION` does not move.

**Why a prefix, not a join per id.** Wherever `join_id` accepts an id of the file under the
namespace, the prefix followed by the id IS that joined id (the first law of
`namespace_prefix`, rule 10 of section 14 of ub-needs-exchange's contract, pinned by its
need-id corpus); wherever it refuses, the prefixed text is a plain id outside the namespace (the
second law). So the prefix is the join on every id that can be joined, and on the others it
keeps the import whole: no need is lost, and every link of the file to it still resolves, as
with `id_prefix`.

**The refusals.** Both options together; a value that is not a namespace (one that ends in
the separator is told to drop it; any other is told the rule a segment obeys); for a source,
an empty value or one that is not a string. Each goes through the place's existing refusal
path: at a `needimport`, one `needs.needimport` warning at the directive and nothing
imported, as for a file that cannot be read (an empty `:namespace:` is docutils' "argument
required"); for a source, `NeedsExternalException`, which stops the build, as a missing
`base_url` does, naming the source by its index.

**The notices: one per import, never per need.** With the switch off (the 9.x default) the
prefix is added all the same, and each import under a namespace gives one
`needs.namespaced_ids_off` warning: its ids are plain, so a namespace filter over them would
select nothing (section 9's rule, applied where the namespace is written). With the switch
on, an import whose ids include some that cannot be joined (`id_problem(prefix + id)` is
not `None`: `a::::b`, `:X`) gives one `needs.import_namespace` warning, naming how many and
the first five; an import whose ids all join gives none. The type is its own, so that it can
be suppressed without silencing `needs.needimport` (a file that cannot be read). The two are
exclusive: with the switch off no id is in a namespace, so none is outside one. An
`id_prefix` gives neither, as before. Counted are the needs the import selects (after
`:ids:` and `:filter:`; a record refused afterwards, a duplicate id say, is counted all the
same), an empty id (refused on its own) left out.

**What an older version does.** sphinx-needs 9.3.0 reports `:namespace:` as an unknown
option (a docutils error; the directive imports nothing), and ignores the source key without
a word: the needs arrive with the file's ids. The docs say so, and point at Sphinx's
`needs_extensions`.

## 11. Deliberately absent

- `c.` values as needtable columns or sort keys (later, a resolver that serves `c.source`
  too);
- short references, a bare id written inside a namespaced need naming a need of that
  namespace (later: a recon, a ruling on the lookup order, a build);
- any `needs.json` key: format 2 is to carry `ns` beside the full `id` (later);
- an index-tier arm for `c.in_namespace` (the fast tier answers it, section 12);
- a lint for a filter that names a namespace no need has, or a bare-id filter (a namespace
  no need is in selects nothing, as any filter matching nothing does);
- any change to `id_prefix`, and any deprecation of it (a text prefix that is not a
  namespace, `SUP_`, has no `namespace` spelling);
- a `namespace` argument on a Python function (`add_external_need`, `create_need`): a
  caller builds the id with `ub_needs_exchange.join_id`;
- did-you-mean hints on `needextend` and `needextract` "not found" messages.

**Alternatives considered.**

- *Declared namespace roots* (an id is namespaced when its first segment is declared): lost
  because every importing project would have to declare every root a file brings.
- *An opt-in switch kept off for good*: lost because namespaces would never become normal;
  the switch is off by default only through 9.x (section 3.1) and on from 10.0.
- *Root-level filter names* (`ns`, `local_id`): lost because they would have to be
  reserved field names, where `c.` can be shadowed by nothing.

## 12. Measurements (unreleased tip, Python 3.13, sphinx 9.2, one machine, with `needs_namespaced_ids = True`)

- **Memory**: the needs of a 10 000-need build, held after a pickle round trip
  (`tracemalloc`), against the base without namespaces, the arms interleaved with a null arm
  (the same code twice, spread at most 62 bytes): 10 000 ids in one namespace (`nc::REQ_…`)
  +0.67 MB, +1.5 %, about 67 bytes a need (the two slot pointers and the local id's own
  string); 10 000 plain ids +0.16 MB, +0.4 %, 16 bytes a need (the two slot pointers alone:
  the empty tuple is shared, and the local id is the id's own string). The pickled needs:
  5.06 MB against 4.87 MB (namespaced), 4.93 MB against 4.83 MB (plain).
- **Filters** over 14 000 needs (7 000 in `nc` or below), fast tier, `filter_needs_view`:
  `c.in_namespace("nc")` is the fastest of the four measured, about 3 ms, about half of
  `id.startswith("nc::")`; `c.id.ns == "nc"` about 4 ms; `type == "req"` (index tier, every
  need selected) about 5 ms (two runs on one machine at different loads, each the minimum of
  five runs of twenty, which differ by up to a quarter and agree on the order). No index arm
  is needed.
