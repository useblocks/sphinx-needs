"""A need list naming a need on a page the builder leaves out of its output.

The ``latex`` and ``texinfo`` builders write only the pages they include (a start
document, what its toctree reaches, and its appendices), so an ``:orphan:`` page is
not written, and asking them for its URI raises :class:`sphinx.errors.NoUri`. A
``needlist``, ``needtable`` or ``needextract`` listing a need on such a page ended the
build with that exception. The need is listed all the same, its text with no link, as
Sphinx writes a cross-reference whose target the builder leaves out.
"""

import re
from pathlib import Path

import pytest

from sphinx_needs_testkit import assert_no_warnings

CONF_PY = """\
extensions = ["sphinx_needs"]
project = "left-out"
"""

#: the page no toctree reaches, holding the need every project below lists
ELSEWHERE_RST = """\
:orphan:

Left out
========

.. req:: A requirement on a page the builder leaves out
   :id: LEFTOUT1
"""

#: what each project's root page holds, by the directive (and the site) it exercises
INDEX_RST = {
    "needlist": """\
Index
=====

.. needlist::
""",
    "needtable": """\
Index
=====

.. needtable::
""",
    # a link column naming the need: the row's own need is on the written page
    "needtable_link_column": """\
Index
=====

.. req:: A requirement on the written page
   :id: INCLUDED1
   :links: LEFTOUT1

.. needtable::
   :filter: id == "INCLUDED1"
   :columns: id, title, outgoing
""",
    "needextract": """\
Index
=====

.. needextract::
   :filter: id == "LEFTOUT1"
""",
}


#: a link written around the need's id. latex: an internal ``\hyperref[...]{...}`` or
#: an external ``\sphinxhref{...}{...}`` whose text holds the id, directly or inside
#: inline commands of one argument. texinfo: an ``@ref{...}`` or ``@uref{...}`` holding
#: it. Neither pattern knows every link form of its builder (texinfo writes an external
#: link as a footnote; latex text inside ``\DUrole{...}{...}`` is not looked into), so
#: the test runs both builders. A link the need's id merely shares a line with does not
#: match.
LINK_AROUND_THE_ID = {
    "latex": re.compile(
        r"\\(?:hyperref\[[^\]]*\]|sphinxhref\{[^}]*\})\{(?:\\\w+\{)*[^{}]*LEFTOUT1"
    ),
    "texinfo": re.compile(r"@u?ref\{[^}]*LEFTOUT1"),
}


def _project(buildername: str, variant: str) -> dict:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), CONF_PY),
            (Path("index.rst"), INDEX_RST[variant]),
            (Path("elsewhere.rst"), ELSEWHERE_RST),
        ],
    }


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_project(builder, variant), id=f"{builder}-{variant}")
        for builder in ("latex", "texinfo")
        for variant in INDEX_RST
    ],
    indirect=True,
)
def test_need_on_a_left_out_page_is_listed_without_a_link(test_app):
    """The build finishes with no warning, and the written document holds the need's
    id as text: no link wraps it (``LINK_AROUND_THE_ID``), and the page the builder
    leaves out is named nowhere."""
    app = test_app
    app.build()

    assert_no_warnings(app)
    suffix = ".tex" if app.builder.name == "latex" else ".texi"
    (written_file,) = Path(app.outdir).glob(f"*{suffix}")
    written = written_file.read_text("utf8")
    # the targets of labels and links are not text a reader sees
    visible = re.sub(r"\\detokenize\{[^}]*\}|@anchor\{[^}]*\}", "", written)
    assert "LEFTOUT1" in visible, written
    assert LINK_AROUND_THE_ID[app.builder.name].search(written) is None, written
    assert "elsewhere" not in written, written


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_project("html", variant), id=f"html-{variant}")
        for variant in INDEX_RST
    ],
    indirect=True,
)
def test_need_on_an_orphan_page_is_linked_in_html(test_app):
    """The ``html`` builder writes the orphan page, and the same lists link the need."""
    app = test_app
    app.build()

    assert_no_warnings(app)
    index = (Path(app.outdir) / "index.html").read_text("utf8")
    assert 'href="elsewhere.html#LEFTOUT1"' in index, index
