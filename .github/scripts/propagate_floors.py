"""Rewrite every dependant's floor on a workspace member to that member's current version.

The workspace's tracking policy is that an intra-workspace runtime dependency is always
declared `X>=<X's current version>,<<X's next major>`: extensions carry no
backwards-compatibility code, so the floor is a claim about what was actually tested, and
the major cap is what stops a future incompatible X being co-installed with a dependant
written against the old one. Keeping that true by hand is exactly the kind of bookkeeping
that rots -- and uv will never notice, because it resolves the workspace copy whatever the
specifier says (uv#9811), and the specifier is not in `uv.lock` at all.

So it is mechanical. Run it in the release **pull request**, right after
`uv version --package X --bump ...`, and never in the release job: the job runs *after* the
tag, so a rewrite there would not be in the tagged commit and the published wheel would
disagree with the tree the tag names. `.github/scripts/check_workspace.py` in Lint is what
fails if somebody forgets.

tomlkit rather than tomllib plus text munging because it round-trips comments and
formatting: the diff is one line per dependant and nothing else.

Usage::

    python .github/scripts/propagate_floors.py sphinx-variants           # the tree's version
    python .github/scripts/propagate_floors.py sphinx-variants --version 2.0.0
    python .github/scripts/propagate_floors.py sphinx-variants --check   # report, write nothing

Run at the workspace root. Needs `tomlkit` and `packaging` (both in the root `dev` group;
in CI, `uv run --no-project --with tomlkit --with packaging python ...`). Afterwards run
`uv lock` -- usually a no-op, which is precisely why this cannot be delegated to the lock.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

import tomlkit
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def member_paths(root: Path) -> list[Path]:
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return [
        path
        for pattern in manifest["tool"]["uv"]["workspace"]["members"]
        for path in sorted(root.glob(f"{pattern}/pyproject.toml"))
    ]


def rewrite(specs: Any, target: str, wanted: str) -> int:
    """Rewrite in place every requirement naming `target`; return how many changed."""
    changed = 0
    for index, spec in enumerate(specs):
        requirement = Requirement(spec)
        if canonicalize_name(requirement.name) != target:
            continue
        marker = f" ; {requirement.marker}" if requirement.marker else ""
        extras = (
            f"[{','.join(sorted(requirement.extras))}]" if requirement.extras else ""
        )
        new = f"{requirement.name}{extras}{wanted}{marker}"
        if new != spec:
            specs[index] = new
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Propagate a workspace member's version into its dependants' floors.",
    )
    parser.add_argument("dist", help="the member whose floor is propagated")
    parser.add_argument("--version", help="default: the version in the tree")
    parser.add_argument(
        "--check", action="store_true", help="report only, write nothing"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="the workspace root (default: the working directory)",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    paths = member_paths(root)
    target = canonicalize_name(args.dist)

    version: str | None = args.version
    if version is None:
        for path in paths:
            data = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
            if canonicalize_name(data["name"]) == target:
                version = data.get("version")
        if version is None:
            print(
                f"::error::{args.dist} is not a member of this workspace (or declares no "
                "static version); pass --version to say which floor to write"
            )
            return 2
    wanted = f">={version},<{Version(version).major + 1}"

    touched = 0
    for path in paths:
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        # tomlkit's items are dynamically typed containers that behave like dicts and
        # lists; the point of using it is that the objects handed back are the ones
        # written out again, comments and all
        project: Any = document["project"]
        if canonicalize_name(project["name"]) == target:
            continue
        changed = rewrite(project.get("dependencies", []), target, wanted)
        for specs in project.get("optional-dependencies", {}).values():
            changed += rewrite(specs, target, wanted)
        if not changed:
            continue
        touched += 1
        print(
            f"{'would rewrite' if args.check else 'rewrote'} {changed} specifier(s) in "
            f"{path.relative_to(root)} -> {args.dist}{wanted}"
        )
        if not args.check:
            path.write_text(tomlkit.dumps(document), encoding="utf-8")

    if not touched:
        print(f"no member declares {args.dist}; nothing to propagate")
    elif not args.check:
        print("now run `uv lock` and commit both")
    return 1 if (args.check and touched) else 0


if __name__ == "__main__":
    sys.exit(main())
