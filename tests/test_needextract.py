import os.path
from pathlib import Path

import pytest
from lxml import html as html_parser
from sphinx.util.console import strip_colors


def build_warnings(app) -> list[str]:
    """Return the warnings of a finished build, one per line.

    The source directory is randomised per test run, so it is collapsed to
    ``<srcdir>/`` to keep the expected strings readable and stable.
    """
    return (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    ).splitlines()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needextract",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_basic(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    def run_checks(checks, html_path):
        html_path = str(Path(app.outdir, html_path))
        tree = html_parser.parse(html_path)
        for check in checks:
            img_src = tree.xpath(
                f"//table[@id='{check[0]}']//td[@class='need content']//img/@src"
            )[0]
            assert img_src == check[1]
            assert os.path.exists(
                str(Path(app.outdir, os.path.dirname(html_path), img_src))
            )

    checks = [
        ("US_SUB_001", "_images/smile.png"),
        ("US_SUB_002", "_images/smile.png"),
        ("US_SUB_003", "_images/smile1.png"),
        ("US_SUB_004", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_002", "_images/smile.png"),
        ("US_003", "_images/smile.png"),
    ]
    run_checks(checks, "check_images.html")

    checks = [
        ("US_002", "../_images/smile.png"),
        ("US_003", "../_images/smile.png"),
    ]
    run_checks(checks, "subfolder/check_images_2.html")

    index_html = Path(app.outdir, "check_need_refs.html").read_text()
    assert "Awesome Sphinx-Needs" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needextract_with_nested_needs",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_with_nested_needs(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    # print(warnings)
    # note these warnings are emitted twice because they are resolved twice: once when first specified and once when copied with needextract
    assert warnings == [
        'srcdir/index.rst:13: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:33: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:13: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:33: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
    ]

    needextract_html = Path(app.outdir, "needextract.html").read_text()

    # ensure that the needs exist and that their hrefs point to the correct location
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1" title="SPEC_1">SPEC_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1_1" title="SPEC_1_1">SPEC_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_1" title="SPEC_1_1_1">SPEC_1_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_2" title="SPEC_1_1_2">SPEC_1_1_2</a>'
        in needextract_html
    )

    # dynamic functions should be executed
    assert "This is id SPEC_1 SPEC_1" in needextract_html
    assert "This is grandchild id SPEC_1_1_2 SPEC_1_1_2" in needextract_html


# -- inputs that used to end the build ---------------------------------------
#
# ``found_needs`` was assigned inside the loop over a document's needextract
# nodes and read once after it, so a node that took one of the three early
# exits left the name unbound whenever it was the last (or only) one, and the
# build ended with ``cannot access local variable 'found_needs' where it is not
# associated with a value``.  Two of the three inputs below warn first and used
# to end the build anyway; the third gave no diagnostic at all.

CONF = """\
extensions = ["sphinx_needs"]
"""

CONF_NEEDS_HIDDEN = """\
extensions = ["sphinx_needs"]
needs_include_needs = False
"""

UNKNOWN_ID_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_NOPE
"""

ARG_AND_FILTER_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_ONE
   :filter: id == "R_ONE"
"""

PLAIN_EXTRACT_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_ONE
"""


@pytest.mark.parametrize(
    ("test_app", "expected_warnings", "expected_cards"),
    [
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), UNKNOWN_ID_INDEX),
                ],
            },
            [
                "<srcdir>/index.rst:9: WARNING: Requested need 'R_NOPE' not found. "
                "[needs.needextract]"
            ],
            1,
            id="unknown-id-argument",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), ARG_AND_FILTER_INDEX),
                ],
            },
            [
                "<srcdir>/index.rst:9: WARNING: filter arguments and option filter "
                "at the same time are disallowed. [needs.needextract]"
            ],
            1,
            id="argument-and-filter-option",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF_NEEDS_HIDDEN),
                    (Path("index.rst"), PLAIN_EXTRACT_INDEX),
                ],
            },
            [],
            0,
            id="needs_include_needs-off",
        ),
    ],
    indirect=["test_app"],
)
def test_needextract_early_exit_does_not_end_the_build(
    test_app, expected_warnings, expected_cards
):
    """A needextract node that contributes nothing leaves the build standing.

    Each input is reported (or, for ``needs_include_needs = False``, silently
    dropped, exactly as every other view directive drops itself) and the page is
    still written.  ``expected_cards`` counts the cards carrying the authored
    need's anchor: one for the need itself, and none from the directive.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == expected_warnings

    # the page exists, and the directive contributed no need card to it
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "<h1>Extract" in html
    assert html.count('id="R_ONE"') == expected_cards


# -- Sphinx-Needs constructs in the copied content ---------------------------
#
# ``env.resolve_references()`` was called on the detached container holding one
# need's copied content, and it ends by emitting ``doctree-resolved`` -- so every
# listener of that event ran a second time with a container standing in for a
# document, ``process_needextract`` itself included.  Content holding a
# ``needtable`` ended the build with ``list index out of range``, and content
# holding a nested ``needextract`` with ``'container' object has no attribute
# 'settings'``.  The post-transforms now run without the emission, and the view
# directives whose rendering the copy cannot honour are dropped from it with a
# warning naming each one.

VIEW_IN_CONTENT_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: Has a view directive inside
   :id: R_VIEW

   Body, and then:

   .. needtable::
      :columns: id
      :style: table
"""

NESTED_EXTRACT_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: Inner
   :id: R_INNER

   Inner body.

.. req:: Contains an extract
   :id: R_OUTER

   Outer body, and then:

   .. needextract:: R_INNER
"""


def extract_doc(need_id: str) -> str:
    """Build a second document that extracts one need."""
    return f"Extract\n=======\n\n.. needextract:: {need_id}\n"


@pytest.mark.parametrize(
    ("test_app", "expected_warning", "still_rendered", "omitted"),
    [
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), VIEW_IN_CONTENT_INDEX),
                    (Path("extract.rst"), extract_doc("R_VIEW")),
                ],
            },
            "A 'needtable' directive in the content of need 'R_VIEW' cannot be "
            "rendered by needextract, and is omitted.",
            'id="R_VIEW"',
            "-table_node",
            id="needtable-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), NESTED_EXTRACT_INDEX),
                    (Path("extract.rst"), extract_doc("R_OUTER")),
                ],
            },
            "A 'needextract' directive in the content of need 'R_OUTER' cannot be "
            "rendered by needextract, and is omitted.",
            'id="R_OUTER"',
            'id="R_INNER"',
            id="needextract-in-content",
        ),
    ],
    indirect=["test_app"],
)
def test_unrenderable_view_in_extracted_content_warns(
    test_app, expected_warning, still_rendered, omitted
):
    """A view directive the copy cannot render is reported, not fatal.

    The extracted need is still rendered; only the directive inside its content
    is left out, and the author is told which one and where.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        f"<srcdir>/extract.rst:4: WARNING: {expected_warning} [needs.needextract]"
    ]

    # the source page renders the directive as it always did
    assert omitted in Path(app.outdir, "index.html").read_text(encoding="utf8")

    extract_html = Path(app.outdir, "extract.html").read_text(encoding="utf8")
    assert still_rendered in extract_html
    assert omitted not in extract_html


# -- the reference contract of an extract ------------------------------------

REFERENCE_CONTRACT_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: Target of the need reference
   :id: R_TARGET

   Plain body.

.. req:: Content with references
   :id: R_REFS

   .. _inner-target:

   A paragraph to point at.

   A ref to it: :ref:`the paragraph <inner-target>`.
   A need ref: :need:`R_TARGET`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), REFERENCE_CONTRACT_INDEX),
                (Path("extract.rst"), extract_doc("R_REFS")),
            ],
        }
    ],
    indirect=True,
)
def test_extract_references_resolve_to_the_source_page(test_app):
    """An extract is a view: every reference in it leads back to the original.

    A ``:ref:`` to a target defined inside the copied content, a ``:need:`` role
    in it, and the card's own ID chip all resolve to the page the need is written
    on -- not to the copy.  The copy's references are resolved by Sphinx's
    post-transforms; this pins that they still are, now that they are applied
    without re-emitting ``doctree-resolved``.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []

    extract_html = Path(app.outdir, "extract.html").read_text(encoding="utf8")

    # the ref and the need role in the copied content point at the source page
    assert 'href="index.html#inner-target"' in extract_html
    assert 'href="index.html#R_TARGET"' in extract_html
    # ... and not at the copy, whose own anchor for them is dead
    assert 'href="#inner-target"' not in extract_html

    # the card's ID chip navigates back to the canonical need
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#R_REFS" title="R_REFS">R_REFS</a>' in extract_html
    )


# -- the event is emitted once per document ----------------------------------

RECORDING_CONF = """\
from pathlib import Path

extensions = ["sphinx_needs"]


def _record(app, doctree, docname):
    with open(Path(app.outdir, "resolved.log"), "a") as f:
        f.write(f"{docname} {type(doctree).__name__}\\n")


def setup(app):
    app.connect("doctree-resolved", _record)
"""

RECORDING_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: A need with a reference in it
   :id: R_ONE

   A need ref: :need:`R_TWO`.

.. req:: Two
   :id: R_TWO

   Plain body.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), RECORDING_CONF),
                (Path("index.rst"), RECORDING_INDEX),
                (Path("extract.rst"), extract_doc("R_ONE")),
            ],
        }
    ],
    indirect=True,
)
def test_needextract_does_not_re_emit_doctree_resolved(test_app):
    """Building an extract does not run the ``doctree-resolved`` listeners again.

    The copy's references used to be resolved with ``env.resolve_references()``,
    which ends by emitting ``doctree-resolved`` -- so every listener of the event,
    this extension's and any other's, was called a second time with the detached
    ``nodes.container`` holding the copied content in place of a document.  A
    listener may reasonably assume it is given a document, and the ones here
    crashed on the container; the post-transforms are now applied without the
    emission.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []

    recorded = Path(app.outdir, "resolved.log").read_text(encoding="utf8").split()
    # one emission per document, each with a document -- never a container
    assert sorted(recorded) == sorted(["extract", "document", "index", "document"]), (
        recorded
    )


# -- footnotes in the copied content -----------------------------------------

FOOTNOTE_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: A need with footnotes
   :id: R_FOOT

   Auto-numbered. [#fn1]_
   Manual. [1]_
   Symbol. [*]_

   .. [#fn1] The auto footnote text.

   .. [1] The manual footnote text.

   .. [*] The symbol footnote text.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), FOOTNOTE_INDEX),
                (Path("extract.rst"), extract_doc("R_FOOT")),
            ],
        }
    ],
    indirect=True,
)
def test_footnote_in_extracted_content_degrades_to_text(test_app):
    """A footnote reference in extracted content is reported, not fatal.

    The content is snapshotted before docutils' ``Footnotes`` transform has given
    each reference the ``refid`` of its footnote, and the reference used to reach
    the HTML writer without one and end the build with ``KeyError: 'refid'``.  All
    three kinds of reference -- auto-numbered, manual and auto-symbol -- are
    covered, since each is numbered by that transform differently.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/extract.rst:4: WARNING: A footnote reference in the content of "
        "need 'R_FOOT' cannot be resolved by needextract, and is rendered as "
        "plain text. [needs.needextract]"
    ]

    extract_html = Path(app.outdir, "extract.html").read_text(encoding="utf8")
    # each reference is now the marker its author wrote, and links nowhere
    assert "Auto-numbered. [#fn1]" in extract_html
    assert "Manual. [1]" in extract_html
    assert "Symbol. [*]" in extract_html
    # the footnote text itself is still on the page
    assert "The auto footnote text." in extract_html
    assert "The manual footnote text." in extract_html
    assert "The symbol footnote text." in extract_html

    # the source page is untouched: its references still resolve
    index_html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert 'class="footnote-reference brackets" href="#fn1"' in index_html
