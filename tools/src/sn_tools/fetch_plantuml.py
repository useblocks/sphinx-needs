"""Fetch the one PlantUML jar this workspace renders with, at the version `pin.toml` names.

The repository used to carry two jars at two versions (10.1 MB for the test suite, 11.3 MB for
the docs) and a third, unpinned `releases/latest` download in the docker image. They were 71 %
of the sphinx-needs sdist, they could not be shared with a second package without a
cross-package path, and nothing said how old they were. `vendor/plantuml/pin.toml` replaces all
of that with two lines and a checksum; this script is what turns them into a file on disk.

It is deliberately **stdlib only** -- `urllib`, `hashlib`, `tomllib` -- because of where it
runs: a CI step before `uv sync` (so before any environment exists), a Read the Docs
`post_install` job, and a developer's `uv run poe fetch-plantuml`. Anything it imported would
have to be installed in all three.

Usage::

    uv run poe fetch-plantuml                                   # the task; what the docs say
    python tools/src/sn_tools/fetch_plantuml.py                 # by path, no environment needed
    python tools/src/sn_tools/fetch_plantuml.py --print-path    # where the jar would be
    python tools/src/sn_tools/fetch_plantuml.py --root /elsewhere

It prints **one line on stdout: the jar's path**, so a caller can use it directly --
`echo "PLANTUML_JAR=$(python tools/src/sn_tools/fetch_plantuml.py)" >> "$GITHUB_ENV"` is what
CI does. Everything else it has to say goes to stderr.

Three things about the contract are worth stating, because each of them is a decision:

* **`PLANTUML_JAR`, set and naming a file, short-circuits the whole thing.** It is the first
  step of the resolution order every consumer here applies (`PLANTUML_JAR` -> the pinned jar ->
  `plantuml` on `PATH`), so a caller who has already made the explicit choice must not be made
  to download 30 MB it will not use -- and the poe tasks declare this script as a dependency,
  so that would otherwise happen on every `poe test-needs` run of a machine that sets the
  variable.
* **A cached jar is re-hashed, not trusted.** ~0.03 s for 30 MB, against a corrupt or truncated
  jar failing somewhere inside a render minutes later. A cached jar whose hash does not match
  is re-fetched rather than refused: the likeliest cause is an interrupted download, and the
  pin is still the authority on what the file should be.
* **A checksum mismatch on a fresh download is a hard failure naming both hashes**, and the
  temp file is removed. That is the whole point of pinning: the alternative is rendering with
  bytes nobody chose.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

#: `<root>/vendor/plantuml/` -- the pin, this script's target directory, and the path every
#: consumer computes for itself (a `conf.py` cannot import from here; see the module docstring
#: of `packages/sphinx-needs/tests/conftest.py`).
VENDOR = ("vendor", "plantuml")

#: How a machine with no network still renders. Repeated in every failure message, because a
#: message that says only "the download failed" leaves the reader with no next move.
ALTERNATIVES = (
    "Alternatives that need no download: set PLANTUML_JAR to a plantuml jar you already "
    "have (with `java` on PATH), or install a `plantuml` executable "
    "(`apt install plantuml`, `brew install plantuml`, `choco install plantuml`)."
)


def default_root() -> Path:
    """The repository root, from this file's own location.

    `tools/src/sn_tools/fetch_plantuml.py` -> four parents up. The tooling is run by path
    rather than imported (`tools` is a virtual member), so `__file__` is always inside the
    checkout it is meant to act on.
    """
    return Path(__file__).resolve().parents[3]


class Pin:
    """`vendor/plantuml/pin.toml`, read."""

    def __init__(self, version: str, sha256: str, url: str) -> None:
        self.version = version
        self.sha256 = sha256
        self.url = url

    @classmethod
    def read(cls, root: Path) -> Pin:
        path = root.joinpath(*VENDOR, "pin.toml")
        if not path.is_file():
            raise SystemExit(f"no pin file at {path}")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        missing = [key for key in ("version", "sha256", "url") if key not in data]
        if missing:
            raise SystemExit(f"{path} is missing {', '.join(missing)}")
        version = str(data["version"])
        return cls(
            version, str(data["sha256"]), str(data["url"]).format(version=version)
        )

    def jar(self, root: Path) -> Path:
        """Where the pinned jar lives. The version is IN the filename, deliberately: the jar
        this replaces was called `plantuml.jar` and was four years old without anyone noticing.
        """
        return root.joinpath(*VENDOR, f"plantuml-{self.version}.jar")


def sha256_of(path: Path) -> str:
    """The file's hash, read in chunks -- the jar is ~30 MB and this runs on every task."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    """Stream `url` into `destination`. Raises `urllib.error.URLError` and friends."""
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def named_jar() -> Path | None:
    """`PLANTUML_JAR`, when it names a file.

    Empty is treated as unset -- that is how the variable arrives from a shell with
    `PLANTUML_JAR=` exported and from a workflow that computes the value with an expression,
    and both suites that read it agree. A value that names something which is not a file is
    NOT silently ignored here: it is reported, and the fetch goes ahead, so the mistake is
    visible without blocking the machine.
    """
    value = os.environ.get("PLANTUML_JAR")
    if not value:
        return None
    path = Path(value)
    if not path.is_file():
        print(
            f"note: PLANTUML_JAR names {value!r}, which is not a file; ignoring it",
            file=sys.stderr,
        )
        return None
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="the repository root (default: the one this script lives in)",
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="print where the pinned jar would be and exit, fetching nothing",
    )
    args = parser.parse_args(argv)
    root = (args.root or default_root()).resolve()
    pin = Pin.read(root)
    jar = pin.jar(root)

    if args.print_path:
        # the PIN's path, deliberately, and never PLANTUML_JAR's: this answers "where does
        # this workspace keep its jar", which is a question about the checkout
        print(jar)
        return 0

    if (named := named_jar()) is not None:
        print(
            f"note: PLANTUML_JAR names {named}; using it and fetching nothing",
            file=sys.stderr,
        )
        print(named)
        return 0

    if jar.is_file():
        found = sha256_of(jar)
        if found == pin.sha256:
            print(jar)
            return 0
        print(
            f"note: {jar} does not match the pin (found {found}); fetching it again",
            file=sys.stderr,
        )

    jar.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching PlantUML {pin.version} from {pin.url}", file=sys.stderr)
    # a temp file in the destination directory, so the move below is a rename on the same
    # filesystem and a half-written jar is never at the path consumers look in
    handle, name = tempfile.mkstemp(dir=jar.parent, prefix=".plantuml-", suffix=".part")
    os.close(handle)
    temporary = Path(name)
    try:
        download(pin.url, temporary)
    except (urllib.error.URLError, OSError) as error:
        temporary.unlink(missing_ok=True)
        print(f"error: could not fetch {pin.url}: {error}", file=sys.stderr)
        print(ALTERNATIVES, file=sys.stderr)
        return 1
    found = sha256_of(temporary)
    if found != pin.sha256:
        temporary.unlink(missing_ok=True)
        print(
            f"error: {pin.url} does not match the pin.\n"
            f"  expected {pin.sha256}\n"
            f"  got      {found}\n"
            "Either the pin is wrong or the download is. Nothing was written.",
            file=sys.stderr,
        )
        return 1
    temporary.replace(jar)
    jar.chmod(0o644)
    print(jar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
