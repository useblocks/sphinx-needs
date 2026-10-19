# Namespaced need ids

This file records the design of namespaced ids in sphinx-needs: what a namespaced id is,
which rules ship in which release, how a namespace is to be queried and why, and what is
deferred. The user's documentation is `docs/namespaced_ids.rst`; the executable contract
both sphinx-needs and ubCode are held to is `tests/fixtures/namespace_conformance.toml`.

Status: the first slice is in the next release, behind the experimental switch
`needs_namespaced_ids`. Each rule below says **this release** or **planned**.

## 1. The identity model

A need's identity stays one string, its id. With the switch on, that string is read as a
**namespace** and a **local id**: `nc::testcase::T_001` is the local id `T_001` in the
namespace `nc::testcase`, of the segments `nc` and `testcase`. An id without `::` has no
namespace and is its own local id.

The split grammar is not sphinx-needs': it is the needs.json exchange contract's,
`packages/ub-needs-exchange/design/exchange-contract.md` section 5.4, and its one
implementation is `ub_needs_exchange.split_id`. sphinx-needs calls it for every id and
never re-implements it, so sphinx-needs, ubCode and any reader of needs.json split an id the
same way.

Storage, **this release**: `NeedItem.ns` (a tuple of segments, `()` for none) and
`NeedItem.local_id`, two slots set once when the need is created, beside the id, which stays
the key of every map and the value of `need["id"]`. With the switch off they are `()` and the
id. They are not fields: no mapping key, no needs.json key, no schema property.

Why the string stays the key (recon `fable/njns-recon.md` Q5, Q9(b)): `need["id"]` is a
string in sphinx-needs' public Python contract (every `needs[some_id]` in user code, Sphinx
and HTML targets, `needs_string_links`), so the joined spelling has to exist anyway; a tuple
key is also the slower lookup (1.6 to 2.9 times a string key, measured on 14 044 ids). Stored
parts cost one slot read where splitting on read costs a parse per access.

## 2. The rules

| rule | release |
|---|---|
| the switch `needs_namespaced_ids` (`[needs] namespaced_ids`), off by default; off, nothing changes | this release |
| every id split with `split_id` -- authored, generated, imported, external | this release |
| an id that does not split is refused like an id failing `needs_id_regex`, its message naming the rule | this release |
| `needs_id_regex` applies to the local id (imported and external needs stay exempt); `needextract`'s id argument likewise | this release |
| `ns` and `local_id` reserved as field and link type names while the switch is on | this release |
| reserved unconditionally | planned, at the next major (refusing a name is a breaking change) |
| the version-level marker `"namespaced_ids": true` written, and read (section 5) | this release |
| filters: `ns`, `local_id`, `in_namespace()` in all three filter tiers | planned, the next slice |
| a namespace declared by an import or external source, replacing `id_prefix` for it and rewriting links through the link object | planned |
| schemas see `local_id`, so an id pattern written for the local id can move there | planned |

A generated id gets no namespace of its own in this release; it is split as written, so a
need type whose `prefix` holds `::` gives its generated ids that namespace, by the same rule
as any other id. That is not a type's default namespace (section 6): it applies only to ids
the author did not write, which already change with the title.

Why the regex applies to the local id (recon Q1, Q6): a project's `needs_id_regex` and the id
patterns in its schemas are written for the local id. Namespacing the 14 025-need benchmark
corpus per page made every one of its needs fail the corpus's own schemas (none in the plain
build), because `^SW_REQ_` began to see `plat::m2::SW_REQ_13708`. Applying the regex to the
local id keeps its meaning; the namespace is checked against the fixed grammar instead. The
schema half is the planned `local_id` property, not a hidden rule in the schema language.

## 3. Querying a namespace (planned)

Three levels, each a different question:

| level | query | selects |
|---|---|---|
| exact | `id == "nc::testcase::T_001"` | one need |
| one level | `ns == "nc::testcase"` | the needs directly in that namespace, not in `nc::testcase::sub` |
| subtree | `in_namespace("nc")` | the needs in `nc` and in every namespace under it: `ns == "nc" or ns.startswith("nc::")` |

In a filter, `ns` is to be the namespace's joined spelling, which the next slice settles
beside the tuple `NeedItem.ns`.

The three levels are established ground (`fable/njns-prior-art.md`, each claim checked
against its primary source):

- **Bazel**, the closest analogue: a label names one target (`//foo:bar`), `//foo:all` every
  rule in package `foo` "but not its subpackages", and `//foo/...` every rule in `foo` and
  every package recursively beneath it; `bazel query` evaluates the same patterns as
  `bazel build` (<https://bazel.build/run/build>, <https://bazel.build/query/language>).
  `ns ==` is Bazel's `:all`.
- **MQTT 5.0** (§4.7.1, <https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html>):
  a topic filter has an exact topic, `+` for "only one topic level", and `#` for "the parent
  and any number of child levels" (`sport/#` "also matches the singular `sport`"). `ns ==` is
  MQTT's `+`, and `in_namespace()` its `#`, parent included.
- **git** (<https://git-scm.com/docs/git-for-each-ref>): `git for-each-ref` matches a literal
  pattern "completely or from the beginning up to a slash", so `refs/heads/nsp` lists the
  `nsp/` subtree but not `nspx`, while a glob's `*` does not cross `/`. `in_namespace("nc")`
  is git's literal rule: the separator is part of the prefix test, so `nc` never matches
  `ncx`.
- **Amazon S3** (<https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-prefixes.html>):
  keys are flat strings with a separator convention; `ListObjectsV2` lists one level with
  `Prefix='a/'` and `Delimiter='/'` or the subtree with `Prefix='a/'` alone, a raw prefix that
  is only level-safe when it ends in the delimiter -- the mistake `in_namespace` rules out by
  appending `::` itself.
- **The qualifier as a field beside the name**: Kubernetes keeps `metadata.namespace` beside
  `metadata.name` and lets a field selector test it
  (<https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/>); SQL's
  information schema exposes `table_schema` beside `table_name` though a table is written
  `schema.table` (<https://www.postgresql.org/docs/current/infoschema-tables.html>); Jira
  queries `project = ABC` beside `issueKey = ABC-123`
  (<https://confluence.atlassian.com/jirasoftwareserver/advanced-searching-fields-reference-939938743.html>).
  That is the case for `ns` as its own name an index can serve, rather than a string test on
  `id`. None of the three nests; storing a nested namespace beside the id has no direct
  precedent among them.

LDAP's three scopes (RFC 4511 §4.5.1.2, <https://www.rfc-editor.org/rfc/rfc4511.txt>) look
similar but are not the model: its `singleLevel` is the immediate subordinates of an *entry*,
the base excluded, whereas `ns ==` selects the needs of a namespace, which is not itself a
need.

Why built in rather than left to `eval` (recon Q2, 14 000 needs): selecting a namespace
today means an `eval` filter at 100 to 130 ms; with `ns` on the index path it was 0.095 ms,
`in_namespace()` 1.1 ms, a type within a namespace 0.35 ms, at no measurable cost to existing
filters.

## 4. One string, a need and a namespace

A need `nc::testcase` (local id `testcase` in `nc`) and needs in the namespace
`nc::testcase` coexist; nothing refuses it (this release, ruled 2026-10-19). git and Java
forbid a name being both an item and a container; MQTT and S3 allow it
(`fable/njns-prior-art.md`). An id names one need, while `ns ==` and `in_namespace()` name
sets, so no query is ambiguous, and a namespace can have a "root" need, such as a component
whose parts live in its namespace. Forbidding it would mean cross-checking every id against
every namespace at load, with a refusal an author can fix only by renaming.

## 5. needs.json, and crossing the switch

**This release.** A project with the switch on writes `"namespaced_ids": true` in each
version it writes; ids and link targets keep the joined spelling. The marker is
version-level because a `needs_file` accumulates versions from builds before and after the
switch was turned on, and only the versions written with it on are namespaced. The marker is
the one commitment the experimental label cannot cover: a file written with it is read for as
long as it exists.

Every deployed reader ignores the marker and reads the joined string as the id
(`ub-needs-exchange` 1.0.0, sphinx-needs 9.0.0, ubCode; recon Q7 addendum), and with the
switch off the output is byte for byte what it was: measured on the recon's probe project and
on every needs.json the test suite writes.

Reading a needs.json (`needimport`, `needs_external_needs`):

- **switch on, marked version**: every id split, nothing reported;
- **switch on, unmarked version**: every id split all the same -- `ns` and `local_id` must
  follow from the id whatever its source -- and, when one of its ids holds `::`, one
  informational message per source. Refusing the version would break every project that
  already uses `::` ids the day it turns the switch on;
- **switch off, marked version**: the joined strings are plain ids, as today, with one
  informational message per source. Off means today's behaviour;
- an imported or external id that does not split is refused, one warning per need, as any
  record that cannot be read is.

## 6. Deferred, and why

- **A need type's default namespace.** Both tools rebuild every need from its source on each
  build, so a namespace taken from the type would change a need's id whenever it is re-typed,
  breaking its inbound links; "stored at creation, never recomputed" cannot hold without
  writing the namespace into the source (recon Q5). In this release a namespace comes only
  from the id itself, so identity is a function of the text the author can see; a source's
  declared namespace is the planned second origin.
- **Short-name resolution** -- a bare `T_001` in a link meaning the local need of the
  linking need's namespace. It makes a link's meaning depend on where it is written, which
  the joined spelling avoids; it needs its own design.
- **The needs.json v2 identity shape.** Structured records cost nothing measurable (at most
  1.3 % in size and 6 % in parse time; recon Q9(a)), so the shape is a semantic choice, made
  with the v2 format. The joined spelling plus the marker is what a v1 projection of it will
  write, so this slice commits nothing v2 would have to undo.
