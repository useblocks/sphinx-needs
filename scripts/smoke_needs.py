#!/usr/bin/env python3
"""Smoke-test the *built* distribution, outside of this project's environment.

Every other gate in this repository imports the source tree: the tests, the docs build
and the type check all run against a checkout, so a file that never reaches the wheel is
invisible to all of them (issue #1829).  This script closes that gap:

1. build the sdist + wheel with the *same* ``uv build`` invocation the release workflow
   runs (``--package <dist> --no-sources -o dist/<dist>``);
2. in the default ``--siblings tree`` mode, build a wheel the same way for every workspace
   member the package depends on at runtime -- its ``[project] dependencies``, followed
   through the workspace transitively, read off the manifests rather than listed here
   (for sphinx-needs: ub-project and ub-needs-exchange; sphinx-ai-index is a ``docs``
   *extra*, which this install does not ask for);
3. assert the sdist carries the trees it is meant to ship, does *not* carry the ones it is
   meant to have stopped shipping, and holds none of the rubbish a used checkout leaves
   behind. Both directions are silent failures. flit 4 does not infer sdist contents from
   git, so ``docs/`` is in the tarball only because ``[tool.flit.sdist] include`` says so;
   and since 9.0.0 ``tests/`` and ``performance/`` must stay out of it, because the suite
   loads its fixtures from ``sphinx-needs-testkit``, a private workspace member that is on
   no index -- a shipped suite nobody can run is worse than none, and re-adding one to
   ``include`` is a two-word edit that no other gate would notice;
4. create a throwaway virtual environment *outside* the project;
5. install the wheel into it with ``uv pip install``, which reads the wheel's own
   ``Requires-Dist`` and resolves it from the index (measured on uv 0.12.9: ``uv pip
   install <wheel>`` does that with or without ``--no-sources`` -- the flag governs
   requirements uv reads from a *pyproject*, so it is passed here for the recipe and the
   intent, not as the mechanism). In tree mode the siblings' wheels from step 2 go into
   the SAME call, so uv takes those distributions from the tree and everything else from
   the index;
6. assert ``sphinx_needs.__file__`` is inside that environment -- without this the whole
   run can pass while testing the checkout again. In tree mode, assert the same of every
   sibling's modules, AND that EVERY workspace member installed in the environment has a
   ``direct_url.json`` (PEP 610) naming the wheel step 2 built for it. A location check
   alone cannot tell the tree's ``ub-project 1.1.0`` from PyPI's ``ub-project 1.1.0``, so
   without the second half a run that quietly fell back to the index would still pass;
   and checking every installed member rather than only the derived ones means a member
   step 2 did not reach (through an extra on a sibling requirement, say) fails by name
   instead of arriving from the index. In published mode, assert every installed member
   came from the index. The run prints each member with its version and where it came
   from;
7. assert the wheel carries every file git tracks under the module directory -- the
   non-Python payload (vendored JS/CSS, images, templates, JSON schemas) is 88% of it by
   file count, and it is the part a packaging mistake drops;
8. build a wheel *from the sdist* -- a second throwaway environment and ``uv pip install
   <sdist>``, which runs the PEP 517 hook (``flit_core.buildapi``) on the tarball -- and
   import it, with the siblings installed and asserted exactly as in steps 5 and 6.
   Step 3 asserts what the tarball *contains*; only this asserts that the
   tarball still builds. They are different failures: a sdist can ship every declared tree
   and still be unbuildable (a ``[build-system]`` requirement that no longer resolves, a
   ``[tool.flit]`` key the backend rejects, a module the ``include`` list quietly stopped
   naming), and a user who installs from source -- as every ``pip install`` on a platform
   with no wheel does, and as conda-forge and the distributions do -- is the only person
   who would find out;
9. build a tiny documentation project with ``-W`` and assert the rendered need, the link,
   the table, the flow image and the copied static assets.

**Why two sibling modes.** A pull request that changes a sibling and uses the change in
sphinx-needs in one go is coherent in the tree, and the siblings are released in bulk
*before* the package that depends on them, not one per pull request. Resolving the
siblings from PyPI on every pull request would therefore keep such a change red until a
release it is not meant to trigger, so ``tree`` -- the default, and what CI requires --
tests the package with the siblings this tree builds. ``--siblings published`` is the
pre-release question instead: the wheel against the siblings as PyPI has them, exactly as
this script ran before it had modes, plus the check that no workspace member came from
anywhere but the index. CI runs it as an informational job; at release time the
workflow's compat cell asks the same published-dependency question fail-closed (the built
wheel resolved against PyPI alone, every module imported, the member's suite run),
whatever that job said.

It is parameterised on the package directory and the distribution name so that a sibling
package in this workspace can reuse it unchanged::

    python scripts/smoke_needs.py .                       # a single-package repository
    python scripts/smoke_needs.py packages/sphinx-needs   # a workspace member
    python scripts/smoke_needs.py packages/sphinx-needs --siblings published

``uv venv`` picks the interpreter from ``UV_PYTHON`` (or ``--python``), so CI runs this at
the declared ``requires-python`` floor -- which is what makes that floor honest.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote

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

# Nothing a build or a test run leaves in the working directory may reach the sdist. flit
# reads the working tree, not git, so `[tool.flit.sdist] exclude` is the only thing keeping
# `docs/_build/` (456 files after one docs build) out of a released tarball.
SDIST_JUNK = ("__pycache__", ".pyc", "_build/", ".pytest_cache")

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


# The two sibling modes; see "Why two sibling modes" in the module docstring
TREE, PUBLISHED = "tree", "published"

# The name at the head of a PEP 508 requirement -- everything a sibling lookup needs, so
# this script stays standard-library only (it runs before, and outside, any environment
# built for it) rather than importing `packaging` for one regular expression
REQUIREMENT_NAME = re.compile(r"\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")

# Run INSIDE a throwaway environment. It reports EVERY installed distribution -- its
# version, and where it was installed from (PEP 610's `direct_url.json`, which uv writes
# for a wheel given by path and not for one resolved from an index) -- and where each module
# named in the JSON argument imports from. Every distribution, not only the expected
# siblings: the caller checks each workspace member it finds, so a member the sibling
# lookup did not reach is still seen. JSON out, because a temporary directory may contain
# a space
SIBLING_PROBE = """\
import importlib, importlib.metadata as md, json, sys
installed = {
    found.metadata["Name"]: {
        "version": found.version,
        "direct_url": found.read_text("direct_url.json"),
    }
    for found in md.distributions()
}
files = {m: importlib.import_module(m).__file__ for m in json.loads(sys.argv[1])}
print(json.dumps({"installed": installed, "files": files}))
"""


class SmokeError(RuntimeError):
    """A step that cannot be recovered from (the build, the install, the doc build)."""


def run(
    cmd: list[str], *, cwd: Path, label: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it (or `label`, for one too long to read) first, and raise
    SmokeError if it fails."""
    print("$", label or " ".join(str(part) for part in cmd), flush=True)
    proc = subprocess.run(
        [str(part) for part in cmd],
        text=True,
        capture_output=True,
        cwd=cwd,
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


def build(dist_name: str) -> tuple[Path, Path]:
    """Build the distribution; return the freshly built (wheel, sdist).

    This is character for character the command the release workflow runs -- `--package`
    rather than a path so uv resolves the member out of the workspace, `--no-sources` so a
    *build* requirement is never substituted from the workspace, and `-o dist/<dist>` so
    that `uv publish` is later pointed at one distribution's artefacts instead of its
    default `dist/*` glob. A smoke test that built the artefact differently from the
    release would not be testing the release.
    """
    out_dir = REPO_ROOT / "dist" / dist_name
    # a stale wheel here would be a silent false pass, so start from nothing
    shutil.rmtree(out_dir, ignore_errors=True)
    run(
        ["uv", "build", "--package", dist_name, "--no-sources", "-o", str(out_dir)],
        cwd=REPO_ROOT,
    )
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise SmokeError(f"expected exactly one wheel in {out_dir}, found {wheels}")
    sdists = sorted(out_dir.glob("*.tar.gz"))
    if len(sdists) != 1:
        raise SmokeError(f"expected exactly one sdist in {out_dir}, found {sdists}")
    return wheels[0], sdists[0]


def canonical(name: str) -> str:
    """PEP 503 normalisation, so `ub_project` and `UB-Project` name one distribution."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec: str) -> str:
    """The canonical distribution name a PEP 508 requirement string asks for."""
    match = REQUIREMENT_NAME.match(spec)
    if match is None:
        raise SmokeError(f"cannot read a distribution name from requirement {spec!r}")
    return canonical(match.group(1))


class Member(NamedTuple):
    """One workspace member, as far as the sibling lookup needs it."""

    name: str  # as the manifest spells it, which is what `uv build --package` is given
    directory: Path
    # canonical name -> the requirement string, runtime `dependencies` only: the smoke
    # test installs the wheel with no extras, so a sibling reached only through an extra
    # (sphinx-ai-index, through sphinx-needs' `docs`) is not installed by it either
    requires: dict[str, str]
    virtual: bool


def workspace_members(root: Path) -> dict[str, Member]:
    """Every member the root's `[tool.uv.workspace] members` globs name, by canonical name."""
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    globs = (
        manifest.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    )
    found: dict[str, Member] = {}
    for pattern in globs:
        for path in sorted(root.glob(f"{pattern}/pyproject.toml")):
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            project = raw.get("project", {})
            if "name" not in project:
                continue
            requires = {
                requirement_name(spec): spec for spec in project.get("dependencies", [])
            }
            found[canonical(project["name"])] = Member(
                name=project["name"],
                directory=path.parent,
                requires=requires,
                virtual=raw.get("tool", {}).get("uv", {}).get("package") is False,
            )
    return found


def runtime_siblings(
    dist: str, members: dict[str, Member], *, refuse_markers: bool = True
) -> list[str]:
    """The members `dist` needs at runtime, transitively within the workspace, sorted.

    Transitive because uv resolves the whole tree: a sibling of a sibling that came from
    PyPI would put a published distribution under a tree one, which is neither of the two
    questions this script answers. `dist` itself is never in the result, even through a
    cycle; a `dist` that is not a member (a single-package repository) has no siblings.
    """
    start = canonical(dist)
    if start not in members:
        return []
    seen: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        for name, spec in members[current].requires.items():
            if name not in members or name == start or name in seen:
                continue
            # a marker would make the wheel's own resolution conditional, and a wheel given
            # by path is installed unconditionally: refuse rather than test a different
            # environment from the one the published wheel would get
            if refuse_markers and ";" in spec:
                raise SmokeError(
                    f"{members[current].name} requires the workspace member {spec!r} under "
                    "an environment marker, which --siblings tree cannot honour"
                )
            seen.add(name)
            pending.append(name)
    return sorted(seen)


def wheel_modules(wheel: Path) -> list[str]:
    """The top-level importable names a wheel installs (packages and single modules)."""
    tops: set[str] = set()
    for entry in zipfile.ZipFile(wheel).namelist():
        head, _, rest = entry.partition("/")
        if head.endswith((".dist-info", ".data")):
            continue
        if rest:
            tops.add(head)
        elif head.endswith(".py"):
            tops.add(head[: -len(".py")])
    return sorted(tops)


class Siblings(NamedTuple):
    """What `check_siblings` checks each environment against; built once, in `main`."""

    package: str
    workspace: set[str]  # the canonical name of every workspace member
    tree: bool  # --siblings tree
    tree_wheels: dict[
        str, Path
    ]  # canonical name -> the wheel built from it (tree mode)
    modules: list[str]  # the top-level modules of those wheels


def check_siblings(
    python: Path, venv: Path, plan: Siblings, where: str, checks: Checks
) -> None:
    """Assert where every workspace member installed in one environment came from.

    Every member the probe finds installed, other than `package` itself -- not only the
    ones `runtime_siblings` derived. In tree mode each must be the wheel this run built for
    it (`plan.tree_wheels`), so a member the derivation did not reach (through an extra on a
    sibling requirement, say) is a failure naming it rather than a distribution quietly
    taken from the index; and each of `plan.modules` must import from `venv`. In published mode each must have come from the index, so the
    pre-release check cannot go green on a tree sibling either. An empty `plan.workspace`
    (a single-package repository) has nothing to check.
    """
    if not plan.workspace:
        return
    tree_wheels, modules = plan.tree_wheels, plan.modules
    proc = run(
        [str(python), "-c", SIBLING_PROBE, json.dumps(modules)],
        cwd=venv.parent,
        label=f"{python} -c <the workspace-member probe> {json.dumps(modules)}",
    )
    report = json.loads(proc.stdout.splitlines()[-1])
    installed = {canonical(name): data for name, data in report["installed"].items()}
    own = canonical(plan.package)
    for name in sorted(tree_wheels):
        checks.check(
            name in installed,
            f"{name} is installed in the {where}",
            "" if name in installed else "its wheel was passed to uv but is not there",
        )
    for name in sorted((set(installed) & plan.workspace) - {own}):
        found = installed[name]
        direct = json.loads(found["direct_url"]) if found["direct_url"] else {}
        source = unquote(direct.get("url", "")) or "the index"
        print(
            f"workspace member in the {where}: {name} {found['version']} from {source}"
        )
        if not plan.tree:
            checks.check(
                source == "the index",
                f"{name} in the {where} is the index's, as published",
                "" if source == "the index" else f"installed from {source}",
            )
            continue
        if name not in tree_wheels:
            checks.check(
                False,
                f"{name} in the {where} is the wheel this tree built, not the index's",
                f"installed from {source}, and no wheel was built for it: it is a "
                "workspace member the runtime `dependencies` of "
                f"{plan.package} do not reach (an extra on a workspace requirement?), "
                "so the sibling lookup missed it",
            )
            continue
        expected = unquote(tree_wheels[name].resolve().as_uri())
        checks.check(
            source == expected,
            f"{name} in the {where} is the wheel this tree built, not the index's",
            ""
            if source == expected
            else f"installed from {source}, expected {expected}",
        )
    for module, location in sorted(report["files"].items()):
        checks.check(
            location is not None
            and Path(location).resolve().is_relative_to(venv.resolve()),
            f"{module} imports from the {where}, not the checkout",
            str(location),
        )


def check_sdist_contents(
    sdist: Path, wanted: list[str], unwanted: list[str], checks: Checks
) -> None:
    """The sdist ships the declared trees, not the withdrawn ones, and no leftovers.

    `uv build` runs `flit_core.buildapi`, and flit 4 dropped flit 3's "infer the sdist from
    git" behaviour -- so `docs/` is in the tarball only while `[tool.flit.sdist] include`
    names it, and losing it warns about nothing.

    The `unwanted` half is the same assertion pointed the other way, and it is the one that
    matters now: `tests/` and `performance/` were shipped until 9.0.0, the suite has since
    moved its fixtures into `sphinx-needs-testkit` -- a member classified
    `Private :: Do Not Upload`, which no sdist can carry -- and a tarball that ships the
    suite anyway ships something that cannot be run. Debian, the one downstream that runs
    these tests, runs them from the GitHub tag tarball `debian/watch` fetches, so nothing
    is lost by keeping them out and nothing warns if they come back.
    """
    with tarfile.open(sdist) as tar:
        names = tar.getnames()
    # every path is prefixed with `<name>-<version>/`; compare on the part after it
    inner = [name.split("/", 1)[1] for name in names if "/" in name]
    for tree in wanted:
        entries = [name for name in inner if name.startswith(f"{tree}/")]
        checks.check(
            bool(entries),
            f"the sdist ships {tree}/",
            f"{len(entries)} entries"
            if entries
            else "none -- is it in [tool.flit.sdist] include?",
        )
    for tree in unwanted:
        entries = sorted(name for name in inner if name.startswith(f"{tree}/"))
        shown = ", ".join(entries[:3]) + (" ..." if len(entries) > 3 else "")
        checks.check(
            not entries,
            f"the sdist does NOT ship {tree}/",
            f"{len(entries)} entries: {shown} -- drop {tree}/ from "
            "[tool.flit.sdist] include; the suite needs sphinx-needs-testkit, "
            "which is on no index"
            if entries
            else "",
        )
    junk = sorted(name for name in inner if any(bad in name for bad in SDIST_JUNK))
    shown = ", ".join(junk[:3]) + (" ..." if len(junk) > 3 else "")
    checks.check(
        not junk,
        f"the sdist carries no build rubbish ({len(names)} entries, {sdist.stat().st_size} bytes)",
        f"{len(junk)} unwanted: {shown}" if junk else "",
    )


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


def interpreter_in(venv: Path) -> Path:
    """The python of a `uv venv`, on this platform."""
    return (
        venv
        / ("Scripts" if sys.platform == "win32" else "bin")
        / ("python.exe" if sys.platform == "win32" else "python")
    )


def manifest_version(package_dir: Path) -> str:
    """The version the member's manifest declares.

    Read from the manifest rather than from the built artefact's file name so that the
    assertion below compares two independent statements of the version: what the tree says
    it is building, and what the module the sdist built actually reports.
    """
    data = tomllib.loads((package_dir / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        raise SmokeError(f"{package_dir}/pyproject.toml declares no [project] version")
    return version


def check_sdist_builds(
    sdist: Path,
    module: str,
    expected: str,
    tmp: Path,
    python: str | None,
    siblings: Siblings,
    checks: Checks,
) -> float:
    """Build a wheel FROM the sdist, in an environment of its own, and import it.

    `check_sdist_contents` above asserts what the tarball carries; this asserts that the
    tarball still *builds*, which is a different failure and one nothing else in this
    repository can see. `uv pip install <sdist>` is the whole mechanism: uv reads the
    tarball's `[build-system]`, resolves it (flit_core) in an isolated build environment,
    runs `build_wheel`, and installs the result -- exactly the path a user on a platform
    with no wheel takes, and the one conda-forge and the distributions take always.

    A SECOND environment, not the wheel's: installing the sdist over an already-installed
    wheel of the same version is a no-op for uv, so the check would pass without ever
    running the build backend.

    The tree's sibling wheels, if any, go into the same `uv pip install` call as the
    tarball, and are checked here exactly as in the wheel's environment.

    Returns the seconds the build-and-install took, which is what this step costs the smoke
    run; the caller prints it.
    """
    venv = tmp / "venv-sdist"
    run(["uv", "venv", *(["--python", python] if python else []), str(venv)], cwd=tmp)
    interpreter = interpreter_in(venv)
    started = time.monotonic()
    try:
        # `--python` on every `uv pip` call: `uv pip` is NOT project-scoped, so without it
        # this would target whatever virtualenv happens to be active
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(interpreter),
                "--no-sources",
                str(sdist),
                *(str(wheel) for wheel in siblings.tree_wheels.values()),
            ],
            cwd=tmp,
        )
    except SmokeError as exc:
        raise SmokeError(
            f"{exc} -- could not build a wheel from the sdist {sdist}. That is a "
            "`[build-system]` or `[tool.flit]` failure in the tarball, not a missing file: "
            "the contents checks above passed"
        ) from exc
    elapsed = time.monotonic() - started
    # `cwd=tmp` for the same reason as the wheel probe: python puts the working directory
    # on `sys.path` for `-c`, so from the repository root this would import the checkout.
    # `splitlines()`, not `split()`: the probe prints one value per LINE, and a path with a
    # space in it -- which `TMPDIR="/…/with space"` gives every temporary directory here --
    # makes a whitespace split yield three fields and unpack with a `ValueError`
    probe = f"import {module} as m; print(m.__version__); print(m.__file__)"
    version, location = run(
        [str(interpreter), "-c", probe], cwd=tmp
    ).stdout.splitlines()
    checks.check(
        version == expected,
        f"the wheel built from the sdist reports the manifest's version ({expected})",
        f"got {version}",
    )
    checks.check(
        Path(location).resolve().is_relative_to(venv.resolve()),
        "the sdist-built import comes from ITS OWN environment, not the checkout",
        location,
    )
    check_siblings(interpreter, venv, siblings, "sdist's environment", checks)
    return elapsed


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
        "--sdist-dirs",
        nargs="*",
        default=["docs"],
        metavar="DIR",
        help="directories the sdist must ship (default: docs); pass none to skip",
    )
    parser.add_argument(
        "--sdist-absent-dirs",
        nargs="*",
        default=["tests", "performance"],
        metavar="DIR",
        help="directories the sdist must NOT ship (default: tests performance); pass none to skip",
    )
    parser.add_argument(
        "--siblings",
        choices=[TREE, PUBLISHED],
        default=TREE,
        help="where the workspace members the package depends on come from: wheels built "
        "from this tree (default; what CI requires), or the index as published (the "
        "pre-release check)",
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
    members = workspace_members(REPO_ROOT)
    wheel, sdist = build(args.dist_name)
    print(f"built {wheel.name} and {sdist.name}")
    # canonical name -> the wheel built from the tree, filled in tree mode only
    tree_wheels: dict[str, Path] = {}
    modules: list[str] = []
    tree = args.siblings == TREE
    names = runtime_siblings(args.dist_name, members, refuse_markers=tree)
    for name in names if tree else []:
        member = members[name]
        if member.virtual:
            raise SmokeError(
                f"{args.dist_name} depends on {member.name}, a virtual member that "
                "`uv build --package` refuses to build"
            )
        tree_wheels[name], _ = build(member.name)
        modules += wheel_modules(tree_wheels[name])
        print(f"built {tree_wheels[name].name} from the tree")
    print(
        f"siblings ({args.siblings}): "
        + (", ".join(members[name].name for name in names) or "none")
    )
    siblings = Siblings(args.dist_name, set(members), tree, tree_wheels, modules)
    check_wheel_contents(wheel, module, package_dir, checks)
    check_sdist_contents(sdist, args.sdist_dirs, args.sdist_absent_dirs, checks)

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
        python = interpreter_in(venv)
        # `--no-sources` states the intent and keeps this identical to the release
        # workflow's install, but it is not what stops the source tree being installed:
        # measured on uv 0.12.9, `uv pip install <wheel>` resolves the wheel's
        # `Requires-Dist` from the index either way (`[tool.uv.sources]` applies to
        # requirements read from a pyproject). The assertion below -- the import comes from
        # this environment -- is what actually catches a checkout being tested instead
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-sources",
                str(wheel),
                # the tree's siblings, in the SAME call: uv then takes these distributions
                # from the given wheels and everything else from the index
                *(str(sibling) for sibling in tree_wheels.values()),
            ],
            cwd=tmp,
        )

        # `cwd=tmp` is not cosmetic: python puts the working directory on `sys.path` for
        # `-c`, so running this from the repository root imports the checkout instead of
        # the wheel -- which is precisely what the next assertion exists to catch
        # `splitlines()`, not `split()`: see `check_sdist_builds` above -- the probe prints
        # one value per line, and a temporary directory whose path contains a space made
        # this unpack raise `ValueError: too many values to unpack`
        probe = f"import {module} as m; print(m.__version__); print(m.__file__)"
        version, location = run([str(python), "-c", probe], cwd=tmp).stdout.splitlines()
        checks.check(True, f"{args.dist_name} imports", f"{version} from {location}")
        checks.check(
            Path(location).resolve().is_relative_to(venv.resolve()),
            "the import comes from the throwaway environment, not the checkout",
            location,
        )
        check_siblings(python, venv, siblings, "wheel's environment", checks)
        interpreter = run(
            [str(python), "-c", "import sys; print(sys.version.split()[0])"], cwd=tmp
        )
        print(f"interpreter: {interpreter.stdout.strip()}")

        seconds = check_sdist_builds(
            sdist,
            module,
            manifest_version(package_dir),
            tmp,
            args.python,
            siblings,
            checks,
        )
        print(f"built and installed {sdist.name} from source in {seconds:.1f}s")

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
