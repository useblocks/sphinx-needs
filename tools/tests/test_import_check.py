"""`import_check.py`: the wheel-only import walk, and the environment it runs in.

The **inner** layer is tested for real -- a scratch package on `PYTHONPATH`, imported by a
subprocess with `sys.executable` -- because its entire subject is what happens at import
time, and a mocked import would prove nothing about it.

The **outer** layer is tested with `subprocess.run` monkeypatched, on its argv. It exists to
issue four exact commands, so the assertions are on the commands rather than on their
results -- and what they pin is the RECIPE: that these are, character for character, the
release build's and the compat cell's own commands. Measured on uv 0.12.9, `--no-sources` on
a *wheel* install changes nothing (a wheel's `Requires-Dist` resolves from the index either
way; the flag governs requirements uv reads from a pyproject), so the argv assertion is the
only thing that can catch its loss -- and losing it would make this check stop matching the
pipeline it stands in for. What makes the check *mean* something is the out-of-project
environment plus `--expect-prefix`, and those are tested against real imports above.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from sn_tools import import_check

SCRIPT = Path(import_check.__file__).resolve()


# --- the inner layer ----------------------------------------------------------------------


def scratch_package(root: Path, modules: dict[str, str]) -> Path:
    for name, body in modules.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
    return root


def walk(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the inner layer the way the outer layer does: by path, in another process."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--walk", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(root)},
    )


def test_a_clean_walk_counts_every_module(tmp_path: Path) -> None:
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/one.py": "VALUE = 1\n",
            "pkg/sub/__init__.py": "",
            "pkg/sub/two.py": "VALUE = 2\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK    4 modules imported in" in proc.stdout


def test_every_failing_module_is_reported_not_just_the_first(tmp_path: Path) -> None:
    """The reader wants every missing symbol at once: the next run costs a wheel build."""
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/good.py": "VALUE = 1\n",
            "pkg/missing_symbol.py": (
                "raise ImportError(\"cannot import name 'gone' from 'dep'\")\n"
            ),
            "pkg/explodes.py": "raise RuntimeError('a module-level boom')\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 1
    out = proc.stdout
    assert (
        "FAIL  pkg.missing_symbol: ImportError: cannot import name 'gone' from 'dep'"
        in out
    )
    assert "FAIL  pkg.explodes: RuntimeError: a module-level boom" in out
    assert "FAIL  2 of 4 modules failed to import" in out
    assert "(2 imported)" in out
    # the innermost frame, so the reader gets the line rather than only the exception
    assert "missing_symbol.py:1 in <module>: raise ImportError" in out


FLAKY_PACKAGE = """\
import pathlib

marker = pathlib.Path({marker!r})
if not marker.exists():
    marker.write_text("seen")
    raise {failure}
"""


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        # the walker's own generator dies on this one, so nothing after it is even listed
        ("SystemExit(0)", "the walk was cut short by SystemExit: 0"),
        # this one goes through `onerror`, so the siblings are listed and the subtree is not
        (
            "ImportError('not yet')",
            "1 package(s) did not import on the walker's first pass",
        ),
    ],
)
def test_an_incomplete_walk_is_never_ok(
    tmp_path: Path, failure: str, expected: str
) -> None:
    """V1. An import-time failure need not be idempotent.

    A `sys.exit()` behind an "already configured?" test, a module that writes a cache and
    then fails, a plugin that registers itself on first import: the package fails while
    `pkgutil` is walking, and succeeds when the loop re-imports it. Every module the loop
    reached then imports cleanly, `failures` is empty -- and the walk printed `OK` and
    exited 0 over a subtree it never listed, with the compat cell's gate step green.
    """
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": FLAKY_PACKAGE.format(
                marker=str(tmp_path / "marker"), failure=failure
            ),
            "pkg/sub/child.py": "VALUE = 1\n",
            "pkg/zzz.py": "VALUE = 1\n",
        },
    )
    proc = walk(root, "pkg")
    out = proc.stdout
    # the second import succeeds, so nothing is recorded as a per-module failure ...
    assert "FAIL  pkg.sub:" not in out
    assert "OK    " not in out
    # ... and the walk is still not a pass, because it did not finish
    assert "FAIL  walk incomplete:" in out
    assert expected in out
    assert "and an unknown number never were" in out
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_a_package_that_cannot_import_stops_its_own_subtree(tmp_path: Path) -> None:
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/broken/__init__.py": "raise RuntimeError('no')\n",
            "pkg/broken/child.py": "VALUE = 1\n",
            "pkg/fine.py": "VALUE = 1\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 1
    out = proc.stdout
    assert "FAIL  pkg.broken: RuntimeError: no" in out
    assert "pkg.broken did not import, so anything under it was never walked" in out
    # the count understates the tree -- `pkg.broken.child` exists and was never reached --
    # so the summary says how many packages hid contents from it
    assert (
        "FAIL  1 of 3 modules failed to import in 0.0s (2 imported; 1 package(s) did not "
        "import, so their contents were never walked)" in out
    )


def test_a_warning_at_import_time_is_not_a_failure(tmp_path: Path) -> None:
    """Measured on the real tree: `sphinx_needs.api.exceptions` emits one on import."""
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/noisy.py": (
                "import warnings\nwarnings.warn('deprecated', UserWarning)\n"
            ),
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK    2 modules imported" in proc.stdout


def test_a_module_that_is_not_there_at_all(tmp_path: Path) -> None:
    proc = walk(tmp_path, "no_such_module_anywhere")
    assert proc.returncode == 1
    assert "FAIL  no_such_module_anywhere: ModuleNotFoundError" in proc.stdout


def test_expect_prefix_accepts_the_tree_it_names(tmp_path: Path) -> None:
    root = scratch_package(tmp_path, {"pkg/__init__.py": ""})
    proc = walk(root, "pkg", "--expect-prefix", str(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "pkg imported from" in proc.stdout


def test_expect_prefix_refuses_another_copy(tmp_path: Path) -> None:
    """Without this the walk could import the checkout and pass against unreleased code."""
    root = scratch_package(tmp_path, {"pkg/__init__.py": ""})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    proc = walk(root, "pkg", "--expect-prefix", str(elsewhere))
    assert proc.returncode == 1
    out = proc.stdout
    assert "which is not under" in out
    assert "the walk is meant to test the installed wheel; this is another copy" in out


# --- the outer layer ----------------------------------------------------------------------


class FakeRun:
    """Records every argv, and fakes the two side effects the outer layer depends on."""

    def __init__(self, inner_returncode: int = 0, build_returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.inner_returncode = inner_returncode
        self.build_returncode = build_returncode

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        if cmd[:2] == ["uv", "build"]:
            if self.build_returncode:
                return subprocess.CompletedProcess(cmd, self.build_returncode)
            out = Path(cmd[cmd.index("-o") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "acme_core-1.0.0-py3-none-any.whl").write_bytes(b"")
        elif cmd[:2] == ["uv", "venv"]:
            binary = Path(cmd[-1]) / "bin" / "python"
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text("", encoding="utf-8")
        elif "--walk" in cmd:
            return subprocess.CompletedProcess(cmd, self.inner_returncode)
        return subprocess.CompletedProcess(cmd, 0)


@pytest.fixture
def fake_uv(monkeypatch):
    """Point the outer layer at a scratch workspace and record what it would run."""

    def build(root: Path, **kwargs: int) -> FakeRun:
        monkeypatch.setattr(import_check, "REPO_ROOT", root)
        fake = FakeRun(**kwargs)
        monkeypatch.setattr(import_check.subprocess, "run", fake)
        return fake

    return build


def test_the_commands_are_the_release_build_and_a_no_sources_install(
    workspace, fake_uv
) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake = fake_uv(root)
    assert import_check.main(["acme-core"]) == 0
    build, venv, install, inner = fake.calls
    # character for character `release.yaml`'s build step and `poe build-needs`
    assert build[:6] == ["uv", "build", "--package", "acme-core", "--no-sources", "-o"]
    assert build[6].endswith("/dist")
    assert venv[:2] == ["uv", "venv"]
    assert venv[2].endswith("/venv")
    # `--no-sources` pins the recipe, not a behaviour: this has to stay the same command
    # the compat cell runs (measured -- for a wheel install the flag is inert)
    assert install[:6] == ["uv", "pip", "install", "--python", venv[2], "--no-sources"]
    assert install[6].endswith(".whl")
    # and the walk runs under the environment's own interpreter, told where to expect it
    assert inner[0] == str(Path(venv[2]) / "bin" / "python")
    assert inner[1] == str(SCRIPT)
    assert inner[2:] == ["--walk", "acme_core", "--expect-prefix", venv[2]]


def test_the_python_flag_is_passed_to_uv_venv(workspace, fake_uv) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake = fake_uv(root)
    assert import_check.main(["acme-core", "--python", "3.11"]) == 0
    venv = fake.calls[1]
    assert venv[:4] == ["uv", "venv", "--python", "3.11"]


def test_a_given_wheel_is_not_rebuilt(workspace, fake_uv, tmp_path: Path) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake = fake_uv(root)
    wheel = tmp_path / "acme_core-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"")
    assert import_check.main(["acme-core", "--wheel", str(wheel)]) == 0
    assert [call[:2] for call in fake.calls[:2]] == [["uv", "venv"], ["uv", "pip"]]
    assert not any(call[:2] == ["uv", "build"] for call in fake.calls)
    assert str(wheel) in fake.calls[1]
    assert fake.calls[2][1:] == [
        str(SCRIPT),
        "--walk",
        "acme_core",
        "--expect-prefix",
        fake.calls[0][-1],
    ]


def test_the_module_name_honours_tool_flit_module(workspace, fake_uv) -> None:
    """`check_workspace.Member.module`'s rule, duplicated because these run by path."""
    root = workspace({"acme-core": {"version": "1.0.0", "module_name": "acme"}})
    fake = fake_uv(root)
    assert import_check.main(["acme-core"]) == 0
    assert fake.calls[3][2:4] == ["--walk", "acme"]


def test_the_outer_exit_status_is_the_inner_one(workspace, fake_uv) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake_uv(root, inner_returncode=1)
    assert import_check.main(["acme-core"]) == 1


def test_a_failed_build_is_named_not_walked_around(workspace, fake_uv, capsys) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake_uv(root, build_returncode=2)
    assert import_check.main(["acme-core"]) == 1
    assert "`uv` failed with exit code 2" in capsys.readouterr().err


def test_a_virtual_member_has_no_wheel_to_check(workspace, fake_uv, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.0.0"},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    fake_uv(root)
    assert import_check.main(["acme-tools"]) == 1
    err = capsys.readouterr().err
    assert "`acme-tools` is a virtual member (`[tool.uv] package = false`)" in err
    assert "there is no released wheel for anything to import" in err


def test_an_unknown_distribution_names_the_ones_there_are(
    workspace, fake_uv, capsys
) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake_uv(root)
    assert import_check.main(["acme-nope"]) == 1
    err = capsys.readouterr().err
    assert "`acme-nope` is not a member of this workspace" in err
    assert "known: acme-core" in err


def test_the_name_is_canonicalised(workspace, fake_uv) -> None:
    """PEP 503: `Acme_Core` and `acme-core` are the same distribution."""
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake = fake_uv(root)
    assert import_check.main(["Acme_Core"]) == 0
    assert fake.calls[0][3] == "Acme_Core"


def test_keep_leaves_the_directory_and_says_where(workspace, fake_uv, capsys) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    fake_uv(root)
    assert import_check.main(["acme-core", "--keep"]) == 0
    kept = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("kept ")
    ]
    assert len(kept) == 1
    directory = Path(kept[0].removeprefix("kept "))
    assert directory.is_dir()
    shutil.rmtree(directory, ignore_errors=True)


# --- fix round 1: `SystemExit` is a failure, and entry points are not import surface -------
# H1. `SystemExit` is a `BaseException`, so it escaped `except Exception`, escaped `walk()`
# and escaped `main()`: the process exited with the module's own code having printed
# NOTHING. `sys.exit(0)` anywhere in the tree turned the compat cell's gate green.


def test_an_entry_point_is_skipped_rather_than_run(tmp_path: Path) -> None:
    """`__main__.py` is a CLI, not import surface: importing it runs it against the
    walker's own argv, and its `sys.exit()` used to end the walk silently."""
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/one.py": "VALUE = 1\n",
            "pkg/__main__.py": "import sys\n\n\ndef main():\n    return 0\n\n\nsys.exit(main())\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert "skipped 1 entry point(s) (__main__): pkg.__main__" in out
    assert "OK    2 modules imported in" in out


def test_a_module_that_exits_is_a_failure_not_a_silent_pass(tmp_path: Path) -> None:
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/good.py": "VALUE = 1\n",
            "pkg/quits.py": "raise SystemExit(0)\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    out = proc.stdout
    assert "FAIL  pkg.quits: SystemExit: 0" in out
    assert "quits.py:1 in <module>: raise SystemExit(0)" in out
    assert "FAIL  1 of 3 modules failed to import" in out


def test_a_top_level_module_that_exits_is_reported(tmp_path: Path) -> None:
    """Every path out of the walk prints at least one line: the absence of `OK` is the only
    thing a reader would otherwise notice about a silent pass."""
    root = scratch_package(tmp_path, {"pkg/__init__.py": "import sys\n\nsys.exit(7)\n"})
    proc = walk(root, "pkg")
    assert proc.returncode == 1
    assert "FAIL  pkg: SystemExit: 7" in proc.stdout


def test_a_package_that_exits_during_the_walk_is_reported(tmp_path: Path) -> None:
    """`pkgutil.walk_packages` imports each package it finds, and its own handlers do not
    cover `SystemExit` -- so the generator died and took the whole walk with it."""
    root = scratch_package(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/aaa/__init__.py": "import sys\n\nsys.exit(3)\n",
            "pkg/aaa/child.py": "VALUE = 1\n",
            "pkg/zzz.py": "VALUE = 1\n",
        },
    )
    proc = walk(root, "pkg")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    out = proc.stdout
    assert "FAIL  pkg.aaa: SystemExit: 3" in out
    assert "the walk itself was cut short by SystemExit: 3" in out


def test_the_prefix_is_asserted_for_every_module_not_only_the_top(
    tmp_path: Path,
) -> None:
    """A package can pull a submodule in from elsewhere on the path -- here by extending
    its own `__path__`, which is what a plugin package or a stale `.pth` does for real -- so
    the wheel-only claim has to be checked per module, not once at the top."""
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    (outside / "stray.py").write_text("VALUE = 2\n", encoding="utf-8")
    scratch_package(
        inside,
        {
            "pkg/__init__.py": f"__path__.append({str(outside)!r})\n",
            "pkg/local.py": "VALUE = 1\n",
        },
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--walk", "pkg", "--expect-prefix", str(inside)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(inside)},
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    out = proc.stdout
    # the top-level module IS under the prefix, and passes its own check
    assert "pkg imported from" in out
    assert f"FAIL  pkg.stray: imported from {outside}" in out
    assert "which is not under" in out
    # the honest submodule is untouched
    assert "pkg.local" not in out
