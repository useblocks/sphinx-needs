# The mount mapping contract

This document is the **normative** specification of how sphinx-mounts turns a
`ubproject.toml` mount declaration into a set of `(docname, absolute path)` pairs,
and of every rule that decides what happens when two things want the same docname.

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
| `mounts_from_toml = None` in `conf.py` | `conf.py`'s (TOML is never read) |

The third row is load-bearing:
a `ubproject.toml` present only to configure *other* tools must never silently
switch a project's mounts off.

`mounts_from_toml` is documented as a path relative to `confdir`.
The implementation also accepts an absolute path, and a relative path may climb
above `confdir` with `..`; neither is rejected.
A second reader may reject them, but must not assume they cannot occur.

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
Unknown keys are rejected (hard error).
Exactly one of `dir` / `files` must be present.

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
| `mounts.deprecated_location` | the array is declared as top-level `[[mounts]]` | reported only; the mounts load identically |
| `mounts.docname_conflict` | collision per rules 1-3 above | whole mount skipped |
| `mounts.empty_docname` | a listed file's name is only a suffix | whole mount skipped |
| `mounts.ignored_option` | a file-list mount sets `include` or `exclude` | reported only; the keys have no effect |
| `mounts.missing_path` | `dir` or a listed file is not on disk | whole mount skipped |
| `mounts.mount_at_occupied` | `strict_mount_at` set, host has a directory at `mount_at` | whole mount skipped |
| `mounts.path_escape` | a reference leaves the bundle root, `path_check = "warn"` (the default) | reported only |
| `mounts.toctree_index` | `toctree_index` exceeds the toctrees present | mount left unwired, its docs marked orphan |
| `mounts.unknown_suffix` | a listed file has no registered suffix | whole mount skipped |

Configuration problems — malformed TOML, wrong types, unknown keys, contradictory
options, both mount locations declared — are **not** in this list.
They are hard errors and are deliberately not suppressible.

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
- Anything about `[source]` other than a nested `mounts` array (§1).
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

Two entries are worth reading twice, because the disagreement is about *which
documents exist* rather than about how a problem is reported:

- While a mount root is absent, sphinx-mounts has already lost that bundle's
  pages from the build while ubCode still holds them in its index. It is the
  largest declared divergence in the table, and it resolves itself the moment the
  root comes back.
- A mount whose `dir` contains the host source directory is published twice by one
  reader and not at all by the other — the widest possible spread from a
  configuration neither reader rejects.
