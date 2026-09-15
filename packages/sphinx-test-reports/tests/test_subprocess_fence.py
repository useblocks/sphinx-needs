"""No test in this suite spawns the build command resolved on ``PATH``.

Three sites here did (``test_env.py``, ``test_test_file.py``, ``test_test_ctest_file.py``),
and all three failed from an unactivated shell -- the bare word resolves to whatever Sphinx
``PATH`` happens to carry first, which is not the environment under test, and to nothing at
all when there is none. That is useblocks/sphinx-test-reports#145; the fix travelled into
the workspace's shared test layer as ``sphinx_build_command`` rather than as three local
argv lists.

The walk is that layer's, so this suite and sphinx-mounts' fence the same rule the same
way, and a fourth suite gets the fence with the helper rather than a file to copy.
"""

from __future__ import annotations

from pathlib import Path

from sphinx_needs_testkit import assert_no_bare_sphinx_build


def test_no_test_in_this_tree_spawns_the_bare_command() -> None:
    assert_no_bare_sphinx_build(Path(__file__).parent)
