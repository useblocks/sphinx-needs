from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/basic_doc")
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>Basic Document' in html
    assert 'ASuccessfulTest' in html


@with_app(buildername='html', srcdir='doc_test/pytest_6_2')
def test_doc_build_html_for_pytest_6_2(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text(encoding="utf-8")

    assert 'Tests: 6' in html
    assert 'Failures: 2' in html
    assert 'Errors: 0' in html
    assert 'Skips: 3' in html
