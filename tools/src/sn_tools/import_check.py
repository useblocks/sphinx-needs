#!/usr/bin/env python3
"""Import every module of a member's built wheel against its dependencies AS PUBLISHED.

The question this answers is "does `sphinx-codelinks` still import against the
`sphinx-needs` that is actually on PyPI?", and today the only thing that answers it is the
release workflow's compat cell -- which answers it by running the whole suite, six minutes
into a release job that has already built and gated the wheel. A missing symbol does not
need six minutes; it needs one import.

**`--no-sources` is the whole trick.** Installing the wheel with it makes uv resolve every
intra-workspace dependency from the index instead of substituting the checkout, so the
scratch environment holds this member as built and its siblings exactly as released. Then
importing every module of the member is a complete answer to "is any name it uses missing
from what is published". It is not a complete answer to "does it still work" -- a behaviour
change imports perfectly -- and the compat cell stays the guard for that.

Two layers, one file:

* **outer** (`import_check.py <dist>`): build the wheel with character-for-character the
  release command, make a throwaway environment, install the wheel into it with
  `--no-sources`, and run the inner layer with that environment's interpreter;
* **inner** (`import_check.py --walk <module> [--expect-prefix <dir>]`): import the module
  and every submodule `pkgutil` can find, reporting all failures rather than the first.

They live in one file so the outer can invoke the inner by path with a different
interpreter, and the inner is **stdlib only** -- it runs under the scratch interpreter,
which has the wheel's dependencies and nothing else. `--expect-prefix` is what makes the
walk mean anything: without it the interpreter could be importing the checkout one
directory up, and every module would import beautifully. It is the assertion
`scripts/smoke_needs.py` makes, and the one the release workflow's compat cell used to make
inline with `python -c`; the compat cell now runs this walk instead, so a red release job
names the missing symbol before the suite starts.

Usage::

    python tools/src/sn_tools/import_check.py sphinx-needs        # or: uv run poe import-check-needs
    python tools/src/sn_tools/import_check.py sphinx-needs --keep
    python tools/src/sn_tools/import_check.py --walk sphinx_needs --expect-prefix /tmp/compat

Run at the workspace root. The outer layer needs `uv`; the inner needs nothing.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import traceback
from pathlib import Path
from typing import Any

# tools/src/sn_tools/import_check.py -> tools/src/sn_tools -> tools/src -> tools -> root
REPO_ROOT = Path(__file__).resolve().parents[3]


class CheckError(RuntimeError):
    """A step of the outer layer that cannot be recovered from."""


# --- the inner layer: stdlib only, runs under the scratch interpreter ---------------------


def innermost(exc: BaseException) -> str:
    """The last frame of the traceback -- the line that actually failed."""
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return "(no traceback)"
    frame = frames[-1]
    where = f"{frame.filename}:{frame.lineno} in {frame.name}"
    return f"{where}: {frame.line.strip()}" if frame.line else where


def walk(module: str, expect_prefix: str | None) -> int:
    """Import `module` and every submodule under it, reporting every failure.

    Deliberately not fail-fast: the reader wants every missing symbol at once, because the
    next run costs another wheel build and another environment. Only `Exception` is caught
    -- a `KeyboardInterrupt` or a `SystemExit` raised by a module at import time must still
    stop the walk rather than be filed as one module's problem.
    """
    started = time.monotonic()
    try:
        top = importlib.import_module(module)
    except Exception as exc:
        print(f"FAIL  {module}: {type(exc).__name__}: {exc}")
        print(f"        {innermost(exc)}")
        return 1

    location = getattr(top, "__file__", None)
    if expect_prefix is not None:
        prefix = Path(expect_prefix).resolve()
        if location is None:
            print(
                f"FAIL  {module} has no __file__, so it cannot be shown to come from {prefix}"
            )
            return 1
        if not Path(location).resolve().is_relative_to(prefix):
            print(
                f"FAIL  {module} was imported from {location}, which is not under {prefix}"
            )
            print(
                "        the walk is meant to test the installed wheel; this is another copy"
            )
            return 1
        print(f"      {module} imported from {location}")

    names = [module]
    unwalkable: list[str] = []
    for info in pkgutil.walk_packages(
        getattr(top, "__path__", []), prefix=f"{module}.", onerror=unwalkable.append
    ):
        names.append(info.name)

    failures: list[tuple[str, str, str]] = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}", innermost(exc)))
    elapsed = time.monotonic() - started

    for name, summary, frame in failures:
        print(f"FAIL  {name}: {summary}")
        print(f"        {frame}")
    for name in unwalkable:
        print(f"      {name} did not import, so anything under it was never walked")
    if failures:
        print(
            f"FAIL  {len(failures)} of {len(names)} modules failed to import in "
            f"{elapsed:.1f}s ({len(names) - len(failures)} imported)"
        )
        return 1
    print(f"OK    {len(names)} modules imported in {elapsed:.1f}s")
    return 0


# --- the outer layer: build the wheel, install it from the index, run the inner -----------


def canonical(name: str) -> str:
    """PEP 503 name normalisation.

    Not `packaging.utils.canonicalize_name`, because this file is one file: the inner layer
    above runs under an interpreter that has only the wheel's dependencies, and a top-level
    import of `packaging` would break it there.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def module_name(manifest: dict[str, Any], dist: str) -> str:
    """The top-level module: `[tool.flit.module] name`, else the dist name, `-` -> `_`.

    Three lines duplicated from `check_workspace.Member.module` on purpose. These scripts
    are run BY PATH and never imported, so an `import check_workspace` here and the tests'
    `sn_tools.check_workspace` would be two module objects for one file. Keep the two rules
    in step; the release workflow's compat cell carries the same rule a third time.
    """
    name = manifest.get("tool", {}).get("flit", {}).get("module", {}).get("name")
    return name if isinstance(name, str) else dist.replace("-", "_")


def find_member(dist: str) -> tuple[Path, dict[str, Any]]:
    """The directory and manifest of the workspace member named `dist`."""
    root = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    globs = root["tool"]["uv"]["workspace"]["members"]
    wanted = canonical(dist)
    known: list[str] = []
    for pattern in globs:
        for path in sorted(REPO_ROOT.glob(f"{pattern}/pyproject.toml")):
            manifest = tomllib.loads(path.read_text(encoding="utf-8"))
            name = manifest.get("project", {}).get("name")
            if not isinstance(name, str):
                continue
            known.append(name)
            if canonical(name) != wanted:
                continue
            if manifest.get("tool", {}).get("uv", {}).get("package") is False:
                raise CheckError(
                    f"`{name}` is a virtual member (`[tool.uv] package = false`): this "
                    "repository never publishes it, `uv build --package` is refused for "
                    "it, and there is no released wheel for anything to import"
                )
            return path.parent, manifest
    raise CheckError(
        f"`{dist}` is not a member of this workspace "
        f"(known: {', '.join(sorted(known)) or 'none'})"
    )


def run(cmd: list[str | Path], **kwargs: Any) -> None:
    """Run a command, echoing it first (`scripts/smoke_needs.py`'s style), and raise if it
    fails. Output is inherited rather than captured: a `uv build` or a resolution failure is
    the answer the reader came for."""
    print("$", " ".join(str(part) for part in cmd), flush=True)
    proc = subprocess.run([str(part) for part in cmd], **kwargs)
    if proc.returncode != 0:
        raise CheckError(f"`{cmd[0]}` failed with exit code {proc.returncode}")


def interpreter_in(venv: Path) -> Path:
    for candidate in (venv / "bin" / "python", venv / "Scripts" / "python.exe"):
        if candidate.exists():
            return candidate
    raise CheckError(
        f"no interpreter in {venv} (looked for bin/python, Scripts/python.exe)"
    )


def check(dist: str, wheel_arg: str | None, python: str | None, keep: bool) -> int:
    """Build, install from the index, walk. Returns the inner layer's exit status."""
    started = time.monotonic()
    directory, manifest = find_member(dist)
    module = module_name(manifest, dist)
    print(f"{dist} -> module {module} ({directory.relative_to(REPO_ROOT).as_posix()})")
    tmp = Path(tempfile.mkdtemp(prefix=f"import-check-{dist}-"))
    try:
        if wheel_arg:
            wheel = Path(wheel_arg).resolve()
            if not wheel.is_file():
                raise CheckError(f"no such wheel: {wheel}")
        else:
            out_dir = tmp / "dist"
            # character for character the command `release.yaml` and `poe build-needs`
            # run: a check that built the artefact differently would not be checking it
            run(
                ["uv", "build", "--package", dist, "--no-sources", "-o", out_dir],
                cwd=REPO_ROOT,
            )
            wheels = sorted(out_dir.glob("*.whl"))
            if len(wheels) != 1:
                raise CheckError(f"expected one wheel in {out_dir}, found {wheels}")
            wheel = wheels[0]
        venv = tmp / "venv"
        # no `--python` by default: the root `.python-version` decides, which is exactly
        # what the compat cell does. `cwd=REPO_ROOT` is what lets uv see that file
        run(
            ["uv", "venv", *(["--python", python] if python else []), venv],
            cwd=REPO_ROOT,
        )
        # `--no-sources` is THE flag. Without it uv honours `[tool.uv.sources]` and installs
        # the sibling member from the checkout, and the check silently proves nothing
        run(
            ["uv", "pip", "install", "--python", venv, "--no-sources", wheel],
            cwd=REPO_ROOT,
        )
        interpreter = interpreter_in(venv)
        inner = [
            interpreter,
            Path(__file__).resolve(),
            "--walk",
            module,
            "--expect-prefix",
            venv,
        ]
        print("$", " ".join(str(part) for part in inner), flush=True)
        code = subprocess.run([str(part) for part in inner], cwd=REPO_ROOT).returncode
    finally:
        if keep:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"import check finished in {time.monotonic() - started:.1f}s")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import every module of a member's built wheel against its dependencies as "
            "PUBLISHED. With --walk it is the inner layer instead: import one module tree "
            "under the current interpreter."
        ),
    )
    parser.add_argument(
        "dist", nargs="?", help="the distribution to check, e.g. sphinx-needs"
    )
    parser.add_argument(
        "--walk",
        metavar="MODULE",
        help="INNER: import this module and every submodule under it, in THIS interpreter",
    )
    parser.add_argument(
        "--expect-prefix",
        metavar="DIR",
        help="INNER: fail unless the module was imported from under this directory",
    )
    parser.add_argument(
        "--wheel", metavar="PATH", help="use this wheel instead of building one"
    )
    parser.add_argument(
        "--python", metavar="X", help="interpreter for the throwaway environment"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the temporary directory"
    )
    args = parser.parse_args(argv)

    if args.walk:
        return walk(args.walk, args.expect_prefix)
    if not args.dist:
        parser.error(
            "name a distribution (outer layer) or pass --walk MODULE (inner layer)"
        )
    try:
        return check(args.dist, args.wheel, args.python, args.keep)
    except CheckError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
