from pathlib import Path

import pytest
from docutils import __version__ as doc_ver
from lxml import html as html_parser

from sphinx_needs_testkit import assert_no_warnings, build_warnings


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


# A link cell reads each link as a link is read (design/parts-contract.md): its address
# split at the FIRST ``.``, live when the need exists and has the part, dead otherwise.
# A dead link is written as text, as a link to a need that does not exist is; a link to a
# part the need does not have was written as a live reference to ``#ID.part``, and the
# cell took the SECOND dot-separated segment as the part (#2488). A need id holding a
# ``.`` (``REQ_9.x``, and there is no need ``REQ_9``) is rendered as in 9.3.0.
# The empty part ``REQ_1.`` is a dead link, written as text with its ``.``.

LINK_CELL_CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://example.org/", "json_path": "external.json", "id_prefix": ""}
]
"""

LINK_CELL_EXTERNAL = """\
{"current_version": "1.0", "versions": {"1.0": {"needs": {"EXT_1": {
  "id": "EXT_1", "type": "req", "title": "External", "docname": "ext",
  "parts": {"rp": {"id": "rp", "content": "a record part"},
            "a.b": {"id": "a.b", "content": "a record part whose id holds a dot"}}
}}}}}
"""

LINK_CELL_INDEX = """\
Cells
=====

.. req:: Parts
   :id: REQ_1

   Text with :np:`(p1) the part`.

.. req:: A need whose id holds a dot
   :id: REQ_9.x
   :links: REQ_1

.. req:: No parts
   :id: REQ_005

.. req:: A need whose id holds a dot, beside REQ_005
   :id: REQ_005.1

.. spec:: Links
   :id: SPEC_1
   :links: REQ_1, REQ_1.p1, REQ_1.p9, REQ_1., NOPE_1, NOPE_1.p1, REQ_9.x, REQ_005.1.p1, EXT_1, EXT_1.rp, EXT_1.a.b, EXT_1.zz

.. needtable::
   :columns: id, links
   :filter: id == "SPEC_1"
   :style: table

.. needtable::
   :columns: id, links_back
   :filter: id == "REQ_1"
   :style: table
"""


def _link_cells(app) -> list[dict[str, tuple[str | None, str | None]]]:
    """Each link cell, as each value's text and the href and class of its reference
    (``None`` and ``None`` for a value written as text)."""
    tree = html_parser.parse(str(Path(app.outdir, "index.html")))
    cells = []
    for cell in tree.xpath("//td[contains(@class, 'needs_links')]"):
        values: dict[str, tuple[str | None, str | None]] = {}
        [paragraph] = cell.xpath("./p")
        if paragraph.text and paragraph.text.strip():
            values[paragraph.text.strip()] = (None, None)
        for child in paragraph:
            if child.tag == "a":
                values[child.text_content()] = (child.get("href"), child.get("class"))
            if child.tail and child.tail.strip():
                values[child.tail.strip()] = (None, None)
        cells.append(values)
    return cells


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINK_CELL_CONF),
                (Path("external.json"), LINK_CELL_EXTERNAL),
                (Path("index.rst"), LINK_CELL_INDEX),
            ],
        }
    ],
    ids=["cells"],
    indirect=True,
)
def test_needtable_link_cell_reads_a_link_as_a_link_is_read(test_app):
    app = test_app
    app.build()

    internal = "reference internal"
    external = "external_link reference internal"
    ext_url = "http://example.org/ext.html#EXT_1"
    outgoing, incoming = _link_cells(app)
    assert outgoing == {
        "REQ_1": ("#REQ_1", internal),
        "REQ_1.p1": ("#REQ_1.p1", internal),
        # dead: a part REQ_1 does not have; a need that does not exist
        "REQ_1.p9": (None, None),
        # dead: the empty part, which no need has, written with its dot (it was
        # written ``REQ_1`` and linked ``#REQ_1``)
        "REQ_1.": (None, None),
        "NOPE_1": (None, None),
        "NOPE_1.p1": (None, None),
        # a need whose id holds a dot, as in 9.3.0
        "REQ_9.x": (None, None),
        # the part ``1.p1`` of REQ_005, which it does not have (the need REQ_005.1
        # has no part ``p1`` either)
        "REQ_005.1.p1": (None, None),
        # an external need's part links the part's anchor, as `:need:` does; a part it
        # does not have is dead
        "EXT_1": (ext_url, external),
        "EXT_1.rp": (f"{ext_url}.rp", external),
        "EXT_1.a.b": (f"{ext_url}.a.b", external),
        "EXT_1.zz": (None, None),
    }
    assert incoming == {"SPEC_1": ("#SPEC_1", internal), "REQ_9.x": (None, None)}


# A need whose id holds a ``.`` beside a need named by the text before that ``.``: a link
# naming the dotted need whole is a link to that need, rendered as in 9.3.0, in the
# forward column and in the back-link column (where it names the source of a link),
# whether or not REQ_005 has parts. What such a link means is not settled; it is not
# read as a part ``1`` of REQ_005, which REQ_005 does not have.

DOTTED_BESIDE_INDEX = """\
Cells
=====

.. req:: The need named by the text before the dot
   :id: REQ_005

   {prefix_parts}

.. req:: A need whose id holds a dot, beside REQ_005
   :id: REQ_005.1
   :links: REQ_2

.. req:: Linked
   :id: REQ_2

.. spec:: Links
   :id: SPEC_1
   :links: REQ_005.1

.. needtable::
   :columns: id, links
   :filter: id == "SPEC_1"
   :style: table

.. needtable::
   :columns: id, links_back
   :filter: id == "REQ_2"
   :style: table
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), 'extensions = ["sphinx_needs"]\n'),
                (Path("index.rst"), DOTTED_BESIDE_INDEX.format(prefix_parts=parts)),
            ],
        }
        for parts in ("", "Text with :np:`(p1) a part` and :np:`(p2) another`.")
    ],
    ids=["dotted-beside", "dotted-beside-a-prefix-with-parts"],
    indirect=True,
)
def test_needtable_link_cell_a_dotted_need_beside_its_prefix(test_app):
    """The cell links ``REQ_005.1`` as in 9.3.0, in both columns, whether REQ_005 has
    parts or none (it has no part ``1``). Resolution reports SPEC_1's link dead, as in
    9.3.0 (its address split at the first ``.``): that reading of a link to a need whose
    id holds a ``.`` is not settled, and not changed here."""
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:16: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'REQ_005.1' in field 'links' [needs.link_outgoing]"
    ]
    outgoing, incoming = _link_cells(app)
    assert outgoing == {"REQ_005.1": ("#REQ_005.1", "reference internal")}
    assert incoming == {"REQ_005.1": ("#REQ_005.1", "reference internal")}
