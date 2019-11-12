from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/needs_dyn_function_doc')
def test_needs_build_html(app, status, warning):
    app.build()
    pass
