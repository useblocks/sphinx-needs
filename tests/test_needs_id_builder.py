import json
import os
from pathlib import Path

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_id", "srcdir": "doc_test/doc_needs_builder"}], indirect=True
)
def test_doc_needs_id_builder(test_app):
    app = test_app
    app.build()
    out_dir = app.outdir
    env = app.env
    data = SphinxNeedsData(env)
    needs_config = NeedsSphinxConfig(env.config)
    needs = data.get_or_create_needs().values()  # We need a list of needs for later filter checks
    needs_build_json_per_id_path = needs_config.build_json_per_id_path
    needs_id_path = os.path.join(out_dir, needs_build_json_per_id_path)
    assert os.path.exists(needs_id_path)
    for need in needs:
        need_id = need["id"]
        need_file_name = f"{need_id}.json"
        needs_json = Path(needs_id_path, need_file_name)
        assert os.path.exists(needs_json)
        with open(needs_json) as needs_file:
            needs_file_content = needs_file.read()
        needs_list = json.loads(needs_file_content)
        assert needs_list["versions"]["1.0"]["needs"][need_id]["docname"]
