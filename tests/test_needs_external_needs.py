from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs_rel_base_path")
def test_doc_build_html(app, status, warning):
    import os

    app.build()

    base_url_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_path.startswith("file://")
    assert os.path.exists(base_url_path.replace("file://", ""))

    html = Path(app.outdir, "index.html").read_text()
    assert html
