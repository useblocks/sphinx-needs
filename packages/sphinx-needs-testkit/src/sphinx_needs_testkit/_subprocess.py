"""Spawning a Sphinx build as a subprocess, for every suite in this workspace.

The argv, because there is one right answer to a question each suite had been answering
for itself -- and answering the same way, wrongly, at every site -- and the fence that
keeps it that way, because two suites here spawn builds and both must be walked, and the
third consumer of this module should get the fence with the helper rather than a file to
copy.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Assembled from pieces, deliberately: :func:`assert_no_bare_sphinx_build` scans a whole
# tests tree for the literal, and the module that forbids it must not contain one either.
_BARE = "sphinx" + "-build"

#: The literal at the head of an argv, followed by a closing quote OR whitespace -- so
#: ``["<bare>", …]`` and ``shlex.split("<bare> -M html")`` both match, and prose does not:
#: a mention in a docstring or a comment has a character in front of the word rather than a
#: quote (measured over both trees this walks: every mention there has one).
#: Two spellings deliberately escape it, ``"sphinx" "-build"`` and a command assembled for
#: ``shell=True``: a pattern that catches those catches prose too, and nobody writes either
#: by accident.
_LITERAL = re.compile("[\"']" + _BARE + "[\"'\\s]")


def sphinx_build_command(*args: str | os.PathLike[str]) -> list[str]:
    """argv for a SUBPROCESS build through the interpreter running the tests.

    The bare word ``sphinx-build`` is resolved on ``PATH``, which is not the environment
    under test: from an unactivated shell, or from any shell whose ``PATH`` happens to
    carry another Sphinx first, the child process is a different Sphinx and a different
    sphinx-needs -- or none at all, and the test dies in ``subprocess`` with
    ``FileNotFoundError`` rather than reporting anything about the build. Measured on
    sphinx-test-reports' suite, whose three equivalent sites all failed from a bare shell
    (useblocks/sphinx-test-reports#145).

    ``python -m sphinx`` is ``sphinx.cmd.build.main``, the same entry point the
    ``sphinx-build`` console script wraps -- ``-M`` make mode included -- so a call site
    changes in argv[0] and nothing else, except that ``-m`` puts the current working
    directory on the child's ``sys.path`` where the console script put its own ``bin/``.
    That is harmless where every task in this workspace runs (a package directory with no
    top-level module to shadow one of sphinx's), and a thing to know when a suite adopts
    this from a working directory of its own. The answer lives HERE rather than in each
    suite because it is the workspace's answer, not one suite's: sphinx-test-reports adopts
    it by importing it (useblocks/sphinx-test-reports#149).

    :param args: Everything after ``sphinx-build`` would have come, in the same order.
        ``os.PathLike`` is spelled out with :func:`os.fspath` rather than left to
        ``subprocess``, so what comes back is a list of ``str`` whatever was passed --
        a ``Path`` srcdir is the usual case, and a list that mixes the two logs badly and
        compares worse.
    :return: ``[sys.executable, "-m", "sphinx", *args]``.
    """
    return [sys.executable, "-m", "sphinx", *(os.fspath(a) for a in args)]


def assert_no_bare_sphinx_build(tests_dir: Path) -> None:
    """Fail naming every ``file:line`` under ``tests_dir`` that spells the build command as
    the bare word.

    The fence for :func:`sphinx_build_command`, and it reads the SOURCE rather than a
    result because there is no result to read: a site that spawns the bare word passes,
    out of whatever environment the machine's ``PATH`` happens to point at, and every CI
    job in this workspace runs where that environment is the right one. Nothing else would
    ever report the regression.

    It lives here rather than in one suite because two suites in this workspace spawn
    builds and both must be walked -- and because the third consumer of this module,
    sphinx-test-reports, gets the fence with the helper rather than a file to copy.

    An explicit ``AssertionError`` rather than a bare ``assert``: pytest rewrites
    assertions in test modules and plugins, not in a package imported by name, so a bare
    one here would report ``assert not offenders`` and nothing about which lines they are.

    :param tests_dir: The suite's own ``tests`` directory, walked recursively for ``*.py``.
        Read with ``errors="replace"`` -- one mis-encoded byte in one fixture module should
        not turn this into a ``UnicodeDecodeError`` naming the fence instead of the file.
    :raises NotADirectoryError: If ``tests_dir`` is not a directory. A walk of nothing
        reports nothing, so a mistyped argument -- which the next caller writes by hand, in
        another repository -- would otherwise be a permanently green fence.
    :raises AssertionError: If any line matches, listing every one of them.
    """
    if not tests_dir.is_dir():
        raise NotADirectoryError(f"not a tests directory: {tests_dir}")
    offenders = [
        f"{path.relative_to(tests_dir)}:{number}: {line.strip()}"
        for path in sorted(tests_dir.rglob("*.py"))
        for number, line in enumerate(
            path.read_text(encoding="utf8", errors="replace").splitlines(), 1
        )
        if _LITERAL.search(line)
    ]
    if offenders:
        raise AssertionError(
            "these lines spawn the build command resolved on PATH rather than through the "
            "interpreter under test; build the argv with "
            "`sphinx_needs_testkit.sphinx_build_command` instead. A line that only names "
            "the command in prose is a false positive of a fence that reads source, not "
            "intent -- reword it.\n" + "\n".join(offenders)
        )
