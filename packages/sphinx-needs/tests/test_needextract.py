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
# Given a need part's address ``ID.part``, needextract extracts the need, as it does
# for ``ID``: the argument names one need. An address naming a part its need does not
# have, or a part of no need, is reported as an id naming no need is, naming the
# address as written; such an argument was read as a filter string and reported as an
# invalid filter. A need id holding a ``.`` is read whole, as it was.

PART_NEEDS = """\
Needs
=====

.. req:: Parts
   :id: REQ_1

   Text with :np:`(p1) the part`.

.. req:: A need whose id holds a dot
   :id: REQ_9.x
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


@pytest.mark.parametrize(
    ("test_app", "extracted"),
    [
        (_extract_app("REQ_1"), "REQ_1"),
        (_extract_app("REQ_1.p1"), "REQ_1"),
        (_extract_app("nc::REQ_3.p3", namespaced=True), "nc::REQ_3"),
        (_extract_app("REQ_9.x"), "REQ_9.x"),
    ],
    ids=["the-need", "a-part-of-it", "a-part-of-a-namespaced-need", "a-dotted-need-id"],
    indirect=["test_app"],
)
def test_needextract_a_part_address_extracts_its_need(test_app, extracted):
    """The need is extracted, as for its id, and nothing is reported.

    ``REQ_9.x`` is a need whose id holds a ``.``, and there is no need ``REQ_9``: it is
    read whole, as in 9.3.0, which takes no side on what such an id should mean.
    """
    app = test_app
    app.build()

    assert warning_lines(app) == []
    assert _extracted(app) == [extracted]


@pytest.mark.parametrize(
    ("test_app", "argument"),
    [
        (_extract_app("REQ_1.p9"), "REQ_1.p9"),
        (_extract_app("NOPE_1.p1"), "NOPE_1.p1"),
        (_extract_app("NOPE_1"), "NOPE_1"),
        (_extract_app("nc::REQ_3.p9", namespaced=True), "nc::REQ_3.p9"),
    ],
    ids=[
        "part-missing",
        "part-of-a-missing-need",
        "need-missing",
        "namespaced-part-missing",
    ],
    indirect=["test_app"],
)
def test_needextract_an_address_that_does_not_resolve(test_app, argument):
    """Reported as an id naming no need is, naming the address as written; nothing is
    extracted, and the page is written."""
    app = test_app
    app.build()

    assert warning_lines(app) == [
        f"<srcdir>/index.rst:8: WARNING: Requested need {argument!r} not found. "
        "[needs.needextract]"
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "<h1>Extract" in html
    assert _extracted(app) == []


# -- A filter is never read as a part address ---------------------------------
#
# An argument is read as a part address only when what follows its first ``.`` is a
# part id (letters, digits, ``_`` and ``-``, and ``.`` for a part a record states). A
# filter whose text before its first ``.`` the id pattern accepts (a ``needs_filter_data``
# name, an upper-case field, or, under a project's ``needs_id_regex``, any field) is a
# filter, as in 9.3.0: what follows its first ``.`` holds a ``(``, a space or a quote.

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
"""

FILTER_CONF = CONF + 'needs_fields = {"ASIL_LEVEL": {"nullable": True}}\n'

# a name the (deprecated) ``needs_filter_data`` gives every filter
FILTER_DATA = 'needs_filter_data = {"CURRENT_VERSION": "1.0"}\n'
FILTER_DATA_DEPRECATED = (
    "WARNING: needs_filter_data is deprecated and will be removed in a future "
    "version. Use needs_variant_data instead. [needs.deprecated]"
)

# matched in full, it accepts every word of these arguments before their first ``.``
LOWER_CASE_ID_REGEX = 'needs_id_regex = "^[A-Za-z0-9_]+"\n'

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


def _filter_app(argument: str, *, id_regex: bool) -> dict[str, object]:
    """A project whose index extracts ``argument`` from the needs of another page."""
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
                FILTER_CONF + FILTER_DATA + (LOWER_CASE_ID_REGEX if id_regex else ""),
            ),
            (Path("index.rst"), index),
            (Path("needs.rst"), FILTER_NEEDS),
        ],
    }


FILTERS = [
    ('CURRENT_VERSION.startswith("1") and status == "open"', ["REQ_1"]),
    ('ASIL_LEVEL.startswith("B")', ["REQ_1"]),
    ('status.upper() == "OPEN"', ["REQ_1"]),
    ('title.startswith("Req t")', ["REQ_1"]),
    ('type.startswith("sp")', ["SPEC_1"]),
    # the needs are on another page than the extract: it selects none
    ("c.this_doc()", []),
]
FILTER_IDS = [
    "filter-data-name",
    "upper-case-field",
    "method-call-compared",
    "method-call-with-a-space",
    "method-call",
    "this-doc",
]


@pytest.mark.parametrize(
    ("test_app", "extracted"),
    [
        *((_filter_app(argument, id_regex=False), ids) for argument, ids in FILTERS),
        *((_filter_app(argument, id_regex=True), ids) for argument, ids in FILTERS),
    ],
    ids=[
        *(f"default-id-regex-{name}" for name in FILTER_IDS),
        *(f"project-id-regex-{name}" for name in FILTER_IDS),
    ],
    indirect=["test_app"],
)
def test_needextract_a_filter_is_read_as_a_filter(test_app, extracted):
    """Each argument is a filter, run as one, as in 9.3.0: the needs it selects are
    extracted (``c.this_doc()`` selects none on this page, and says so), and nothing is
    reported but the configuration's deprecation."""
    app = test_app
    app.build()

    assert warning_lines(app) == [FILTER_DATA_DEPRECATED]
    assert _extracted(app) == extracted
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert ("No needs passed the filters" in html) is (not extracted)


@pytest.mark.parametrize(
    ("test_app", "argument", "extracted"),
    [
        (_filter_app("REQ_1.p1", id_regex=True), "REQ_1.p1", ["REQ_1"]),
        (_filter_app("REQ_1.p9", id_regex=True), "REQ_1.p9", []),
        (_filter_app("NOPE_1.p1", id_regex=True), "NOPE_1.p1", []),
    ],
    ids=["a-part-of-it", "part-missing", "part-of-a-missing-need"],
    indirect=["test_app"],
)
def test_needextract_a_part_address_under_a_project_id_regex(
    test_app, argument, extracted
):
    """Under a project's id pattern too, a part address names its need, and one that
    does not resolve is reported as an id naming no need is."""
    app = test_app
    app.build()

    assert warning_lines(app) == [
        FILTER_DATA_DEPRECATED,
        *(
            []
            if extracted
            else [
                f"<srcdir>/index.rst:8: WARNING: Requested need {argument!r} not "
                "found. [needs.needextract]"
            ]
        ),
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
