"""Fetch and verify clang's builtin headers that sphinx-codelinks ships.

The libclang engine of sphinx-codelinks passes clang's builtin headers (``stddef.h``,
``stdint.h``, ``limits.h``, ``stdatomic.h`` ...) to every parse as ``-resource-dir``,
because the ``libclang`` wheel carries none (see the package's
``analyse/preproc/builtin_headers.py``). The 30 portable ones are committed under
``packages/sphinx-codelinks/src/sphinx_codelinks/analyse/preproc/clang_resource/``:
``include/*.h``, the LLVM licence as ``LICENSE.TXT``, and ``manifest.toml``, which names
the LLVM tag they were taken from and the sha256 of every file. This script has the two
jobs that arrangement leaves:

* **``--verify``** (no network): the files on disk are exactly the ones the manifest names,
  byte for byte, and no other header is there. The package's own suite asserts the same
  (``tests/test_builtin_headers.py``), so a hand-edited header is red there too.
* **the download**, for a bump with the ``libclang`` pin: run it with ``--tag`` naming the
  new LLVM release tag (``llvmorg-<version>``); it fetches the same file names from
  ``clang/lib/Headers/`` and ``clang/LICENSE.TXT`` at that tag on GitHub and rewrites the
  files and the manifest. Review the diff, then run the codelinks suite.

Stdlib only, run by path::

    python tools/src/sn_tools/clang_headers.py --verify
    python tools/src/sn_tools/clang_headers.py --tag llvmorg-18.1.1
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
import urllib.request
from pathlib import Path

#: The directory, relative to the repository root.
RESOURCE = (
    "packages",
    "sphinx-codelinks",
    "src",
    "sphinx_codelinks",
    "analyse",
    "preproc",
    "clang_resource",
)

#: Where a file of an LLVM tag is served from.
SOURCE = "https://raw.githubusercontent.com/llvm/llvm-project/{tag}/{path}"

LICENSE = "LICENSE.TXT"
"""The licence's name here; it is ``clang/LICENSE.TXT`` in the LLVM tree."""


def default_root() -> Path:
    """The repository root: ``tools/src/sn_tools/`` is three levels below it."""
    return Path(__file__).resolve().parents[3]


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(directory: Path) -> tuple[str, str, dict[str, str]]:
    """The manifest's LLVM tag, the licence's sha256 and each header's sha256."""
    data = tomllib.loads((directory / "manifest.toml").read_text(encoding="utf-8"))
    return str(data["llvm_tag"]), str(data["license_sha256"]), dict(data["headers"])


def render_manifest(tag: str, license_sha: str, headers: dict[str, str]) -> str:
    lines = [
        "# clang's portable builtin headers, as libclang's -resource-dir: see",
        "# tools/src/sn_tools/clang_headers.py, which writes this file and verifies",
        "# the files against it. Each sha256 is of the file's bytes at `llvm_tag`.",
        f'llvm_tag = "{tag}"',
        f'license_sha256 = "{license_sha}"',
        "",
        "[headers]",
        *(f'"{name}" = "{headers[name]}"' for name in sorted(headers)),
        "",
    ]
    return "\n".join(lines)


def verify(directory: Path) -> list[str]:
    """Every way the files on disk differ from the manifest; empty when they agree."""
    _tag, license_sha, headers = read_manifest(directory)
    problems = []
    license_path = directory / LICENSE
    if not license_path.is_file():
        problems.append(f"{LICENSE} is missing")
    elif sha256_of(license_path.read_bytes()) != license_sha:
        problems.append(f"{LICENSE} does not match the manifest")
    include = directory / "include"
    on_disk = {p.name for p in include.iterdir()} if include.is_dir() else set()
    for name in sorted(set(headers) - on_disk):
        problems.append(f"include/{name} is missing")
    for name in sorted(on_disk - set(headers)):
        problems.append(f"include/{name} is not in the manifest")
    for name in sorted(set(headers) & on_disk):
        actual = sha256_of((include / name).read_bytes())
        if actual != headers[name]:
            problems.append(
                f"include/{name}: sha256 {actual}, the manifest says {headers[name]}"
            )
    return problems


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return bytes(response.read())


def download(directory: Path, tag: str) -> None:
    """Fetch the manifest's header names and the licence at ``tag``; rewrite all."""
    _old_tag, _license_sha, old_headers = read_manifest(directory)
    license_bytes = fetch(SOURCE.format(tag=tag, path="clang/LICENSE.TXT"))
    contents = {
        name: fetch(SOURCE.format(tag=tag, path=f"clang/lib/Headers/{name}"))
        for name in sorted(old_headers)
    }
    (directory / LICENSE).write_bytes(license_bytes)
    for name, data in contents.items():
        (directory / "include" / name).write_bytes(data)
    (directory / "manifest.toml").write_text(
        render_manifest(
            tag,
            sha256_of(license_bytes),
            {name: sha256_of(data) for name, data in contents.items()},
        ),
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true", help="check, no network")
    mode.add_argument("--tag", help="download the headers of this LLVM tag")
    parser.add_argument("--root", type=Path, default=None, help="repository root")
    args = parser.parse_args(argv)
    directory = (args.root or default_root()).joinpath(*RESOURCE)
    if args.tag:
        download(directory, args.tag)
    problems = verify(directory)
    for problem in problems:
        print(f"clang_headers: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
