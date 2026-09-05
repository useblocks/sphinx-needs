# The mount mapping contract

This document is the **normative** specification of how sphinx-mounts turns a
`ubproject.toml` mount declaration into a set of `(docname, absolute path)` pairs,
and of every rule that decides what happens when two things want the same docname.

It also specifies `[[source.variant_sources]]` (§12), the second key this reader
takes out of the same file — because that key decides *which documents exist*,
which is exactly what this document is for.

It exists because "declarative TOML so any language can read the mapping" is only
a real promise if the mapping is written down.
Without it, a second implementation — an editor plugin, a language server,
an indexer, a build-system integration — has to infer the rules from prose
scattered across the user documentation, and will diverge on exactly the
under-specified points: suffix matching order, path resolution, pattern dialect,
tie-breaks.
Those divergences surface to a user as "the editor shows a page the build does not"
(or the reverse), which is worse than either behaviour alone.

Audience: implementers of a second reader.
End users should read [`docs/source/configuration.rst`](../docs/source/configuration.rst),
which links here for the precise rules.

Status: describes the implementation as it is, not as it might become.
When behaviour changes, this document changes in the same commit.

## 1. Where the mounts array lives

The array of tables may be declared in either of two locations:

| Location | Status |
| --- | --- |
| `[[source.mounts]]` | **Canonical.** `[source]` owns source discovery in the shared `ubproject.toml` vocabulary. |
| `[[mounts]]` (top level) | **Deprecated.** Reads identically, and emits `mounts.deprecated_location`. |

Rules:

1. Exactly one location may be **declared** in a file.
   Declaring both is a hard configuration error (`TomlConfigError`) naming both
   locations.
   A reader must not pick a winner or merge the two: the effective mount list
   would then depend on a precedence rule invisible to anyone reading the file.
   This is unchanged by the deprecation — a deprecated location is still a
   declaration.
1a. The deprecated location must be **read**, not ignored, and reported.
   A second implementation that honours only `[[source.mounts]]` is the reason
   the deprecation exists in the first place: if the two readers disagree about
   which tables count, the same file describes two different projects. Warning
   on the old spelling while still honouring it is what lets both readers agree
   during the migration. Removal is not scheduled by this document.
2. "Declared" means the key is present, including when its value is an empty array.
   `mounts = []` is a statement that the project has no mounts.
3. A `[source]` table that contains no `mounts` key is not a declaration.
4. A `source` key whose value is not a table is ignored entirely
   (another tool may own that name for something else).
5. Nesting under `[source]` implies **no inheritance**.
   A mount does not read, default from, or otherwise consult any other `[source]` key.
   See §5 on why this matters for `include` / `exclude` specifically.

Both spellings are identical in every other respect covered by this document —
keys, anchoring, validation, precedence against `conf.py`, everything in §2
onwards. The only difference is the diagnostic.
Where the rest of this document says "the mounts array", it means whichever one
was declared.

## 2. Config precedence: TOML versus `conf.py`

A mount list may also come from a `mounts = [...]` value in `conf.py` (the legacy path).
The rule is about *declaration*, not about file existence:

| Situation | Effective mount list |
| --- | --- |
| TOML declares a mounts array | the TOML's |
| TOML declares an empty array | empty — `conf.py` is overridden |
| TOML exists but declares no mounts key | `conf.py`'s |
| TOML file absent | `conf.py`'s |
| `sources_from_toml = None` in `conf.py` | `conf.py`'s (TOML is never read) |

The third row is load-bearing:
a `ubproject.toml` present only to configure *other* tools must never silently
switch a project's mounts off.

`sources_from_toml` is documented as a path relative to `confdir`.
The implementation also accepts an absolute path, and a relative path may climb
above `confdir` with `..`; neither is rejected.
A second reader may reject them, but must not assume they cannot occur.

`mounts_from_toml` is the deprecated spelling of the same value and is still
honoured; setting it explicitly is reported (`mounts.deprecated_confval`).
Setting both explicitly to different values is a hard configuration error, for
the reason §1 rule 1 gives about the two array locations: the effective value
must be readable off the file, not off a precedence rule.
`= None` disables **everything** this reader takes from the TOML — the mounts
array and the variant rules of §12 alike.

## 3. Path anchoring and resolution

Two separate steps, in this order.

**Step 1 — anchor.** A relative `dir` or `files` entry is made absolute against:

| Declared in | Anchor |
| --- | --- |
| `ubproject.toml` (either location) | the directory containing **the TOML file** |
| `conf.py` (legacy) | `confdir` |

Anchoring to the TOML's own directory — not to `confdir` — makes the file
self-describing: moving it as a unit keeps its relative paths meaningful,
and a TOML in a subdirectory of `confdir` does not silently re-anchor.

**Step 2 — resolve.** Every `dir` and every `files` entry is then resolved:
`..` segments collapsed and **symlinks followed**.
This applies to paths that were already absolute, too.
There is no opt-out.

Consequences a second implementation must reproduce or knowingly deviate from:

- Path confinement (§9) compares resolved paths on both sides.
  This is what makes a bundle reached through a symlinked directory work rather
  than being reported as an escape — the case that matters whenever a build
  system exposes its outputs through a symlink.
- Diagnostics name the **resolved** path, not the path the user wrote.
  A mount configured through a symlink is reported by its target.
- The resolved absolute paths are what reach Sphinx as the `mounts` config value,
  so **relocating the checkout changes that value** and invalidates the build
  environment even though nothing semantic changed.
  This is the same mechanism that makes an edit to `ubproject.toml` correctly
  invalidate the cache, so it is a deliberate trade.
  Comment-only edits change nothing.

Existence is **not** part of resolution.
A path that resolves but is not on disk is not a configuration error;
it is reported later, during discovery, as `mounts.missing_path` (§7).
A build whose upstream bundle has not been produced yet still runs.

## 4. Per-key reference

One table is one mount entry.
Exactly one of `dir` / `files` must be present.

**Unknown keys are reported and ignored** (`mounts.unknown_key`), not rejected.
This contract previously specified a hard error, and the change is deliberate.

A `ubproject.toml` is shared with tools on independent release cadences, so a
key one reader does not model is routine rather than a mistake — and aborting
takes down every build of that project on every older reader, including builds
the key would not have changed. It cannot be staged either: a mono-repo cannot
upgrade every consumer atomically.

The change is timed rather than merely reasoned. The window it closes is the
one a future **gating** key would fall into: a reader that mounts a bundle while
ignoring a key saying *not to* publishes content the author gated, silently and
at full size. That window opens exactly when a version exists which reads
`[[source.mounts]]` but not the gating key — so the tolerant path has to ship
no later than the release that makes `[[source.mounts]]` readable at all, and
it does. A reader implementing this contract from scratch inherits the closed
window; one that keeps the old strictness reopens it.

**A gating key still ships simultaneously across readers.** Tolerance makes an
older reader survive the key, not honour it; a reader that ignores a gating key
still builds a document set the author did not ask for. So the key itself is
introduced in coordinated releases of every reader, and tolerance is what makes
the transition survivable rather than what makes it unnecessary.

The same posture applies to a `variant_sources` entry (§12) and matches ubCode's
`config.mount_unknown_key` / `config.variant_source_unknown_key`, so neither
reader is the strict one.

| Key | Type | Default | Meaning and constraints |
| --- | --- | --- | --- |
| `mount_at` | string \| absent | absent | Docname prefix; see §4.1 for the accepted shape. Absent means the bundle mounts at the project root, so a bundle file `tutorial.rst` becomes the docname `tutorial`. |
| `dir` | string | — | **Directory mode.** Root of a tree to walk. Mutually exclusive with `files`. |
| `files` | array of strings | — | **File-list mode.** Explicit files, at least one. Mutually exclusive with `dir`. |
| `include` | array of strings | `[]` | Allowlist patterns, directory mode only. See §5. |
| `exclude` | array of strings | `[]` | Denylist patterns, directory mode only. See §5. |
| `gitignore` | bool | `true` | Honour `.gitignore` / `.ignore` files **inside** the walked tree. Directory mode only. See §5. |
| `attach_to` | string \| absent | absent | Docname whose toctree receives this mount's entries. Same shape rules as `mount_at` (§4.1). May name a *mounted* docname, not just a host one (§8). |
| `toctree_index` | non-negative int | `0` | Which toctree inside `attach_to`, in document order. Booleans are rejected even though `bool` is an `int` in Python. |
| `entry_doc` | string | `"index"` | Mount-relative docname to wire. Same shape rules as `mount_at` (§4.1). |
| `attach_each` | bool | `false` | Wire *every* file instead of `entry_doc`. Requires `files` **and** `attach_to`, and is mutually exclusive with a non-default `entry_doc`. |
| `strict_mount_at` | bool | `false` | Skip the mount if the host srcdir already has a directory at `mount_at`. Requires an explicit `mount_at`. |
| `path_check` | `"warn"` \| `"error"` \| `"off"` | `"warn"` | Reaction to a reference that escapes the bundle root (§9). |
| `if` | string \| absent | absent | A condition over the variant map (§12.5). When it is **false** for the current variant the whole mount is gated off (§13). Absent means the mount is always built. |

### 4.1 Docname-shaped values

`mount_at`, `attach_to` and `entry_doc` are all docname-shaped strings and are
validated identically.
Applied **in this order**, because the order is observable — `//a/b` must be
rejected as absolute, not silently repaired:

1. Not a string, or the empty string → hard error.
2. Starts with `/` → hard error. A docname is always relative.
   This is checked **before** any slash trimming, so `//a/b` and `/abs` are
   both rejected. An implementation that strips surrounding slashes first
   would accept `mount_at = "/_generated/api"`, which this one does not.
3. Contains a `..` component → hard error.
4. Has leading or trailing whitespace → hard error.
5. Contains an empty interior segment (`a//b`), a `.` segment (`a/./b`, or a
   bare `.`), or a segment with whitespace around it (`a/ b`) → hard error.
6. Otherwise accepted, with **trailing** slashes stripped: `a/b/` and `a/b//`
   both normalise to `a/b`. This applies to all three fields alike.

Only rule 6 normalises. Everything else rejects, per §7's doctrine that a
configuration this extension cannot interpret is not suppressible.

Rules 4 and 5 exist because a docname is matched **literally**, never resolved
as a filesystem path, so the alternative is worse than either accepting or
rejecting cleanly:

- A docname holding an empty segment or a space cannot match any host
  document, so such a mount was accepted and then silently unreferenceable.
- A `.` segment is not a no-op. A bare `mount_at = "."` — the natural way to
  try to write "the project root" — yields the docname `./index` *alongside*
  the host's own `index`: two distinct docnames resolving to one output file,
  so one page is overwritten with no diagnostic at all. A root mount is
  expressed by **omitting** `mount_at`.

## 5. Discovery: which files a mount contributes

### 5.1 Directory mode

The tree under `dir` is walked with the Rust `ignore` crate (via `ignore-python`).
The walk policy is fixed:

| Setting | Value | Why it is not configurable |
| --- | --- | --- |
| ignore files inside the tree | per-mount `gitignore` (default on) | Only takes effect when the tree is itself a git repository, per the crate's contract. |
| ignore files in **parent** directories | never consulted | A mount often lives under a path the host workspace gitignores (a build-output directory). Honouring parents would silently produce zero files. |
| global git config, `.git/info/exclude` | never consulted | Builds must not depend on a developer's machine. |
| hidden entries (dotfiles, dot-directories) | skipped | |

Only files whose name ends with a registered source suffix are kept (§5.3).

`dir` must not contain the host source directory.
Nothing detects it: the docnames differ (every host page gains a second
docname under `mount_at`), so no collision rule in §7 can fire, and the whole
host project is published a second time under the mount prefix.

### 5.2 File-list mode

No walk. `include`, `exclude` and `gitignore` are therefore not read at all:
they configure the walker, and there is none.
Setting `include` or `exclude` here is reported as
`mounts.ignored_option` and changes nothing.

Each listed file is taken as given, and:

- a listed file that does not exist skips the **whole mount**
  (`mounts.missing_path`);
- a listed file with no registered suffix skips the **whole mount**
  (`mounts.unknown_suffix`) — the user named the file explicitly, so ignoring it
  silently would be wrong;
- a listed file whose name is *nothing but* a suffix (a file called `.rst`) has no
  docname and skips the **whole mount** (`mounts.empty_docname`).

Because there is no walker, there is no hidden-entry rule:
a listed dotfile such as `.hidden.rst` **is** mounted, as the docname tail
`.hidden`.
This is the one place the two modes disagree, and it is deliberate — file-list
mode is an explicit request for named files.
A second reader must reproduce the asymmetry:

| Mode | `.hidden.rst` in the mount | Result |
| --- | --- | --- |
| directory | present on disk | skipped (hidden) |
| file-list | listed | mounted as `<mount_at>/.hidden` |

### 5.3 Pattern dialect

`include` and `exclude` are **gitignore-style patterns**, evaluated relative to
`dir`, and fed to the `ignore` crate's override builder:
every `include` pattern is added as a positive override, then every `exclude`
pattern is added as a negated one (`!pattern`).

The crate's semantics are **last match wins**.
Because all includes are added before all excludes, that yields one rule worth
stating explicitly, since the gitignore intuition ("more specific wins") points
the other way:

> A broad `exclude` always beats a narrow `include`, regardless of the order the
> keys appear in the TOML.

So `include = ["keep.rst"]` with `exclude = ["**/*.rst"]` mounts **nothing**.

**These keys are not the same dialect as a same-named key elsewhere in the file.**
`[source].include` / `[source].exclude`, as used by ubCode, are globset globs with
their own default sets, and ubCode additionally path-expands them.
A mount's `include` / `exclude` are gitignore-style override patterns scoped to
that mount's `dir`, with no defaults and no expansion.
Nesting the mounts array under `[source]` (§1) puts two same-named keys with
different dialects one level apart; it changes nothing about either.
A second implementation must not share a pattern compiler between the two without
first making them the same dialect deliberately.

## 6. Docname derivation

A docname is `mount_at` joined to a *tail* with a single `/`
(or the bare tail when `mount_at` is absent).

The tail is the file's path with **one** matched source suffix removed:

| Mode | Tail |
| --- | --- |
| directory | the file's path relative to `dir` (POSIX separators), suffix removed — directory structure preserved |
| file-list | the file's **basename**, suffix removed — directories discarded, flat namespace |

The suffix removed is the **first** entry of Sphinx's `source_suffix` that the
filename ends with, iterating in registration order.
It is **not** the longest match.

This is exactly what Sphinx core does for files in the host source directory,
so mounted and host files derive docnames identically — but it means overlapping
suffixes are order-sensitive:

| `source_suffix` order | file | docname tail |
| --- | --- | --- |
| `.rst`, `.txt`, `.rst.txt` | `a.rst.txt` | `a.rst` (`.txt` matched first) |
| `.rst`, `.rst.txt`, `.txt` | `a.rst.txt` | `a` |

A second implementation must iterate the *host project's registered order*,
not a sorted or longest-first order.
Where it cannot observe that order, it must say so rather than guess.

Enumeration order of a mount's entries is deterministic and is part of the
contract, because it decides which entry is reported first in a conflict and the
order `attach_each` wires files:

- directory mode: sorted by the file's absolute POSIX path;
- file-list mode: the order of the `files` array.

## 7. Tie-breaks and failure modes

The whole-mount skip is the single reaction to every mount-level problem.
When a mount is skipped, **none** of its files are registered — not just the
offending one.
This is deliberate: a partially mounted bundle leaves its siblings dangling and
can wire broken toctrees, i.e. it modifies the host project despite the problem.

Collision rules, in the order they are evaluated for each candidate docname:

1. **Host wins.** A docname the host source directory already provides is not
   taken over. The mount is skipped (`mounts.docname_conflict`).
2. **First mount wins.** A docname an *earlier* mount in the array already
   provides is not taken over. The later mount is skipped
   (`mounts.docname_conflict`).
3. **Intra-mount collisions are an error, not a last-one-wins.** Two files of the
   same mount that map to one docname skip the mount
   (`mounts.docname_conflict`, naming both contributing paths).
   This happens in both modes: two listed files sharing a basename (file-list mode
   is flat), or two files differing only in registered suffix such as `index.rst`
   beside `index.md`.
   A second implementation must not resolve this by order.

"Earlier" and "later" in rule 2 mean position in the mounts array.
Declaration order therefore matters for conflicts, and only for conflicts —
toctree wiring does not depend on it (§8).

Other whole-mount skips: `mounts.missing_path`, `mounts.unknown_suffix`,
`mounts.empty_docname`, `mounts.mount_at_occupied`.

### 7.1 Warning subtypes are a stable contract

Every diagnostic carries the Sphinx warning type `mounts` with a per-problem
subtype, so it can be suppressed at either granularity and mapped onto another
tool's diagnostic codes.
**This list is stable.** Subtypes may be added; existing ones will not be renamed
or repurposed without a breaking release.

| Subtype | Condition | Effect |
| --- | --- | --- |
| `mounts.attach_to_missing` | `attach_to` names a docname that does not exist | nothing wired |
| `mounts.deprecated_confval` | `mounts_from_toml` is set explicitly | reported only; the value is honoured |
| `mounts.deprecated_location` | the array is declared as top-level `[[mounts]]` | reported only; the mounts load identically |
| `mounts.docname_conflict` | collision per rules 1-3 above | whole mount skipped |
| `mounts.empty_docname` | a listed file's name is only a suffix | whole mount skipped |
| `mounts.ignored_option` | a file-list mount sets `include` or `exclude` | reported only; the keys have no effect |
| `mounts.missing_path` | `dir` or a listed file is not on disk | whole mount skipped |
| `mounts.mount_at_occupied` | `strict_mount_at` set, host has a directory at `mount_at` | whole mount skipped |
| `mounts.mount_gate_unevaluable` | a mount `if` is declared where this reader never evaluates one (§13) | whole mount gated off |
| `mounts.path_escape` | a reference leaves the bundle root, `path_check = "warn"` (the default) | reported only |
| `mounts.toctree_index` | `toctree_index` exceeds the toctrees present | mount left unwired, its docs marked orphan |
| `mounts.unknown_key` | a mount entry or a `variant_sources` entry carries an unmodelled key (§4) | reported only; the key is ignored |
| `mounts.unknown_suffix` | a listed file has no registered suffix | whole mount skipped |
| `mounts.variant_rule_dropped` | a variant rule lists no files (§12) | rule dropped; document set unchanged |
| `mounts.variant_rule_unevaluable` | a rule's or a mount's condition cannot be evaluated (§12, §13) | reported **and** what it gates is excluded |

Configuration problems — malformed TOML, wrong types, contradictory options,
both mount locations declared — are **not** in this list.
They are hard errors and are deliberately not suppressible.
So are the four refusals of §12.4, which carry codes
(`mounts.variant_glob_dialect`, `mounts.variant_layout`,
`mounts.variant_root_doc`, `mounts.variant_data_unreadable`) purely so a user can
grep for them; they name a hard failure, never a suppressible warning.
Two further codes mark an **INFO** record rather than a warning:
`mounts.variant_excluded_reference` (§12.6) and `mounts.mount_gated` (§13).

## 8. Toctree wiring (`attach_to`)

`attach_to` names a docname whose toctree receives this mount's entries.

- The entries wired are `<mount_at>/<entry_doc>` — or every docname the mount
  produced, in enumeration order, when `attach_each` is set.
- Entries are **gated on what the mount actually produced**. A skipped or absent
  mount wires nothing, so it cannot leave a dangling reference behind.
- `toctree_index` selects which toctree, in document order. If the target document
  has no toctree at all, one is created at the **end of its first top-level
  section** — after everything the author wrote. If the index exceeds the number of
  toctrees present, nothing is wired (`mounts.toctree_index`) and the mount's docs
  are marked as orphans so the single warning is not joined by one per file.
- Wiring is **idempotent**: an entry the author already listed by hand is not
  added twice.
- `attach_to` may name a **mounted** docname, so one mount can be wired into
  another mount's toctree. Declaration order does not matter for this, because the
  injection happens while each document is read, not while the config is parsed.
- Wiring **tracks appearance and disappearance across incremental builds**.
  The set of entries each mount would wire is compared against a signature
  persisted on the build environment, and the `attach_to` document is re-read when
  they differ. Both directions converge on the build where the change happened,
  without a full rebuild.

  The guarantee is **conditional on the `attach_to` target existing**.
  The host framework intersects the reported names with the set of documents it
  found, so a dangling `attach_to` re-reads nothing, no environment is
  persisted, and the same change is recomputed on every run.
  A mounted docname referenced only by a *hand-written* host toctree is
  likewise not covered — nothing marks that host page outdated, so its dead
  link persists until the page is touched or the cache is discarded.
  That residue is upstream behaviour, not something mounting introduces
  (deleting an ordinary host document behaves identically), and a second
  implementation may reproduce or improve on it, but must not claim the
  unconditional form.

## 9. Path confinement (`path_check`)

Each mount has a **root set**, shared by every document it provides:

| Mode | Root set |
| --- | --- |
| directory | exactly one root: the resolved `dir` |
| file-list | one root per entry in `files`: that entry's resolved parent directory (duplicates collapsed, `files` order preserved) |

A dependency is inside the bundle iff it is under — or equal to — **at least
one** root of its document's mount.
There is one check per mount, not one per document.

**The bound is normative, and it is bounded on both sides.**
Two other rules were implemented and are both wrong; a second reader must
implement neither.

- *One root per document* (each listed file confined to its own parent) makes
  the verdict depend on how deep a file happens to sit.
  With `rn/index.rst` and `rn/notes/2026-q1.rst` listed, the reference *down*
  from `index.rst` into `notes/` passes while the mirror-image reference *up*
  from `notes/2026-q1.rst` to `../shared.txt` is rejected — same mount, same
  tree, opposite verdicts.
- *The common ancestor of the listed parents* fixes that asymmetry but is
  unbounded in the other direction, because the `files` list itself drives the
  root.
  Two entries in sibling subtrees promote their shared parent to the root; two
  entries on unrelated filesystem branches promote `/`, at which point the
  check permits every file on the machine and emits nothing — at any
  `path_check` setting, including `"error"`.

The union of the listed parents is a strict superset of the first rule (so the
asymmetry stays fixed) and a strict subset of the second (so no directory the
user did not name is ever admitted — noting that a file listed at the
filesystem root therefore names `/` as its root, which is the widest a
correctly-implemented root set can get).
Listing files from unrelated trees widens the bundle by exactly those trees'
directories, and by nothing else.
There is no failure case to report: a set of one or more parents always exists,
so no diagnostic accompanies root computation.

Every file the document is recorded as depending on must resolve into that root
set.
The comparison is per path component, on both sides passed through the platform's
case normalisation, because resolving a path does not fold case.
That normalisation is `os.path.normcase`, which folds on **Windows only** — on
POSIX, macOS included, it is the identity function.
So on macOS the comparison is case-sensitive even though the default filesystem is
not: a reference whose written case differs from the root's own spelling is
reported as an escape there, and matching the case is the fix.
A second implementation must fold on Windows or it will reject legitimate
references; on macOS it may match this behaviour or fold, but must say which.

Three shapes escape:

1. a leading `/`, which means "absolute from the source root" and for a mounted
   document is the **host** source directory, not the bundle;
2. a `..` climb that lands outside every root in the set;
3. a symlink inside the bundle whose target is outside it — the written path looks
   local, and only its resolved form reveals the escape.

Two limits are inherent to running this check after the read phase, and any
second implementation should state its own position rather than inherit these
silently:

- **It detects; it does not prevent.** The offending document has already been
  read and parsed, and its parsed form persisted, before the check runs. What a
  *failing* build prevents is the *output*: no escaped asset is copied and no
  page is written.
- **It is not evaluated on a build that reads no document.** Sphinx runs its
  consistency checks only when at least one document was read, so an unchanged
  re-run skips them. `path_check` is a gate on builds that do work, not a
  standing invariant.

The second limit is why the default is `"warn"` rather than a hard failure: a
hard default would have advertised an invariant this placement cannot provide.
Escalation belongs to the build driver (`-W` in Sphinx's case), and `"error"`
stays available for a hard stop without it — its one real advantage being that
an aborted build discards the cached environment, so the failure re-fires on
every subsequent run.

`path_check` says nothing about collisions *inside* the output: two bundles that
both ship `diagram.png` get one unsuffixed and one numbered asset name, and which
is which depends on document read order, hence on docnames. Adding or renaming a
mount can therefore change an unrelated page's asset URL. That naming is Sphinx's,
not this extension's.

## 10. What this contract does not cover

- The rendering of documents. sphinx-mounts does not parse anything; it only
  decides which docnames exist and where their bytes live.
- Anything about `[source]` other than a nested `mounts` array (§1), a nested
  `variant_sources` array and a `dir` value (§12). This is a three-key reader,
  never a general `[source]` bridge.
- A machine-readable schema. The key table in §4 is currently the only
  specification of types and defaults besides the implementation's own validator.

## 11. Known second readers: ubCode's declared divergences

ubCode's `[[source.mounts]]` support is the first second reader of this contract.
The table below records, as of that implementation's first shipped version, every
point where it deliberately diverges from the behaviour specified above — plus the
handful of points where it deliberately *matches* and the match is worth stating.

§1–§9 remain the normative contract for sphinx-mounts, and each reader's own
documentation is normative for that reader; nothing in this section amends either.
What the table is for is the case this document opens with. A user running both
tools over one project can read off exactly where the two will disagree about that
project, and why — instead of discovering it as "the editor shows a page the build
does not".

Every entry here is **declared**: chosen, reviewed, and written down. This is not
a catalogue of drift found after the fact, and a divergence that is not in the
table is a defect in one of the two implementations rather than a third position.

Two rows concern `if` on a mount entry (§13). That key ships in a **coordinated
release of both readers** — neither project releases a `[[source.mounts]]`
reader carrying it until both have it — so those rows describe the paired
implementation rather than one already in the field.

| Point | sphinx-mounts | ubCode | Why the difference is deliberate |
| --- | --- | --- | --- |
| Invalid `mount_at` (§4.1) | Hard `MountConfigError`; the build stops. | Reported (`config.mount_invalid`) and the mount is **dropped**. | ubCode has no config-time equivalent of `-W`, so an unusable entry follows its established posture for unusable configuration — report and carry on — the same one its intersphinx handling takes. |
| Spelling a root mount (§4.1) | A root mount is spelled by **omitting** `mount_at`; the empty string is a hard error (§4.1 rule 1). | `""` means exactly what an absent key means, and is reported (`config.mount_at_root`). | Both spellings have to mean one thing, and `[project] root_doc` already treats `""` as unset in the same shared TOML vocabulary. |
| NFC normalisation of `mount_at` (§4.1) | Not normalised: a decomposed (NFD) prefix yields a docname distinct from its composed form. | NFC-normalised at resolve time. | ubCode writes docnames NFC throughout, so a prefix in any other normalisation would yield a docname nothing can reference. |
| Backslashes in docname-shaped values (§4.1) | `a\..\b` is rejected on Windows only — the component split is delegated to the platform. | `\` is refused anywhere in `mount_at`, `attach_to` and `entry_doc`, on every platform. | Splitting on `/` alone accepts on POSIX a value that *is* a parent traversal wherever `\` separates, so one file would describe two different projects depending on the reader's platform. |
| A listed file named only a suffix (§5.2) | No docname; the **whole mount** is skipped (`mounts.empty_docname`). | The tail `".rst"` is minted and the file is mounted. | ubCode's mount tails come from its host-side suffix handling; the difference is recorded as a declared divergence rather than repaired. |
| A docname collision, and `strict_mount_at` (§7) | Any collision skips the whole mount; `strict_mount_at` is a mount-level pre-check with the same reaction. | Per-**file** loss (`std.duplicate_docname`), and `strict_mount_at` itself is reported as a key ubCode does not model. | ubCode's collision handling is per docname across the whole project. The dangling-sibling cascade a whole-mount skip prevents is mitigated instead by naming the mount in the message. |
| A mount `dir` containing the host source directory (§5.1) | The host project is published a **second** time under the prefix, and nothing detects it. | Published **zero** times: the host claims every path first, so the mount contributes no docnames, no confinement reports, and nothing for the absent-root row's retention to hold. Its configuration diagnostics (absent root, root mount, unhonoured `attach_to`) still fire. | Neither result is a check firing. Both fall out of the precedence each reader already applies to a contested path, which is why §5.1 states the constraint instead of promising a diagnostic. |
| Naming the mount in a collision message (§7.1) | The label renders `mounts[0] (dir=/abs/path)`, so the resolved root's absolute, machine-specific path appears in the diagnostic. | The label is index-only (`mounts[0]`), and every claimant path is rendered relative to the configuration folder in climbing (`../`) form, so no absolute path appears in the message. | Both name the root; they differ in where. Upstream puts it in the label, ubCode puts it in the claimant paths it prints. |
| `include` / `exclude` on a `files` mount (§5.2) | Reported (`mounts.ignored_option`); the keys change nothing. | Reported (`config.mount_dead_option`); the keys change nothing. | **Parity**, adopted deliberately. A dead filter that neither reader silently honours is one less way for the two to disagree about a mount's file set. |
| `attach_each` misuse (§4) | Hard `MountConfigError` in all three shapes: without `files`, without `attach_to`, and with a non-default `entry_doc`. | Reported and normalised away; where `attach_each` meets a non-default `entry_doc`, **`attach_each` wins**. | With no hard stop available an outcome has to be chosen, and `attach_each` wires a superset of what `entry_doc` would wire, so choosing it loses nothing. |
| `path_check` severity (§9) | Per-mount `warn` / `error` / `off`. | One fixed-severity warning (`build.mount_path_escape`), suppressible project-wide with `lint.ignore`, per tree with `lint.per_file_ignores` globbed on the mount root, and escalatable with `[build.html] deny`. | A fourth severity mechanism inside ubCode would be a support burden for no gain. The **default** reaction agrees on both sides (`"warn"`). |
| The escape diagnostic's name (§7.1) | `mounts.path_escape`. | `build.mount_path_escape`. | `build.*` is where ubCode's asset-resolution diagnostics already live; a `mounts.*` namespace for one code was not worth introducing. |
| When the escape check runs (§9) | From `env-check-consistency`, so it is skipped on a build that reads no document (§9 states the limit). | A project-level scan on every pass, so it survives a warm rebuild. | Strictly stronger, and recorded as a deliberate improvement rather than a violation: §9 already asks a second implementation to state its own position on that limit instead of inheriting it silently. |
| Ignore files in parent directories (§5.1) | Never consulted, so a gitignored parent cannot strip a mount. | Consulted — ubCode's shared walker reads them, so a mount root under a gitignored parent yields nothing unless the mount sets `gitignore = false`. | That walk is shared with ubCode's other per-tree features and is fenced there; the recipe is documented on its side. |
| Hidden entries in directory mode (§5.1) | Skipped. | Walked, exactly as ubCode's host walk treats them everywhere. | Internal consistency within one tool beats per-feature parity across two, and a dotfile that should not publish can be excluded. |
| Case folding in the containment check (§9) | Folds on **Windows only**: `os.path.normcase` is the identity on POSIX, macOS included. | Folds on Windows only, by an explicit platform-gated fold. | **Parity in behaviour.** §9 states the shared position: on macOS the comparison is case-sensitive even though the default filesystem is not, so the written case must match the root's spelling there. |
| An absent mount root, across incremental builds (§7, §8) | The mount contributes nothing, and pages it previously contributed drop out of the build — Sphinx's environment owns deletion. | Contributes nothing, and the pages already indexed from that mount are **exempted from the deletion sweep** until the root returns or the mount leaves the configuration. | ubCode has a persistent index and chooses retention, so a temporarily unbuilt bundle does not thrash downstream consumers. Sphinx rebuilds its environment and cannot retain. |
| A mount root's own spelling | `normcase` is applied and no spelling is ever rejected. | No config-time spelling diagnostic ships either. | **Parity**, recorded because a spelling check was considered and deliberately not shipped: a mount root is an OS path in every consumer, so refusing spellings would refuse legitimate absolute roots. Confinement (§9) is the only guard on where references may point. |
| An ABSOLUTE `variant_sources` glob (§12.4) | Refused; the configuration does not resolve. | Accepted — its fence has only `{a,b}` and `..`, and an absolute pattern simply never matches a relative path. | Refusing a spelling that can never match is the safe direction for a gating key: the author who wrote it meant to gate something, and accepting it silently gates nothing. The divergence is in the build-STOPPING direction, which is why it is declared rather than assumed harmless — a project using the spelling builds there and aborts here. Making the other reader refuse it too is the better end state and is a candidate for the paired change. |
| Unknown key on an entry (§4, §12.1) | Reported (`mounts.unknown_key`); the key is ignored and the rest of the entry is honoured. | Reported (`config.mount_unknown_key`, `config.variant_source_unknown_key`); same. | **Parity**, adopted deliberately, and the reason this contract stopped specifying a hard error. Neither reader being the strict one is what lets a gating key be introduced without an older reader aborting every build of the project. |
| A `variant_sources` glob with `?` beside a separator (§12.4) | Refused; the configuration does not resolve. | Accepted — globset compiles it, and ubCode has no second dialect to translate it into. | It is the one spelling with no faithful gitignore form: `?` may cross a path separator in one engine and never does in another. Refusing keeps "one rule string, one document set"; documenting it as a divergence would put the hazard back where the whole grammar narrowing removed it from. No corpus row and no shipped fixture uses it. |
| A rule condition outside the grammar (§12.5) | Hard `VariantRuleError`, listing every offending rule at once; the build stops. | Reported (`config.variant_source_invalid_condition`) and the rule is **retained as permanently false**, so its files are excluded. | Both are fail-closed; they differ in severity, and each follows its own host's posture — ubCode has no config-time equivalent of `-W`, while this reader can stop the build and a condition it cannot interpret is a configuration mistake the author fixes once. |
| A mount `if` outside the grammar (§13.3) | Hard `VariantRuleError`, in the **same** error that lists any offending rule; the build stops. | Reported (`config.mount_invalid_condition`) and the mount is gated **off**. | Identical to the row above, for the identical reason, and deliberately so: one grammar must not mean two things in one file. Both are fail-closed and both keep the bundle out; only the severity differs. |
| Diagnostics about a gated-off mount's own keys (§13.2) | **Suppressed.** The gated mount's discovery pipeline still runs, so its whole-mount skips still apply, but every report it would make — an absent root, an unregistered suffix, a docname that is only a suffix, a dead `include`/`exclude`, an occupied `strict_mount_at`, a collision between two of its own files — goes to the debug log instead. | **Every RESOLVE-tier report still fires**, gated or not: `config.mount_invalid`, `config.mount_unknown_key` and `config.mount_at_root` are emitted where the entry is resolved, and `config.mount_dead_option` at discovery time but hoisted ahead of the gate check precisely so gating cannot silence it — so a gated mount's key mistakes are still reported. Its discovery-tier reports are not — `config.mount_missing` in particular — because a gated mount is never planned. | Each reader suppresses what its own architecture makes variant-dependent. These are warnings here, and `-W` is a real thing: reporting an absent bundle root would fail a build whose author gated the bundle precisely because CI has not checked it out. ubCode has no `-W`, and its resolve tier is **not handed the variant map** — the map is resolved just before `[source]` resolution but is not threaded into it — so a key typo there cannot be variant-dependent and is worth reporting once. The consequence to know is that a CI building only the gated variant learns less about the bundle here than it would there. |
| A gated-off mount that provides `root_doc` (§13.7) | **Not guarded.** The mount is gated, the root document goes with it, and Sphinx aborts with a message blaming the source directory. | Refused (`config.mount_excludes_root`) when a gated mount is the only root that would CONTRIBUTE `root_doc` — decided at configuration time as an approximation of the walker's admission rule, answering "does not contribute" and standing down wherever the two could differ. It can refuse in two shapes only: a `files` mount in either mode (the list IS the selection), and a `dir` mount with `gitignore = false` in classic mode. A mount respecting ignore files is never refused over (ignore semantics are the walker's); in parser mode the router owns inclusion, so the guard stands down; and it stands down for any project declaring a rule that is false for this variant, because rule-driven removal is settled in a later fold. The suppressing side over-approximates the other way: any candidate file on disk under the host root, or under a live mount claiming the docname — symlinks and all — is reason enough to stay silent. | This reader's root-document guard runs at configuration time and cannot know what a mount will produce (§12.8 records the same limit for a rule-narrowed mount). ubCode's guard is deliberately NARROWER than "a gated mount has a file named like `root_doc`": an unsuppressible refusal is reserved for the shapes it can prove match the walk, and every undecidable input degrades to the ordinary missing-root-document path instead. |
| The root-document guard (§12.4) | **Stronger on suffixes, WEAKER on mounts.** The candidate suffixes are the project's registered ones — the `source_suffix` confval UNION the extension registry — so the candidate paths are the real ones, including an extension-registered `.md`. But a root document provided by a MOUNT is not covered: the guard runs at configuration time and cannot know what a mount will produce (§12.8 states the same limitation). | Best-effort on suffixes — they are inferred from the project's discovery `include` globs, so a project whose only include glob is unreadable *and* whose root document has an exotic suffix keeps the pre-guard behaviour — and it DOES cover mount-resident root documents. | Neither guard is a superset of the other, and an earlier version of this row claimed one was. Each reader is stronger on the axis its own architecture makes cheap: registered suffixes here, a resolved document set there. |
| Non-identity source-root layouts (§12.7) | Refused (`mounts.variant_layout`) when rules are declared and the source root is not `srcdir`. | Supported: rule globs are re-anchored per source root, and ubCode has no single `srcdir` to disagree with. | Sphinx has exactly one source directory, and a prefix-shifted rewrite has no correct form for a basename-matching rule. So some layouts that work in ubCode need one extra line (`[source] dir`) here. The alternative — gating only the root that happens to coincide — is the failure the key exists to prevent. |
| Where the merged variant map comes from (§12.6) | Computed by this reader: the file is deep-merged under the inline table unconditionally, whether or not sphinx-needs is installed. | Computed by ubCode from the same two keys. | **Parity in result, by different routes.** The merge is idempotent, so when sphinx-needs is present its resolved value is this reader's *input* and the re-merge is a no-op. That is what lets sphinx-mounts never import, depend on, or version-gate against sphinx-needs while always agreeing with it. |
| A variant-excluded toctree reference (§12.6) | Sphinx's own record is downgraded to **INFO** and reworded, carrying `mounts.variant_excluded_reference`. | Its own informational `toctree.variant_excluded` code. | **Parity in severity**, different mechanism: ubCode emits its own diagnostic where this reader has to reclassify one Sphinx already emitted. Both name the rule that removed the document, and both are informational because a shared index listing every variant's pages is the normal 150% shape. |

Two entries are worth reading twice, because the disagreement is about *which
documents exist* rather than about how a problem is reported:

- While a mount root is absent, sphinx-mounts has already lost that bundle's
  pages from the build while ubCode still holds them in its index. It is the
  largest declared divergence in the table, and it resolves itself the moment the
  root comes back.
- A mount whose `dir` contains the host source directory is published twice by one
  reader and not at all by the other — the widest possible spread from a
  configuration neither reader rejects.

## 12. Variant-gated source selection (`[[source.variant_sources]]`)

The second thing this reader takes out of the shared file, and the second thing
that decides **which documents exist** — which is what §1–§9 specify for mounts,
so it is specified here on the same terms.

Numbered 12 rather than slotted in ahead of §10 and §11 so that no existing
section number moves: other repositories cite these numbers.

### 12.1 Shape

`[[source.variant_sources]]` is an array of tables under `[source]`. One table
is one rule, with exactly two modelled keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `if` | string | A condition over the variant map (§12.5). Required. |
| `files` | array of strings | The globs this rule gates (§12.3). Required. |

Unknown keys are reported and ignored, exactly as on a mount entry (§4).
A missing or wrongly typed `if` / `files` is a hard configuration error: a rule
that cannot be parsed says nothing about which files the variant contains, and
guessing is how a gating key fails open.

Nesting under `[source]` implies no inheritance, per §1 rule 5. This reader
takes `mounts`, `variant_sources` and `dir` out of `[source]` and nothing else.

### 12.2 Semantics, and evaluation order

> Every rule whose condition is **false** excludes its `files`; a file no false
> rule matches is unaffected.

Equivalently: a file is discovered unless some rule matching it is false, which
is an AND over the conditions of all rules matching that file. The semantics are
**order-independent** and rules only ever **narrow**, so an ordered `else` could
be added later without redefining any configuration written today.

**Variant rules never gate a file-list mount** (§5.2), in either reader.
ubCode's `files`-mount entries are pushed straight into its result with no
include or exclude consulted, and a variant rule reaches its discovery only by
being folded into `[source] extend_exclude` — so no rule can remove such a
document there under any spelling, and this reader matches rather than
diverging. A second implementation must reproduce the limitation or declare
that it does not; gating one is a "one rule string, two document sets"
divergence in the removes-more-here direction. Neither reader reports it per
build, because a diagnostic only one of them emits is itself a difference.
A bundle whose FILE SET has to be narrowable by a rule is declared as a `dir`
mount.

That is a statement about **rules**, and §13 does not weaken it. A whole-mount
`if` gates a file-list mount exactly as it gates a directory one, in both
readers, because dropping a bundle touches neither `include` nor `exclude`. The
two questions have opposite answers and are stated separately on purpose.

Relative to a mount's own `include` / `exclude` (§5.3), a variant exclusion is
**appended after** every `exclude` the user wrote. The override list is
last-match-wins and all `include`s are added before all `exclude`s, so §5.3's
rule — a broad `exclude` always beats a narrow `include` — extends to variant
exclusions unchanged: a rule always narrows, and nothing a mount declares can
widen past it.

The checks run in this order, and the order is observable because two of them
are hard failures:

1. **glob dialect** (§12.4) — variant-*independent*: a pattern no reader can
   share is unusable in every variant, so it is refused before any condition is
   looked at;
2. **layout** (§12.4) — variant-independent for the same reason;
3. **condition validation** (§12.5) — statically knowable, so a hard error;
4. **condition evaluation** — data-dependent, so warn-and-exclude;
5. **root document** (§12.4) — variant-*dependent*: a rule matching the root
   document is legal while its condition holds, so it can only be judged after
   step 4;
6. the fold.

### 12.3 The glob dialect, and the two translations

A rule glob is authored in one dialect and has to reach two engines with
different semantics. The authored dialect is globset with
`literal_separator = false`, plus a raw-basename match — i.e. `*` and `?` cross
`/`, an interior `**` matches zero or more directories, and a **separator-less**
pattern matches by file name at every depth, in every tree.

A second implementation must reproduce both translations or knowingly deviate.

**The authored dialect is MODELLED, not executed.** There is no globset for
Python, so this reader compiles the authored pattern to a regular expression of
its own. The two *translations* below are checked against the real engines —
the `ignore` crate's walker and Sphinx's own `get_matching_files` — and the
tables' expected values were measured against them, so the tables are an
external oracle. The reference reading beside them is not. A third reader
should treat the tables as the contract and the model as an implementation
detail; where they could disagree, the tables win.

Four spellings that the model and the engines read differently are refused
outright, so the question does not arise for them: an EMPTY pattern and a
pattern with a TRAILING SEPARATOR (both select nothing here and a whole
subtree, or everything, in a mount's walk), an absolute path, and — see §12.4 —
`{a,b}`, `..` and `?` beside a separator. A refusal is also raised for a
pattern carrying more than six zero-widening `**` components, because the
Sphinx-side expansion doubles per wildcard.

**Rule glob -> mount `exclude` (gitignore, anchored at the mount's `dir`):**

| Rule glob | Mount `exclude` | Why |
| --- | --- | --- |
| `name.rst` (no separator) | `name.rst` | identity — both match the basename at every depth |
| `*.rst` (no separator) | `*.rst` | identity |
| `a?c.rst` (no separator) | `a?c.rst` | identity |
| `a[bX]c.rst` | `a[bX]c.rst` | identity — same class syntax |
| `dir/name.rst` | `dir/name.rst` | identity — root-anchored once a separator is present |
| `dir/**` | `dir/**` | identity |
| `dir/**/*.rst` | `dir/**/*.rst` | identity — both treat an interior `**` as zero-or-more |
| `dir/*.rst` | **`dir/**/*.rst`** | globset's `*` crosses `/`; gitignore's does not |
| `dir/*` | **`dir/**`** | same reason, said directly (gitignore's `dir/*` also prunes a matching sub-directory, which happens to agree here) |

**Rule glob -> `exclude_patterns` (Sphinx `_translate_pattern`, anchored at
`srcdir`):** two behaviours need *two* patterns each, so this translation
returns a list.

| Rule glob | `exclude_patterns` | Why |
| --- | --- | --- |
| `name.rst` (no separator) | `name.rst`, `**/name.rst` | Sphinx's `**/x` is `.*/x$` and cannot match `x` at the root; `Project.discover` reaches the matcher through `compile_matchers`, which — unlike `Matcher` — does not expand the `**/` form |
| `dir/name.rst` | `dir/name.rst` | identity |
| `dir/*.rst` | `dir/**.rst` | globset's `*` crosses `/`, and Sphinx's `**` is exactly `.*` |
| `dir/*` | `dir/**` | same |
| `dir/**` | `dir/**` | identity — a trailing `**` needs one or more components on both sides |
| `dir/**/*.rst` | `dir/**/**.rst`, `dir/**.rst` | a leading or interior `**` matches zero directories in globset; Sphinx's requires the surrounding literal `/`, so a present form and an absent form are both emitted |
| `**/pro/**` | `**/pro/**`, `pro/**` | same |

Two asymmetries worth stating because neither is obvious:

- **Directory pruning.** Both target engines apply their exclude matchers to
  *directories* as well as files, pruning the subtree. A translated pattern that
  can match a directory name therefore gates more than a path-only reading
  suggests. The widened forms above are chosen so that the three engines remove
  the same set; leaving `dir/*` alone would have been correct only by
  coincidence.
- **Root anchoring.** `pro/**` removes nothing when `pro/` is not at the
  anchoring root. That is parity with the authored dialect, but it is the
  opposite of the intuition the separator-less case creates.

### 12.4 The four hard refusals

Each refuses the **whole configuration**, listing every offender at once. None
is a warning that skips its rule: skipping leaves every file the rule named —
including the files its valid patterns named — in the build, behind a diagnostic
a project could suppress. For a key whose only purpose is keeping content out of
a build, failing open is the one outcome that must not be possible.

| Refusal | Condition |
| --- | --- |
| `mounts.variant_glob_dialect` | a glob that is EMPTY or ends with a path separator; uses `{a,b}` alternation; climbs with `..`; is an absolute path; carries a `?` beside a separator; or carries more than six zero-widening `**` components. Every test runs against the pattern with its `[...]` character classes blanked out, because a `?` or a `{` inside a class is a literal character in all three engines |
| `mounts.variant_layout` | rules are declared but the source root they anchor at is not `srcdir` (§12.7) |
| `mounts.variant_root_doc` | a rule that is false for this variant would exclude `root_doc` |
| `mounts.variant_data_unreadable` | the variant data file is missing, undecodable or not a JSON object, and sphinx-needs is not installed to report it itself |

The one **safe** drop is an empty `files` list (`mounts.variant_rule_dropped`):
a rule that named nothing has nothing to leak, so dropping it leaves the
document set unchanged.

### 12.5 The condition grammar — the two normative tables

**This section is the grammar contract.** The vendored corpus
(`tests/fixtures/variant_condition_conformance.toml`, a byte-identical copy of
ubCode's canonical file with the source commit in its header) is the shared
**test-vector set** — 46 conditions with their verdicts, useful for checking an
implementation — but it is silent about most of the surface below, and a reader
implementing only it lands on Python's semantics, which are not these.

Both tables are **mirrored on ubCode's shipped engine**: derived from
`rust/ubc_query/src/py_expr.pest`, `py_expr.rs`, `filter.rs` and
`rust/ubc_config/src/needs/variant_data.rs`, and confirmed by running every
expression through that engine itself.

They **deliberately depart from Python**, and that is the point. `var.debug == 0`
is FALSE here because it is false there; Python's `False == 0` would have made
it true and the two tools would have built different sites from one file,
silently. ubCode's own `docs/source/usage/variants.rst` claims these semantics
match Python's — measured, they do not; that is a defect in its documentation,
named here rather than adopted. If the two engines ever move to Python
semantics they move **together**, in the same release.

#### Table 1 — the accept-set

An expression is a boolean form:

```text
boolean := boolean ('and'|'or') boolean
         | 'not' boolean
         | '(' boolean ')'
         | comparison
         | 'True' | 'False'
         | receiver '.' ('startswith'|'endswith') '(' string ')'
```

A comparison is exactly one of these seven rows. **Every row carries at least
one receiver**, because the engine has no arm holding two literals — `True ==
True` and `'a' == 'b'` are parse errors there, not design choices:

| # | Left | Operator | Right |
| --- | --- | --- | --- |
| 1 | receiver | `==` `!=` | receiver \| scalar-literal |
| 2 | scalar-literal | `==` `!=` | receiver |
| 3 | receiver | `<` `>` `<=` `>=` | receiver \| number-literal |
| 4 | number-literal | `<` `>` `<=` `>=` | receiver |
| 5 | receiver | `in` `not in` | `[` scalar-literal, … `]` |
| 6 | scalar-literal | `in` `not in` | receiver |
| 7 | receiver | `is` `is not` | `None` |

```text
receiver       := 'var' ('.' name)+ ('.upper()' | '.lower()')?   -- ONE function
scalar-literal := string | integer | float | 'True' | 'False' | 'None'
number-literal := integer | float          -- NOT bool, None or string
```

Both integers and floats may carry a leading `-`. Consequences worth stating,
because an AST-shaped reader gets each of them wrong:

- a list literal is legal **only** as the right-hand side of `in` / `not in`;
- `in` / `not in` never take a string or a field on the right;
- a predicate call may not appear **inside** a comparison, though `.upper()`
  may — an asymmetry an author will not guess;
- an ordering operator takes only a number on the literal side;
- a comparison with no receiver at all is refused;
- exactly one transformer suffix: `var.name.upper().upper()` is refused.

Two further narrowings, both configuration errors:

- **the top level must be boolean.** A bare field (`var.debug`) is refused, and
  so is a bare `.upper()` / `.lower()`, which returns a string — but a bare
  `.startswith(…)` / `.endswith(…)` **is** accepted, because it returns a
  boolean. The rule is type-aware, and prose summaries of it (including
  ubCode's own schema doc comment) are imprecise here.
- **every field reference must be rooted at `var`.** A prefix-less
  `edition == 'pro'` is refused, as is any other bare name. A TOML-spelled
  `true` / `false` is a *field name* to the parser and is refused with a message
  naming that mistake.

#### Table 1b — the spelling gate is a PORT, not an enumeration

The accept-set above is necessary and **not sufficient**, and the shape of the
insufficiency is the important part. Python's tokenizer normalises away
spellings ubCode's lexer refuses, so a reader validating a *parsed tree* is not
closed over the difference: two independent review rounds each produced a fresh
class of leak that no prior enumeration had a rule for — first whitespace and
numeral bases, then comments, `not not`, parenthesised operands and NFKC
identifier folding. Every member let a rule ubCode drops be kept, which is one
string and two document sets.

**So this section does not enumerate refusals, and a third reader should not
implement one.** The rule is:

> A condition is accepted only if **ubCode's own grammar derives it**. That
> grammar is `rust/ubc_query/src/py_expr.pest`; port it, and run the port over
> the RAW condition text before handing the text to whatever parser the reader
> is built on.

sphinx-mounts implements this as `_PestRecogniser` in
`src/sphinx_mounts/variants.py` — a recursive-descent recogniser with one method
per pest production, each citing the line it ports, reproducing PEG ordered
choice and its backtracking. It is closed by construction: a spelling nobody
anticipated is refused because the grammar cannot produce it, not because a
rule was added for it.

The consequences are therefore **derived, not declared**. Listed here so a
reader can sanity-check a port, never as the specification:

| Behaviour | Where it comes from |
| --- | --- |
| word operators (`and` `or` `in` `is` `not`) need whitespace on both sides; comparison operators do not | `ws+` in `or_expr`/`and_expr`/`in_list_expr`/`is_null_expr` (pest :5, :8, :61-65) vs `ws*` in `comparison_expr` (:45-52) |
| no whitespace around a `var.*` dot; none inside a call's parentheses | `var_field` (:67), `var_field_with_upper` (:71-72), `str_predicate_method` (:108) are atomic |
| no trailing comma in a list, and no tuple form at all | `list_literal` (:104-106); there is no tuple production |
| decimal numerals only — no `0x`/`0b`/`0o`, no `_`, a leading digit before the point | `integer_literal` (:93), `decimal_literal` (:94), `float_literal` (:95) |
| no comments | there is no comment production |
| `not` does not chain (`not not x`), but `not (not (x))` does | `not_expr = not_keyword ~ ws+ ~ expr` (:12) — the body is an `expr`, and a `not_expr` is not one; a `paren_expr` is |
| parentheses wrap a boolean sub-expression, never an operand | `paren_expr` (:15) is reachable only from `expr` |
| field names are ASCII | `id_start` / `id_part` (:81-82) |
| implicit string concatenation is not derivable | nothing can consume a second `string_literal` |

Tolerances, equally derived and equally load-bearing — a port that refuses
these is a divergence in the *other* direction, a project that builds there and
aborts here:

`var.count>=2`, `var.edition=='pro'`, `[ 'a' , 'b' ]`, doubled spaces, tabs and
newlines as whitespace, `2.`, `2e1`, `2.5e-1`, `-2`, `var.name.upper().startswith('W')`,
and a dotted `var.count.upper` with no parentheses (an ordinary field path — the
`!("(")` lookahead at :67 only excludes a segment a call follows).

String escapes are the one row handled by **mirroring rather than refusing**,
because ubCode accepts them and merely reads a different string. Its decoder
(`common.rs::process_escape_sequences`) knows
`\n \t \r \b \f \v \a \0 \\ \' \"` and leaves every other escape with its
backslash attached, so `'a\x41b'` is six characters there and four in Python. A
reader must decode the same way.

**A declared divergence in the fail-CLOSED direction.** `ws` includes a newline
(:119), so a condition split across lines is derivable there; Python cannot
parse a bare newline in an expression, so this reader refuses it. The same
divergence fires for a raw newline INSIDE a string literal, which
`string_single_char` / `string_double_char` (:99-102, `ANY`-based) admit there
and Python's single-quoted literals cannot contain. Parenthesised
(or, for the literal, spelled `\n`), both accept. The build stops here and
succeeds there — no leak, but a difference, recorded rather than discovered.

**A second declared divergence, same direction: leading-underscore fields.**
`id_start` (:81) admits `_`, so `var._x == 1` is derivable there — ubCode
evaluates it, fails on the unknown key, warns and EXCLUDES the rule's files.
This reader refuses the spelling outright (a hard configuration error; see
`_refuse_bare_name`), because an underscore-led attribute is the doorway every
Python sandbox escape walks through and the grammar is the right place to bar
it. Both engines end with the files out of the build; the severity differs —
the build stops here and warns there. Variant data keys are ordinary names, so
nothing legitimate is lost.

#### Table 2 — the comparison semantics

Values are lowered first
(`rust/ubc_config/src/needs/variant_data.rs::variant_value_to_filter`):

```text
scalar  -> str | bool | int | float
array   -> list[str] | list[bool] | list[int] | list[float]
           (an EMPTY array lowers to an empty list of STRINGS)
mapping -> bool(non-empty)          -- a map is compared by its TRUTHINESS
```

**Equality** (`filter.rs::value_matches_literal`); `!=` is its negation:

| Left value | Right literal | Result |
| --- | --- | --- |
| str | str | `==` |
| bool | bool | `==` |
| int | int | `==` |
| int | float | `float(v) == l` |
| float | float | `==` |
| float | int | `v == float(l)` |
| **any other pair** | | **False** |

So `(bool, int)` has no arm: `var.debug == 0` is **False** with `debug = false`,
where Python says True — and its twin `var.debug != 0` is **True** where Python
says False. These two change which documents a build contains.

**Field vs field** converts the right value to a literal first, and a **list
cannot be converted** — that RAISES. `var.tags == var.build.features` is an
evaluation error, not `False`.

**Ordering** (`filter.rs::value_compares_number`): the left value must be int or
float, else it RAISES; a field on the right must be int or float, else it
raises. `var.debug > 0` raises here and is `False` in Python.

**Membership, `literal in receiver`** (`filter.rs::LiteralInVarField`):

| Receiver | Literal | Result |
| --- | --- | --- |
| str | str | substring |
| list[str] | str | contains |
| list[bool] | bool | contains |
| list[int] | int | contains |
| list[int] | float | `any(float(i) == l)` |
| list[float] | float | contains |
| list[float] | int | `any(f == float(l))` |
| a list, any other literal type | | **RAISES** |
| bool \| int \| float (a mapping lowers to bool) | | **RAISES** |

So `2 in var.tags` and `'debug' in var.build` are evaluation errors where
Python returns a value.

**Membership, `receiver in [literals]`** (`filter.rs::VarInLiteralList`):
`any(…)` over the equality table above; a list receiver matches nothing and
returns `False` rather than raising.

**`is None` / `is not None`**: variant data can never hold a null, so a
resolvable key is never `None`. An unknown key raises, as everywhere else.

**`.upper()` / `.lower()` and the string predicates** require a `str` value and
raise otherwise (`filter.rs::apply_function`).

**Short-circuiting**: `and` / `or` evaluate left to right and an unreached
operand's error never surfaces — measured on both engines, which agree.

#### How this reader implements the tables

sphinx-mounts *interprets*: `ast.parse`, a whitelist walk, a lexical pass over
the raw text, then a second walk over the plain merged mapping. There is no
`eval`, no `exec` and no namespace object anywhere in the extension. A second
reader is free to evaluate instead, but then the whitelist's completeness is a
security property rather than a correctness one — and it still owes the lexical
layer, which an evaluator does not get for free either.

A condition that cannot be **evaluated** — an unknown `var.*` key, or any of the
raising cells above — is reported (`mounts.variant_rule_unevaluable`) and the
rule is **false**, so its files are excluded.

### 12.6 The variant map, and the two anchors

Conditions are evaluated against a merged mapping: the JSON object named by
`[needs] variant_data_file` first, with `[needs] variant_data` deep-merged on
top. The merge recurses **only when both sides are mappings**; anything else is
a wholesale replacement. Keys must be strings, leaves must be
`str` / `bool` / `int` / `float`, and a list must be empty or uniform-scalar.

sphinx-mounts computes this itself rather than depending on sphinx-needs, and
performs the merge **unconditionally**. That is safe because the merge is
idempotent — `deep_merge(file, already_merged) == already_merged` — so when
sphinx-needs has already resolved, its result is the input and the re-merge
changes nothing. A second reader may take the same route or depend on
sphinx-needs; it must not do both halfway.

**Two anchors.** A relative `variant_data_file` declared in the TOML resolves
against the **TOML file's own directory** (the same anchor §3 gives mount paths);
one declared in `conf.py` or overridden with `-D` resolves against **confdir**.
Reading only one of the two means reading the wrong file for one of the routes.

Finally, a rule that removes a document leaves toctree entries naming it
dangling. sphinx-mounts **downgrades** those records to INFO, reworded to name
the rule, carrying `mounts.variant_excluded_reference`; a reference to a
document no rule mentions is untouched. It is a reclassification, never a
suppression — the record is still reported, because it is the only place left
where an over-broad rule is visible.

### 12.7 Anchoring, and the supported layouts

Rule globs are anchored at **one** source root, resolved as §3 resolves a mount
path. The precedence is the sibling reader's:

1. `[source] dir` — a **string**, never an array. It names one path, and the
   canonical reader declares it as one and fails to deserialize anything else,
   so accepting an array here would let a file build in one reader and be
   unreadable to the other. An empty string means unset.
2. the deprecated `[project] srcdir`, when `dir` is unset — it still stands as
   the source root there, so a reader that ignores it anchors rule globs
   somewhere the other reader does not.
3. otherwise, the directory containing the TOML file.

The host arm of the fold expresses a rule as an `exclude_patterns` entry, which
Sphinx anchors at `srcdir`. So the layout must be an identity: the source root
must BE `srcdir` — unless it is also a mount root, which is reached through the
mount's own walk instead. Anything else is `mounts.variant_layout`, naming both
directories and both remedies: move the TOML beside the source directory, or
declare `[source] dir = "<srcdir relative to the TOML>"`.

The message must also say that `[source] dir` is the sibling reader's
**discovery** root, because the obvious fix for a TOML at a repository root is
`dir = "."` — which satisfies the Sphinx-side check by making the other tool
index the whole repository.

Refusing rather than prefix-shifting is deliberate: a shifted rewrite has no
correct form for a basename-matching rule, and gating only the root that
happens to coincide is the failure this key exists to prevent.

### 12.8 What this does not promise

- Output is not deleted for documents that leave the build. A gating flip in a
  warm output directory leaves the excluded page on disk, live and
  URL-reachable, absent only from navigation, `objects.inv` and search. That is
  upstream Sphinx behaviour; the remedy is a per-variant doctree and output
  directory, or `-E` with a clean `outdir`.
- A mount that *provides* `root_doc` and is narrowed by a rule is not covered by
  the root-document refusal, which is evaluated at configuration time against
  the host source suffixes and cannot know what a mount will produce.

## 13. Whole-mount variant gating (`if` on a mount entry)

The **second** variant-gating key, and the third thing in this file that decides
which documents exist. §12 narrows a file set by glob; this one removes a whole
mount.

Numbered 13 rather than folded into §12 so that no existing number moves, and
because the two keys answer different questions. They share a grammar and a
validator, and nothing else.

### 13.1 Shape

One optional key on a `[[source.mounts]]` entry (§4):

| Key | Type | Meaning |
| --- | --- | --- |
| `if` | string | A condition over the variant map. Exactly the grammar of §12.5, evaluated by exactly the machinery of §12.5 and §12.6. |

An absent `if` means the mount is built in every variant, which is what every
mount written before this key existed says.

### 13.2 Semantics

> A mount whose `if` is **false** for the current variant contributes nothing:
> no documents, no toctree wiring, no confinement roots, no diagnostics of its
> own.

The bundle is out of the build, not merely unwired. Its `attach_to` is a no-op,
its `entry_doc` is not a docname, and every problem its own discovery pipeline
would report — an absent root, a contested docname, an occupied `mount_at`, an
unregistered suffix, a dead `include`/`exclude` — goes to the debug log instead.
Those are all *warnings*, so reporting them would fail `sphinx-build -W` on a
project whose only sin is gating a bundle its CI has not checked out.

Two of those are genuinely hypothetical for a gated mount (an absent root, an
occupied `mount_at`); the rest are properties of the bundle that hold in every
variant, and suppressing them is a stated trade-off rather than an obvious win —
a CI that only builds the gated variant does not learn the bundle is broken.
Every one of them is still reported in a variant that builds the bundle. §11
records where ubCode differs, which is on the checks its architecture evaluates
before variants exist.

**Both mount modes are gated, uniformly.** A `files` mount and a `dir` mount are
one line apart here and in ubCode, because dropping a whole bundle touches
neither `include` nor `exclude`.

**This is a different question from §12.2's, with the opposite answer, and the
two must not be blurred.** §12.2 records that a variant *rule* never gates a
file-list mount in either reader — a `files` mount's entries bypass pattern
matching entirely. That limitation is unchanged. What is new is that a
**whole-mount `if`** gates a file-list mount, which no rule spelling can do.
A reader that concluded from this section that rules now reach file-list mounts
would have read it backwards.

### 13.3 Evaluation order and failure postures

The checks of §12.2 apply, with two scoping rules:

1. the **glob dialect** refusal and the **layout** guard are about rule GLOBS,
   so they are evaluated only for a project that declares rules. A mount `if`
   anchors nothing, so a project that gates only mounts is legal in any layout —
   including the `conf.py`-in-`docs/`, sources-in-`docs/source/` layout §12.7
   refuses for rules;
2. **condition validation and evaluation run once, over both keys together.**
   One hard error lists every offender from either key. Two error paths for one
   grammar could disagree about what the grammar is.

| Failure | Reaction |
| --- | --- |
| the condition is **false** | mount gated off; `mounts.mount_gated` (INFO) |
| the condition is **outside the grammar**, or is not a string | the whole configuration is refused, listing every offender from both keys |
| the condition cannot be **evaluated** (unknown `var.*`, type mismatch) | mount gated off; `mounts.variant_rule_unevaluable` |
| the condition is declared where **nothing evaluates** it | mount gated off; `mounts.mount_gate_unevaluable` |

Every row ends with the bundle out of the build. Fail-closed is not a preference
here: a reader that published a bundle whose gate it could not evaluate would be
doing the one thing this key exists to prevent.

The last row covers four routes, and the invariant behind it is the one to
reproduce: **every route that gates is a route that reports.** A gating key
whose verdict can be reached without a diagnostic is a bundle that vanishes in
silence, which §13.4 exists to prevent.

Three of the four are this reader's stand-downs: `sources_from_toml = None`
switches off everything read from TOML, a `ubproject.toml` that does not exist
supplies nothing, and a variant map that cannot be read leaves nothing to
evaluate against. In the first two the mounts came from `conf.py`. The fourth is
structural rather than a stand-down: a mount can reach the parser carrying a
condition the reader never saw — here, through a `config-inited` handler that
writes the mounts array after the reader has run, or a `conf.py` that sets the
internal gate field directly. Both gate the bundle off, because fail-closed is
the only defensible reading of a condition nothing evaluated, and both are
reported at the parse seam rather than at the reader.

Each route carries its own **remedy**, not only its own reason; the three
stand-downs share none. A second implementation with no `conf.py` route and one
configuration pass has fewer routes, but it owes the invariant, not the list.

### 13.4 The record, and why it is not optional

A gated-off mount emits `mounts.mount_gated` (INFO) **whether or not anything in
the project references the bundle**.

This is a requirement rather than a nicety. A variant rule names a glob the
author wrote beside the files it removed; a mount `if` can remove hundreds of
pages that live in another repository, and if nothing in the host happens to
reference them there is no other signal at all — no missing page, no toctree
warning, nothing. A second implementation that reports gating only when
something dangles leaves "where did my 400 pages go" answerable only by
re-reading `ubproject.toml`.

INFO rather than a warning, for the reason §12.6 gives about the toctree
downgrade: gating is what the author asked for, and `-W` has to pass on a
correctly configured variant build — with the one exception §13.7's last bullet
records.

**When that exception fires the record says so.** A gated mount whose
attribution was emptied by a contest names the contested docname in this
record, because a whole-mount skip leaves references to the bundle's *other*
pages as ordinary missing-document warnings and nothing else in the build log
connects them to the gate. It is therefore emitted after discovery rather than
at configuration time: the gate is a configuration fact and the contest is a
discovery fact, and the record has to carry both.

### 13.5 Toctree references into a gated bundle

Reclassified exactly as §12.6 describes, carrying the same
`mounts.variant_excluded_reference` code and naming the gate rather than a rule:

```text
sphinx-mounts: toctree entry 'guides/pro/index' names a document this variant
excludes, per [[source.mounts]][0] (if = "var.edition == 'pro'"). …
```

The attributed set is built by running the gated mount through the **real**
per-mount discovery pipeline and recording what it would have produced, rather
than by walking the bundle a second time. §12.6's attribution is safe because it
diffs two walks and the diff cancels the walk's approximations; a whole-mount
gate has no second walk to diff against, so every reduction the pipeline applies
would have to be reproduced exactly. A docname invented by a missed reduction is
attributed but still walkable, and the filter would then downgrade a **genuine**
warning about it. A second implementation that computes this set some other way
owes the same property, not the same method.

### 13.6 Config-value visibility, and convergence

The verdict is folded into the `mounts` config **value**: the `if` key is
stripped from every mount whose condition holds and left in place on every mount
that is gated off. The two variants therefore differ by one key, `mounts` is
declared `rebuild="env"`, and a gating flip is a `[config changed ('mounts')]`
rebuild that converges in both directions on the build where it happened.

A reader that gated without touching a config value leaves both values
byte-identical across a flip and needs an invalidation story of its own.

### 13.7 What this does not promise

- **§12.8's stale-output caveat applies unchanged, and matters more.** A gating
  flip in a warm output directory leaves a whole bundle's pages on disk, live
  and URL-reachable. Build each variant into its own doctree and output
  directory.
- **A mount that provides `root_doc` is not covered by any guard here.** §12.8
  records the same limitation for a rule-narrowed mount; a gated-off root mount
  can remove the root document, and Sphinx aborts with a message blaming the
  source directory. ubCode's reader does guard this case — see §11.
- **A `conf.py`-declared `MountConfig` *instance* cannot carry a condition.**
  `if` is a Python keyword, so no dataclass field can be named for it. A
  `conf.py` mount written as a plain mapping is read like any TOML table. TOML
  is the primary config target, so this is a documented limitation of one route
  rather than of the key. Setting the internal gate field on such an instance
  gates the mount off — fail-closed — and is reported at the parse seam like
  any other condition nothing evaluated (§13.3).
- **A gated mount whose docname is claimed by the host or by a live mount
  attributes nothing at all**, including its uncontested pages. The contested
  docname triggers the same whole-mount skip §7 applies everywhere, and the
  reduction reaches the siblings with it. Whether the mount would have supplied
  those pages in the variant where it is live depends on which mounts are live
  *there*, which this build cannot know — so the conservative reading is taken.
  The alternative cost is a phantom, and a phantom silences a real warning.

  The consequence is user-visible and belongs in any statement of the `-W`
  posture: a toctree entry naming one of those uncontested siblings is an
  ordinary `toc.not_readable` warning, so **`sphinx-build -W` fails in the
  gated variant**. Two mounts sharing one `mount_at` with mutually exclusive
  conditions is the shape that reaches it, and it is a natural thing to write;
  distinct `mount_at` prefixes remove the cost entirely. §13.4's record names
  the contested docname so the warning is traceable to the gate.
- **A contest is not the only skip that empties the attribution.** Every
  whole-mount skip of §7 does, and each has the same `-W` consequence: an
  occupied `strict_mount_at`, a bundle root that is not on disk, a listed file
  with no registered suffix or with no name before its suffix, and a collision
  between two of the mount's own files. The absent-root case is the one to know
  about, because gating a bundle a CI has not checked out is a normal reason to
  gate: the pages are absent, the absence is unreported (§13.2), and a
  reference to them warns genuinely. §13.4's record names the skip in every
  case, so a second implementation owes the same traceability — it must not
  claim a downgrade it did not perform.
