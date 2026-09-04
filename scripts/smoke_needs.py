#!/usr/bin/env python3
"""Smoke-test the *built* distribution, outside of this project's environment.

Every other gate in this repository imports the source tree: the tests, the docs build
and the type check all run against a checkout, so a file that never reaches the wheel is
invisible to all of them (issue #1829).  This script closes that gap:

1. build the sdist + wheel with ``uv build``;
2. create a throwaway virtual environment *outside* the project;
3. install the wheel into it with ``--no-sources``, so uv resolves from the index instead
   of silently substituting the local source tree;
4. assert ``sphinx_needs.__file__`` is inside that environment -- without this the whole
   run can pass while testing the checkout again;
5. assert the wheel carries every file git tracks under the module directory -- the
   non-Python payload (vendored JS/CSS, images, templates, JSON schemas) is 88% of it by
   file count, and it is the part a packaging mistake drops;
6. build a tiny documentation project with ``-W`` and assert the rendered need, the link,
   the table, the flow image and the copied static assets.

It is parameterised on the package directory and the distribution name so that a sibling
package in this workspace can reuse it unchanged::

    python scripts/smoke_needs.py .                       # a single-package repository
    python scripts/smoke_needs.py packages/sphinx-needs   # a workspace member

``uv venv`` picks the interpreter from ``UV_PYTHON`` (or ``--python``), so CI runs this at
the declared ``requires-python`` floor -- which is what makes that floor honest.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Named canaries: files whose loss no other assertion would report readably. The real
# payload check is `tracked_module_files` below -- these only make a failure legible.
WHEEL_FILES = [
    "directives/needimport_template.rst",
    "directives/needreport_template.rst",
    "templates/permalink.html",
    "templates/time_measurements.html",
    "needsfile.json",
]

CONF_PY = """\
extensions = ["sphinx.ext.graphviz", "sphinx_needs"]
needs_flow_engine = "graphviz"
"""

INDEX_RST = """\
Smoke test
==========

.. req:: A requirement
   :id: REQ_1

.. spec:: A specification
   :id: SPEC_1
   :links: REQ_1

.. needtable::
   :columns: id;title

.. needflow::
"""


class SmokeError(RuntimeError):
    """A step that cannot be recovered from (the build, the install, the doc build)."""


def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it first, and raise SmokeError if it fails."""
    print("$", " ".join(str(part) for part in cmd), flush=True)
    proc = subprocess.run(
        [str(part) for part in cmd],
        text=True,
        capture_output=True,
        **kwargs,
    )
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if proc.returncode != 0:
        print(proc.stderr, end="", file=sys.stderr, flush=True)
        raise SmokeError(f"command failed with exit code {proc.returncode}")
    return proc


class Checks:
    """Collects the assertions so one failure does not hide the others."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        print(
            f"{'OK  ' if ok else 'FAIL'}  {label}{f'  -- {detail}' if detail else ''}"
        )
        if not ok:
            self.failures.append(label)


def build_wheel(package_dir: Path, dist_name: str) -> Path:
    """Build the distribution and return the path of the freshly built wheel."""
    out_dir = REPO_ROOT / "dist" / dist_name
    # a stale wheel here would be a silent false pass, so start from nothing
    shutil.rmtree(out_dir, ignore_errors=True)
    run(["uv", "build", str(package_dir), "-o", str(out_dir)], cwd=REPO_ROOT)
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise SmokeError(f"expected exactly one wheel in {out_dir}, found {wheels}")
    if not list(out_dir.glob("*.tar.gz")):
        raise SmokeError(f"no sdist was built in {out_dir}")
    return wheels[0]


def tracked_module_files(package_dir: Path, module: str) -> set[str]:
    """Every tracked file under the module directory, relative to that directory.

    This is what the wheel is checked against. Counting files cannot express the thing
    that matters -- a file that is in the repository and *not* in the built distribution
    is exactly the #1829 failure, and a minimum count has as much slack as the difference
    between the floor and the inventory. A superset check has none: files added to the
    package pass automatically, and any one that stops being packaged fails.
    """
    for candidate in (package_dir / "src" / module, package_dir / module):
        if candidate.is_dir():
            module_dir = candidate
            break
    else:
        raise SmokeError(f"no {module}/ directory under {package_dir}")
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--", str(module_dir)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:  # git is not on PATH
        raise SmokeError(f"git is needed to list the packaged files: {exc}") from exc
    if proc.returncode != 0:
        raise SmokeError(f"git ls-files failed: {proc.stderr.strip()}")
    prefix = f"{module_dir.relative_to(REPO_ROOT).as_posix()}/"
    tracked = {
        path[len(prefix) :]
        for path in proc.stdout.split("\0")
        if path and "__pycache__" not in path and not path.endswith(".pyc")
    }
    if not tracked:
        raise SmokeError(f"git tracks no files under {module_dir}")
    return tracked


def check_wheel_contents(
    wheel: Path, module: str, package_dir: Path, checks: Checks
) -> None:
    names = zipfile.ZipFile(wheel).namelist()
    owned = {n[len(module) + 1 :] for n in names if n.startswith(f"{module}/")}
    checks.check(
        bool(owned), f"wheel contains the {module} package", f"{len(names)} entries"
    )
    tracked = tracked_module_files(package_dir, module)
    missing = sorted(tracked - owned)
    shown = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
    checks.check(
        not missing,
        f"the wheel carries every tracked file under {module}/ ({len(tracked)} files)",
        f"{len(missing)} missing: {shown}" if missing else "",
    )
    for name in WHEEL_FILES:
        checks.check(name in owned, f"wheel has {module}/{name}")


def write_project(src: Path) -> None:
    src.mkdir(parents=True)
    (src / "conf.py").write_text(CONF_PY, encoding="utf-8")
    (src / "index.rst").write_text(INDEX_RST, encoding="utf-8")


def check_build_output(out: Path, checks: Checks) -> None:
    html = (out / "index.html").read_text(encoding="utf-8")
    checks.check('id="REQ_1"' in html, "the need is rendered")
    checks.check('id="SPEC_1"' in html, "the linked need is rendered")
    checks.check('href="#REQ_1"' in html, "the link between them resolves")
    checks.check("NEEDS_DATATABLES" in html, "needtable is rendered")
    images = sorted(
        p.name for p in (out / "_images").glob("needflow*") if p.suffix != ".map"
    )
    checks.check(bool(images), "needflow image is emitted", ", ".join(images))
    static = (
        sorted(p.name for p in (out / "_static" / "sphinx-needs").glob("*"))
        if (out / "_static" / "sphinx-needs").is_dir()
        else []
    )
    checks.check(bool(static), "static assets are copied", f"{len(static)} entries")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "package_dir",
        nargs="?",
        default=".",
        help="directory holding the package's pyproject.toml, relative to the repository root (default: .)",
    )
    parser.add_argument(
        "--dist-name",
        default="sphinx-needs",
        help="distribution name (default: sphinx-needs)",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="interpreter for the throwaway environment (default: uv's)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the temporary directory for inspection",
    )
    args = parser.parse_args()

    package_dir = (REPO_ROOT / args.package_dir).resolve()
    if not (package_dir / "pyproject.toml").is_file():
        raise SmokeError(f"no pyproject.toml in {package_dir}")
    module = args.dist_name.replace("-", "_")

    started = time.monotonic()
    checks = Checks()
    wheel = build_wheel(package_dir, args.dist_name)
    print(f"built {wheel.name}")
    check_wheel_contents(wheel, module, package_dir, checks)

    tmp = Path(tempfile.mkdtemp(prefix=f"smoke-{args.dist_name}-"))
    try:
        # deliberately outside the workspace: an environment inside it can pick up the
        # source tree through the workspace's own configuration
        venv = tmp / "venv"
        run(
            [
                "uv",
                "venv",
                *(["--python", args.python] if args.python else []),
                str(venv),
            ],
            cwd=tmp,
        )
        python = (
            venv
            / ("Scripts" if sys.platform == "win32" else "bin")
            / ("python.exe" if sys.platform == "win32" else "python")
        )
        # `--no-sources` is load-bearing: without it uv honours `tool.uv.sources` and
        # installs the local source tree even into an environment outside the workspace
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-sources",
                str(wheel),
            ],
            cwd=tmp,
        )

        # `cwd=tmp` is not cosmetic: python puts the working directory on `sys.path` for
        # `-c`, so running this from the repository root imports the checkout instead of
        # the wheel -- which is precisely what the next assertion exists to catch
        probe = f"import {module} as m; print(m.__version__); print(m.__file__)"
        version, location = run([str(python), "-c", probe], cwd=tmp).stdout.split()
        checks.check(True, f"{args.dist_name} imports", f"{version} from {location}")
        checks.check(
            Path(location).resolve().is_relative_to(venv.resolve()),
            "the import comes from the throwaway environment, not the checkout",
            location,
        )
        interpreter = run(
            [str(python), "-c", "import sys; print(sys.version.split()[0])"], cwd=tmp
        )
        print(f"interpreter: {interpreter.stdout.strip()}")

        src, out = tmp / "src", tmp / "out"
        write_project(src)
        run(
            [str(python), "-m", "sphinx", "-b", "html", "-W", str(src), str(out)],
            cwd=tmp,
        )
        check_build_output(out, checks)
    finally:
        if args.keep:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(checks.failures)} failed in {time.monotonic() - started:.1f}s")
    if checks.failures:
        for label in checks.failures:
            print(f"::error::smoke check failed: {label}")
        return 1
    print(f"smoke test passed: {wheel.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        sys.exit(1)
