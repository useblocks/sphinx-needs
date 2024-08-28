from pathlib import Path

import pytest
from docutils import __version__ as doc_ver


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()
    # We set unique ID's for node.table, so the following exception shall not occur anymore.
    assert "WARNING: Any IDs not assigned for table node" not in warnings

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
    assert len(tree.xpath("//table/caption")) == 1

    # check needtable has correct caption
    assert tree.xpath("//table/caption/span")[0].text == "Test table caption"

    # Test classes
    assert "awesome_test_class" in html
    assert "another_test_class" in html

    # Test colwidths
    colwidths_html_path = Path(app.outdir, "test_colwidths.html").read_text()

    if int(doc_ver.split(".")[1]) >= 18:
        assert '<col style="width: 50.0%" />' in colwidths_html_path
        assert '<col style="width: 40.0%" />' in colwidths_html_path
        assert '<col style="width: 10.0%" />' in colwidths_html_path
    else:
        assert '<col style="width: 50%" />' in colwidths_html_path
        assert '<col style="width: 40%" />' in colwidths_html_path
        assert '<col style="width: 10%" />' in colwidths_html_path


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_needtable_options(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "test_options.html").read_text()
    assert "SP_TOO_003" in html
    assert 'id="needtable-test_options-0"' in html
    assert 'id="needtable-test_options-1"' in html

    column_order = """
<tr class="row-odd"><th class="head"><p>Incoming</p></th>
<th class="head"><p>ID</p></th>
<th class="head"><p>Tags</p></th>
<th class="head"><p>Status</p></th>
<th class="head"><p>Title</p></th>
</tr>
"""

    assert column_order in html

    # Checks for needs_string_links in needtable
    assert "EXAMPLE_STRING_LINKS" in html
    assert (
        '<a class="reference external" href="https://github.com/useblocks/sphinxcontrib-needs/issues/404">'
        "GitHub #404</a>" in html
    )
    assert (
        '<a class="reference external" href="https://github.com/useblocks/sphinxcontrib-needs/issues/303">'
        "GitHub #303</a>" in html
    )
    assert "Sphinx-Needs docs for needs-string-links" in html

    string_column_order = """
<tr class="row-odd"><th class="head"><p>ID</p></th>
<th class="head"><p>Title</p></th>
<th class="head"><p>Config</p></th>
<th class="head"><p>Github</p></th>
</tr>
"""

    assert string_column_order in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_needtable_styles(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "test_styles.html").read_text()
    assert "style_1" in html
    assert "NEEDS_TABLE" in html
    assert "NEEDS_DATATABLES" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_needtable_parts(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "test_parts.html").read_text()
    assert "table_001.1" in html
    assert "table_001.2" in html
    assert "table_001.3" in html
    assert 'class="need_part' in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_needtable_titles(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "test_titles.html").read_text()
    assert '<th class="head"><p>Headline</p></th>' in html
    assert '<th class="head"><p>To this need123</p></th>' in html
    assert '<th class="head"><p>Special Characters!</p></th>' in html
    assert '<td class="needs_special-chars!"><p>special-chars value</p></td>' in html
