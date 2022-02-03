import json
import os
from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("needs", "doc_test/doc_export_id")])
def test_export_id(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    content = Path(app.outdir, "needs.json").read_text()
    assert "filters" in content

    content_obj = json.loads(content)
    assert content_obj is not None
    assert "created" in content_obj
    assert "FLOW_1" in content_obj["versions"]["1.0"]["filters"]
    assert "TABLE_1" in content_obj["versions"]["1.0"]["filters"]
    assert "LIST_1" in content_obj["versions"]["1.0"]["filters"]


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_export_id")])
def test_export_id_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    assert not os.path.exists(os.path.join(app.outdir, "needs.json"))
