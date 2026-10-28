"""Pytest configuration for the sphinx-ub-directives suite.

The Sphinx application lifecycle (``test_app``) and the warning normalisation are the
workspace's, in ``packages/sphinx-needs-testkit``; the two fixtures below are what that
plugin deliberately does not know: where this suite's tests live, and what every build of
it must assert besides the test (nothing, here).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

# The order is load-bearing: the testkit's `sphinx_test_tempdir` must win over
# `sphinx.testing.fixtures`' one, and where two plugins define a fixture the one
# registered LAST wins (the testkit's `test_app` asserts it).
pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    """This suite's own ``tests`` directory."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def test_app_events() -> Sequence[tuple[str, Callable[..., object], int]]:
    """Sphinx events every ``test_app`` build of this suite connects: none."""
    return ()
