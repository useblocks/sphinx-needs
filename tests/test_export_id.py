import json
import os
from pathlib import Path

import pytest
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_export_id"}],
    indirect=True,
)
def test_export_id(test_app, snapshot):
    app = test_app
    app.build()
    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_data == snapshot(exclude=props("created", "project"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_export_id"}],
    indirect=True,
)
def test_export_id_html(test_app):
    app = test_app
    app.build()
    assert not os.path.exists(os.path.join(app.outdir, "needs.json"))
