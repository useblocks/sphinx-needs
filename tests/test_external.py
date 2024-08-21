import json
from pathlib import Path

import pytest
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/external_doc"}],
    indirect=True,
)
def test_external_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" href="http://my_company.com/docs/v1/index.html#TEST_02">'
        "EXT_TEST_02</a>" in html
    )

    assert (
        '<p>Test need ref: <a class="external_link reference external"'
        ' href="http://my_company.com/docs/v1/index.html#TEST_01">EXT_TEST_01</a></p>'
        in html
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/external_doc"}],
    indirect=True,
)
def test_external_json(test_app, snapshot):
    app = test_app
    app.build()
    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/external_doc"}],
    indirect=True,
)
def test_external_needs_warnings(test_app):
    import os
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = os.path.join(srcdir, "_build")

    out = subprocess.run(
        ["sphinx-build", "-b", "html", srcdir, out_dir], capture_output=True
    )
    assert (
        "WARNING: Couldn't create need EXT_TEST_03. Reason: The need-type (i.e. `ask`) is not"
        " set in the project's 'need_types' configuration in conf.py."
        in out.stderr.decode("utf-8")
    )
