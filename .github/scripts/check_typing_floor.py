"""Check that the type-checking floor environment is the floor it claims to be.

Run inside `.venvs/typing`, the environment the `typing` dependency group installs. Two
things can drift there, and both would leave ty checking against an API the floor does not
have, silently and green:

- the stubs and the library they describe: `types-docutils` must be the same series
  (`major.minor`) as the installed `docutils`. Dependabot cannot know the two are coupled,
  and once proposed moving the stubs three series ahead of the library.
- the floor and the matrix: the installed `docutils` must be the lowest series the
  installed `sphinx` accepts. When the oldest sphinx leaves the matrix, the `typing` group
  has to move with it; this is where forgetting that is caught.

Usage: python .github/scripts/check_typing_floor.py
"""

import sys
from importlib.metadata import PackageNotFoundError, requires, version

from packaging.requirements import Requirement
from packaging.version import Version


def series(text):
    parsed = Version(text)
    return f"{parsed.major}.{parsed.minor}"


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
        lower = [
            Version(spec.version)
            for spec in parsed.specifier
            if spec.operator in (">=", "==", "~=")
        ]
        return series(str(min(lower))) if lower else None
    return None


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

    floor = docutils_floor_of_sphinx()
    if floor is None:
        print(
            f"::error::sphinx {sphinx_version} declares no docutils requirement to read"
        )
        return 2
    if series(docutils_version) != floor:
        print(
            f"::error::sphinx {sphinx_version} accepts docutils from {floor}, but the "
            f"`typing` group installs docutils {docutils_version}: the floor moved, so "
            "move the group with it"
        )
        ok = False

    if ok:
        print(
            f"typing floor: sphinx {sphinx_version} (accepts docutils from {floor}), "
            f"docutils {docutils_version}, types-docutils {stubs_version}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print("usage: check_typing_floor.py (no arguments; run inside .venvs/typing)")
        sys.exit(2)
    sys.exit(check())
