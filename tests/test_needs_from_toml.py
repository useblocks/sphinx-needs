import json
from pathlib import Path

import pytest
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needs_from_toml(test_app, snapshot):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    assert data == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )
