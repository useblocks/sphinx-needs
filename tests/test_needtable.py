from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/doc_needtable')
def test_doc_build_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'SP_TOO_001' in html
    assert 'id="needtable-index-0"' in html


@with_app(buildername='html', srcdir='doc_test/doc_needtable')
def test_doc_needtable_options(app, status, warning):
    app.build()
    html = (app.outdir / 'test_options.html').read_text()
    assert 'SP_TOO_003' in html
    assert 'id="needtable-test_options-0"' in html
    assert 'id="needtable-test_options-1"' in html
    column_order = """
<tr class="row-odd"><th class="head">Incoming</th>
<th class="head">ID</th>
<th class="head">Tags</th>
<th class="head">Status</th>
<th class="head">Title</th>
"""
    assert column_order in html


@with_app(buildername='html', srcdir='doc_test/doc_needtable')
def test_doc_needtable_styles(app, status, warning):
    app.build()
    html = (app.outdir / 'test_styles.html').read_text()
    assert 'style_1' in html
    assert 'NEEDS_TABLE' in html
    assert 'NEEDS_DATATABLES' in html
