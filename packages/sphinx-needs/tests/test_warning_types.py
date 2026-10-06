"""The ``[needs.<subtype>]`` suffix of a warning is rendered exactly once (#2091).

Sphinx appends `` [type.subtype]`` to a typed warning itself when ``show_warning_types``
is on: the option exists since Sphinx 7.3 (default ``False``) and defaults to ``True``
since 8.0. Before 8.0 sphinx-needs appends the suffix itself, so it must do so only when
Sphinx will not -- on 7.4 with the option on, both appended it.
"""

import re
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

CONF = 'extensions = ["sphinx_needs"]\n'

INDEX = """\
Test
====

.. req:: A
   :id: REQ_1
   :links: REQ_MISSING
"""


def _suffixes(app: SphinxTestApp) -> list[list[str]]:
    """The ``[needs.*]`` bracket groups of each warning naming the dangling link."""
    lines = [w for w in build_warnings(app) if "REQ_MISSING" in w]
    assert len(lines) == 1, build_warnings(app)
    return [re.findall(r"\[needs\.[a-z_]+\]", line) for line in lines]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INDEX)],
            "confoverrides": {"show_warning_types": True},
        }
    ],
    indirect=True,
)
def test_suffix_once_when_sphinx_shows_warning_types(test_app: SphinxTestApp):
    """With ``show_warning_types = True`` Sphinx renders the suffix on every version
    (7.4 included), so sphinx-needs adds none: exactly one ``[needs.link_outgoing]``."""
    test_app.build()
    assert _suffixes(test_app) == [["[needs.link_outgoing]"]]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), INDEX)],
            "confoverrides": {"show_warning_types": False},
        }
    ],
    indirect=True,
)
def test_suffix_per_version_when_sphinx_hides_warning_types(test_app: SphinxTestApp):
    """With ``show_warning_types = False`` the expectation depends on the version:
    before Sphinx 8 sphinx-needs appends the suffix itself (once); from 8 on it never
    appends and Sphinx renders nothing, so the line carries no suffix at all."""
    test_app.build()
    expected = ["[needs.link_outgoing]"] if version_info < (8,) else []
    assert _suffixes(test_app) == [expected]
