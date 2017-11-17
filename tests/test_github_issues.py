from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_github_issue_21')
def test_doc_github_21(app, status, warning):
    """
    https://github.com/useblocks/sphinxcontrib-needs/issues/21
    """
    #app.builder.build_all()
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>Some needs' in html
    assert 'OWN_ID_123' in html
