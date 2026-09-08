from pathlib import Path

import pytest
from docutils import __version__ as doc_ver

from sphinx_needs_testkit import assert_no_warnings


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

    # The dead `style_col` option is accepted for compatibility but warns:
    # it has never had any effect (declared but never read).
    assert warnings.count("The 'style_col' option has never had any effect") == 1
    assert "test_styles.rst" in warnings

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
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
    colwidths_html_path = Path(app.outdir, "test_colwidths.html").read_text(
        encoding="utf-8"
    )

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
    html = Path(app.outdir, "test_options.html").read_text(encoding="utf-8")
    assert "SP_TOO_003" in html
    assert 'id="needtable-test_options-0"' in html
    assert 'id="needtable-test_options-1"' in html

    column_order = """
<tr class="row-odd"><th class="head needs_col_incoming" data-col="incoming" scope="col"><p>Incoming</p></th>
<th class="head needs_col_id" data-col="id" scope="col"><p>ID</p></th>
<th class="head needs_col_tags" data-col="tags" scope="col"><p>Tags</p></th>
<th class="head needs_col_status" data-col="status" scope="col"><p>Status</p></th>
<th class="head needs_col_title" data-col="title" scope="col"><p>Title</p></th>
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
<tr class="row-odd"><th class="head needs_col_id" data-col="id" scope="col"><p>ID</p></th>
<th class="head needs_col_title" data-col="title" scope="col"><p>Title</p></th>
<th class="head needs_col_config" data-col="config" scope="col"><p>Config</p></th>
<th class="head needs_col_github" data-col="github" scope="col"><p>Github</p></th>
</tr>
"""

    assert string_column_order in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_string_links_no_trailing_separator(test_app):
    """Test that single-value string_links fields don't get a trailing separator."""
    app = test_app
    app.build()
    html = Path(app.outdir, "test_options.html").read_text(encoding="utf-8")

    # Find the SINGLE_STRING_LINK need's github cell content
    assert "SINGLE_STRING_LINK" in html
    assert (
        '<a class="reference external" href="https://github.com/useblocks/sphinxcontrib-needs/issues/404">'
        "GitHub #404</a>" in html
    )

    # The single-value field should NOT have a trailing "; " separator.
    # Before the fix, len(data) was used instead of len(data_list), causing
    # a trailing separator for any string value longer than 1 character.
    from lxml import html as html_parser

    tree = html_parser.parse(str(Path(app.outdir, "test_options.html")))

    # Find the need card/layout for SINGLE_STRING_LINK and check its github field
    # In the need layout, string_links values are rendered inside <span class="needs_data">
    # We look for the github content in the SINGLE_STRING_LINK need
    single_need_elements = tree.xpath(
        '//*[@id="SINGLE_STRING_LINK"]//span[@class="needs_data"]'
    )
    for elem in single_need_elements:
        text_content = elem.text_content()
        if "GitHub #404" in text_content:
            # Should contain exactly "GitHub #404" with no trailing "; "
            assert text_content.strip() == "GitHub #404", (
                f"Expected no trailing separator, got: {text_content!r}"
            )
            break
    else:
        pytest.fail("Could not find GitHub #404 in SINGLE_STRING_LINK need layout")


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needtable"}],
    indirect=True,
)
def test_doc_needtable_styles(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "test_styles.html").read_text(encoding="utf-8")
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
    html = Path(app.outdir, "test_parts.html").read_text(encoding="utf-8")
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
    html = Path(app.outdir, "test_titles.html").read_text(encoding="utf-8")
    assert (
        '<th class="head needs_col_title" data-col="title" scope="col">'
        "<p>Headline</p></th>" in html
    )
    assert (
        '<th class="head needs_col_incoming" data-col="incoming" scope="col">'
        "<p>To this need123</p></th>" in html
    )
    # the column key is the option name verbatim -- as it already is for the cell
    # class below, punctuation and all
    assert (
        '<th class="head needs_col_special-chars!" data-col="special-chars!"'
        ' scope="col"><p>Special Characters!</p></th>' in html
    )
    assert '<td class="needs_special-chars!"><p>special-chars value</p></td>' in html


# -- the option-level ``[[...]]`` path ---------------------------------------
#
# ``needtable``'s ``style_row`` is the one live consumer of
# ``check_and_get_content``: ``:style:`` is itself a dynamic-function FIELD, so the
# field path has already resolved it before ``need.py`` re-runs the option parser over
# ``classes``.  Nothing else in this suite writes ``[[...]]`` in an option, so a break in
# that path shows up only as a silently wrong row class -- no warning, no failing build.

STYLE_ROW_CONF = """\
extensions = ["sphinx_needs"]
"""

STYLE_ROW_INDEX = """\
Style row
=========

.. req:: One
   :id: R_ONE
   :status: open

.. needtable::
   :style_row: needs_[[copy("status")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), STYLE_ROW_CONF),
                (Path("index.rst"), STYLE_ROW_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_needtable_style_row_dynamic_function(test_app):
    app = test_app
    app.build()

    assert_no_warnings(app)

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert '<tr class="need needs_open' in html
    assert "[[copy(" not in html
