from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs_rel_base_path")
def test_external_needs_base_url_relative_path(app, status, warning):
    app.build()

    base_url_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_path == "../../../doc_needs_external_needs/_build/html"

    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" '
        'href="../../../doc_needs_external_needs/_build/html/index.html#TEST_01">'
        "EXT_TEST_01: TEST_01 DESCRIPTION</a>" in html
    )
