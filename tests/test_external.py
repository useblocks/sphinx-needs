from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/external_doc")  # , warningiserror=True)
def test_external_html(app, status, warning):
    app.build()
    Path(app.outdir, "index.html").read_text()


@with_app(buildername="needs", srcdir="doc_test/external_doc")  # , warningiserror=True)
def test_external_json(app, status, warning):
    app.build()
    Path(app.outdir, "needs.json").read_text()
