"""Spawning a Sphinx build as a subprocess, for every suite in this workspace.

One function, because there is one right answer to a question each suite had been
answering for itself -- and answering the same way, wrongly, at every site.
"""

from __future__ import annotations

import os
import sys


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
    changes in argv[0] and nothing else. The answer lives HERE rather than in each suite
    because it is the workspace's answer, not one suite's: sphinx-test-reports adopts it by
    importing it (useblocks/sphinx-test-reports#149).

    :param args: Everything after ``sphinx-build`` would have come, in the same order.
        ``os.PathLike`` is spelled out with :func:`os.fspath` rather than left to
        ``subprocess``, so what comes back is a list of ``str`` whatever was passed --
        a ``Path`` srcdir is the usual case, and a list that mixes the two logs badly and
        compares worse.
    :return: ``[sys.executable, "-m", "sphinx", *args]``.
    """
    return [sys.executable, "-m", "sphinx", *(os.fspath(a) for a in args)]
