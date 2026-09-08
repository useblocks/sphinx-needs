"""Tests for the testkit's subprocess argv (``sphinx_needs_testkit._subprocess``).

Two of these pin the argv helper's contract, three pin the fence's, and the sixth points
the fence at this tree -- the one that matters now that no test in it spawns a build at
all. A site that spells the build command as the bare word again is not a failing test: it
passes, out of whatever environment the machine's ``PATH`` points at, so nothing would
report it. The fence does.

The fence's three are here because it is a published kit function now, and its two call
sites only ever assert that it does NOT fire -- which a fence-shaped no-op would satisfy
too. They pin the three halves nothing else can see: that it raises at all, that the walk
is recursive, and that a ``tests_dir`` naming no directory is loud rather than green.

The walk itself is the kit's (``assert_no_bare_sphinx_build``) because the tree that must
never spawn a build and the one that legitimately does are both walked; sphinx-mounts calls
it from a module of its own. These
unit tests live in THIS suite for the same reason the warning tests do, and the note at the
top of ``test_testkit_warnings.py`` is that reason: sphinx-needs' is the only one of the
three suites a test of the kit can join without a fourth suite, task and CI cell.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import sphinx

from sphinx_needs_testkit import assert_no_bare_sphinx_build, sphinx_build_command

# the fence's own tests need the literal it forbids; assembled from pieces so that this
# module stays exempt from the walk it is the entry point for
_BARE = "sphinx" + "-build"


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


def test_the_fence_fires_and_names_the_file_and_line_below_the_top_level(
    tmp_path: Path,
) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.py").write_text(
        'run(["' + _BARE + '", "-M"])\n', encoding="utf8"
    )
    # through `Path` so that the separator is the platform's: the walk reports what
    # `relative_to` gives it, which is a backslash on Windows
    located = re.escape(f"{Path('sub', 'x.py')}:1")
    with pytest.raises(AssertionError, match=located) as caught:
        assert_no_bare_sphinx_build(tmp_path)
    assert "sphinx_build_command" in str(caught.value)


def test_the_fence_passes_a_tree_that_only_names_the_command_in_prose(
    tmp_path: Path,
) -> None:
    (tmp_path / "conf.py").write_text(
        f'"""The ``{_BARE}`` console script is not what this project runs."""\n',
        encoding="utf8",
    )
    assert_no_bare_sphinx_build(tmp_path)


def test_a_tests_dir_that_is_no_directory_is_loud(tmp_path: Path) -> None:
    # a walk of nothing reports nothing, so this is the difference between a mistyped
    # argument and a fence that is green for ever
    a_file = tmp_path / "conftest.py"
    a_file.write_text("", encoding="utf8")
    for wrong in (tmp_path / "missing", a_file):
        with pytest.raises(NotADirectoryError, match=re.escape(str(wrong))):
            assert_no_bare_sphinx_build(wrong)


def test_no_test_in_this_tree_spawns_the_bare_command() -> None:
    assert_no_bare_sphinx_build(Path(__file__).parent)


def test_no_test_in_this_tree_builds_in_a_subprocess() -> None:
    """The other half: the kit's argv helper is not for THIS suite either.

    ``assert_no_bare_sphinx_build`` guards the bare word, which a site built with
    ``sphinx_build_command`` never contains -- and that argv is exactly the shape all 28
    converted sites had. This walk is what makes "no test in this suite spawns a build" a
    fenced claim rather than a description of today.
    """
    here = Path(__file__).resolve()
    offenders = [
        f"{path.relative_to(here.parent)}:{number}"
        for path in sorted(here.parent.rglob("*.py"))
        if path.resolve() != here
        for number, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1)
        if "sphinx_build_command(" in line
    ]
    assert not offenders, (
        "this suite builds in process: `test_app` / `make_app` for the build, "
        "`build_warnings(app)` for the warnings, `app._status` for the status text, "
        "`pytest.raises` for the failures -- see the 'Rendering PlantUML is opt in' "
        "paragraph in packages/sphinx-needs/AGENTS.md:\n" + "\n".join(offenders)
    )
