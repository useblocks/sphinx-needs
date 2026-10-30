"""``create_need`` and ``add_need``: the two doors of one creation path."""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

DEPRECATED_KEY_EXT = '''\
"""Calls ``add_need`` with a deprecated key, and keeps what it warned."""

import warnings

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need


class DeprecatedKey(SphinxDirective):
    def run(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            nodes = add_need(
                self.env.app,
                self.state,
                self.env.docname,
                self.lineno,
                need_type="req",
                title="a need given a deprecated key",
                id="R_DEP",
                hide_tags=True,
            )
        # Sphinx's own deprecations (``env.app``) are not this test's
        self.env.deprecated_key_warnings = [
            (w.category.__name__, str(w.message), w.filename)
            for w in caught
            if not w.category.__name__.startswith("RemovedInSphinx")
        ]
        return nodes


def setup(app):
    app.add_directive("deprecated-key", DeprecatedKey)
    return {"parallel_read_safe": False}
'''


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "import sys\nfrom pathlib import Path\n\n"
                    "sys.path.insert(0, str(Path(__file__).parent))\n"
                    'sys.modules.pop("deprecated_key_ext", None)\n'
                    'extensions = ["sphinx_needs", "deprecated_key_ext"]\n',
                ),
                (Path("deprecated_key_ext.py"), DEPRECATED_KEY_EXT),
                (Path("index.rst"), "Keys\n====\n\n.. deprecated-key::\n"),
            ],
        }
    ],
    indirect=True,
)
def test_add_need_still_warns_once_of_a_deprecated_key(test_app: SphinxTestApp):
    """``add_need``'s own ``DeprecationWarning`` for a key it no longer reads is
    unchanged: once per call, from ``api/need.py`` (its ``stacklevel=1``), and the key
    is dropped rather than refused."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert "R_DEP" in SphinxNeedsData(app.env).get_needs_view()
    caught = app.env.deprecated_key_warnings
    assert [(category, message) for category, message, _ in caught] == [
        ("DeprecationWarning", "deprecated key found in kwargs")
    ]
    assert Path(caught[0][2]).as_posix().endswith("sphinx_needs/api/need.py")
