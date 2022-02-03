from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needtable")])
def test_doc_build_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SP_TOO_001" in html
    assert 'id="needtable-index-0"' in html

    # check table caption exists
    assert "Test table caption" in html

    html_path = str(Path(app.outdir, "index.html"))

    from lxml import html as html_parser

    tree = html_parser.parse(html_path)
    tables = tree.xpath("//table")

    # check if there are only 2 needtables in this document
    cnt = 0
    for table in tables:
        if "NEEDS_TABLE" in table.attrib["class"]:
            cnt += 1
    assert cnt == 2

    # check only one needtable with caption
    # assert len(tree.xpath("//section/table/caption")) == 1
    assert len(tree.xpath("//table/caption")) == 1

    # check needtable has correct caption
    assert tree.xpath("//table/caption/span")[0].text == "Test table caption"

    # Test classes
    assert "awesome_test_class" in html
    assert "another_test_class" in html

    # Test colwidths
    colwidths_html_path = Path(app.outdir, "test_colwidths.html").read_text()
    assert '<col style="width: 50%" />' in colwidths_html_path
    assert '<col style="width: 40%" />' in colwidths_html_path
    assert '<col style="width: 10%" />' in colwidths_html_path


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needtable")])
def test_doc_needtable_options(create_app, buildername):
    import sphinx

    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

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


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needtable")])
def test_doc_needtable_styles(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "test_styles.html").read_text()
    assert "style_1" in html
    assert "NEEDS_TABLE" in html
    assert "NEEDS_DATATABLES" in html


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needtable")])
def test_doc_needtable_parts(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "test_parts.html").read_text()
    assert "table_001.1" in html
    assert "table_001.2" in html
    assert "table_001.3" in html
    assert 'class="need_part' in html


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_needtable")])
def test_doc_needtable_titles(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "test_titles.html").read_text()
    assert '<th class="head"><p>Headline</p></th>' in html
    assert '<th class="head"><p>To this need123</p></th>' in html
