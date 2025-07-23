import json
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_list_needs", "no_plantuml": True}],
    indirect=True,
)
def test_list_needs(test_app, snapshot):
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).splitlines()
    assert warnings == []

    needs = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    assert needs == snapshot(exclude=props("created", "project", "creator"))
