"""Check that the type-checking floor environment is the floor it claims to be.

Run inside `.venvs/typing`, the environment the `typing` dependency group installs. Two
things can drift there, and both would leave ty checking against an API the floor does not
have, silently and green:

- the stubs and the library they describe: `types-docutils` must be the same series
  (`major.minor`) as the installed `docutils`. Dependabot cannot know the two are coupled,
  and once proposed moving the stubs three series ahead of the library.
- the floor and the workspace: the installed `docutils` must be the WORKSPACE's docutils
  floor -- the highest of the floor the installed `sphinx` declares and the floor every
  installed workspace member declares (in `dependencies` or in any extra). When the oldest
  sphinx leaves the matrix, or a member raises its floor, the `typing` group has to move
  with it; this is where forgetting that is caught. The members are the ones the root
  `pyproject.toml` lists under `[tool.uv.workspace] members`, and their floors are read from
  the installed metadata, as sphinx's is. A member declaring no docutils at all is not this
  script's business: `tools/src/sn_tools/check_workspace.py` check (8) refuses that, and a
  declared floor in another series than the `typing` group's, from the manifests alone.

Usage: python .github/scripts/check_typing_floor.py
"""

import sys
import tomllib
from importlib.metadata import PackageNotFoundError, metadata, requires, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


def series(text):
    parsed = Version(text)
    return f"{parsed.major}.{parsed.minor}"


ROOT = Path(__file__).resolve().parents[2]


def lower_bound(parsed):
    """The floor one requirement declares, or None if it declares none."""
    lower = [
        Version(spec.version)
        for spec in parsed.specifier
        if spec.operator in (">=", "==", "~=")
    ]
    return max(lower) if lower else None


def docutils_floor_of_sphinx():
    """The lowest docutils series the installed sphinx accepts, or None if not declared."""
    for requirement in requires("sphinx") or []:
        parsed = Requirement(requirement)
        if parsed.name.lower() != "docutils":
            continue
        # sphinx declares docutils unconditionally; skip an extra-only declaration if
        # one ever appears, since the floor environment installs no sphinx extras
        if parsed.marker is not None and not parsed.marker.evaluate({"extra": ""}):
            continue
        floor = lower_bound(parsed)
        return series(str(floor)) if floor else None
    return None


def workspace_members():
    """Every member's distribution name, from the root manifest's workspace globs."""
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    globs = manifest.get("tool", {}).get("uv", {}).get("workspace", {}).get("members")
    names = []
    for pattern in globs or []:
        for path in sorted(ROOT.glob(f"{pattern}/pyproject.toml")):
            project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
            if "name" in project and project["name"] not in names:
                names.append(project["name"])
    return names


def docutils_floors_of_members():
    """(declaration, series) for each docutils floor an installed member declares.

    Extras count: a floor a member declares in an extra is still a floor it promises its
    users, and the `typing` group type-checks that code too.
    """
    floors = []
    for name in workspace_members():
        try:
            declared = requires(name) or []
            extras = [""] + (metadata(name).get_all("Provides-Extra") or [])
        except PackageNotFoundError:
            continue  # not installed here (the testkit, the virtual tooling member)
        for requirement in declared:
            parsed = Requirement(requirement)
            if parsed.name.lower() != "docutils":
                continue
            matched = [
                extra
                for extra in extras
                if parsed.marker is None or parsed.marker.evaluate({"extra": extra})
            ]
            if not matched:
                continue
            floor = lower_bound(parsed)
            if floor is None:
                continue  # a floorless declaration is check_workspace.py's to refuse
            where = name if "" in matched else f"{name}[{matched[0]}]"
            floors.append((f"{where}: docutils{parsed.specifier}", series(str(floor))))
    return floors


def check():
    try:
        docutils_version = version("docutils")
        stubs_version = version("types-docutils")
        sphinx_version = version("sphinx")
    except PackageNotFoundError as exc:
        print(
            f"::error::{exc.name} is not installed here; this check runs inside "
            "`.venvs/typing`, which `uv run poe typecheck` creates"
        )
        return 2

    ok = True
    if series(stubs_version) != series(docutils_version):
        print(
            f"::error::types-docutils {stubs_version} describes docutils "
            f"{series(stubs_version)}, but docutils {docutils_version} is installed: "
            "move both entries of the `typing` group together"
        )
        ok = False

    sphinx_floor = docutils_floor_of_sphinx()
    if sphinx_floor is None:
        print(
            f"::error::sphinx {sphinx_version} declares no docutils requirement to read"
        )
        return 2
    declarations = [
        (
            f"sphinx {sphinx_version} (accepts docutils from {sphinx_floor})",
            sphinx_floor,
        ),
        *docutils_floors_of_members(),
    ]
    floor = max((floor for _, floor in declarations), key=Version)
    set_by = ", ".join(where for where, got in declarations if got == floor)
    if series(docutils_version) != floor:
        print(
            f"::error::the workspace's docutils floor is {floor}, set by {set_by}; but "
            f"the `typing` group installs docutils {docutils_version}: the floor moved, "
            "so move the group's docutils and types-docutils entries with it"
        )
        ok = False

    if ok:
        print(
            f"typing floor: docutils {floor}, set by {set_by}; installed docutils "
            f"{docutils_version}, types-docutils {stubs_version}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print("usage: check_typing_floor.py (no arguments; run inside .venvs/typing)")
        sys.exit(2)
    sys.exit(check())
