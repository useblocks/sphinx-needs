"""Decide whether a release tag may proceed, and in what order members must be released.

This is the `plan` job of `.github/workflows/release.yaml`, and it is the only thing
standing between a mistyped tag and a PyPI upload. GitHub *creates* an environment that a
workflow names and that does not yet exist -- with no protection rules at all -- so
`environment: pypi-${{ needs.plan.outputs.dist }}` cannot be the fence; the fence has to be
this script, and `publish` reaching it through `needs:` is what stops the expression from
ever being evaluated when it fails. Everything here therefore fails closed: an answer that
is not a clear "no" is an error, never a pass.

Given a tag `<dist>-v<version>` it asserts, in order:

0. `<dist>` is a member this repository actually publishes. A member declaring
   `[tool.uv] package = false` is VIRTUAL, and this check is what makes it unreleasable.
   The flag itself only hides the member from uv's workspace selectors (`--all-packages`
   skips it, `--package` is refused); it is not a build prohibition, because
   `uv build tools/` falls through to PEP 517's default backend and does produce a
   distribution. Since a tag is the only thing that starts this workflow, refusing the tag
   here is the fence -- do not remove it as redundant. A dependency on one is refused for a
   related reason: the wheel would name a distribution that is never on PyPI;
1. the tag parses, and `<dist>` is a member of this workspace;
2. `<version>` is exactly the version that member declares -- the tag cannot publish
   something the tree does not build;
3. `<version>` is not already on PyPI (a re-tag of a published version is always a
   mistake). This is the one check `--rehearsal` downgrades to a notice, so that a
   `workflow_dispatch` on `master` at the CURRENT version rehearses the whole pipeline;
4. every *other* workspace member this one depends on at runtime is on PyPI **at the
   version this tree builds**. That is the release-order gate: an extension cannot be
   published against a core that only exists on somebody's disk;
5. the tagged commit is an ancestor of the default branch. A tag pushed from a branch that
   was never merged would publish code no one reviewed on `master`, and the tag is the only
   human approval in this pipeline. A rehearsal *reports* the answer rather than failing on
   it -- a dispatch legitimately runs from whatever ref it was given -- but it still runs
   the check, so the plumbing this one depends on (a checkout deep enough to have
   `origin/master`) is exercised before a real tag needs it; a git failure is fatal in both
   modes.

It also emits `previous_tag`, the release this one follows, for GitHub's
`releases/generate-notes` API.

With no `--tag` this is the **planner**, meant to be run before the release pull request
rather than by CI. It prints the topological release order, then for every publishable
member the last release tag, what PyPI has, the commits since that tag that touched the
member's *shipped* code, and -- for each of its dependants -- the version of it the compat
cell would install from PyPI; then a suggested sequence with the exact commands.

**The planner is advice and never a gate: it exits 0 whatever it finds**, and 1 only when
the data could not be gathered (a manifest it cannot read, a PyPI answer that is not a
clean 404, a git failure). That is deliberate. The release ORDER is enforced by check 4
above and by the compat cell running a dependant's suite against the *released* dependency;
making "there are commits since the last tag" fatal instead would force a premature core
release off a master carrying unfinished work every time an unrelated extension shipped a
fix. The planner says the same thing early, in words, and lets a human decide.

Usage::

    python tools/src/sn_tools/release_plan.py                      # the planner
    python tools/src/sn_tools/release_plan.py --tag sphinx-needs-v8.6.0
    python tools/src/sn_tools/release_plan.py --tag ... --rehearsal --github-output

Run at the workspace root. Needs `packaging`; PyPI is reached with the standard library,
and git with `git`. In CI it runs as
`uv run --no-project --with packaging python tools/src/sn_tools/release_plan.py`, so a
manifest mistake is named here rather than reported as "sync failed" -- and always with
`--tag`, which is why none of the planner's git or PyPI calls happen in the release job.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

PYPI = "https://pypi.org/pypi/{name}/{version}/json"
# the whole-project document, which the planner reads to learn every published version at
# once; `PYPI` above answers one exact version and is all the tag checks need
PYPI_PROJECT = "https://pypi.org/pypi/{name}/json"

# `git log --name-only` interleaves headers and file names, and a file name may contain
# anything. Prefixing each record with a record separator makes the parse unambiguous
COMMIT_SEP = "\x1e"

# The bare `<version>` tag namespace belongs to sphinx-needs, and only to it. Every tag in
# this repository that is not `<dist>-v<version>` predates the monorepo move, when the
# repository built exactly one distribution -- so a bare tag can only ever be a sphinx-needs
# release. Historical tags are never renamed (`git+...@8.5.0` pins and Read the Docs version
# names have to keep working), so `previous_tag` for sphinx-needs has to look in both
# namespaces or the first prefixed release would generate notes against nothing.
BARE_TAG_DIST = "sphinx-needs"


class PlanError(RuntimeError):
    """A condition that must stop the release rather than be guessed at."""


class Workspace(NamedTuple):
    """What `members()` reads off the manifests.

    A tuple rather than a richer object so that `projects, virtual, directories =
    members(root)` keeps reading like the two-value version it replaced. `directories` is
    the planner's addition: it needs each member's directory to ask git which commits
    touched the code that member ships.
    """

    projects: dict[str, dict[str, Any]]
    virtual: set[str]
    directories: dict[str, Path]


def members(root: Path) -> Workspace:
    """Every workspace member's `[project]` table, directory, and whether it is virtual.

    A member with `[tool.uv] package = false` is virtual: `uv build --all-packages` skips
    it and `uv build --package <it>` is refused, so nothing this repository's workflows run
    can build one. That is a selector property, not a build prohibition -- `uv build
    tools/` still produces a distribution through PEP 517's default backend -- which is why
    the caller's rules below are the actual fence, and why they are errors rather than
    warnings.
    """
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    globs = manifest["tool"]["uv"]["workspace"]["members"]
    out: dict[str, dict[str, Any]] = {}
    virtual: set[str] = set()
    directories: dict[str, Path] = {}
    for pattern in globs:
        for path in sorted(root.glob(f"{pattern}/pyproject.toml")):
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            # This job runs FIRST, so a broken manifest reaches it before it reaches
            # `check_workspace.py` in `build` -- which means it, not the fence, is the one
            # that has to name the file and the fix rather than print a traceback
            if "project" not in raw:
                raise PlanError(f"{path}: no [project] table -- is this a package?")
            data = raw["project"]
            if "name" not in data:
                raise PlanError(f"{path}: [project] declares no `name`")
            if "version" in data.get("dynamic", []):
                raise PlanError(
                    f"{path}: {data['name']} has a dynamic version; the release pipeline "
                    "cannot read it without running the build backend"
                )
            if "version" not in data:
                raise PlanError(
                    f"{path}: {data['name']} declares no [project] version; the tag says "
                    "which version is being released and this is what it is checked against"
                )
            key = canonicalize_name(data["name"])
            out[key] = data
            directories[key] = path.parent
            if raw.get("tool", {}).get("uv", {}).get("package") is False:
                virtual.add(key)
    return Workspace(out, virtual, directories)


def edges(project: dict[str, Any], names: set[str]) -> set[str]:
    """The workspace members this member depends on at runtime (extras included)."""
    specs = list(project.get("dependencies", []))
    for extra_specs in project.get("optional-dependencies", {}).values():
        specs.extend(extra_specs)
    own = canonicalize_name(project["name"])
    found = {canonicalize_name(Requirement(spec).name) for spec in specs}
    return {name for name in found if name in names and name != own}


def order(graph: dict[str, set[str]]) -> list[str]:
    """Kahn's algorithm, alphabetical within a rank so the output is reproducible."""
    remaining = {key: set(value) for key, value in graph.items()}
    result: list[str] = []
    while remaining:
        ready = sorted(key for key, deps in remaining.items() if not deps)
        if not ready:
            raise PlanError(
                "cycle among workspace members: " + ", ".join(sorted(remaining))
            )
        for name in ready:
            del remaining[name]
            result.append(name)
        for deps in remaining.values():
            deps.difference_update(ready)
    return result


def on_pypi(name: str, version: str) -> bool:
    """True if this exact version is published. Any non-404 answer is fatal, not a pass."""
    url = PYPI.format(name=name, version=version)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise PlanError(
            f"PyPI returned {exc.code} for {url}; refusing to guess whether "
            f"{name} {version} is published"
        ) from exc
    except urllib.error.URLError as exc:
        raise PlanError(
            f"cannot reach PyPI ({exc.reason}); refusing to guess whether "
            f"{name} {version} is published"
        ) from exc


def published_versions(name: str) -> dict[Version, bool]:
    """Every version PyPI has of `name`, mapped to "is this release entirely yanked?".

    The planner's view of the index, and one request per member rather than one per
    version. A 404 for the WHOLE project means the distribution has never been published,
    which is a perfectly good state for a first release -- so it is an empty answer, not an
    error. Every other status, and an unreachable index, is a `PlanError`: the planner
    would otherwise print advice built on a guess about what is released, which is worse
    than printing nothing.

    Versions PyPI reports that are not PEP 440 are skipped rather than fatal -- they are
    somebody else's history, and no release decision here can turn on one. A document that
    is not the shape this function assumes is not skipped: it is a `PlanError`, because the
    alternative is an `AttributeError` traceback out of the one script whose subject is
    never guessing.

    `except OSError` rather than `except URLError`: a socket read timeout raises
    `TimeoutError`, which is an `OSError` and NOT a `URLError` -- `urlopen`'s read phase
    does not wrap it -- so the narrower clause let a timeout through as a traceback.
    """
    url = PYPI_PROJECT.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise PlanError(
            f"PyPI returned {exc.code} for {url}; refusing to advise on a guess about "
            f"what {name} has published"
        ) from exc
    except OSError as exc:  # URLError, and a read TimeoutError, which is not one
        # `.reason` where there is one, so a URLError still reads `[Errno 61] Connection
        # refused` rather than `<urlopen error [Errno 61] Connection refused>` -- which is
        # what `on_pypi` prints two functions away, and the two should not drift
        raise PlanError(
            f"cannot reach PyPI ({getattr(exc, 'reason', exc)}); refusing to advise on a "
            f"guess about what {name} has published"
        ) from exc
    except ValueError as exc:  # json.JSONDecodeError
        raise PlanError(f"PyPI returned unreadable JSON for {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanError(
            f"PyPI returned a {type(payload).__name__}, not an object, for {url}"
        )
    releases = payload.get("releases", {})
    if not isinstance(releases, dict):
        raise PlanError(
            f"PyPI's `releases` for {url} is a {type(releases).__name__}, not an object"
        )
    out: dict[Version, bool] = {}
    for raw, files in releases.items():
        try:
            parsed = Version(raw)
        except InvalidVersion:
            continue
        if not isinstance(files, list) or not all(
            isinstance(item, dict) for item in files
        ):
            raise PlanError(
                f"PyPI's file list for {name} {raw} is not a list of objects ({url})"
            )
        # yanked means "every file of this release is yanked", because one usable file is
        # enough to install. A release with no files left is unusable for the same reason
        out[parsed] = all(item.get("yanked") for item in files) if files else True
    return out


def git(*args: str, cwd: Path | None = None) -> str:
    """Run git, returning stdout; a failure is a PlanError, never a silent empty answer.

    `cwd` is what makes `--root` mean something to the planner: without it every git call
    would answer about the process's working directory while the pathspecs were built for
    another tree, which is confident misinformation rather than an error. It defaults to
    None -- `subprocess.run`'s own default -- so the tag path, which passes no `cwd`, runs
    byte-identically to before.
    """
    proc = subprocess.run(
        ["git", *args], text=True, capture_output=True, check=False, cwd=cwd
    )
    if proc.returncode != 0:
        raise PlanError(
            f"`git {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def list_tags(cwd: Path | None = None) -> list[str]:
    """Every tag in the checkout. The plan job's checkout has to fetch them."""
    return [
        line.strip()
        for line in git("tag", "--list", cwd=cwd).splitlines()
        if line.strip()
    ]


def is_ancestor(commit: str, branch: str, cwd: Path | None = None) -> bool:
    """Is `commit` on `branch`? Anything other than a clean yes/no is fatal."""
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, branch],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise PlanError(
        f"`git merge-base --is-ancestor {commit} {branch}` failed "
        f"({proc.returncode}): {proc.stderr.strip()} -- refusing to guess whether the "
        f"commit is on {branch}. Does the checkout have the history (`fetch-depth: 0`)?"
    )


def resolve(ref: str, cwd: Path | None = None) -> str | None:
    """The commit `ref` names, or None when it does not resolve. Never fatal.

    Only the planner uses this, and only for context: a checkout without `origin/master`
    (a shallow clone, a fresh worktree that has never fetched) is a fact to report, not a
    reason to refuse advice. `is_ancestor` above is the fail-closed one, and the planner
    calls it only after this has said the ref exists.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )
    return proc.stdout.strip() or None


def head_context(cwd: Path | None = None) -> tuple[str, str]:
    """(short sha, branch name or "detached") for HEAD, for the planner's header line."""
    sha = git("rev-parse", "--short", "HEAD", cwd=cwd).strip()
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd).strip()
    return sha, "detached" if branch == "HEAD" else branch


def commits_since(
    ref: str, paths: list[str], cwd: Path | None = None
) -> list[tuple[str, str]]:
    """(short sha, subject) for every commit since `ref` that touched `paths`, newest first.

    An empty `ref` means the member has never been tagged, and the range becomes the whole
    history -- the caller says so in its output, because "412 unreleased commits" reads
    like a bug otherwise.
    """
    span = [f"{ref}..HEAD"] if ref else ["HEAD"]
    out: list[tuple[str, str]] = []
    for line in git(
        "log", "--format=%h%x09%s", *span, "--", *paths, cwd=cwd
    ).splitlines():
        sha, tab, subject = line.partition("\t")
        if tab:
            out.append((sha, subject))
    return out


def touched_files(
    ref: str, paths: list[str], cwd: Path | None = None
) -> dict[str, set[str]]:
    """Every commit since `ref` touching `paths`, mapped to which of those files it changed.

    One `git log` for as many path sets as the caller cares about, which is what lets the
    "this commit changed the core AND the extension" heuristic cost one process rather than
    one per dependency edge. `--name-only` honours the pathspec, so the file lists are
    already restricted to `paths`.

    `core.quotePath=false` is load-bearing: by default git C-quotes any path with a
    non-ASCII or control character -- `"packages/core/src/x/t\303\253st.py"`, quotes and
    all -- and `under()` would then see a name that starts with `"` and match nothing, so
    the both-packages heuristic would silently miss such a commit. Measured.
    """
    span = [f"{ref}..HEAD"] if ref else ["HEAD"]
    raw = git(
        "-c",
        "core.quotePath=false",
        "log",
        f"--format={COMMIT_SEP}%h%x09%s",
        "--name-only",
        *span,
        "--",
        *paths,
        cwd=cwd,
    )
    out: dict[str, set[str]] = {}
    for record in raw.split(COMMIT_SEP):
        lines = [line for line in record.splitlines() if line]
        if not lines:
            continue
        out[lines[0].partition("\t")[0]] = set(lines[1:])
    return out


def release_tags(dist: str, tags: list[str]) -> list[tuple[Version, str]]:
    """Every tag that names a release of `dist`, as (version, tag).

    Considers `<dist>-v<semver>` for every member and, for sphinx-needs only, the bare
    `<semver>` tags this repository used before the monorepo move (see BARE_TAG_DIST).
    Tags that are not PEP 440 once the prefix is off -- `v2.0.0`, `v.1.4`,
    `depbatch-backup-...` -- are somebody's else's refs and are skipped in silence.

    `previous_tag` and the planner share this one parser deliberately: "which tags are this
    distribution's releases" must have exactly one answer.
    """
    out: list[tuple[Version, str]] = []
    for tag in tags:
        raw: str | None = None
        if tag.startswith(f"{dist}-v"):
            raw = tag[len(dist) + 2 :]
        elif dist == BARE_TAG_DIST and "-v" not in tag:
            raw = tag
        if raw is None:
            continue
        try:
            out.append((Version(raw), tag))
        except InvalidVersion:
            continue
    return out


def previous_tag(dist: str, version: str, tags: list[str]) -> str:
    """The tag of the release immediately below `version`, or "" if there is none."""
    try:
        current = Version(version)
    except InvalidVersion as exc:
        raise PlanError(f"`{version}` is not a PEP 440 version") from exc
    candidates = [pair for pair in release_tags(dist, tags) if pair[0] < current]
    if not candidates:
        return ""
    # max on the version, and on the tag name to break a bare/prefixed tie deterministically
    return max(candidates)[1]


def split_tag(tag: str, known: list[str]) -> tuple[str, str]:
    """`<dist>-v<version>` -> (dist, version). Longest member name first, so a name that
    is a prefix of another cannot swallow it."""
    for candidate in sorted(known, key=len, reverse=True):
        if tag.startswith(f"{candidate}-v"):
            return candidate, tag[len(candidate) + 2 :]
    raise PlanError(
        f"tag `{tag}` does not name a member of this workspace (expected "
        f"`<dist>-v<version>` with <dist> one of {', '.join(sorted(known))})"
    )


# --- the planner: what to release, in what order, tested against what --------------------
# Everything below runs only when no `--tag` was given. None of it is reachable from the
# release workflow, which always passes one -- see R3 in the module docstring: the plan job
# runs with `--no-project`, and a planner that woke up there would add PyPI and git calls to
# the one job standing between a mistyped tag and an upload.

# how many commits to list under a member before summarising the rest. A member that has
# never been tagged has its whole history here, and a screenful is enough to recognise it
LISTED_COMMITS = 10


class Status(NamedTuple):
    """One publishable member's release situation, as the planner sees it."""

    name: str
    declared: Version
    published: dict[Version, bool]  # every version PyPI has -> is it entirely yanked?
    latest: Version | None  # the highest version PyPI has that is not yanked
    last_tag: str  # "" when this member has never been tagged
    declared_tag: str  # the tag naming `declared`, if one exists locally
    commits: list[tuple[str, str]]  # unreleased commits touching the shipped code
    paths: list[str]  # that shipped code, repository-relative
    root: Path  # the tree those paths and every git call below are relative to
    verdict: int  # 1 up to date | 2 bump first | 3 ready to tag | 4 behind PyPI


def shipped_paths(root: Path, directory: Path) -> list[str]:
    """A member's SHIPPED code: `<dir>/src` and `<dir>/pyproject.toml`.

    Documentation and tests are deliberately excluded -- a docs commit is not a reason to
    cut a release, and counting one would make the planner cry wolf on every branch. The
    filter is printed in the output, because "5 unreleased commits" says nothing until the
    reader knows what "touched" was taken to mean.
    """
    where = directory.relative_to(root).as_posix()
    return [f"{where}/src", f"{where}/pyproject.toml"]


def under(path: str, roots: list[str]) -> bool:
    """Is `path` one of `roots`, or inside one of them?"""
    return any(path == root or path.startswith(f"{root}/") for root in roots)


def requirement_for(project: dict[str, Any], dependency: str) -> str | None:
    """A dependant's own requirement on `dependency`, extras included (as `edges()` is).

    The manifest's own text, not a re-rendered `Requirement`: `packaging` normalises a
    specifier set into sorted order, so `sphinx-needs>=8.5.0,<9` comes back as
    `<9,>=8.5.0` -- correct, and not what the reader will find when they open the file.
    """
    specs = list(project.get("dependencies", []))
    for extra_specs in project.get("optional-dependencies", {}).values():
        specs.extend(extra_specs)
    for spec in specs:
        if canonicalize_name(Requirement(spec).name) == dependency:
            return spec
    return None


def status_of(
    name: str, project: dict[str, Any], paths: list[str], tags: list[str], root: Path
) -> Status:
    """Gather one member's facts and reach a verdict. Every outside call here is a seam."""
    try:
        declared = Version(project["version"])
    except InvalidVersion as exc:
        raise PlanError(
            f"{project['name']} declares version `{project['version']}`, which is not "
            "PEP 440; nothing in this pipeline can compare it with a tag or with PyPI"
        ) from exc
    releases = release_tags(name, tags)
    last_tag = max(releases)[1] if releases else ""
    declared_tag = next((tag for version, tag in releases if version == declared), "")
    published = published_versions(name)
    live = [version for version, yanked in published.items() if not yanked]
    latest = max(live) if live else None
    commits = commits_since(last_tag, paths, cwd=root)
    # order matters: a tree BEHIND the index is an old branch, and that is the useful
    # answer even though `declared` is (necessarily) published as well
    if latest is not None and declared < latest:
        verdict = 4
    elif declared in published:
        verdict = 2 if commits else 1
    else:
        verdict = 3
    return Status(
        name,
        declared,
        published,
        latest,
        last_tag,
        declared_tag,
        commits,
        paths,
        root,
        verdict,
    )


def print_commits(commits: list[tuple[str, str]], indent: str) -> None:
    for sha, subject in commits[:LISTED_COMMITS]:
        print(f"{indent}{sha}  {subject}")
    if len(commits) > LISTED_COMMITS:
        print(f"{indent}... and {len(commits) - LISTED_COMMITS} more")


def print_status(status: Status, directory: str) -> None:
    """One member's block: where it stands, and what to do about it."""
    name, declared = status.name, status.declared
    count = len(status.commits)
    plural = "" if count == 1 else "s"
    since = status.last_tag or "the start of history"
    print()
    print(f"{name} {declared}   ({directory})")
    if status.last_tag:
        print(f"  last release tag   {status.last_tag}")
    else:
        print(
            "  last release tag   none -- never tagged, so everything below is its whole history"
        )
    if status.published:
        yanked = sum(1 for value in status.published.values() if value)
        how_many = f"{len(status.published)} version{'' if len(status.published) == 1 else 's'}"
        if status.latest is None:
            print(
                f"  on PyPI            {how_many}, latest: none -- every version yanked"
            )
        else:
            note = f", {yanked} yanked" if yanked else ""
            print(f"  on PyPI            {how_many}, latest {status.latest}{note}")
    else:
        print(f"  on PyPI            nothing -- {name} has never been published")
    if status.verdict == 1:
        print(
            f"  up to date, nothing to release: {declared} is on PyPI and no commit since {since} touched its shipped code"
        )
    elif status.verdict == 2:
        print(
            f"  {count} unreleased commit{plural} since {since}; {declared} is already published -- bump before tagging:"
        )
        print(
            f"      uv version --package {name} --bump {{patch|minor|major}} --no-sync"
        )
        print_commits(status.commits, "    ")
    elif status.verdict == 3:
        print(f"  release pending: {declared} is not on PyPI, and this tree builds it")
        print(f"      git tag {name}-v{declared} && git push origin {name}-v{declared}")
        print(
            f"      rehearse first: gh workflow run release.yaml -f tag={name}-v{declared}"
        )
        if status.declared_tag:
            print(
                f"  the tag {status.declared_tag} exists but PyPI has no {declared}: that release did not complete -- re-run the workflow from the tag, do not re-tag"
            )
        if count:
            print(f"  {count} commit{plural} since {since} touched its shipped code:")
            print_commits(status.commits, "    ")
    else:
        print(
            f"  this tree is BEHIND PyPI ({declared} vs {status.latest}) -- an old branch?"
        )


def shared_commits(core: Status, dependant: Status) -> list[tuple[str, str]]:
    """The core's unreleased commits that ALSO touched the dependant's shipped code.

    The scenario no version comparison can see: one feature commit changes the core and the
    extension together, so the extension almost certainly relies on the core that is not
    released yet. One `git log` covers both path sets.
    """
    changed = touched_files(core.last_tag, core.paths + dependant.paths, cwd=core.root)
    subjects = dict(core.commits)
    out: list[tuple[str, str]] = []
    for sha, _ in core.commits:
        files = changed.get(sha, set())
        if any(under(item, core.paths) for item in files) and any(
            under(item, dependant.paths) for item in files
        ):
            out.append((sha, subjects[sha]))
    return out


def print_dependant(core: Status, dependant: Status, spec: str) -> None:
    """What a release of `dependant` would be stopped by, or tested against.

    The gates are asked in the order the pipeline asks them, and each branch names the ONE
    that fires:

    1. the plan job's check (4) -- `on_pypi(<core>, <core's TREE version>)`. Note what that
       predicate is: not "does something published satisfy the dependant's specifier" but
       "is the version this tree builds on the index at all". Answering the second question
       and reporting it as the first is how this line came to reassure a reader about a tag
       the plan job then refused (and to threaten a refusal that never came, for a yanked
       release: the per-version PyPI URL answers 200 for one, so check (4) passes);
    2. the resolver gate and the compat cell's install, which resolve a RANGE from the
       index and therefore skip yanked releases even though check (4) accepted one;
    3. the compat cell itself, which is the only content-aware guard and the only thing
       that can catch a behaviour change.

    One limit worth stating: `SpecifierSet.filter` compares versions and nothing else, so a
    release whose only artefacts are incompatible with the compat cell's interpreter -- a
    higher `Requires-Python`, a platform-specific wheel set -- would be named here and
    passed over by uv. Both members are pure-python `py3-none-any` today.
    """
    live = sorted(version for version, yanked in core.published.items() if not yanked)
    tag = f"{dependant.name}-v{dependant.declared}"
    count = len(core.commits)
    plural = "" if count == 1 else "s"
    print(f"    {dependant.name} {dependant.declared} needs {spec}")
    if core.declared not in core.published:
        # check (4)'s own predicate, verbatim: is the TREE's version on the index?
        if core.latest is not None:
            have = f"has {core.latest} as its newest live version"
        elif core.published:
            # `latest` is None but the index is not empty: every release is yanked, and
            # "PyPI has nothing" would be a different, wronger fact
            how_many = f"{len(core.published)} version{'' if len(core.published) == 1 else 's'}"
            have = f"has {how_many}, all yanked"
        else:
            have = "has nothing"
        print(
            f"      the plan job WILL refuse `{tag}`: check 4 needs {core.name} {core.declared} on PyPI, and PyPI {have} -- release {core.name} first"
        )
    else:
        # the specifier is consulted BEFORE the yank, because a yanked tree version is only
        # a problem when nothing else live satisfies the dependant: the resolver gate and the
        # compat cell resolve a RANGE, so a live 2.0.0 answers `>=2.0.0,<3` perfectly well
        # even while the tree's own 2.1.0 is withdrawn
        usable = sorted(Requirement(spec).specifier.filter(live))
        withdrawn = core.published[core.declared]
        if not usable and withdrawn:
            print(
                f"      the plan job passes ({core.name} {core.declared} is on PyPI) but every file of it is yanked and no other live {core.name} satisfies {spec}, so the resolver gate -- `uv pip install --dry-run` against the index -- cannot resolve it: release a new {core.name}"
            )
        elif not usable:
            print(
                f"      no published {core.name} satisfies {spec}: the resolver gate fails (and Lint's check-workspace refuses a specifier that does not admit the tree's {core.declared})"
            )
        else:
            instead = (
                f" ({core.name} {core.declared}, this tree's version, is yanked, so the index resolves to {usable[-1]} instead)"
                if withdrawn
                else ""
            )
            lacks = (
                f", which lacks {core.name}'s {count} commit{plural} since {core.last_tag or 'the start of history'}"
                if count
                else ""
            )
            print(
                f"      the compat cell installs {core.name} from PyPI: `{tag}` would be tested against {core.name} {usable[-1]}{instead}{lacks}"
            )
            both = shared_commits(core, dependant)
            if both:
                print(
                    f"      these changed both {core.name} and {dependant.name} -- {dependant.name} very likely relies on the unreleased {core.name}; bump and release {core.name} first:"
                )
                print_commits(both, "        ")
    print(
        f"      `uv run python tools/src/sn_tools/import_check.py {dependant.name}` installs the PUBLISHED {core.name} and imports every {dependant.name} module -- a missing symbol is named in seconds; behaviour changes still need the suite (the compat cell)"
    )


def print_sequence(sequence: list[str], statuses: dict[str, Status]) -> None:
    """The topological order, filtered to what is actually pending, with the commands."""
    pending = [name for name in sequence if statuses[name].verdict in (2, 3)]
    settled = [name for name in sequence if statuses[name].verdict == 1]
    behind = [name for name in sequence if statuses[name].verdict == 4]
    print()
    if not pending:
        # one line, not two: the "behind" note IS the answer when nothing is pending
        if behind:
            print(
                f"behind PyPI, so nothing to release from this tree: {', '.join(behind)}"
            )
        else:
            print("nothing to release: every member is up to date")
        return
    print("suggested sequence (dependencies first):")
    for rank, name in enumerate(pending, 1):
        status = statuses[name]
        if status.verdict == 2:
            version = "<new version>"
            print(f"  {rank}. after a bump: {name}")
            print(
                f"       uv version --package {name} --bump {{patch|minor|major}} --no-sync"
            )
        else:
            version = str(status.declared)
            print(f"  {rank}. {name} {version}")
        print(f"       rehearse: gh workflow run release.yaml -f tag={name}-v{version}")
        print(
            f"       tag:      git tag {name}-v{version} && git push origin {name}-v{version}"
        )
    if settled:
        print(f"  nothing to release: {', '.join(settled)}")
    if behind:
        print(
            f"  behind PyPI, so nothing to release from this tree: {', '.join(behind)}"
        )


def planner(
    root: Path, workspace: Workspace, graph: dict[str, set[str]], sequence: list[str]
) -> None:
    """Everything after the release order when no `--tag` was given. Prints; never gates."""
    found, _virtual, directories = workspace
    print()
    print("release plan -- advice, never a gate: this exits 0 whatever it finds")
    sha, branch = head_context(cwd=root)
    print(f"  HEAD {sha} ({branch})")
    if resolve("origin/master", cwd=root) is None:
        print("  origin/master not found (no fetch?): ancestry not checked")
    elif not is_ancestor("HEAD", "origin/master", cwd=root):
        print(
            "  HEAD is not on origin/master -- releases are cut from master; this describes THIS tree"
        )
    print(
        '  "unreleased" counts commits touching a member\'s SHIPPED code -- <member>/src and <member>/pyproject.toml. Docs and tests are deliberately not counted'
    )

    tags = list_tags(cwd=root)
    statuses = {
        name: status_of(
            name, found[name], shipped_paths(root, directories[name]), tags, root
        )
        for name in sequence
    }
    for name in sequence:
        print_status(statuses[name], directories[name].relative_to(root).as_posix())
        dependants = [other for other in sequence if name in graph[other]]
        if dependants:
            print("  dependants:")
        for other in dependants:
            spec = requirement_for(found[other], name)
            # `edges()` found the edge in the same two tables, so this cannot be None --
            # but the planner must never traceback at a reader who wanted advice
            if spec is not None:
                print_dependant(statuses[name], statuses[other], spec)
    print_sequence(sequence, statuses)


def plan(args: argparse.Namespace) -> int:
    root: Path = args.root
    workspace = members(root)
    found, virtual = workspace.projects, workspace.virtual
    names = set(found)
    graph = {name: edges(data, names) for name, data in found.items()}
    sequence = [name for name in order(graph) if name not in virtual]

    print("release order (dependencies first):")
    for rank, name in enumerate(sequence, 1):
        deps = ", ".join(sorted(graph[name])) or "-"
        print(f"  {rank}. {name} {found[name]['version']}   depends on: {deps}")
    # listed, but not numbered: a virtual member has no release to order
    for name in sorted(virtual):
        print(f"  -- {name} {found[name]['version']}   (virtual -- never published)")

    if not args.tag:
        if args.no_git:
            # the planner IS git reasoning -- which commits since the last tag touched a
            # member's shipped code -- so the flag would not skip a check, it would empty
            # the answer. Refusing is clearer than printing advice with the middle missing
            raise PlanError(
                "--no-git makes no sense without --tag: the planner's whole subject is "
                "what git says has changed since each member's last release tag. Drop "
                "--no-git, or pass --tag to run the release-tag checks without git"
            )
        planner(root, workspace, graph, sequence)
        return 0

    failures = 0

    # 1. the tag names a member, and one this repository publishes
    dist, version = split_tag(args.tag, sorted(names))
    if dist in virtual:
        raise PlanError(
            f"`{found[dist]['name']}` is a virtual member (`[tool.uv] package = false`): "
            "this repository never releases it, and refusing this tag is what makes that "
            "true -- there is nothing to release"
        )

    # 2. the tag's version is the version this tree builds
    declared = found[dist]["version"]
    if version != declared:
        print(
            f"::error::tag `{args.tag}` says {dist} {version}, but this tree builds "
            f"{declared}; tag the commit whose manifest carries the version you mean"
        )
        return 1

    # 3. not already published -- a notice rather than an error in a rehearsal, which is
    #    what lets a dispatch on master re-run the whole pipeline at the current version
    if on_pypi(dist, version):
        if args.rehearsal:
            print(
                f"::notice::{dist} {version} is already on PyPI. In a real run this is "
                "fatal -- a re-tag of a published version cannot be published again -- but "
                "this is a rehearsal, so the pipeline continues and publishes nothing"
            )
        else:
            print(
                f"::error::{dist} {version} is already on PyPI; a re-tag of a published "
                "version cannot be published again"
            )
            failures += 1
    else:
        print(f"OK    {dist} {version} is not on PyPI yet")

    # 4. every intra-workspace runtime dependency is published at the tree's version.
    #    A virtual dependency is never on PyPI at any version, so it is not a question to
    #    ask the index -- it is a wheel that could not be installed, and it is fatal here
    #    exactly as it is in `check_workspace.py` on every pull request.
    for dependency in sorted(graph[dist]):
        # `and dist not in virtual` is belt and braces -- rule 0 above already refused a
        # tag naming a virtual member -- but it states the actual rule: the objection is
        # that the WHEEL would name something never on PyPI, and only a publishable
        # dependant has a wheel
        if dependency in virtual and dist not in virtual:
            raise PlanError(
                f"{found[dist]['name']} declares a runtime (or extra) dependency on "
                f"{found[dependency]['name']}, which is a virtual member "
                "(`[tool.uv] package = false`); the published wheel could never be "
                f"installed: `{found[dependency]['name']}` is never on PyPI"
            )
        needed = found[dependency]["version"]
        if on_pypi(dependency, needed):
            print(f"OK    {dependency} {needed} is on PyPI")
        else:
            position = sequence.index(dependency) + 1
            print(
                f"::error::{dist} depends on {dependency}, and this tree builds "
                f"{dependency} {needed}, which is NOT on PyPI. Release it first: the order "
                f"is {' -> '.join(sequence)} ({dependency} is #{position})"
            )
            failures += 1

    # 5. the tagged commit is on the default branch. The check RUNS in a rehearsal too and
    #    only its verdict is downgraded: a dispatch legitimately runs from another ref, but
    #    if the answer were never computed then `git merge-base` -- and the checkout depth
    #    it needs -- would first execute on a real tag, which is the worst possible moment
    #    to find out the history is not there. A PlanError out of git stays fatal in both
    #    modes for the same reason.
    if not args.no_git:
        on_branch = is_ancestor(args.commit, args.default_branch)
        if args.rehearsal:
            print(
                f"::notice::{args.commit} is{'' if on_branch else ' NOT'} an ancestor of "
                f"{args.default_branch} (a rehearsal runs from whatever ref was dispatched, "
                "so this is informational)"
            )
        elif on_branch:
            print(f"OK    {args.commit} is an ancestor of {args.default_branch}")
        else:
            print(
                f"::error::the tagged commit ({args.commit}) is not an ancestor of "
                f"{args.default_branch}; releases are cut from the default branch, and a "
                "tag is the only human approval this pipeline has. Merge first, then tag "
                "the merged commit"
            )
            failures += 1

    if failures:
        return 1

    tags = list_tags()
    previous = previous_tag(dist, version, tags)
    print(
        f"OK    previous release tag: {previous or '(none -- this is the first)'}"
        f"  [{len(tags)} tags]"
    )

    if args.github_output:
        # the one place in these scripts that could fail OPEN: the flag was asked for, the
        # variable is missing, and every job downstream of `plan` would read an empty `dist`
        destination = os.environ.get("GITHUB_OUTPUT")
        if not destination:
            raise PlanError(
                "--github-output was asked for but GITHUB_OUTPUT is not set; the job's "
                "outputs would be empty and every job downstream of `plan` would run "
                "against an empty distribution name"
            )
        with open(destination, "a", encoding="utf-8") as handle:
            handle.write(f"dist={dist}\nversion={version}\nprevious_tag={previous}\n")
    print(json.dumps({"dist": dist, "version": version, "previous_tag": previous}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a release tag and print the workspace's release order.",
    )
    parser.add_argument("--tag", help="the pushed tag, `<dist>-v<version>`")
    parser.add_argument(
        "--rehearsal",
        action="store_true",
        help="dry run: an already-published version and a commit off the default branch "
        "are reported as notices instead of errors. Every check still RUNS, and every "
        "other one stays fatal",
    )
    parser.add_argument(
        "--commit",
        default="HEAD",
        help="the commit the tag points at (default: HEAD)",
    )
    parser.add_argument(
        "--default-branch",
        default="origin/master",
        help="the branch a release must be cut from (default: origin/master)",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="skip the ancestry check (for a checkout without the branch history)",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="append dist=, version= and previous_tag= to $GITHUB_OUTPUT",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="the workspace root (default: the working directory)",
    )
    args = parser.parse_args(argv)
    try:
        return plan(args)
    except PlanError as exc:
        print(f"::error::{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
