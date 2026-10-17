"""A ``needextend`` leaves no node behind, on every path of ``process_need_nodes`` (#2296).

The handler removes the ``Needextend`` nodes before the output is written, since no
writer has a visitor for them. It used to do so only after two early returns: one for a
project with no needs, and one for ``needs_include_needs = False``. On either path the
node reached the HTML writer, and the build stopped with ``NotImplementedError``.
"""

from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings


def project(conf: str, index: str) -> list[dict[str, object]]:
    """``test_app`` parameters for an HTML build of one page."""
    return [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
        }
    ]


@pytest.mark.parametrize(
    "test_app",
    project(
        'extensions = ["sphinx_needs"]\n',
        "Test\n====\n\n.. needextend:: NOPE\n   :status: done\n",
    ),
    indirect=True,
)
def test_needextend_in_a_project_without_needs(test_app: Sphinx):
    """The needextend matches nothing and says so, as in a project with needs."""
    test_app.build()
    assert build_warnings(test_app) == [
        "<srcdir>/index.rst:4: WARNING: Provided id 'NOPE' for needextend does not exist. [needs.needextend]",
    ]
    assert Path(test_app.outdir, "index.html").is_file()


@pytest.mark.parametrize(
    "test_app",
    project(
        'extensions = ["sphinx_needs"]\nneeds_include_needs = False\n',
        "Test\n====\n\n.. req:: A\n   :id: REQ_001\n\n"
        ".. needextend:: REQ_001\n   :status: done\n",
    ),
    indirect=True,
)
def test_needextend_with_include_needs_false(test_app: Sphinx):
    """The need is left out of the output, and so is the needextend's node."""
    test_app.build()
    assert build_warnings(test_app) == []
    html = Path(test_app.outdir, "index.html").read_text()
    assert "REQ_001" not in html
