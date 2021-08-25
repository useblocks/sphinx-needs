# -*- coding: utf-8 -*-

from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needtable")
def test_doc_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SP_TOO_001" in html
    assert 'id="needtable-index-0"' in html

    # check table caption exists
    assert "Test table caption" in html

    # check table cpation and table wrapped into figure
    figure = """
<figure class="align-default" id="needtable-index-0">
<figcaption>
<p><span class="caption-text">Test table caption<table class="NEEDS_TABLE rtd-exclude-wy-table docutils align-default">
"""
    assert figure in html

    # negative test to check table without caption
    assert '<table class="NEEDS_TABLE rtd-exclude-wy-table docutils align-default" id="needtable-index-1">' in html


@with_app(buildername="html", srcdir="doc_test/doc_needtable")
def test_doc_needtable_options(app, status, warning):
    import sphinx

    app.build()
    html = Path(app.outdir, "test_options.html").read_text()
    assert "SP_TOO_003" in html
    assert 'id="needtable-test_options-0"' in html
    assert 'id="needtable-test_options-1"' in html

    if sphinx.version_info[0] < 2:
        column_order = """
<tr class="row-odd"><th class="head">Incoming</th>
<th class="head">ID</th>
<th class="head">Tags</th>
<th class="head">Status</th>
<th class="head">Title</th>
"""
    else:
        column_order = """
<tr class="row-odd"><th class="head"><p>Incoming</p></th>
<th class="head"><p>ID</p></th>
<th class="head"><p>Tags</p></th>
<th class="head"><p>Status</p></th>
<th class="head"><p>Title</p></th>
</tr>
"""

    assert column_order in html


@with_app(buildername="html", srcdir="doc_test/doc_needtable")
def test_doc_needtable_styles(app, status, warning):
    app.build()
    html = Path(app.outdir, "test_styles.html").read_text()
    assert "style_1" in html
    assert "NEEDS_TABLE" in html
    assert "NEEDS_DATATABLES" in html


@with_app(buildername="html", srcdir="doc_test/doc_needtable")
def test_doc_needtable_parts(app, status, warning):
    app.build()
    html = Path(app.outdir, "test_parts.html").read_text()
    assert "table_001.1" in html
    assert "table_001.2" in html
    assert "table_001.3" in html
    assert 'class="need_part' in html


@with_app(buildername="html", srcdir="doc_test/doc_needtable")
def test_doc_needtable_titles(app, status, warning):
    app.build()
    html = Path(app.outdir, "test_titles.html").read_text()
    assert '<th class="head"><p>Headline</p></th>' in html
    assert '<th class="head"><p>To this need123</p></th>' in html
