import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/external_doc")])
def test_external_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" href="http://my_company.com/docs/v1/index.html#TEST_02">'
        "EXT_TEST_02</a>" in html
    )


@pytest.mark.parametrize("buildername, srcdir", [("needs", "doc_test/external_doc")])
def test_external_json(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    external_need = needs["versions"]["1.0"]["needs"]["EXT_TEST_01"]
    assert external_need["external_url"] == "http://my_company.com/docs/v1/index.html#TEST_01"
    assert external_need["external_css"] == "external_link"
    assert external_need["is_external"] is True
