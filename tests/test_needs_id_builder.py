import json
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs_id", "srcdir": "doc_test/doc_needs_builder"}],
    indirect=True,
)
def test_doc_needs_id_builder(test_app, snapshot):
    app = test_app
    app.build()
    data = SphinxNeedsData(app.env)
    needs_config = NeedsSphinxConfig(app.config)
    needs_id_path = Path(app.outdir, needs_config.build_json_per_id_path)
    data = {
        path.name: json.loads(path.read_text()) for path in needs_id_path.glob("*.json")
    }
    assert data == snapshot(exclude=props("created", "project", "creator"))
