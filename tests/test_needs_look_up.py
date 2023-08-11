import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_lut", "srcdir": "doc_test/doc_needs_builder"}], indirect=True
)
def test_doc_needs_id_builder(test_app):
    app = test_app
    app.build()

    needs_json = Path(app.outdir, "needs_lut.json")
    with open(needs_json) as needs_file:
        needs_file_content = needs_file.read()

    needs_list = json.loads(needs_file_content)
    assert needs_list["TC_NEG_001"]
