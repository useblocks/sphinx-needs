"""A warning's ``[needs.<subtype>]`` suffix is rendered at most once (#2091)."""

import re
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

INDEX = "Test\n====\n\n.. req:: A\n   :id: REQ_1\n   :links: REQ_MISSING\n"
ONCE = ["[needs.link_outgoing]"]


def _app(show: bool) -> dict:
    conf = f'extensions = ["sphinx_needs"]\nshow_warning_types = {show}\n'
    return {"files": [(Path("conf.py"), conf), (Path("index.rst"), INDEX)]}


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        # Sphinx renders the suffix itself, so sphinx-needs adds none
        pytest.param(_app(True), ONCE, id="on"),
        # before Sphinx 8 sphinx-needs appends it; from 8 nothing renders it
        pytest.param(_app(False), ONCE if version_info < (8,) else [], id="off"),
    ],
    indirect=["test_app"],
)
def test_the_type_suffix_is_rendered_at_most_once(test_app: SphinxTestApp, expected):
    test_app.build()
    lines = [w for w in build_warnings(test_app) if "REQ_MISSING" in w]
    assert [re.findall(r"\[needs\.[a-z_]+\]", line) for line in lines] == [expected]
