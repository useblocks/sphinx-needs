"""Assert the Sphinx version a tox leg claims to be testing.

This exists because the claim was false. `tox.ini` pinned
`sphinx7: sphinx>=7.4,<8`, the CI matrix listed `py312-sphinx7`, and the leg
installed Sphinx **9.1.0** — the `testing` dependency group installs after
`deps` and re-resolves, and `myst-parser>=4.0.0` now resolves to 5.1.0, whose
own floor is `sphinx>=8`. So the declared floor had never been exercised,
locally or in CI, while a build report asserted that it had.

Pinning it down is only half a fix, because the same thing can happen again the
next time a test dependency raises its floor. The other half is measuring the
outcome, which is this module: each leg exports
``SPHINX_MOUNTS_EXPECT_SPHINX`` and the environment has to match it.

Skipped when the variable is unset, so a bare ``pytest`` run in a developer's
own environment is unaffected.
"""

from __future__ import annotations

import os

import pytest
import sphinx


def test_the_installed_sphinx_matches_this_leg() -> None:
    """The leg's name and its Sphinx major version must agree."""
    expected = os.environ.get("SPHINX_MOUNTS_EXPECT_SPHINX")
    if not expected:
        pytest.skip("SPHINX_MOUNTS_EXPECT_SPHINX is unset (not a tox leg)")
    assert sphinx.version_info[0] == int(expected), (
        f"this leg declares Sphinx {expected}.x but has "
        f"{sphinx.__version__} installed. A transitive dependency has almost "
        f"certainly raised its Sphinx floor — see constraints/sphinx7.txt."
    )
