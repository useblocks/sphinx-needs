from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/broken_syntax_doc")
def test_doc_broken_syntax(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()  # noqa: F841
