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
need attributes are **experimental**; the configuration value is not.

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
a structured key is the slower lookup: a dict keyed by `(segments, local id)` tuples takes
3.6 to 3.8 times as long as one keyed by the joined strings to look up 14 044 namespaced
ids (prebuilt keys, the minimum of five runs of fifty lookups, three rounds, at this tip).

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

`needs_namespaced_ids` (`[needs] namespaced_ids`), a boolean, **on by default**, rebuild
`"env"` (flipping it re-reads every document). It is read where a need is created, in the
creation funnel (`api.need._generate_need`, which every route passes: a directive, the API,
`list2need`, `needservice`, `needimport`, `needs_external_needs`, and the family's
producers), and by `needextract` to classify an argument naming an id that does not exist.
Nothing else reads it: the filters and the hints read what the funnel stored. Off, no id is
split and every need is plain; the filter names stay defined and read `""` and the whole id,
and no hint is offered, as no need is in a namespace. "No namespaces" is the empty rule,
not a second mode of the code.

## 4. What does not split, and why it is never refused

An id that holds `::` but does not split cleanly (`A::::B`, `NS::`,
`std::vector<int>::size`) is a **plain id**. It is never refused: with the rule on by
default, refusing would break projects whose ids hold `::` for another reason, and every
import of such a file. An id the project writes or generates is reported at the need, once
per need directive (a duplicate of such an id, refused as a duplicate, is reported for its
id too), as `needs.id_namespace`, with the class of the problem and the three ways out
(correct the id; `needs_namespaced_ids = False`; suppress the warning type). It does not
name the offending segment: finding it would mean cutting the id outside the one module.
An imported or external need is the data of the project that wrote it and is not
reported, as it is not checked against the id patterns. The report is the funnel's last
act: a need an id pattern or a value refuses is reported for that refusal, not for its id.

## 5. Id patterns

`needs_id_regex` and a need type's `id_regex` accept an id whose LOCAL id matches, or
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
name at once. None of those is wanted: `needs.json` format 1 and the draft `"2a1"` are
byte-identical with the switch on and off, and the names `ns`, `local_id`, `id_ns` and
`id_local` stay free for a project's fields. `ENV_DATA_VERSION` 27 records the two slots.

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

A dead outgoing link (an external need's too: it explains why the target is not found
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

## 9. Deliberately absent

- a `namespace` option on `needimport` and `needs_external_needs`, beside `id_prefix`
  (later; `id_prefix` ending in `::` already gives a namespace, and is unchanged);
- `c.` values as needtable columns or sort keys (later, a resolver that serves `c.source`
  too);
- short references, a bare id resolving inside the referencing need's own namespace first
  (later: a recon, a ruling, a build);
- any `needs.json` key: format 2 is to carry `ns` beside the full `id` (later);
- an index-tier arm for `c.in_namespace` (the fast tier answers it, section 10);
- a lint for a filter that names a namespace no need has, or a bare-id filter (a namespace
  no need is in selects nothing, as any filter matching nothing does);
- any change to `id_prefix`;
- did-you-mean hints on `needextend` and `needextract` "not found" messages.

**Alternatives considered.**

- *Declared namespace roots* (an id is namespaced when its first segment is declared): lost
  because every importing project would have to declare every root a file brings.
- *An opt-in switch*, off by default: lost because namespaces would never become normal,
  and turning it on later is the same change with an off-switch kept for ever.
- *Root-level filter names* (`ns`, `local_id`): lost because they would have to be
  reserved field names, where `c.` can be shadowed by nothing.

## 10. Measurements (unreleased tip, Python 3.13, sphinx 9.2, one machine)

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
  need selected) about 5 ms (two machines' runs, each the minimum of five runs of twenty,
  which differ by up to a quarter and agree on the order). No index arm is needed.
