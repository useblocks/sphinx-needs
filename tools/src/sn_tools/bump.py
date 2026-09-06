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
not push. And it is not a gate: `check_workspace.py` in Lint and the plan job in
`release.yaml` are still what stand between a half-done bump and PyPI -- this only makes
the half-done state unlikely rather than routine.

**Preconditions, all fail-closed**: the distribution is a member this repository publishes
(the virtual `tools` member is refused, by the same rule that refuses its tag), and every
file this run will write is clean in `git status --porcelain`. The rest of the tree may be
dirty and the branch is not checked: a release pull request is cut from `master`, but so is
a rehearsal, and refusing to run anywhere else would only teach people to bypass this.

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
# in this repository today and a release must not change the one the file it stamps uses
DAY_FIRST = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
UNRELEASED = "Unreleased"


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


def rewrite_module_literal(text: str, old: str, new: str) -> str:
    """Move `__version__` in a module's `__init__.py`. Exactly one match, or refuse.

    Keyed on the OLD value, not just on the name: a module that carries two `__version__`
    assignments, or one whose literal already disagrees with the manifest, is a state this
    cannot silently pick a winner in -- `check_workspace.py`'s check (5) exists precisely
    because the two numbers drift.
    """
    matches = [m for m in MODULE_LITERAL.finditer(text) if m.group("value") == old]
    if len(matches) != 1:
        raise BumpError(
            f'expected exactly one `__version__ = "{old}"` assignment, found '
            f"{len(matches)}; fix the module by hand and re-run"
        )
    match = matches[0]
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


def released_line(text: str, when: date) -> str:
    """`:Released:` in THIS file's own date format.

    sphinx-needs writes `03.09.2026` and sphinx-mounts writes `2026-08-27`. Neither is more
    correct, and a release is not the moment to unify them -- so the format is read off the
    newest existing entry (changelogs here are newest-first, so that is the first
    `:Released:` in the file) and ISO is the answer only when the file has none.
    """
    for line in text.splitlines():
        match = RELEASED.match(line)
        if match:
            iso = not DAY_FIRST.match(match["value"])
            return (
                f":Released: {when:%Y-%m-%d}" if iso else f":Released: {when:%d.%m.%Y}"
            )
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


def changelog_title(lines: list[str]) -> int | None:
    """The index of the `Changelog` section title, if the file has one."""
    for index in range(len(lines) - 1):
        underline = lines[index + 1].strip()
        if (
            lines[index].strip() == "Changelog"
            and underline
            and set(underline) == {"="}
        ):
            return index
    return None


def unreleased_section(
    lines: list[str], title_at: int | None, label_at: int | None
) -> int | None:
    """The index of an `Unreleased` heading sitting above every released entry."""
    start = 0 if title_at is None else title_at + 2
    stop = len(lines) - 1 if label_at is None else min(label_at, len(lines) - 1)
    for index in range(start, stop):
        underline = lines[index + 1].strip()
        if lines[index].strip() == UNRELEASED and underline and set(underline) == {"-"}:
            return index
    return None


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
    step line.
    """
    lines = text.splitlines()
    label_at = next(
        (i for i, line in enumerate(lines) if RELEASE_LABEL.match(line)), None
    )
    title_at = changelog_title(lines)
    if label_at is None and title_at is None:
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
        released_line(text, when),
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

    at = label_at if label_at is not None else title_at + 2  # ty: ignore[unsupported-operator]
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
    root: Path = args.root
    dry = args.dry_run

    # --- 1. preconditions ----------------------------------------------------------------
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
    needs_docker = dist == DOCKER_DIST and (root / DOCKER_WORKFLOW).is_file()
    downstream = dependants(workspace.projects, dist)

    writes = [manifest, changelog]
    if literal is not None:
        writes.append(literal[0])
    if needs_docker:
        writes.append(root / DOCKER_WORKFLOW)
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

    # --- 2. the manifest version, written by uv and read back ----------------------------
    value = ["--bump", args.bump] if args.bump else [args.to]
    printed = runner.run(
        [
            "uv",
            "version",
            "--package",
            dist,
            *value,
            "--no-sync",
            *(["--dry-run"] if dry else []),
        ]
    )
    # read back rather than computed: `uv version` owns the bump semantics, and a second
    # implementation of them here is a second thing to be wrong. A dry run writes no
    # manifest to read back from, so its own `<name> <old> => <new>` line is the preview
    version = preview_version(printed) if dry else read_version(manifest)
    tag = f"{dist}-v{version}"
    print(
        f'2. {"would set" if dry else "set"} version = "{version}" in {manifest.relative_to(root)}'
    )

    # --- 3. the `__version__` literal ----------------------------------------------------
    if literal is None:
        print(
            f"3. no `__version__` literal under {directory.relative_to(root)}/src/"
            f"{member.module}/ -- nothing to rewrite"
        )
    else:
        module_path, module_value = literal
        text = rewrite_module_literal(
            module_path.read_text(encoding="utf-8"), module_value, version
        )
        if not dry:
            module_path.write_text(text, encoding="utf-8")
        print(
            f'3. {"would write" if dry else "wrote"} __version__ = "{version}" in '
            f"{module_path.relative_to(root)}"
        )

    # --- 4. the docker workflow's NEEDS_VERSION fallback ---------------------------------
    if not needs_docker:
        print(f"4. no version literal in a workflow for {args.dist} -- skipped")
    else:
        workflow = root / DOCKER_WORKFLOW
        text = rewrite_docker_literal(workflow.read_text(encoding="utf-8"), tag)
        if not dry:
            workflow.write_text(text, encoding="utf-8")
        print(
            f"4. {'would write' if dry else 'wrote'} NEEDS_VERSION fallback `{tag}` in {DOCKER_WORKFLOW}"
        )

    # --- 5. the dependants' floors -------------------------------------------------------
    if not downstream:
        print(
            f"5. no dependants: no member declares {args.dist} at runtime -- propagate_floors skipped"
        )
    elif dry:
        print(
            f"5. would run propagate_floors.py {args.dist} for {', '.join(downstream)}"
        )
    else:
        runner.run(
            [
                sys.executable,
                str(Path(__file__).resolve().with_name("propagate_floors.py")),
                args.dist,
                "--root",
                str(root),
            ]
        )
        print(
            f"5. propagated the {args.dist} {version} floor to {', '.join(downstream)}"
        )

    # --- 6. the lock ---------------------------------------------------------------------
    # NOT `--frozen`: `--no-sync` above left uv.lock claiming the old version, and the
    # `uv-lock` prek hook would fail the release pull request for a reason that has nothing
    # to do with the release
    if dry:
        print(
            "6. would run `uv lock` (not --frozen: the lock still claims the old version)"
        )
    else:
        runner.run(["uv", "lock"])
        print("6. relocked uv.lock")

    # --- 7. the changelog ----------------------------------------------------------------
    # through the runner like every other git call, so the whole orchestration is one seam
    tags = [
        line.strip()
        for line in runner.run(["git", "tag", "--list"], quiet=True).splitlines()
        if line.strip()
    ]
    previous = release_plan.previous_tag(dist, version, tags)
    text, what = stamp_changelog(
        changelog.read_text(encoding="utf-8"),
        version=version,
        when=args.date,
        previous_tag=previous,
        new_tag=tag,
        path=changelog.relative_to(root).as_posix(),
    )
    if not dry:
        changelog.write_text(text, encoding="utf-8")
    print(
        f"7. {'would stamp' if dry else 'stamped'} {changelog.relative_to(root)}: {what}"
    )

    # --- 8. what was written, and what is left ------------------------------------------
    print()
    print(f"{'would write' if dry else 'wrote'}:")
    for path in relative:
        print(f"  {path}")
    print()
    print('by hand, from AGENTS.md "Releasing a package":')
    print(
        f"  1. write the summary paragraph under the new {version} heading in {changelog.relative_to(root)}"
    )
    print("  2. uv run poe lint")
    if dist == DOCKER_DIST:
        print("  3. uv run poe smoke-needs")
        print("  4. merge the release pull request, then from master:")
        print(f"  5. git tag {tag} && git push origin {tag}")
    else:
        print("  3. merge the release pull request, then from master:")
        print(f"  4. git tag {tag} && git push origin {tag}")
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
