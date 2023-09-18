import json
from pathlib import Path

import pytest
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_lut", "srcdir": "doc_test/doc_needs_builder"}], indirect=True
)
def test_doc_needs_lut_builder(test_app, snapshot):
    app = test_app
    app.build()
    needs_list = json.loads(Path(app.outdir, "needs_lut.json").read_text())
    print(needs_list)
    print(snapshot(exclude=props("created")))
    assert needs_list == snapshot(exclude=props("created"))
