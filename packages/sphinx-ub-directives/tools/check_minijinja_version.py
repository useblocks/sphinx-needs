"""Assert that the workspace's locked minijinja is the version the template corpus records.

The template corpus (``tests/fixtures/template_directives_conformance.toml``) records, in
its header, the minijinja version its expansions were recorded against, and ubCode's
runner records its own ``Cargo.lock`` version beside its vendored copy. A lock check alone
is not enough -- the two sides compile different FEATURES of one version -- so the dialect
cases are the feature check; this is the version half (contract §9.4).

Usage, from the repository root (standard library only, no environment needed)::

    python packages/sphinx-ub-directives/tools/check_minijinja_version.py

Exits 1, naming both versions, when they differ.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
LOCK = PACKAGE.parents[1] / "uv.lock"
CORPUS = PACKAGE / "tests" / "fixtures" / "template_directives_conformance.toml"


def recorded() -> str:
    """The minijinja version the corpus header records."""
    header = CORPUS.read_text(encoding="utf-8")
    match = re.search(r"^# minijinja:\s+(\d+\.\d+\.\d+)", header, re.MULTILINE)
    if match is None:
        msg = f"{CORPUS.name} records no minijinja version in its header"
        raise SystemExit(msg)
    return match[1]


def locked() -> set[str]:
    """Every minijinja version the workspace lock resolves (one, unless a split forks it)."""
    with LOCK.open("rb") as handle:
        lock = tomllib.load(handle)
    return {
        p["version"] for p in lock.get("package", []) if p.get("name") == "minijinja"
    }


def main() -> int:
    want, have = recorded(), locked()
    if have != {want}:
        print(
            f"::error file={LOCK}::uv.lock resolves minijinja {sorted(have)}, and "
            f"{CORPUS.name} was recorded against {want}: re-record the corpus (and tell "
            "ubCode, which vendors it) or move the lock back",
            file=sys.stderr,
        )
        return 1
    print(f"OK    minijinja {want}: the lock and the template corpus agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
