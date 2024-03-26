import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needsfile"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    needs_json_path = Path(app.outdir, "needs.json")

    assert needs_json_path.exists()

    needs_json_content = needs_json_path.read_text()
    nj = json.loads(needs_json_content)

    for version, vdata in nj["versions"].items():
        if nj["current_version"] == version:
            for need_id, need_data in vdata["needs"].items():
                assert "lineno" in need_data
