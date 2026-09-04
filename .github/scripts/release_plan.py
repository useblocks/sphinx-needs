"""Decide whether a release tag may proceed, and in what order members must be released.

This is the `plan` job of `.github/workflows/release.yaml`, and it is the only thing
standing between a mistyped tag and a PyPI upload. GitHub *creates* an environment that a
workflow names and that does not yet exist -- with no protection rules at all -- so
`environment: pypi-${{ needs.plan.outputs.dist }}` cannot be the fence; the fence has to be
this script, and `publish` reaching it through `needs:` is what stops the expression from
ever being evaluated when it fails. Everything here therefore fails closed: an answer that
is not a clear "no" is an error, never a pass.

Given a tag `<dist>-v<version>` it asserts, in order:

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

With no `--tag` it just prints the topological release order, dependencies first, which is
the answer to "what do I release, and in what sequence".

Usage::

    python .github/scripts/release_plan.py                      # print the order
    python .github/scripts/release_plan.py --tag sphinx-needs-v8.6.0
    python .github/scripts/release_plan.py --tag ... --rehearsal --github-output

Run at the workspace root. Needs `packaging`; PyPI is reached with the standard library,
and git with `git`. In CI it runs as
`uv run --no-project --with packaging python .github/scripts/release_plan.py`, so a
manifest mistake is named here rather than reported as "sync failed".
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
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

PYPI = "https://pypi.org/pypi/{name}/{version}/json"

# The bare `<version>` tag namespace belongs to sphinx-needs, and only to it. Every tag in
# this repository that is not `<dist>-v<version>` predates the monorepo move, when the
# repository built exactly one distribution -- so a bare tag can only ever be a sphinx-needs
# release. Historical tags are never renamed (`git+...@8.5.0` pins and Read the Docs version
# names have to keep working), so `previous_tag` for sphinx-needs has to look in both
# namespaces or the first prefixed release would generate notes against nothing.
BARE_TAG_DIST = "sphinx-needs"


class PlanError(RuntimeError):
    """A condition that must stop the release rather than be guessed at."""


def members(root: Path) -> dict[str, dict[str, Any]]:
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    globs = manifest["tool"]["uv"]["workspace"]["members"]
    out: dict[str, dict[str, Any]] = {}
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
            out[canonicalize_name(data["name"])] = data
    return out


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


def git(*args: str) -> str:
    """Run git, returning stdout; a failure is a PlanError, never a silent empty answer."""
    proc = subprocess.run(["git", *args], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise PlanError(
            f"`git {' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def list_tags() -> list[str]:
    """Every tag in the checkout. The plan job's checkout has to fetch them."""
    return [line.strip() for line in git("tag", "--list").splitlines() if line.strip()]


def is_ancestor(commit: str, branch: str) -> bool:
    """Is `commit` on `branch`? Anything other than a clean yes/no is fatal."""
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, branch],
        capture_output=True,
        text=True,
        check=False,
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


def previous_tag(dist: str, version: str, tags: list[str]) -> str:
    """The tag of the release immediately below `version`, or "" if there is none.

    Considers `<dist>-v<semver>` for every member and, for sphinx-needs only, the bare
    `<semver>` tags this repository used before the monorepo move (see BARE_TAG_DIST).
    """
    try:
        current = Version(version)
    except InvalidVersion as exc:
        raise PlanError(f"`{version}` is not a PEP 440 version") from exc
    candidates: list[tuple[Version, str]] = []
    for tag in tags:
        raw: str | None = None
        if tag.startswith(f"{dist}-v"):
            raw = tag[len(dist) + 2 :]
        elif dist == BARE_TAG_DIST and "-v" not in tag:
            raw = tag
        if raw is None:
            continue
        try:
            parsed = Version(raw)
        except InvalidVersion:
            continue
        if parsed < current:
            candidates.append((parsed, tag))
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


def plan(args: argparse.Namespace) -> int:
    root: Path = args.root
    found = members(root)
    names = set(found)
    graph = {name: edges(data, names) for name, data in found.items()}
    sequence = order(graph)

    print("release order (dependencies first):")
    for rank, name in enumerate(sequence, 1):
        deps = ", ".join(sorted(graph[name])) or "-"
        print(f"  {rank}. {name} {found[name]['version']}   depends on: {deps}")

    if not args.tag:
        return 0

    failures = 0

    # 1. the tag names a member
    dist, version = split_tag(args.tag, sorted(names))

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

    # 4. every intra-workspace runtime dependency is published at the tree's version
    for dependency in sorted(graph[dist]):
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
