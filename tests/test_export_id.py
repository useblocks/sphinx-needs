import json
import os
from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="needs", srcdir="doc_test/doc_export_id")
def test_export_id(app, status, warning):
    app.build()
    content = Path(app.outdir, "needs.json").read_text()
    assert "filters" in content

    content_obj = json.loads(content)
    assert content_obj is not None
    assert "created" in content_obj
    assert "FLOW_1" in content_obj["versions"]["1.0"]["filters"]
    assert "TABLE_1" in content_obj["versions"]["1.0"]["filters"]
    assert "LIST_1" in content_obj["versions"]["1.0"]["filters"]


@with_app(buildername="html", srcdir="doc_test/doc_export_id")
def test_export_id_html(app, status, warning):
    app.build()
    assert not os.path.exists(os.path.join(app.outdir, "needs.json"))
