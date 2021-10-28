from sphinx_testing import with_app


@with_app(buildername="needs", srcdir="doc_test/doc_needsfile")
def test_doc_build_html(app, status, warning):
    app.build()
