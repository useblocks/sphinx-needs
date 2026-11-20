import os.path
from pathlib import Path

import pytest
from lxml import html as html_parser

from sphinx_needs_testkit import assert_no_warnings, build_warnings


def warning_lines(app) -> list[str]:
    """The build's warnings, one entry per LINE rather than one per record.

    This module's expectations were written line by line, and a multi-line warning is one
    record; splitting the shared normalisation back into lines keeps them as they are.
    """
    return ("\n".join(build_warnings(app))).splitlines()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needextract",
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

    index_html = Path(app.outdir, "check_need_refs.html").read_text(encoding="utf-8")
    assert "Awesome Sphinx-Needs" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needextract_with_nested_needs",
        }
    ],
    indirect=True,
)
def test_needextract_with_nested_needs(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needextract_html = Path(app.outdir, "needextract.html").read_text(encoding="utf-8")

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

    # the extracted copy runs the ``ndf`` role against the need it was copied from, and
    # leaves ``[[...]]`` in the content alone, exactly as the original does.  (The copy is
    # taken before docutils' smartquotes transform, so its quotes are still straight ones,
    # where the original page renders them curled.)
    assert "This is id [[copy(&quot;id&quot;)]] SPEC_1" in needextract_html
    assert (
        "This is grandchild id [[copy(&quot;id&quot;)]] SPEC_1_1_2" in needextract_html
    )


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

    assert warning_lines(app) == expected_warnings

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


def view_in_content_index(payload: str) -> str:
    """Build a document whose need's content holds one view directive."""
    return f"""\
Index
=====

.. toctree::

   extract

.. req:: Has a view directive inside
   :id: R_VIEW

   Body, and then:

   {payload}
"""


VIEW_IN_CONTENT_INDEX = view_in_content_index(
    """.. needtable::
      :columns: id
      :style: table"""
)

NEEDPIE_IN_CONTENT_INDEX = view_in_content_index(
    """.. needpie::
      :labels: reqs,rest

      type == 'req'
      type != 'req'"""
)

NEEDBAR_IN_CONTENT_INDEX = view_in_content_index(
    """.. needbar:: A bar
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

           , A
      Reqs , type == 'req'"""
)

# ``needuml`` reads the id it was never given long before it reaches its
# "is PlantUML installed" guard, so this needs no PlantUML to exercise.
NEEDUML_IN_CONTENT_INDEX = view_in_content_index(
    """.. needuml::

      Alice -> Bob: hello"""
)

# one level deeper: the view directive is in a CHILD need's content, which the
# copy carries along with everything else
NEEDTABLE_IN_CHILD_INDEX = """\
Index
=====

.. toctree::

   extract

.. req:: Has a child need
   :id: R_VIEW

   Outer body.

   .. spec:: A child
      :id: S_CHILD

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
    ("test_app", "expected_warning", "still_rendered", "omitted", "extra_warnings"),
    [
        pytest.param(
            {
                "buildername": "html",
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
            [],
            id="needtable-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
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
            [],
            id="needextract-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), NEEDPIE_IN_CONTENT_INDEX),
                    (Path("extract.rst"), extract_doc("R_VIEW")),
                ],
            },
            "A 'needpie' directive in the content of need 'R_VIEW' cannot be "
            "rendered by needextract, and is omitted.",
            'id="R_VIEW"',
            "_images/need_pie_",
            [],
            id="needpie-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), NEEDBAR_IN_CONTENT_INDEX),
                    (Path("extract.rst"), extract_doc("R_VIEW")),
                ],
            },
            "A 'needbar' directive in the content of need 'R_VIEW' cannot be "
            "rendered by needextract, and is omitted.",
            'id="R_VIEW"',
            "_images/need_bar_",
            [],
            id="needbar-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), NEEDUML_IN_CONTENT_INDEX),
                    (Path("extract.rst"), extract_doc("R_VIEW")),
                ],
            },
            "A 'needuml' (or 'needarch') directive in the content of need 'R_VIEW' "
            "cannot be rendered by needextract, and is omitted.",
            'id="R_VIEW"',
            "PlantUML is not available!",
            # the *source* document's own needuml genuinely cannot render
            # without sphinxcontrib.plantuml, and says so on its own account --
            # nothing to do with the copy needextract makes of it
            [
                "<srcdir>/index.rst:13: WARNING: PlantUML is not available, so "
                "the diagram was not rendered. Install 'sphinxcontrib-plantuml' "
                "and add it to the 'extensions' list to render it. "
                "[needs.needuml]"
            ],
            id="needuml-in-content",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), NEEDTABLE_IN_CHILD_INDEX),
                    (Path("extract.rst"), extract_doc("R_VIEW")),
                ],
            },
            "A 'needtable' directive in the content of need 'R_VIEW' cannot be "
            "rendered by needextract, and is omitted.",
            'id="S_CHILD"',
            "-table_node",
            [],
            id="needtable-in-a-child-need",
        ),
    ],
    indirect=["test_app"],
)
def test_unrenderable_view_in_extracted_content_warns(
    test_app, expected_warning, still_rendered, omitted, extra_warnings
):
    """A view directive the copy cannot render is reported, not fatal.

    The extracted need is still rendered; only the directive inside its content
    is left out, and the author is told which one and where.

    ``extra_warnings`` carries anything the *source* document reports on its own
    account. Sphinx emits warnings in document write order (sorted docnames), so
    here ``extract`` sorts before ``index`` and the source document's own warning
    comes second.
    """
    app = test_app
    app.build()

    assert warning_lines(app) == [
        f"<srcdir>/extract.rst:4: WARNING: {expected_warning} [needs.needextract]",
        *extra_warnings,
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
    assert_no_warnings(app)

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
    ``nodes.container`` holding the copied content in place of a document.  The
    post-transforms are now applied without that emission.  The listener this
    project's ``conf.py`` registers stands in for any third-party one: it records
    what it is handed, and a listener is entitled to be handed a document.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

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

    assert warning_lines(app) == [
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


# -- the per-document state the post-transforms run against ------------------

LEAK_PROBE_CONF = """\
from pathlib import Path

from sphinx.transforms.post_transforms import SphinxPostTransform

extensions = ["sphinx_needs"]


class LeakProbe(SphinxPostTransform):
    \"\"\"Write into the per-document state, as a third-party post-transform may.\"\"\"

    default_priority = 999

    def run(self, **kwargs):
        self.env.temp_data["PROBE_SENTINEL"] = "written by a post-transform"
        self.env.temp_data["highlight_language"] = "probe-language"


def _report(app, exception):
    state = app.env.temp_data
    Path(app.outdir, "state.log").write_text(
        f"sentinel={'PROBE_SENTINEL' in state}\\n"
        f"highlight_language={state.get('highlight_language') or ''!r}\\n"
    )


def setup(app):
    app.add_post_transform(LeakProbe)
    app.connect("build-finished", _report)
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LEAK_PROBE_CONF),
                # a need with a reference in it, so the post-transforms have
                # something to resolve while the scratch state is in place
                (Path("index.rst"), RECORDING_INDEX),
                (Path("extract.rst"), extract_doc("R_ONE")),
            ],
        }
    ],
    indirect=True,
)
def test_needextract_discards_post_transform_state(test_app):
    """Running the post-transforms for an extract leaves no state behind.

    ``BuildEnvironment.apply_post_transforms`` hands the post-transforms a *copy*
    of the per-document state and puts the original back afterwards, so what they
    write into it is discarded.  Applying them for an extract does the same: a
    third-party post-transform writing into ``env.temp_data`` -- and the sentinel
    below stands in for one -- must not have its writes outlive the extract, and
    must not be able to change a real field, such as the default highlighting
    language, for the rest of the build.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)

    state = Path(app.outdir, "state.log").read_text(encoding="utf8").split()
    assert state == ["sentinel=False", "highlight_language=''"], state


# -- A part address as the argument ------------------------------------------
#
# Given a need part's address ``ID.part`` of a need that has the part, needextract
# extracts the need, as it does for ``ID``: the argument names one need. Any other
# argument is read as in 9.3.0: an address naming a part its need does not have, or a
# part of no need, is a filter string there, reported as the invalid filter it is. A
# need id holding a ``.`` is read whole, as it was.

PART_NEEDS = """\
Needs
=====

.. req:: Parts
   :id: REQ_1

   Text with :np:`(p1) the part` and :np:`(é1) a part whose id is not ASCII`.

.. req:: A need whose id holds a dot
   :id: REQ_9.x

.. req:: A need whose id the default pattern accepts by its prefix alone
   :id: REQ_001-A

   Text with :np:`(p1) its part`.
"""

NAMESPACED_PART_NEEDS = """\
Needs
=====

.. req:: In a namespace
   :id: nc::REQ_3

   Text with :np:`(p3) a namespaced part`.
"""

NAMESPACED_CONF = CONF + "needs_namespaced_ids = True\n"


def _extract_app(argument: str, *, namespaced: bool = False) -> dict[str, object]:
    """A project whose index extracts ``argument`` and whose needs are on another page."""
    index = f"""\
Extract
=======

.. toctree::

   needs

.. needextract:: {argument}
"""
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), NAMESPACED_CONF if namespaced else CONF),
            (Path("index.rst"), index),
            (Path("needs.rst"), NAMESPACED_PART_NEEDS if namespaced else PART_NEEDS),
        ],
    }


def _extracted(app) -> list[str]:
    """The ids of the need cards on the index page, which only the extract puts there."""
    tree = html_parser.parse(str(Path(app.outdir, "index.html")))
    return tree.xpath("//table[contains(concat(' ', @class, ' '), ' need ')]/@id")


def _invalid_filter(argument: str, error: str) -> str:
    """The warning of an argument read as a filter that cannot be evaluated."""
    return (
        f"<srcdir>/index.rst:8: WARNING: Filter {argument!r} not valid. Error: "
        f"{error}. [needs.filter]"
    )


@pytest.mark.parametrize(
    ("test_app", "extracted"),
    [
        (_extract_app("REQ_1"), "REQ_1"),
        (_extract_app("REQ_1.p1"), "REQ_1"),
        (_extract_app("REQ_1.é1"), "REQ_1"),
        (_extract_app("REQ_001-A.p1"), "REQ_001-A"),
        (_extract_app("nc::REQ_3.p3", namespaced=True), "nc::REQ_3"),
        (_extract_app("REQ_9.x"), "REQ_9.x"),
    ],
    ids=[
        "the-need",
        "a-part-of-it",
        "a-non-ascii-part",
        "a-part-of-a-need-the-id-pattern-matches-by-prefix",
        "a-part-of-a-namespaced-need",
        "a-dotted-need-id",
    ],
    indirect=["test_app"],
)
def test_needextract_a_part_address_extracts_its_need(test_app, extracted):
    """The need is extracted, as for its id, and nothing is reported.

    ``REQ_9.x`` is a need whose id holds a ``.``, and there is no need ``REQ_9``: it is
    read whole, as in 9.3.0, which takes no side on what such an id should mean.
    ``REQ_001-A.p1`` resolves although the id pattern does not accept ``REQ_001-A`` in
    full: that the need exists and has the part decides, not the pattern.
    """
    app = test_app
    app.build()

    assert warning_lines(app) == []
    assert _extracted(app) == [extracted]


@pytest.mark.parametrize(
    ("test_app", "warning"),
    [
        (
            _extract_app("REQ_1.p9"),
            _invalid_filter("REQ_1.p9", "name 'REQ_1' is not defined"),
        ),
        (
            _extract_app("NOPE_1.p1"),
            _invalid_filter("NOPE_1.p1", "name 'NOPE_1' is not defined"),
        ),
        (
            _extract_app("NOPE_1"),
            "<srcdir>/index.rst:8: WARNING: Requested need 'NOPE_1' not found. "
            "[needs.needextract]",
        ),
        (
            _extract_app("nc::REQ_3.p9", namespaced=True),
            _invalid_filter("nc::REQ_3.p9", "invalid syntax (<string>, line 1)"),
        ),
    ],
    ids=[
        "part-missing",
        "part-of-a-missing-need",
        "need-missing",
        "namespaced-part-missing",
    ],
    indirect=["test_app"],
)
def test_needextract_an_address_that_does_not_resolve(test_app, warning):
    """Read as in 9.3.0: an id naming no need is reported as not found, and an address
    naming a part its need does not have, or a part of no need, is a filter string,
    reported as the invalid filter it is. Nothing is extracted, and the page is
    written."""
    app = test_app
    app.build()

    assert warning_lines(app) == [warning]
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "<h1>Extract" in html
    assert _extracted(app) == []


# -- A filter is read as a filter ---------------------------------------------
#
# An argument is read as a part address only when it resolves: the need exists and has
# the part. Its text cannot say so (``var.flag`` and ``REQ_1.p1`` have one shape), so
# any other argument is read as in 9.3.0, whatever the text before its first ``.``: a
# ``needs_filter_data`` name, an upper-case field, the filter context ``c``, the
# variant data ``var``, or, under a project's ``needs_id_regex``, any field.

FILTER_NEEDS_IDS = ["REQ_1", "SPEC_1", "SUP01::REQ_7"]

FILTER_NEEDS = """\
Needs
=====

.. req:: Req title
   :id: REQ_1
   :status: open
   :ASIL_LEVEL: B

   Text with :np:`(p1) the part`.

.. spec:: Spec one
   :id: SPEC_1
   :status: closed
   :ASIL_LEVEL: A

.. req:: Supplier req
   :id: SUP01::REQ_7
   :status: closed
   :ASIL_LEVEL: A
"""

FILTER_CONF = (
    CONF
    + 'needs_fields = {"ASIL_LEVEL": {"nullable": True}}\n'
    + "needs_namespaced_ids = True\n"
    + 'needs_variant_data = {"flag": True}\n'
)

# a name the (deprecated) ``needs_filter_data`` gives every filter
FILTER_DATA = 'needs_filter_data = {"CURRENT_VERSION": "1.0"}\n'
FILTER_DATA_DEPRECATED = (
    "WARNING: needs_filter_data is deprecated and will be removed in a future "
    "version. Use needs_variant_data instead. [needs.deprecated]"
)

# matched in full, each accepts the word before the first ``.`` of the lower-case
# arguments below; the second the upper-case ones too
LOWER_CASE_ID_REGEX = "^[a-z0-9_]+"
MIXED_CASE_ID_REGEX = "^[A-Za-z0-9_]+"

#: the id pattern (``None``: the default), and whether the needs' ids are lower case
ID_REGEXES = {
    "default-id-regex": (None, False),
    "lower-case-id-regex": (LOWER_CASE_ID_REGEX, True),
    "mixed-case-id-regex": (MIXED_CASE_ID_REGEX, False),
}

EXTERNAL_PART_JSON = """\
{"current_version": "1.0", "versions": {"1.0": {"needs": {"EXT_1": {
  "id": "EXT_1", "type": "req", "title": "External", "docname": "ext",
  "parts": {"a.b": {"id": "a.b", "content": "a record part whose id holds a dot"}}
}}}}}
"""

EXTERNAL_CONF = (
    CONF
    + "needs_external_needs = [\n"
    + '    {"base_url": "http://example.org/", "json_path": "external.json",'
    + ' "id_prefix": ""}\n'
    + "]\n"
)


def _filter_app(argument: str, *, regex: str) -> dict[str, object]:
    """A project whose index extracts ``argument`` from the needs of another page,
    under the id pattern ``regex`` names (:data:`ID_REGEXES`)."""
    pattern, lower_case = ID_REGEXES[regex]
    needs = FILTER_NEEDS
    if lower_case:
        for need_id in FILTER_NEEDS_IDS:
            needs = needs.replace(f":id: {need_id}\n", f":id: {need_id.lower()}\n")
    index = f"""\
Extract
=======

.. toctree::

   needs

.. needextract:: {argument}
"""
    return {
        "buildername": "html",
        "files": [
            (
                Path("conf.py"),
                FILTER_CONF
                + FILTER_DATA
                + ("" if pattern is None else f"needs_id_regex = {pattern!r}\n"),
            ),
            (Path("index.rst"), index),
            (Path("needs.rst"), needs),
        ],
    }


#: (argument, the ids extracted, the warning after the deprecation's, if any)
FILTERS: list[tuple[str, list[str], str | None]] = [
    ('CURRENT_VERSION.startswith("1") and status == "open"', ["REQ_1"], None),
    ('ASIL_LEVEL.startswith("B")', ["REQ_1"], None),
    ('status.upper() == "OPEN"', ["REQ_1"], None),
    ('title.startswith("Req t")', ["REQ_1"], None),
    ('type.startswith("sp")', ["SPEC_1"], None),
    # the needs are on another page than the extract: it selects none
    ("c.this_doc()", [], None),
    # the needs that have a namespace
    ("c.id.ns", ["SUP01::REQ_7"], None),
    ("var.flag", FILTER_NEEDS_IDS, None),
    (
        "status.open",
        [],
        _invalid_filter("status.open", "'str' object has no attribute 'open'"),
    ),
]
FILTER_IDS = [
    "filter-data-name",
    "upper-case-field",
    "method-call-compared",
    "method-call-with-a-space",
    "method-call",
    "this-doc",
    "id-facet",
    "variant-data",
    "an-invalid-filter",
]


@pytest.mark.parametrize(
    ("test_app", "lower_case", "extracted", "warning"),
    [
        (_filter_app(argument, regex=regex), lower_case, ids, warning)
        for regex, (_, lower_case) in ID_REGEXES.items()
        for argument, ids, warning in FILTERS
    ],
    ids=[f"{regex}-{name}" for regex in ID_REGEXES for name in FILTER_IDS],
    indirect=["test_app"],
)
def test_needextract_a_filter_is_read_as_a_filter(
    test_app, lower_case, extracted, warning
):
    """Each argument is a filter, run as one, as in 9.3.0, under each id pattern: the
    needs it selects are extracted (``c.this_doc()`` selects none on this page, and says
    so), and nothing is reported but the configuration's deprecation and, for a filter
    that cannot be evaluated, its invalid filter."""
    app = test_app
    app.build()

    assert warning_lines(app) == [
        FILTER_DATA_DEPRECATED,
        *([] if warning is None else [warning]),
    ]
    assert _extracted(app) == [
        need_id.lower() if lower_case else need_id for need_id in extracted
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert ("No needs passed the filters" in html) is (not extracted)


WORD_NEEDS = """\
Needs
=====

.. req:: A need named as the filter context
   :id: c

.. req:: A need named as the variant data
   :id: var

.. req:: Supplier req
   :id: SUP01::REQ_7
"""


def _word_app(argument: str) -> dict[str, object]:
    """A project with needs named ``c`` and ``var``, which have no parts, under a
    project's id pattern, whose index extracts ``argument``."""
    index = f"""\
Extract
=======

.. toctree::

   needs

.. needextract:: {argument}
"""
    return {
        "buildername": "html",
        "files": [
            (
                Path("conf.py"),
                FILTER_CONF + f"needs_id_regex = {MIXED_CASE_ID_REGEX!r}\n",
            ),
            (Path("index.rst"), index),
            (Path("needs.rst"), WORD_NEEDS),
        ],
    }


@pytest.mark.parametrize(
    ("test_app", "extracted"),
    [
        (_word_app("c.id.ns"), ["SUP01::REQ_7"]),
        (_word_app("var.flag"), ["c", "var", "SUP01::REQ_7"]),
    ],
    ids=["id-facet", "variant-data"],
    indirect=["test_app"],
)
def test_needextract_a_filter_whose_first_word_names_a_need_is_a_filter(
    test_app, extracted
):
    """A need named ``c`` or ``var`` has no part ``id.ns`` or ``flag``: the argument
    does not resolve, so it is the filter it is, as in 9.3.0."""
    app = test_app
    app.build()

    assert warning_lines(app) == []
    assert _extracted(app) == extracted


@pytest.mark.parametrize(
    ("test_app", "extracted", "warning"),
    [
        (_filter_app("req_1.p1", regex="lower-case-id-regex"), ["req_1"], None),
        (_filter_app("REQ_1.p1", regex="mixed-case-id-regex"), ["REQ_1"], None),
        (
            _filter_app("REQ_1.p9", regex="mixed-case-id-regex"),
            [],
            _invalid_filter("REQ_1.p9", "name 'REQ_1' is not defined"),
        ),
        (
            _filter_app("NOPE_1.p1", regex="mixed-case-id-regex"),
            [],
            _invalid_filter("NOPE_1.p1", "name 'NOPE_1' is not defined"),
        ),
    ],
    ids=[
        "lower-case-id-regex-a-part-of-it",
        "a-part-of-it",
        "part-missing",
        "part-of-a-missing-need",
    ],
    indirect=["test_app"],
)
def test_needextract_a_part_address_under_a_project_id_regex(
    test_app, extracted, warning
):
    """Under a project's id pattern too, a part address names its need, and one that
    does not resolve is read as in 9.3.0."""
    app = test_app
    app.build()

    assert warning_lines(app) == [
        FILTER_DATA_DEPRECATED,
        *([] if warning is None else [warning]),
    ]
    assert _extracted(app) == extracted


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), EXTERNAL_CONF),
                (Path("external.json"), EXTERNAL_PART_JSON),
                (Path("index.rst"), "Extract\n=======\n\n.. needextract:: EXT_1.a.b\n"),
            ],
        }
    ],
    ids=["record-part"],
    indirect=True,
)
def test_needextract_a_record_part_whose_id_holds_a_dot(test_app):
    """A part a record states may hold a ``.``: ``EXT_1.a.b`` is the part ``a.b`` of the
    external need EXT_1, so the argument names EXT_1, which needextract reports it
    cannot extract (an external need has no content here), rather than an invalid
    filter."""
    app = test_app
    app.build()

    assert warning_lines(app) == [
        "<srcdir>/index.rst:4: WARNING: External needs cannot be used as targets by "
        "needextract (ID 'EXT_1'). [needs.needextract]"
    ]


@pytest.mark.parametrize(
    "test_app", [_extract_app('"REQ_1.p1"')], ids=["quoted"], indirect=True
)
def test_needextract_a_quoted_part_address_is_a_filter(test_app):
    """Written ``"REQ_1.p1"``, the argument is a filter string, as in 9.3.0: a string
    constant, reported as the invalid filter it is. Nothing is extracted."""
    app = test_app
    app.build()

    warnings = warning_lines(app)
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith(
        """<srcdir>/index.rst:8: WARNING: Filter '"REQ_1.p1"' not valid."""
    ), warnings[0]
    assert warnings[0].endswith("[needs.filter]"), warnings[0]
    assert _extracted(app) == []
