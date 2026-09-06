"""Stamp a release into the tree: the version, the two literals, the floors, the lock, the changelog.

Step 1 of AGENTS.md's "Releasing a package" is six edits across five files that must all
say the same number, and every one of them has a gate somewhere else that fails when it is
forgotten -- `check_workspace.py` on the `__version__` literal, the `uv-lock` hook on the
lock, the plan job on the manifest, a reader on the changelog. Doing them by hand is how a
release pull request comes to fail Lint for a reason that has nothing to do with the
release. This does them in one command, in the order the recipe gives, and prints the file
it wrote at each step::

    python tools/src/sn_tools/bump.py sphinx-needs --bump minor
    python tools/src/sn_tools/bump.py sphinx-mounts --to 0.3.0 --date 2026-09-06
    uv run poe bump sphinx-needs --bump minor --dry-run

What it does NOT do is decide anything. It writes no prose: the changelog gets its label,
its heading, its `:Released:` and (where that file's convention has one) its
`:Full Changelog:` link, and the summary paragraph stays hand-written, because a
placeholder in a changelog is a thing that ships. It does not commit, does not tag and does
not push.

**RETRACTION.** An earlier version of this docstring said "it is not a gate:
`check_workspace.py` in Lint and the plan job in `release.yaml` are still what stand
between a half-done bump and PyPI -- this only makes the half-done state unlikely rather
than routine." That is FALSE, and measured to be false for the half-done state this module
can actually produce: a tree bumped everywhere except the changelog is green under
`uv run poe lint`, `check_workspace.py` AND the plan job, because **nothing in this
repository fences a missing changelog entry**. The manifest, the literal, the lock and the
docker fallback all agree; the only thing absent is prose no gate reads. So there is no
downstream fence to fall back on, and this module cannot be allowed to create that state
by refusing halfway through -- which is why `bump()` below is split into a COMPUTE phase
and an APPLY phase: every refusal any step can raise fires while the tree is still
untouched. What remains possible is a crash, a `KeyboardInterrupt`, or a failure of the two
subprocesses in the apply phase; for those, the failure message names the files already
written and the `git checkout --` that undoes them.

**Preconditions, all fail-closed**: the distribution is a member this repository publishes
(the virtual `tools` member is refused, by the same rule that refuses its tag); every file
this run will write is clean in `git status --porcelain`; the new version is strictly above
the current one (a release never moves down, and re-releasing the current version is the
same mistake wearing a different hat); and the changelog does not already carry a label for
it. The rest of the tree may be dirty and the branch is not checked: a release pull request
is cut from `master`, but so is a rehearsal, and refusing to run anywhere else would only
teach people to bypass this.

**Sharing with the other scripts.** These scripts are run by path
(`uv run --no-project --with packaging python tools/src/sn_tools/<script>.py`), which puts
`tools/src/sn_tools` on `sys.path` and NOT `tools/src` -- so `import sn_tools` fails, as
AGENTS.md says. The guard below adds `tools/src` in exactly that case, so this module can
take the member discovery, the runtime-edge rule, the release-tag parser and
`previous_tag` from `release_plan.py`, and the module-location and `__version__`-literal
readers from `check_workspace.py`, rather than growing a second copy of each that would
drift from the fences they belong to. `tools/tests/conftest.py` already imports these
modules the same way; the guard is what makes the by-path invocation agree with it.
`propagate_floors.py` is deliberately NOT imported: it is run as a subprocess with
`sys.executable`, so its argv contract stays the one the recipe documents and its `tomlkit`
dependency stays out of this module's import graph.

Run at the workspace root (or pass `--root`). Needs `packaging`, and `uv` and `git` on
`PATH`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

if __package__ in (None, ""):  # run by path: `sys.path[0]` is this directory
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sn_tools import check_workspace, release_plan

# Both distributions live in this repository, so one compare URL serves both; the tags in
# it are not both prefixed, which is why `previous_tag` is asked rather than assumed (a
# sphinx-needs release before the monorepo move is a bare `8.5.0` tag)
COMPARE = "https://github.com/useblocks/sphinx-needs/compare/{previous}...{new}"

# The one workflow carrying a version literal, and the only member it names. It is a git
# REF, not a version: the Dockerfile installs `git+...@$NEEDS_VERSION`, so the value is the
# prefixed tag. `check_workspace.py` does not fence this one (it reads manifests and module
# source, not workflows), which is exactly why forgetting it is invisible until a docker
# run on a branch with no tag of its own tries to check out a ref that does not exist
DOCKER_WORKFLOW = ".github/workflows/docker.yaml"
DOCKER_DIST = "sphinx-needs"

# `NEEDS_VERSION: ${{ startsWith(github.ref, 'refs/tags/') && github.ref_name || '8.5.0' }}`
# -- the literal after `||` is the fallback for a run with no tag, and it is the only part
# a release moves
DOCKER_LITERAL = re.compile(
    r"(?m)^(?P<head>\s*NEEDS_VERSION:.*\|\|\s*')(?P<literal>[^']*)(?P<tail>'.*)$"
)

# `__version__ = "8.5.0"`, with or without an annotation, in either quote
MODULE_LITERAL = re.compile(
    r"""(?m)^(?P<head>__version__\s*(?::[^=\n]+)?=\s*)(?P<quote>["'])(?P<value>[^"']*)(?P=quote)"""
)

RELEASE_LABEL = re.compile(r"^\.\. _`release:(?P<version>[^`]+)`:\s*$")
RELEASED = re.compile(r"^:Released:\s*(?P<value>\S.*?)\s*$")
FULL_CHANGELOG = ":Full Changelog:"
# `03.09.2026` (sphinx-needs) as against `2026-08-27` (sphinx-mounts). Both conventions are
# in this repository today and a release must not change the one the file it stamps uses.
# The day-first pattern is deliberately lenient about padding: a hand-stamped `3.9.2026` is
# still that file's format, and reading it as "unrecognised" would silently flip the file to
# ISO for that release and every one after it
DAY_FIRST = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UNRELEASED = "Unreleased"

# Every character docutils accepts as a section adornment. RST fixes none of them: a
# document picks its own, and the heading LEVEL follows first use -- so `Changelog` under
# `=` and `Unreleased` under `-` are conventions of the two files in this repository, not
# rules. Matching one hard-coded character per heading is how an `Unreleased` section
# underlined with `=` came to be silently left standing while the new entry went in below it
ADORNMENT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


class BumpError(RuntimeError):
    """A condition that must stop the bump rather than be guessed at."""


class Runner:
    """The one seam this module reaches `uv`, `git` and `propagate_floors.py` through.

    One class rather than direct `subprocess` calls so the orchestration -- which command
    runs, with what arguments, in what order -- is testable without a uv, a git or a
    network anywhere near it. Every call runs at the workspace root.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, command: list[str], *, quiet: bool = False) -> str:
        if not quiet:
            print("$", " ".join(command))
        proc = subprocess.run(
            command, cwd=self.root, text=True, capture_output=True, check=False
        )
        if proc.stdout and not quiet:
            print(proc.stdout, end="")
        if proc.returncode != 0:
            print(proc.stderr, end="", file=sys.stderr)
            raise BumpError(
                f"`{' '.join(command)}` failed ({proc.returncode}): {proc.stderr.strip()}"
            )
        return proc.stdout


# --- the pure rewrites: everything below is text in, text out ----------------------------


def rewrite_module_literal(
    text: str, old: str, new: str, path: str = "__init__.py"
) -> str:
    """Move `__version__` in a module's `__init__.py`, or refuse. Two separate refusals.

    `old` is the MANIFEST's version, not the literal's own. That distinction is the whole
    point: keying on the literal's value made the `old` argument match by construction, so
    a literal that had drifted from the manifest was silently overwritten and the one gate
    that knew about the drift -- `check_workspace.py`'s check (5) -- went green again
    without anyone seeing which of the two numbers had won. A release bump is the worst
    moment to guess which of two hand edits was the intended one.

    The count is taken over EVERY `__version__` assignment, not only the matching ones, so
    a module carrying two of them is refused whichever values they hold. (Both
    `check_workspace.module_version` and this regex read top to bottom, so a second
    assignment is what Python actually leaves in `__version__` at import time and what
    would be stamped into `needs.json` -- while the fence, reading the first, stayed
    green.)
    """
    matches = list(MODULE_LITERAL.finditer(text))
    if len(matches) != 1:
        raise BumpError(
            f"{path}: expected exactly one `__version__` assignment, found "
            f"{len(matches)}; fix the module by hand and re-run"
        )
    match = matches[0]
    found = match["value"]
    if found != old:
        raise BumpError(
            f'{path}: `__version__` is "{found}", but the manifest declares "{old}". '
            "`check-workspace` reports exactly this drift; fix it by hand first -- the "
            "release bump will not guess which of the two numbers is right"
        )
    replacement = f"{match['head']}{match['quote']}{new}{match['quote']}"
    return text[: match.start()] + replacement + text[match.end() :]


def rewrite_docker_literal(text: str, tag: str) -> str:
    """Move the `NEEDS_VERSION` fallback in docker.yaml. Exactly one match, or refuse.

    `tag` is a git ref (`sphinx-needs-v8.6.0`), not a bare version: the Dockerfile uses the
    value as a ref, and the prefixed tag is the one `release.yaml` is triggered by -- the
    bare companion tag it pushes afterwards may not exist yet when the docker workflow
    starts (#540).
    """
    matches = list(DOCKER_LITERAL.finditer(text))
    if len(matches) != 1:
        raise BumpError(
            f"expected exactly one `NEEDS_VERSION: ... || '<literal>'` line in "
            f"{DOCKER_WORKFLOW}, found {len(matches)}"
        )
    match = matches[0]
    return (
        text[: match.start()]
        + match["head"]
        + tag
        + match["tail"]
        + text[match.end() :]
    )


def dependants(projects: dict[str, dict[str, Any]], target: str) -> list[str]:
    """The members with a runtime (or extra) dependency on `target`.

    `release_plan.edges` is the edge rule `check_workspace.py`'s check (4) and the plan
    job's check (4) both use -- `[project] dependencies` plus every
    `[project.optional-dependencies]` list -- so "does this release need floors propagated"
    is answered by the same reading of the manifests that later fails if it was not.
    """
    names = set(projects)
    return sorted(
        name
        for name, project in projects.items()
        if name != target and target in release_plan.edges(project, names)
    )


def released_line(text: str, when: date, path: str = "changelog.rst") -> str:
    """`:Released:` in THIS file's own date format, or refuse.

    sphinx-needs writes `03.09.2026` and sphinx-mounts writes `2026-08-27`. Neither is more
    correct, and a release is not the moment to unify them -- so the format is read off the
    newest existing entry (changelogs here are newest-first, so that is the first
    `:Released:` in the file).

    "ISO when the file has none" and "ISO when the file has one I cannot classify" are
    different rules, and only the first is a documented convention. The second was the
    behaviour: one hand-stamped `3 Sep 2026` -- or `2026/08/27` -- would have flipped the
    file to ISO for that release and, by the same detection, every release after it. So an
    unrecognised value is a refusal naming the line, and ISO is reached only by a file with
    no `:Released:` at all, which is a first release.
    """
    for line in text.splitlines():
        match = RELEASED.match(line)
        if match:
            value = match["value"]
            if DAY_FIRST.match(value):
                return f":Released: {when:%d.%m.%Y}"
            if ISO_DATE.match(value):
                return f":Released: {when:%Y-%m-%d}"
            raise BumpError(
                f"{path}: the newest `:Released: {value}` is neither DD.MM.YYYY nor "
                "YYYY-MM-DD, so this file states no date format to follow; fix that line, "
                "or stamp this entry by hand"
            )
    # the documented fallback, and the only way to reach it: a changelog with no released
    # entry at all
    return f":Released: {when:%Y-%m-%d}"


def compare_line(previous: str, new: str) -> str:
    """The `:Full Changelog:` line, in the exact RST shape the file already uses."""
    return f":Full Changelog: `{previous}...{new} <{COMPARE.format(previous=previous, new=new)}>`__"


def newest_entry_has_compare(lines: list[str]) -> bool:
    """Does the newest existing release entry carry a `:Full Changelog:` line?

    sphinx-needs' entries do and sphinx-mounts' do not, and that is the whole rule: the
    stamp mirrors the file rather than imposing one convention on both.
    """
    start = next(
        (i for i, line in enumerate(lines) if RELEASE_LABEL.match(line)),
        None,
    )
    if start is None:
        return False
    for line in lines[start + 1 :]:
        if RELEASE_LABEL.match(line):
            return False
        if line.startswith(FULL_CHANGELOG):
            return True
    return False


def is_heading(lines: list[str], index: int, title: str) -> bool:
    """Is `lines[index]` a section heading reading `title`, adorned by the line below it?

    By SHAPE, not by character. RST fixes no adornment character and no level ordering: a
    document's first-used adornment becomes its top level, so `Changelog` under `=` with
    `Unreleased` under `-` (this repository) and the same two under `-` and `=` are both
    valid, and only one of them used to be recognised. What docutils actually requires is a
    run of one repeated punctuation character, at least as long as the title text -- which
    is what this asks, once, for both headings this module looks for. Two hard-coded and
    DIFFERENT characters in one module was the drift waiting to happen: an `Unreleased`
    section adorned with `=` was left standing above a new, empty release entry, keeping
    the bullets that were meant to be that release's changelog, and nothing was raised.
    """
    if index + 1 >= len(lines) or lines[index].strip() != title:
        return False
    adornment = lines[index + 1].strip()
    return (
        len(adornment) >= len(title)
        and len(set(adornment)) == 1
        and adornment[0] in ADORNMENT
    )


def changelog_title(lines: list[str]) -> int | None:
    """The index of the `Changelog` section title, if the file has one."""
    return next(
        (index for index in range(len(lines)) if is_heading(lines, index, "Changelog")),
        None,
    )


def unreleased_section(
    lines: list[str], title_at: int | None, label_at: int | None
) -> int | None:
    """The index of an `Unreleased` heading sitting above every released entry.

    The `label_at` bound is what "above every released entry" means, and it is load-bearing
    rather than tidy: an `Unreleased` heading left by mistake INSIDE an older entry's body
    would otherwise be converted, which inserts the new release below the older one --
    newest-first ordering broken and the older entry's body silently annexed. Below the
    first label, the insert branch is the right answer.
    """
    start = 0 if title_at is None else title_at + 2
    stop = len(lines) if label_at is None else min(label_at, len(lines))
    return next(
        (index for index in range(start, stop) if is_heading(lines, index, UNRELEASED)),
        None,
    )


def stamp_changelog(
    text: str,
    *,
    version: str,
    when: date,
    previous_tag: str,
    new_tag: str,
    path: str = "changelog.rst",
) -> tuple[str, str]:
    """Stamp one release entry, in the convention the file already follows.

    Two shapes, and which one applies is read off the file rather than configured:

    * an `Unreleased` section above every released entry (sphinx-mounts today) is
      CONVERTED -- the label goes in above it, the heading becomes the version, the
      `:Released:` line goes in at the top of its body, and every bullet already written
      there is kept, because that is the release's changelog;
    * otherwise a new entry is INSERTED above the newest existing one, with no body at all.
      The summary paragraph is hand-written; a placeholder here is a thing that ships.

    Returns the new text and a one-line description of what was written, for the caller's
    step line. The output is LF-joined whatever the input used, so a CRLF changelog would
    come back rewritten whole; in this repository `.gitattributes`' `* text=auto` normalises
    the blobs either way, so the diff stays one hunk -- the sentence "the diff is the whole
    file" is false here only because of that line, which nothing else connects to this code.
    """
    lines = text.splitlines()
    label_at = next(
        (i for i, line in enumerate(lines) if RELEASE_LABEL.match(line)), None
    )
    title_at = changelog_title(lines)
    # the line a new entry goes in ABOVE: the newest label, or the first line after the
    # `Changelog` title's adornment when the file has no released entry yet. Bound here,
    # where each branch narrows locally, rather than re-derived as a ternary 40 lines on --
    # which is the same invariant stated twice, and the second statement needed a
    # `ty: ignore` because the narrowing does not survive a compound guard
    if label_at is not None:
        at = label_at
    elif title_at is not None:
        at = title_at + 2
    else:
        raise BumpError(
            f"{path} has neither a `Changelog` title nor a `release:` label, so there is "
            "no entry shape to mirror; stamp this release by hand"
        )
    header = [
        f".. _`release:{version}`:",
        "",
        version,
        "-" * len(version),
        "",
        released_line(text, when, path),
    ]
    if newest_entry_has_compare(lines):
        if not previous_tag:
            raise BumpError(
                f"{path}'s newest entry carries a `{FULL_CHANGELOG}` line, but no release "
                f"tag below {version} exists in this checkout, so the compare link would "
                "be broken. Fetch the tags (`git fetch --tags`), or stamp by hand"
            )
        header.append(compare_line(previous_tag, new_tag))

    unreleased_at = unreleased_section(lines, title_at, label_at)
    if unreleased_at is not None:
        body = lines[unreleased_at + 2 :]
        # a field list must be separated from what follows it, or docutils reads the next
        # block as part of the field's body
        if body and body[0].strip():
            body = ["", *body]
        # only THIS section's bullets: `body` runs to the end of the file, and every
        # released entry below it has bullets of its own
        section: list[str] = []
        for line in body:
            if RELEASE_LABEL.match(line):
                break
            section.append(line)
        kept = sum(1 for line in section if line.startswith("- "))
        return (
            "\n".join(lines[:unreleased_at] + header + body) + "\n",
            f"converted the `{UNRELEASED}` section to {version} "
            f"({kept} top-level bullet{'' if kept == 1 else 's'} kept)",
        )

    before = lines[:at]
    while before and not before[-1].strip():
        before.pop()  # exactly one blank line before the new label, however many there were
    after = lines[at:]
    return (
        "\n".join(before + [""] + header + ([""] if after else []) + after) + "\n",
        f"inserted {version} above the newest entry -- the summary paragraph is yours to write",
    )


# --- the run ------------------------------------------------------------------------------


def read_version(manifest: Path) -> str:
    """The `[project] version` a member's manifest declares, right now."""
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        raise BumpError(f"{manifest} declares no static [project] version")
    return version


def preview_version(output: str) -> str:
    """The new version out of `uv version --dry-run`'s `<name> <old> => <new>` line."""
    for line in reversed(output.splitlines()):
        _, arrow, new = line.strip().rpartition("=>")
        if arrow and new.strip():
            return new.strip()
    raise BumpError(
        f"could not read a new version out of `uv version`'s output: {output!r}"
    )


def bump(args: argparse.Namespace, runner: Runner) -> int:
    """Compute everything, refuse if anything is wrong, and only then write.

    The two phases are the whole design. Every refusal this module can raise -- a drifted
    `__version__`, a `NEEDS_VERSION` line that is not there, a changelog with no shape to
    mirror, a `:Released:` format it cannot read, a missing previous tag for a compare
    link, a version that does not move -- is reachable only from data, so all of them can
    fire before a byte is written. They used to fire in file order instead, which meant the
    changelog's refusal arrived with four files and the lock already rewritten: the exact
    half-done state no gate in this repository can see (see the RETRACTION at the top of
    this module). Two `uv version` calls is what that costs -- a `--dry-run` for the
    preflight and the real one in the apply phase -- and `--no-sync` makes each of them a
    manifest read and a manifest write, so the cost is nothing.

    What is still not atomic: the apply phase runs `propagate_floors.py` and `uv lock`, and
    a crash or a `KeyboardInterrupt` anywhere in it leaves part of the tree written. That
    is why the apply phase tracks what it wrote and says so, with the `git checkout --`
    that undoes it, on any failure.
    """
    root: Path = args.root
    dry = args.dry_run

    # === PRECONDITIONS ===================================================================
    workspace = release_plan.members(root)
    dist = release_plan.canonicalize_name(args.dist)
    if dist not in workspace.projects:
        raise BumpError(
            f"`{args.dist}` is not a member of this workspace (members: "
            f"{', '.join(sorted(workspace.projects))})"
        )
    if dist in workspace.virtual:
        raise BumpError(
            f"`{args.dist}` is a virtual member (`[tool.uv] package = false`): this "
            "repository never releases it, and the plan job refuses its tag, so there is "
            "no version to bump"
        )
    directory = workspace.directories[dist]
    manifest = directory / "pyproject.toml"
    old_version = read_version(manifest)
    member = check_workspace.Member(
        root, manifest, tomllib.loads(manifest.read_text(encoding="utf-8"))
    )
    literal = check_workspace.module_version(member)
    changelog = directory / "docs" / "changelog.rst"
    if not changelog.is_file():
        raise BumpError(f"no changelog at {changelog.relative_to(root)}")
    changelog_path = changelog.relative_to(root).as_posix()
    needs_docker = dist == DOCKER_DIST and (root / DOCKER_WORKFLOW).is_file()
    workflow = root / DOCKER_WORKFLOW
    downstream = dependants(workspace.projects, dist)

    writes = [manifest, changelog]
    if literal is not None:
        writes.append(literal[0])
    if needs_docker:
        writes.append(workflow)
    writes += [workspace.directories[name] / "pyproject.toml" for name in downstream]
    guarded = sorted(path.relative_to(root).as_posix() for path in writes)
    status = runner.run(
        ["git", "status", "--porcelain", "--", *guarded], quiet=True
    ).splitlines()
    if any(line.strip() for line in status):
        raise BumpError(
            "these files are not clean, and this run would overwrite them -- commit or "
            "revert them first (the rest of the tree may be dirty):\n  "
            + "\n  ".join(line for line in status if line.strip())
        )
    # `uv.lock` is written but NOT guarded, and the difference is what "overwrite" means.
    # Every file above carries text somebody typed, so a dirty one is work this run would
    # destroy. The lock carries none: `uv lock` derives it from the manifests, so a dirty
    # lock is work this run REDOES. Guarding it would also make the release sequence the
    # planner prints impossible -- releasing two members in one pull request means the
    # second `bump` necessarily meets the lock the first one left dirty.
    relative = sorted([*guarded, "uv.lock"])
    print(
        f"1. {args.dist} {old_version} is a publishable member; its {len(guarded)} "
        "hand-written files are clean (uv.lock is regenerated, not guarded)"
    )

    # === COMPUTE: nothing below writes anything ==========================================
    value = ["--bump", args.bump] if args.bump else [args.to]
    # `--dry-run` prints `<name> <old> => <new>` and writes no manifest, so this is the
    # version the real call in the apply phase will produce, obtained without producing it
    version = preview_version(
        runner.run(
            ["uv", "version", "--package", dist, *value, "--no-sync", "--dry-run"]
        )
    )
    tag = f"{dist}-v{version}"

    try:
        moved = Version(version) > Version(old_version)
    except InvalidVersion as exc:
        raise BumpError(
            f"`{version}` is not a PEP 440 version, so nothing downstream -- the tag "
            f"check, the index, `check-workspace` -- can compare it with {old_version}"
        ) from exc
    if not moved:
        raise BumpError(
            f"{args.dist} {old_version} -> {version} is not a release: a version never "
            "moves down, and re-releasing the current one cannot be published again "
            "(the plan job's check 3 refuses a version already on PyPI). Name a higher "
            "version, or use --bump {patch|minor|major}"
        )
    changelog_text = changelog.read_text(encoding="utf-8")
    if any(
        (match := RELEASE_LABEL.match(line)) and match["version"] == version
        for line in changelog_text.splitlines()
    ):
        raise BumpError(
            f"{changelog_path} already carries a `release:{version}` label, so this would "
            "stamp a second entry for the same version -- two identical RST targets, which "
            "`poe docs-needs` fails on (`-nW`) minutes later with a docutils warning that "
            "says nothing about a release. Was this release already stamped?"
        )

    # the tag list is a pure read, and `previous_tag` is a pure function of it, the
    # distribution and the new version -- so the compare link can be resolved here, which
    # is what lets the changelog's refusals fire before the manifest moves
    tags = [
        line.strip()
        for line in runner.run(["git", "tag", "--list"], quiet=True).splitlines()
        if line.strip()
    ]
    previous = release_plan.previous_tag(dist, version, tags)

    module_text: str | None = None
    if literal is not None:
        module_path, _ = literal
        module_text = rewrite_module_literal(
            module_path.read_text(encoding="utf-8"),
            old_version,
            version,
            module_path.relative_to(root).as_posix(),
        )
    workflow_text: str | None = None
    if needs_docker:
        workflow_text = rewrite_docker_literal(
            workflow.read_text(encoding="utf-8"), tag
        )
    changelog_new, what = stamp_changelog(
        changelog_text,
        version=version,
        when=args.date,
        previous_tag=previous,
        new_tag=tag,
        path=changelog_path,
    )
    print(
        f"   preflight: {old_version} -> {version}; every rewrite computed, "
        f"{'nothing will be written (--dry-run)' if dry else 'nothing written yet'}"
    )

    # === APPLY ============================================================================
    written: list[str] = []
    try:
        # --- 2. the manifest version, written by uv and read back -------------------------
        if not dry:
            runner.run(["uv", "version", "--package", dist, *value, "--no-sync"])
            written.append(manifest.relative_to(root).as_posix())
            # read back rather than trusted: `uv version` owns the bump semantics, and the
            # preview above is only a preview until the manifest agrees with it
            got = read_version(manifest)
            if got != version:
                raise BumpError(
                    f"`uv version` previewed {version} but wrote {got} to "
                    f"{manifest.relative_to(root)}; refusing to stamp two different numbers"
                )
        print(
            f'2. {"would set" if dry else "set"} version = "{version}" in '
            f"{manifest.relative_to(root)}"
        )

        # --- 3. the `__version__` literal -------------------------------------------------
        if literal is None:
            print(
                f"3. no `__version__` literal under {directory.relative_to(root)}/src/"
                f"{member.module}/ -- nothing to rewrite"
            )
        else:
            module_path, _ = literal
            if not dry:
                module_path.write_text(module_text or "", encoding="utf-8")
                written.append(module_path.relative_to(root).as_posix())
            print(
                f'3. {"would write" if dry else "wrote"} __version__ = "{version}" in '
                f"{module_path.relative_to(root)}"
            )

        # --- 4. the docker workflow's NEEDS_VERSION fallback ------------------------------
        if not needs_docker:
            print(f"4. no version literal in a workflow for {args.dist} -- skipped")
        else:
            if not dry:
                workflow.write_text(workflow_text or "", encoding="utf-8")
                written.append(DOCKER_WORKFLOW)
            print(
                f"4. {'would write' if dry else 'wrote'} NEEDS_VERSION fallback `{tag}` "
                f"in {DOCKER_WORKFLOW}"
            )

        # --- 5. the dependants' floors ----------------------------------------------------
        # the numbered line comes BEFORE the subprocess, so the transcript reads as a
        # recipe rather than as output with a caption underneath it
        if not downstream:
            print(
                f"5. no dependants: no member declares {args.dist} at runtime -- "
                "propagate_floors skipped"
            )
        elif dry:
            print(
                f"5. would run propagate_floors.py {args.dist} for {', '.join(downstream)}"
            )
        else:
            print(
                f"5. propagate the {args.dist} {version} floor to "
                f"{', '.join(downstream)}:"
            )
            runner.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().with_name("propagate_floors.py")),
                    args.dist,
                    "--root",
                    str(root),
                ]
            )
            written += [
                (workspace.directories[name] / "pyproject.toml")
                .relative_to(root)
                .as_posix()
                for name in downstream
            ]

        # --- 6. the lock ------------------------------------------------------------------
        # NOT `--frozen`: `--no-sync` above left uv.lock claiming the old version, and the
        # `uv-lock` prek hook would fail the release pull request for a reason that has
        # nothing to do with the release
        if dry:
            print(
                "6. would run `uv lock` (not --frozen: the lock still claims the old "
                "version)"
            )
        else:
            runner.run(["uv", "lock"])
            written.append("uv.lock")
            print("6. relocked uv.lock")

        # --- 7. the changelog -------------------------------------------------------------
        if not dry:
            changelog.write_text(changelog_new, encoding="utf-8")
            written.append(changelog_path)
        print(f"7. {'would stamp' if dry else 'stamped'} {changelog_path}: {what}")
    except BaseException:
        # a crash, a Ctrl-C or a failing subprocess is the one way a half-done tree is
        # still reachable; the least this can do is name it and how to undo it
        if written:
            print()
            print(
                "this run had already written "
                + ", ".join(sorted(written))
                + " when it failed. To undo them:"
            )
            print(f"  git checkout -- {' '.join(sorted(written))}")
        raise

    # --- 8. what was written, and what is left --------------------------------------------
    print()
    print(f"{'would write' if dry else 'wrote'}:")
    for path in relative:
        print(f"  {path}")
    print()
    print('by hand, from AGENTS.md "Releasing a package":')
    # bullets, not numbers: the actions below are AGENTS.md's steps 2 to 4, and a second
    # numbering that starts at 1 drifts against the file this line claims to quote every
    # time either changes
    print(
        f"  - write the summary paragraph under the new {version} heading in "
        f"{changelog_path}"
    )
    print("  - uv run poe lint")
    if dist == DOCKER_DIST:
        print("  - uv run poe smoke-needs")
    print("  - merge the release pull request, then from master:")
    print(f"  - git tag {tag} && git push origin {tag}")
    return 0


def main(argv: list[str] | None = None, runner: Runner | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stamp a release of one workspace member into the tree.",
    )
    parser.add_argument("dist", help="the member being released, e.g. sphinx-needs")
    level = parser.add_mutually_exclusive_group(required=True)
    level.add_argument(
        "--bump",
        choices=["patch", "minor", "major"],
        help="how far to move the version",
    )
    level.add_argument("--to", metavar="X.Y.Z", help="the exact version to release")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="the release date (default: today); written in the changelog's own format",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print every step with the values it would write, and write nothing",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="the workspace root (default: the working directory)",
    )
    args = parser.parse_args(argv)
    try:
        return bump(args, runner or Runner(args.root))
    except (BumpError, release_plan.PlanError) as exc:
        print(f"::error::{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
