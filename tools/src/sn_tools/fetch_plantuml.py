"""The bump tool for the workspace's one PlantUML jar, and the fence that keeps it honest.

`vendor/plantuml/pin.toml` names one version and one sha256, and
`vendor/plantuml/plantuml-<version>.jar` **is committed** beside it. This script has the two
jobs that arrangement leaves:

* **`--verify`** (no network, ever): the jar on disk is the one the pin names. It is what CI's
  Lint job and `uv run poe lint` run, so a pull request that edits `pin.toml` without
  committing the matching jar -- or commits a jar that is not what the pin claims -- goes red
  on a message that names both hashes, rather than on a rendering failure somewhere else.
* **the download**, for a bump: edit the two lines in `pin.toml`, run this, `git rm` the old
  jar and `git add` the new one. It is also the repair for a jar that a checkout mangled.

The repository used to carry two jars at two versions (10.1 MB for the test suite, 11.3 MB for
the docs) and a third, unpinned `releases/latest` download in the docker image. They were 71 %
of the sphinx-needs sdist, they could not be shared with a second package without a
cross-package path, and nothing said how old they were. The pin plus one shared jar replaces
all of that.

**A fetched design was built and reviewed on this same pull request first, and dropped.** In
it nothing was committed and every consumer downloaded the jar on demand. That makes rendering
depend on `release-assets.githubusercontent.com` (measured: what the release URL redirects to)
at 22 CI jobs per run, at every Read the Docs build, on every offline machine, and in every
sandboxed agent session whose network allowlist is set outside this repository and does not
include that host. A committed jar needs none of it.

It is deliberately **stdlib only** -- `urllib`, `hashlib`, `tomllib` -- because of where it
runs: a CI step before `uv sync` (so before any environment exists), and a developer's
`uv run poe verify-plantuml` / `uv run poe fetch-plantuml`. Anything it imported would have to
be installed in both.

Usage::

    uv run poe verify-plantuml                                  # the fence; no network
    uv run poe fetch-plantuml                                   # the bump step; downloads
    python tools/src/sn_tools/fetch_plantuml.py --verify        # by path, no environment
    python tools/src/sn_tools/fetch_plantuml.py --print-path    # where the jar lives
    python tools/src/sn_tools/fetch_plantuml.py --root /elsewhere

It prints **one line on stdout: the jar's path**, and everything else it has to say goes to
stderr, so a caller captures it directly. CI does, at every job that renders::

    jar="$(uv run --no-project python tools/src/sn_tools/fetch_plantuml.py --verify | tr -d '\r')"
    echo "PLANTUML_JAR=$jar" >> "$GITHUB_ENV"

under `shell: bash`; `vendor/plantuml/README.md` ("The step CI runs") says why each part of
that is load-bearing.

Three things about the contract are worth stating, because each of them is a decision:

* **`PLANTUML_JAR` is respected AND verified.** Set and naming a file, it short-circuits the
  whole thing: it is the first step of the resolution order every consumer here applies
  (`PLANTUML_JAR` -> the pinned jar -> `plantuml` on `PATH`), so a caller who has already made
  the explicit choice must not be made to download 30 MB it will not use -- and the poe tasks
  declare this script as a dependency, so that would otherwise happen on every `poe test-needs`
  run of a machine that sets the variable. Set and naming NO file, it is a hard failure here,
  with the same message the consumers give. This script used to say "ignoring it" and fetch
  anyway, on the theory that it left the machine able to run; measured, it does not -- every
  consumer (`tests/conftest.py`, `docs/conf.py`, `performance_test.py`) refuses the same value
  seconds later, so all the note bought was a pointless download and a log that says the value
  was ignored just above the failure that was caused by it.
* **The jar on disk is re-hashed, not trusted.** ~0.03 s for 30 MB, against a corrupt or
  truncated jar failing somewhere inside a render minutes later. Under `--verify` a mismatch
  is a hard failure -- that is the whole job -- while the default mode re-fetches it, because
  there the likeliest cause is an interrupted download and the pin is still the authority on
  what the file should be.
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
    and both suites that read it agree.

    A value that is set but names no file stops the run, with the message its consumers give.
    Falling through to the fetch would be worse than useless: `tests/conftest.py`,
    `docs/conf.py` and `performance_test.py` all raise on that same value, so the download
    would never be used, and the "ignoring it" note would sit in the log immediately above a
    failure caused by the thing it said was ignored. In CI, where this is run through
    `jar="$( … )"`, stopping here is one red step naming the variable instead of a green step
    followed by every rendering test erroring.
    """
    value = os.environ.get("PLANTUML_JAR")
    if not value:
        return None
    path = Path(value)
    if not path.is_file():
        raise SystemExit(
            f"error: PLANTUML_JAR names {value!r}, which is not a file. Point it at a "
            "plantuml jar (with `java` on PATH), or unset it to render with the pinned jar "
            "this fetches into vendor/plantuml/."
        )
    return path


def verify(pin: Pin, jar: Path) -> int:
    """`--verify`: the committed jar is the one the pin names. **Never touches the network.**

    This is the fence, and it is why the jar can be committed at all: CI's Lint job and
    `uv run poe lint` both run it, so a pull request that edits `pin.toml` and forgets the jar
    -- or commits a jar that is not what the pin claims -- is one red step naming both hashes
    rather than a rendering failure in some other job, or worse, a green run against bytes
    nobody chose.

    `PLANTUML_JAR` still wins, for the same reason it does everywhere else: an explicit choice
    is the first step of the resolution order every consumer applies, and a machine that has
    made it is not rendering with the committed jar at all, so the committed jar is not what
    decides whether that machine can run. A value naming no file still stops the run, in
    `named_jar()`, with the message its consumers give.
    """
    if (named := named_jar()) is not None:
        print(
            f"note: PLANTUML_JAR names {named}; the pinned jar is not what this run uses",
            file=sys.stderr,
        )
        print(named)
        return 0

    fix = (
        "Run `uv run poe fetch-plantuml` to download the pinned jar, then commit "
        f"vendor/plantuml/plantuml-{pin.version}.jar."
    )
    if not jar.is_file():
        print(
            f"error: {jar} does not exist.\n"
            f"  vendor/plantuml/pin.toml names PlantUML {pin.version}, sha256 {pin.sha256}\n"
            f"{fix}",
            file=sys.stderr,
        )
        return 1
    found = sha256_of(jar)
    if found != pin.sha256:
        print(
            f"error: {jar} is not what vendor/plantuml/pin.toml names.\n"
            f"  expected {pin.sha256}\n"
            f"  got      {found}\n"
            f"{fix}",
            file=sys.stderr,
        )
        return 1
    print(jar)
    return 0


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
        help="print where the pinned jar lives and exit, verifying nothing",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check the committed jar against the pin and print its path; never downloads",
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

    if args.verify:
        return verify(pin, jar)

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
    except urllib.error.HTTPError as error:
        # BEFORE `URLError`, which it subclasses. A 404 is not a connectivity problem and the
        # offline alternatives are not the answer to it: the network worked, and it said the
        # asset the pin names is not there. That is a mistake in `pin.toml` -- a version that
        # was never released, or a release whose asset is named differently (before ~v1.2025.0
        # only `plantuml-<version>.jar` exists, never a plain `plantuml.jar`) -- so the message
        # points at the pin. Any other status keeps the offline advice.
        temporary.unlink(missing_ok=True)
        if error.code == 404:
            print(
                f"error: {pin.url} does not exist (HTTP 404). The pin names an asset that is "
                "not there: check `version` and `url` in vendor/plantuml/pin.toml against "
                "https://github.com/plantuml/plantuml/releases.",
                file=sys.stderr,
            )
            return 1
        print(f"error: could not fetch {pin.url}: {error}", file=sys.stderr)
        print(ALTERNATIVES, file=sys.stderr)
        return 1
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
