"""Assert the five facts that hold this uv workspace together, from the manifests alone.

Each of these is a pair of statements in two different files that must agree, and each has
a failure mode that no other gate in this repository can see:

1. **the root lists every member, bare.** The root is a non-packaged project whose only
   `[project] dependencies` job is to make a plain `uv sync` install every member; a member
   missing from it silently drops out of the default environment (and of the lock's
   `sphinx-needs-workspace` entry), and a *non*-member listed there is resolved from PyPI.
2. **every member has a `[tool.uv.sources] <name> = { workspace = true }` entry.**
3. **every member's `requires-python` equals the root's.** uv resolves ONE lock against the
   root, so a member that floored itself higher (or failed to move when the root did) still
   locks, builds and publishes; the mismatch surfaces only as an install failure for a user
   on the interpreter in the gap.
4. **every intra-workspace runtime specifier is honest, and tight.** uv never validates the
   specifier of a dependency it resolves through `workspace = true` (uv#9811): the copy on
   disk is used whatever the specifier says, so `uv lock`, `uv sync`, the suite and
   `uv build` all stay green while the *published* wheel carries a `Requires-Dist` nobody
   can satisfy. Worse, the specifier is not in `uv.lock` at all -- changing it gives a
   zero-line lock diff and `uv lock --check` still exits 0 -- so no amount of `--frozen`
   and no review of the lock can ever see it. "Tight" is the workspace's tracking policy:
   `>=<the dependency's current version>,<<its next major>`. Extensions carry no
   backwards-compatibility code, so the floor is a claim about what was actually tested,
   and the cap is what stops a future major being co-installed with a dependant written
   against the old one. `--no-policy` keeps only the honesty half.
5. **`__version__` equals `[project] version`.** sphinx-needs writes `__version__` into
   every generated `needs.json`, a documented interchange format, so it cannot become an
   `importlib.metadata` lookup; the number is therefore written twice and this is what
   keeps the two equal. A module with no `__version__` is skipped, not an error.

Every failure is reported before the script exits, each on its own `::error file=...::`
line, so one run names every mistake rather than the first one.

Usage::

    python .github/scripts/check_workspace.py [--no-policy]

Run at the workspace root. Needs `packaging` and nothing else, and it reads only manifests
and source text -- deliberately: a check on the manifests must not depend on an environment
built from those manifests, or a manifest mistake is reported as "sync failed" instead of
being named. In CI it runs as
`uv run --no-project --with packaging python .github/scripts/check_workspace.py`, which
needs no `uv sync` at all.
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

ROOT_MANIFEST = "pyproject.toml"


class Report:
    """Collects failures so that one run names every mistake, not just the first."""

    def __init__(self) -> None:
        self.failures = 0

    def error(self, path: str, message: str) -> None:
        print(f"::error file={path}::{message}")
        self.failures += 1

    def ok(self, message: str) -> None:
        print(f"OK    {message}")


class Member:
    """One workspace member, as its manifest declares it."""

    def __init__(self, root: Path, manifest: Path, data: dict[str, Any]) -> None:
        self.manifest = manifest
        self.path = manifest.parent
        self.relative = manifest.relative_to(root).as_posix()
        self.data = data
        self.project: dict[str, Any] = data.get("project", {})
        self.name: str = self.project["name"]
        self.key = canonicalize_name(self.name)
        self.dynamic: list[str] = list(self.project.get("dynamic", []))

    @property
    def version(self) -> Version | None:
        """The declared version, or None if it is dynamic or unparseable."""
        raw = self.project.get("version")
        if not isinstance(raw, str):
            return None
        try:
            return Version(raw)
        except InvalidVersion:
            return None

    @property
    def module(self) -> str:
        """The top-level module name: `[tool.flit.module] name`, else the dist name."""
        flit = self.data.get("tool", {}).get("flit", {}).get("module", {})
        name = flit.get("name")
        return name if isinstance(name, str) else self.name.replace("-", "_")

    def requirements(self) -> list[tuple[str | None, str]]:
        """Every runtime requirement, with the extra it came from (None = unconditional)."""
        out: list[tuple[str | None, str]] = [
            (None, spec) for spec in self.project.get("dependencies", [])
        ]
        for extra, specs in self.project.get("optional-dependencies", {}).items():
            out.extend((extra, spec) for spec in specs)
        return out


class ManifestError(RuntimeError):
    """A manifest that cannot even be parsed. Reported, never raised at the reader."""


def load(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path}: not valid TOML -- {exc}") from exc


def find_members(root: Path, manifest: dict[str, Any], report: Report) -> list[Member]:
    globs = (
        manifest.get("tool", {}).get("uv", {}).get("workspace", {}).get("members") or []
    )
    if not globs:
        report.error(
            ROOT_MANIFEST, "no [tool.uv.workspace] members in the root manifest"
        )
        return []
    found: list[Member] = []
    for pattern in globs:
        for path in sorted(root.glob(f"{pattern}/pyproject.toml")):
            relative = path.relative_to(root).as_posix()
            try:
                data = load(path)
            except ManifestError as exc:
                report.error(relative, str(exc))
                continue
            if "project" not in data:
                report.error(relative, "no [project] table -- is this a package?")
                continue
            found.append(Member(root, path, data))
    if not found:
        report.error(
            ROOT_MANIFEST,
            f"[tool.uv.workspace] members {globs} matches no package in this tree",
        )
    return found


def check_root_lists_members(
    manifest: dict[str, Any], members: list[Member], report: Report
) -> None:
    """(1) the root depends on every member, bare, and on nothing else."""
    declared: dict[str, str] = {}
    for spec in manifest.get("project", {}).get("dependencies", []):
        try:
            requirement = Requirement(spec)
        except InvalidRequirement as exc:
            report.error(ROOT_MANIFEST, f"cannot parse root dependency `{spec}`: {exc}")
            continue
        declared[canonicalize_name(requirement.name)] = spec
        if requirement.specifier or requirement.extras or requirement.marker:
            report.error(
                ROOT_MANIFEST,
                f"the root dependency `{spec}` is not bare. The root is never built or "
                "published, so a version specifier, an extra or a marker here constrains "
                "nothing a user ever sees -- it only risks disagreeing with the member's "
                f"own metadata. Write `{requirement.name}`",
            )
    known = {member.key for member in members}
    for missing in sorted(known - set(declared)):
        report.error(
            ROOT_MANIFEST,
            f"`{missing}` is a workspace member but is not in the root's [project] "
            "dependencies, so a bare `uv sync` does not install it and nothing in the "
            "default environment can import it. Add it (bare)",
        )
    for extra in sorted(set(declared) - known):
        report.error(
            ROOT_MANIFEST,
            f"the root depends on `{declared[extra]}`, which is not a workspace member, so "
            "it is resolved from PyPI. The root's [project] dependencies list exists only "
            "to install the members; shared tooling belongs in a [dependency-groups] group",
        )
    if not (known - set(declared)) and not (set(declared) - known):
        report.ok(
            f"the root lists every member, bare: {', '.join(sorted(known)) or '-'}"
        )


def check_workspace_sources(
    manifest: dict[str, Any], members: list[Member], report: Report
) -> None:
    """(2) every member has a `= { workspace = true }` source entry at the root."""
    sources = manifest.get("tool", {}).get("uv", {}).get("sources", {})
    good = 0
    for member in sorted(members, key=lambda m: m.key):
        entry = sources.get(member.name, sources.get(member.key))
        if entry == {"workspace": True}:
            good += 1
            continue
        if entry is None:
            report.error(
                ROOT_MANIFEST,
                f"`{member.name}` is a workspace member with no [tool.uv.sources] entry. "
                "uv 0.12.9 refuses to resolve at all in this state -- `uv lock` exits 1 "
                f'with "`{member.name}` is included as a workspace member, but is missing '
                'an entry in `tool.uv.sources`" -- so this line only says it earlier, and '
                f"names the file. Add `{member.name} = {{ workspace = true }}`",
            )
            continue
        else:
            report.error(
                ROOT_MANIFEST,
                f"[tool.uv.sources] {member.name} = {entry} does not resolve the member "
                "in this tree; a member is always `{ workspace = true }`, or the workspace "
                "silently tests something other than the code in this repository",
            )
            continue
    if members and good == len(members):
        report.ok("every member is sourced from the workspace")


def check_requires_python(
    manifest: dict[str, Any], members: list[Member], report: Report
) -> None:
    """(3) every member's requires-python equals the root's."""
    root_value = manifest.get("project", {}).get("requires-python")
    if not root_value:
        report.error(ROOT_MANIFEST, "the root declares no requires-python")
        return
    for member in sorted(members, key=lambda m: m.key):
        got = member.project.get("requires-python")
        if got == root_value:
            report.ok(f"{member.relative}: requires-python {got}")
        else:
            report.error(
                member.relative,
                f"requires-python is {got}, but the root declares {root_value}. uv "
                "resolves ONE lock against the root, so a member out of step with it still "
                "locks, builds and publishes, and the gap only shows up as an install "
                "failure for a user on an interpreter in it",
            )


def check_specifiers(members: list[Member], policy: bool, report: Report) -> None:
    """(4) intra-workspace runtime specifiers are honest, and tight."""
    versions: dict[str, Version] = {}
    for member in members:
        if "version" in member.dynamic:
            report.error(
                member.relative,
                f"{member.name} declares a dynamic version. The release pipeline reads the "
                "version from the manifest -- `uv version --package` refuses a dynamic one, "
                "and the workflow's tag/version agreement check cannot run the build "
                'backend -- so it has to be `version = "..."` in [project]',
            )
            continue
        version = member.version
        if version is None:
            report.error(
                member.relative,
                f"{member.name} has no parseable [project] version "
                f"({member.project.get('version')!r})",
            )
            continue
        versions[member.key] = version

    edges = 0
    for member in sorted(members, key=lambda m: m.key):
        for extra, spec in member.requirements():
            try:
                requirement = Requirement(spec)
            except InvalidRequirement as exc:
                report.error(member.relative, f"cannot parse `{spec}`: {exc}")
                continue
            target = canonicalize_name(requirement.name)
            if target not in versions or target == member.key:
                continue
            edges += 1
            where = f"{member.name}{f'[{extra}]' if extra else ''} -> {requirement}"
            current = versions[target]
            # prereleases=True so a member sitting on a release candidate is not reported
            # as un-admitted by a floor that names that very candidate
            if not requirement.specifier.contains(current, prereleases=True):
                report.error(
                    member.relative,
                    f"{where}: the workspace builds {target} {current}, which this "
                    "specifier does not admit -- uv resolves the workspace copy regardless "
                    "(uv#9811), so this would publish a wheel nobody can install",
                )
                continue
            if policy:
                want = SpecifierSet(f">={current},<{current.major + 1}")
                if set(requirement.specifier) != set(want):
                    report.error(
                        member.relative,
                        f"{where}: tight tracking wants `{target}{want}` (the floor is "
                        f"{target}'s current version and the cap is its next major); run "
                        f"`python .github/scripts/propagate_floors.py {target}`",
                    )
                    continue
            report.ok(f"{where}  (workspace {target} {current})")
    if not edges:
        report.ok(
            f"no intra-workspace runtime dependencies among {len(members)} member(s): "
            + (", ".join(f"{k} {v}" for k, v in sorted(versions.items())) or "-")
        )


def module_version(member: Member) -> tuple[Path, str] | None:
    """`__version__` as a literal in the member's top-level module, if it has one.

    Read with `ast`, not by importing: this script runs with nothing installed but
    `packaging`, and importing a package to read its version is exactly the failure mode
    the literal exists to avoid.
    """
    for candidate in (
        member.path / "src" / member.module / "__init__.py",
        member.path / member.module / "__init__.py",
    ):
        if not candidate.is_file():
            continue
        tree = ast.parse(candidate.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            else:
                continue
            if "__version__" not in names:
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return candidate, value.value
        return None
    return None


def check_module_version(members: list[Member], report: Report) -> None:
    """(5) `__version__` in the module equals `[project] version`."""
    for member in sorted(members, key=lambda m: m.key):
        declared = member.project.get("version")
        if "version" in member.dynamic or not isinstance(declared, str):
            continue  # already reported by check (4)
        found = module_version(member)
        if found is None:
            continue  # a module without a `__version__` literal is not an error
        path, literal = found
        where = path.relative_to(member.path.parent.parent).as_posix()
        if literal == declared:
            report.ok(f"{where}: __version__ == {declared}")
        else:
            report.error(
                where,
                f'__version__ = "{literal}", but {member.relative} declares '
                f'version = "{declared}". The two are written separately (the literal is '
                "stamped into generated artefacts, so it cannot be an `importlib.metadata` "
                "lookup) and the release bump has to move both",
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the workspace's manifests agree with each other.",
    )
    parser.add_argument(
        "--no-policy",
        action="store_true",
        help="check only that intra-workspace specifiers admit the tree's versions, "
        "not that they have the tight-tracking shape",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="the workspace root (default: the working directory)",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    report = Report()
    manifest_path = root / ROOT_MANIFEST
    if not manifest_path.is_file():
        print(f"::error::no {ROOT_MANIFEST} in {root}; run this at the workspace root")
        return 2
    try:
        manifest = load(manifest_path)
    except ManifestError as exc:
        print(f"::error file={ROOT_MANIFEST}::{exc}")
        return 2

    members = find_members(root, manifest, report)
    check_root_lists_members(manifest, members, report)
    check_workspace_sources(manifest, members, report)
    check_requires_python(manifest, members, report)
    check_specifiers(members, not args.no_policy, report)
    check_module_version(members, report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
