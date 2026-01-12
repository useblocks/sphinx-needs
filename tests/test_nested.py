from __future__ import annotations

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api.need import get_needs_view


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_nested", "no_plantuml": False}],
    indirect=True,
)
def test_nested(test_app: SphinxTestApp, snapshot, get_warnings_list):
    app = test_app
    app.build()
    warnings = get_warnings_list(app)
    assert warnings == snapshot

    needs = list(get_needs_view(app).values())
    assert needs == snapshot
