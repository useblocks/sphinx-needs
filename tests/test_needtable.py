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


@with_app(buildername="xml", srcdir="doc_test/doc_needtable")
def test_doc_needtable_caption(app, status, warning):
    app.build()
    xml = Path(app.outdir, "index.xml")

    import xml.etree.ElementTree as ElementTree

    tree = ElementTree.parse(xml)

    # check if there are only 2 needtables in this document
    cnt = 0
    for el in tree.findall("section/table"):
        if el.attrib["classes"] == "NEEDS_TABLE rtd-exclude-wy-table":
            assert el.attrib["ids"].startswith("needtable-index-")
            cnt += 1
    assert cnt == 2

    # check only one needtable with caption/title
    assert len(tree.findall("section/table/title")) == 1

    # check needtable has correct caption/title
    assert tree.find("section/table/title").text == "Test table caption"


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
