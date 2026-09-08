"""Tests for the testkit's subprocess argv (``sphinx_needs_testkit._subprocess``).

Two of these pin the helper's contract; the third is a fence over this whole tree, and it
is the one that matters after the conversion. A site that spells the build command as the
bare word again is not a failing test -- it passes, out of whatever environment the
machine's ``PATH`` points at -- so nothing would report it. The fence does.

They live in THIS suite for the same reason the warning tests do, and the note at the top
of ``test_testkit_warnings.py`` is that reason: sphinx-needs' is the only one of the three
suites a test of the kit can join without a fourth suite, task and CI cell.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import sphinx

from sphinx_needs_testkit import sphinx_build_command

# Assembled from pieces, deliberately: the last test scans every file in this tree for the
# literal, and it must not find one in the file that forbids it.
_BARE = "sphinx" + "-build"
_LITERAL = re.compile("[\"']" + _BARE + "[\"']")


def test_the_argv_is_this_interpreter_and_a_list_of_strings() -> None:
    argv = sphinx_build_command("-b", "html", Path("src"), Path("out"))
    assert argv[:3] == [sys.executable, "-m", "sphinx"]
    assert argv[3:] == ["-b", "html", os.fspath(Path("src")), os.fspath(Path("out"))]
    # a `Path` that reached `subprocess` unconverted would run, and then read back as a
    # `PosixPath(...)` repr in every log and comparison
    assert all(isinstance(argument, str) for argument in argv), argv


def test_the_spawned_process_is_the_sphinx_this_interpreter_imports() -> None:
    version = subprocess.run(
        sphinx_build_command("--version"), capture_output=True, text=True, check=True
    )
    # the VERSION, not the program name in front of it: measured, sphinx 7.4 answers
    # `__main__.py 7.4.7` here and sphinx 9.1 `sphinx-build 9.1.0`, because only the newer
    # series names the console script when it was not the console script that was run. The
    # version is the half that says WHICH sphinx the subprocess got, which is the claim.
    # Both series answer on stdout; neither writes anything to stderr.
    assert version.stdout.split()[-1:] == [sphinx.__version__], version


def test_no_test_in_this_tree_spawns_the_bare_command() -> None:
    tests_dir = Path(__file__).parent
    offenders = [
        f"{path.relative_to(tests_dir)}:{number}: {line.strip()}"
        for path in sorted(tests_dir.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1)
        if _LITERAL.search(line)
    ]
    assert not offenders, (
        "these lines spawn the build command resolved on PATH rather than through the "
        "interpreter under test; build the argv with "
        "`sphinx_needs_testkit.sphinx_build_command` instead:\n" + "\n".join(offenders)
    )
