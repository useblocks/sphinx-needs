import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_id", "srcdir": "doc_test/docs_needs_id_builder"}], indirect=True
)
def test_doc_needs_id_builder(test_app):
    import os

    from sphinx_needs.utils import unwrap

    app = test_app
    app.build()
    out_dir = app.outdir
    env = unwrap(app.env)
    needs = env.needs_all_needs.values()
    needs_per_id_build_path = app.config.needs_per_id_build_path
    needs_id_path = os.path.join(out_dir, needs_per_id_build_path)
    assert os.path.exists(needs_id_path)
    for need in needs:
        need_id = need["id"]
        need_file_name = f"{need_id}.json"
        needs_json = Path(needs_id_path, need_file_name)
        assert os.path.exists(needs_json)
        with open(needs_json) as needs_file:
            needs_file_content = needs_file.read()
        needs_list = json.loads(needs_file_content)
        assert needs_list[need_id]["docname"]
