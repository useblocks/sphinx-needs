"""No test in this suite spawns the build command resolved on ``PATH``.

The two subprocess builds here (``test_example.py``, ``test_bazel.py``) both sit behind
``@pytest.mark.bazel``: ``poe test-mounts`` deselects them, and the one CI job that does run
them passes whatever argv[0] says, because inside a CI environment the bare word resolves to
the right Sphinx anyway. So a regression at either site has no result to fail -- which is
why this reads the SOURCE, and why it is NOT marked ``bazel`` itself: it has to run in every
cell, including the ones with no ``bazel`` on ``PATH``.

The walk is the workspace's, in ``sphinx_needs_testkit``, so that this suite and
sphinx-needs' fence the same rule the same way. sphinx-codelinks has no such module because
its suite spawns no build at all.
"""

from __future__ import annotations

from pathlib import Path

from sphinx_needs_testkit import assert_no_bare_sphinx_build


def test_no_test_in_this_tree_spawns_the_bare_command() -> None:
    assert_no_bare_sphinx_build(Path(__file__).parent)
