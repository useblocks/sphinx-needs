"""Tests for the ``max_items`` option and the ``needs_views_max_items`` configuration.

Each case builds its own miniature project, since what is being tested is how many
needs a view shows, and that is only meaningful against a known number of needs.

The needs live in their own document, so that an assertion over ``index.html`` sees
the ids a view rendered and not the ids of the need definitions themselves.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import html as html_parser
from sphinx.testing.util import SphinxTestApp
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.directives.needflow._directive import NeedflowGraphiz

NEED_IDS = ("REQ_1", "REQ_2", "REQ_3", "REQ_4", "REQ_5")
"""The ids of the needs that :data:`NEEDS` defines."""

CONF = """\
extensions = ["sphinx_needs"]
needs_id_regex = "^[A-Za-z0-9_]"
"""

PLANTUML_CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_id_regex = "^[A-Za-z0-9_]"
"""

INDEX = """\
TEST DOCUMENT
=============

.. toctree::
   :hidden:

   needs

{view}
"""

NEEDS = """\
NEEDS
=====

.. req:: Requirement 1
   :id: REQ_1

.. req:: Requirement 2
   :id: REQ_2

.. req:: Requirement 3
   :id: REQ_3

.. req:: Requirement 4
   :id: REQ_4

.. req:: Requirement 5
   :id: REQ_5
"""

NEEDS_WITH_STATUS = """\
NEEDS
=====

.. req:: Requirement 1
   :id: REQ_1
   :status: eee

.. req:: Requirement 2
   :id: REQ_2
   :status: ddd

.. req:: Requirement 3
   :id: REQ_3
   :status: ccc

.. req:: Requirement 4
   :id: REQ_4
   :status: bbb

.. req:: Requirement 5
   :id: REQ_5
   :status: aaa
"""

NEEDS_WITH_PARTS = """\
NEEDS
=====

.. req:: Requirement 1
   :id: REQ_1

   :need_part:`(part_a)First part`

   :need_part:`(part_b)Second part`

.. req:: Requirement 2
   :id: REQ_2

   :need_part:`(part_c)Third part`

.. req:: Requirement 3
   :id: REQ_3
"""

SEQUENCE_NEEDS = """\
NEEDS
=====

.. req:: User A
   :id: USER_A
   :links: MSG_1

.. spec:: Message 1
   :id: MSG_1
   :links: USER_B, USER_C

.. req:: User B
   :id: USER_B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_D

.. req:: User C
   :id: USER_C
   :links: MSG_3

.. spec:: Message 3
   :id: MSG_3
   :links: USER_E

.. req:: User D
   :id: USER_D

.. req:: User E
   :id: USER_E
"""

DIAMOND_NEEDS = """\
NEEDS
=====

.. req:: User A
   :id: USER_A
   :links: MSG_1

.. spec:: Message 1
   :id: MSG_1
   :links: USER_B, USER_C

.. req:: User B
   :id: USER_B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_D

.. req:: User C
   :id: USER_C
   :links: MSG_3

.. spec:: Message 3
   :id: MSG_3
   :links: USER_D

.. req:: User D
   :id: USER_D
   :links: MSG_4

.. spec:: Message 4
   :id: MSG_4
   :links: USER_E

.. req:: User E
   :id: USER_E
"""
"""A walk that branches and re-converges, so a cap can fall in the middle of a branch.

Uncapped it draws five messages -- A to B, B to D, D to E, A to C, C to D -- declaring
USER_A, USER_B, USER_D and USER_C, and leaving only the leaf USER_E to PlantUML.
"""

NOTICE_CLASS = "needs_max_items_notice"


def notice_text(shown: int, total: int, unit: str = "needs") -> str:
    """The exact text of the truncation notice."""
    return (
        f"Showing the first {shown} of {total} {unit};"
        " refine the filter or set :max_items: (0 for all)."
    )


def files(view: str, *, needs: str = NEEDS, conf: str = CONF) -> list[tuple[Path, str]]:
    """Build the inline project for a single view directive."""
    return [
        (Path("conf.py"), conf),
        (Path("index.rst"), INDEX.format(view=view)),
        (Path("needs.rst"), needs),
    ]


def params(
    view: str,
    *,
    needs: str = NEEDS,
    conf: str = CONF,
    plantuml: bool = False,
    **overrides: object,
) -> dict[str, object]:
    """Build the ``test_app`` parameters for a single view directive."""
    param: dict[str, object] = {
        "buildername": "html",
        "files": files(view, needs=needs, conf=PLANTUML_CONF if plantuml else conf),
    }
    if not plantuml:
        param["no_plantuml"] = True
    if overrides:
        param["confoverrides"] = overrides
    return param


def shown_ids(app: SphinxTestApp) -> set[str]:
    """The need ids that the view on ``index.html`` rendered."""
    html = Path(app.outdir, "index.html").read_text()
    return {need_id for need_id in NEED_IDS if need_id in html}


def index_html(app: SphinxTestApp) -> str:
    return Path(app.outdir, "index.html").read_text()


def capture_diagrams(app: SphinxTestApp) -> list[str]:
    """Collect the diagram source of every needflow / needsequence that is rendered.

    The generated source is asserted on instead of the rendered image, so that the
    tests describe what the directive decided to draw, and do not depend on the
    PlantUML or Graphviz binaries being able to draw it.
    """
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(NeedflowGraphiz):
            sources.append(node["resolved_content"])
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

    app.connect("doctree-resolved", collect, priority=900)
    return sources


def diagram_ids(source: str) -> set[str]:
    """The need ids that a generated diagram source refers to."""
    return {need_id for need_id in NEED_IDS if need_id in source}


def arrows(uml: str) -> list[str]:
    """The messages a generated sequence diagram draws, in order."""
    return [line for line in uml.splitlines() if " -> " in line]


def declared(uml: str) -> set[str]:
    """The ids a generated sequence diagram declares a participant for."""
    return {
        line.split(" as ")[1].strip()
        for line in uml.splitlines()
        if line.startswith("participant ")
    }


def auto_declared(uml: str) -> set[str]:
    """The ids that a drawn message refers to without a participant declaration.

    PlantUML creates a lifeline for these itself, labelled with the raw need id rather
    than the need title. Sphinx-Needs has always left leaf receivers in this state; what
    matters for ``max_items`` is that truncating a diagram does not add to the set.
    """
    referenced = {
        id_ for arrow in arrows(uml) for id_ in arrow.split(":")[0].split(" -> ")
    }
    return {id_.strip() for id_ in referenced} - declared(uml)


# 1. the option caps each of the four view directives


@pytest.mark.parametrize(
    "test_app",
    [
        params(".. needlist::\n   :types: req\n   :max_items: 2\n"),
        params(".. needtable::\n   :types: req\n   :max_items: 2\n"),
    ],
    ids=["needlist", "needtable"],
    indirect=True,
)
def test_option_caps_list_and_table(test_app: SphinxTestApp):
    """A view with ``:max_items:`` shows that many needs, and says what it hides."""
    app = test_app
    app.build()
    assert shown_ids(app) == {"REQ_1", "REQ_2"}
    assert notice_text(2, 5) in index_html(app)


@pytest.mark.parametrize(
    ("test_app", "expected_ids"),
    [
        (
            params(
                ".. needflow::\n   :types: req\n   :max_items: 2\n",
                plantuml=True,
            ),
            {"REQ_1", "REQ_2"},
        ),
        (
            params(
                ".. needflow::\n   :types: req\n   :max_items: 2\n",
                plantuml=True,
                needs_flow_engine="graphviz",
            ),
            {"REQ_1", "REQ_2"},
        ),
        (
            params(
                ".. needsequence::\n   :start: USER_A\n   :max_items: 2\n",
                needs=SEQUENCE_NEEDS,
                plantuml=True,
            ),
            None,
        ),
    ],
    ids=["needflow-plantuml", "needflow-graphviz", "needsequence"],
    indirect=["test_app"],
)
def test_option_caps_diagrams(test_app: SphinxTestApp, expected_ids: set[str] | None):
    """A diagram with ``:max_items:`` draws that many items, and says what it hides.

    The generated diagram source is asserted on, not just the notice: a bug that
    counted correctly whilst drawing everything would otherwise pass.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    assert len(sources) == 1
    source = sources[0]
    if expected_ids is None:
        assert len(arrows(source)) == 2
    else:
        assert diagram_ids(source) == expected_ids
    html = index_html(app)
    assert NOTICE_CLASS in html
    assert "Showing the first 2 of" in html


# 2. an unset option falls back to the configuration


@pytest.mark.parametrize(
    "test_app",
    [
        params(".. needlist::\n   :types: req\n", needs_views_max_items=2),
        params(".. needtable::\n   :types: req\n", needs_views_max_items=2),
    ],
    ids=["needlist", "needtable"],
    indirect=True,
)
def test_config_caps_list_and_table(test_app: SphinxTestApp):
    """Without the option, the view is capped by ``needs_views_max_items``."""
    app = test_app
    app.build()
    assert shown_ids(app) == {"REQ_1", "REQ_2"}
    assert notice_text(2, 5) in index_html(app)


@pytest.mark.parametrize(
    ("test_app", "expected_ids"),
    [
        (
            params(
                ".. needflow::\n   :types: req\n",
                plantuml=True,
                needs_views_max_items=2,
            ),
            {"REQ_1", "REQ_2"},
        ),
        (
            params(
                ".. needflow::\n   :types: req\n",
                plantuml=True,
                needs_flow_engine="graphviz",
                needs_views_max_items=2,
            ),
            {"REQ_1", "REQ_2"},
        ),
        (
            params(
                ".. needsequence::\n   :start: USER_A\n",
                needs=SEQUENCE_NEEDS,
                plantuml=True,
                needs_views_max_items=2,
            ),
            None,
        ),
    ],
    ids=["needflow-plantuml", "needflow-graphviz", "needsequence"],
    indirect=["test_app"],
)
def test_config_caps_diagrams(test_app: SphinxTestApp, expected_ids: set[str] | None):
    """Without the option, the diagram is capped by ``needs_views_max_items``.

    The diagram source is asserted on, so that the configuration path is pinned to
    actually truncating the drawing, and not only to reporting that it did.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    assert len(sources) == 1
    source = sources[0]
    if expected_ids is None:
        assert len(arrows(source)) == 2
    else:
        assert diagram_ids(source) == expected_ids
    assert "Showing the first 2 of" in index_html(app)


# 3. the option wins over the configuration


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needlist::\n   :types: req\n   :max_items: 3\n", needs_views_max_items=1
        )
    ],
    indirect=True,
)
def test_option_overrides_config(test_app: SphinxTestApp):
    """A view that sets the option ignores the configured limit."""
    app = test_app
    app.build()
    assert shown_ids(app) == {"REQ_1", "REQ_2", "REQ_3"}
    assert notice_text(3, 5) in index_html(app)


# 4. the cap is applied after the sort, not before it


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needtable::\n   :types: req\n   :sort: status\n   :max_items: 2\n",
            needs=NEEDS_WITH_STATUS,
        )
    ],
    indirect=True,
)
def test_cap_is_applied_after_sort(test_app: SphinxTestApp):
    """The table keeps the first rows of the sorted table, not of the unsorted one.

    The statuses run in the opposite order to the ids, so a cap applied before the
    ``:sort:`` would keep REQ_1 and REQ_2 instead.
    """
    app = test_app
    app.build()
    assert shown_ids(app) == {"REQ_4", "REQ_5"}
    assert notice_text(2, 5) in index_html(app)


# 5. what zero means, from either source


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        (params(".. needlist::\n   :types: req\n"), set(NEED_IDS)),
        (
            params(".. needlist::\n   :types: req\n   :max_items: 2\n"),
            {"REQ_1", "REQ_2"},
        ),
        (
            params(
                ".. needlist::\n   :types: req\n   :max_items: 0\n",
                needs_views_max_items=2,
            ),
            set(NEED_IDS),
        ),
        (
            params(".. needlist::\n   :types: req\n", needs_views_max_items=2),
            {"REQ_1", "REQ_2"},
        ),
    ],
    ids=[
        "default-is-unlimited",
        "option-caps",
        "explicit-zero-opts-out",
        "config-caps",
    ],
    indirect=["test_app"],
)
def test_zero_means_unlimited(test_app: SphinxTestApp, expected: set[str]):
    """``0`` means no limit, and an explicit ``0`` beats a configured limit.

    The first case is the whole back-compatibility story: with the configuration at
    its default, a view without the option shows everything, as it always has.
    """
    app = test_app
    app.build()
    assert shown_ids(app) == expected
    html = index_html(app)
    if expected == set(NEED_IDS):
        assert NOTICE_CLASS not in html
    else:
        assert notice_text(len(expected), 5) in html


# 6. the notice and the warning appear only when the cap actually bit


@pytest.mark.parametrize(
    ("test_app", "origin"),
    [
        (params(".. needlist::\n   :types: req\n   :max_items: 2\n"), "needlist"),
        (params(".. needtable::\n   :types: req\n   :max_items: 2\n"), "needtable"),
        (
            params(".. needlist::\n   :types: req\n", needs_views_max_items=2),
            "needlist",
        ),
    ],
    ids=["option-needlist", "option-needtable", "config-needlist"],
    indirect=["test_app"],
)
def test_truncation_is_reported_twice(test_app: SphinxTestApp, origin: str):
    """Truncation is reported to the reader and to whoever runs the build.

    The notice is for the page, the warning is for the log, since a notice alone
    would have to be hunted for across the whole built site. Both fire on the same
    condition, whether the limit came from the option or from the configuration.
    """
    app = test_app
    app.build()
    html = index_html(app)
    assert f'class="{NOTICE_CLASS}"' in html
    assert notice_text(2, 5) in html

    warnings = app._warning.getvalue()
    assert f"{origin}: showing the first 2 of 5 needs, due to the max_items limit." in (
        warnings
    )
    assert "[needs.max_items]" in warnings


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needlist::\n   :types: req\n   :max_items: 2\n",
            suppress_warnings=["needs.max_items"],
        )
    ],
    indirect=True,
)
def test_warning_can_be_suppressed(test_app: SphinxTestApp):
    """A project that caps deliberately can silence the warning, and keep the notice.

    This is why the warning has its own sub-type: without one, capping a view on
    purpose would make a ``-W`` build unbuildable.
    """
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""
    assert notice_text(2, 5) in index_html(app)


@pytest.mark.parametrize(
    "test_app",
    [params(".. needlist::\n   :types: req\n   :max_items: 5\n")],
    indirect=True,
)
def test_no_notice_when_nothing_is_hidden(test_app: SphinxTestApp):
    """A limit that is not reached leaves no trace in the output, nor in the log."""
    app = test_app
    app.build()
    assert shown_ids(app) == set(NEED_IDS)
    assert NOTICE_CLASS not in index_html(app)
    assert app._warning.getvalue() == ""


# 7. both needflow engines cap identically


@pytest.mark.parametrize(
    "test_app",
    [
        params(".. needflow::\n   :types: req\n   :max_items: 2\n", plantuml=True),
        params(
            ".. needflow::\n   :types: req\n   :max_items: 2\n",
            plantuml=True,
            needs_flow_engine="graphviz",
        ),
    ],
    ids=["plantuml", "graphviz"],
    indirect=True,
)
def test_both_needflow_engines_cap_the_same_set(test_app: SphinxTestApp):
    """The option must select the same needs whichever engine draws them.

    A dropped need must not be referenced at all: both engines skip a link whose
    target was not rendered, which is what makes truncating a graph safe.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    assert len(sources) == 1
    assert diagram_ids(sources[0]) == {"REQ_1", "REQ_2"}


# 8. the sequence cap counts messages, and declares no orphan participant


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needsequence::\n   :start: USER_A\n   :max_items: 2\n",
            needs=SEQUENCE_NEEDS,
            plantuml=True,
        )
    ],
    indirect=True,
)
def test_needsequence_caps_messages(test_app: SphinxTestApp):
    """The cap counts arrows, and the total counts every arrow the walk would draw.

    The corpus draws four messages: USER_A sends one message to USER_B and USER_C,
    and each of those two sends one on. A cap of two therefore keeps the first
    branch only, and USER_C, whose message was dropped, must not be declared: an
    undeclared participant is auto-created by PlantUML, but a declared one with no
    arrows is output that truncation added rather than removed.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    assert len(sources) == 1
    uml = sources[0]

    assert arrows(uml) == [
        "USER_A -> USER_B: Message 1",
        "USER_B -> USER_D: Message 2",
    ]
    # USER_C, whose message was dropped, must not be declared: a declared participant
    # with no arrows is output that truncation added rather than removed
    assert declared(uml) == {"USER_A", "USER_B"}
    # and USER_D, which the kept second arrow points at, must not have become
    # auto-declared by the truncation -- it is a leaf, so it is auto-declared uncapped
    # too, which is what the companion test pins
    assert auto_declared(uml) == {"USER_D"}

    # the walk keeps counting past the cap, so the total is over all four messages
    assert notice_text(2, 4, "messages") in index_html(app)
    assert (
        "needsequence: showing the first 2 of 4 messages, due to the max_items limit."
        in app._warning.getvalue()
    )


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needsequence::\n   :start: USER_A\n",
            needs=SEQUENCE_NEEDS,
            plantuml=True,
        )
    ],
    indirect=True,
)
def test_needsequence_without_a_cap(test_app: SphinxTestApp):
    """Without a cap the same corpus draws all four messages and no notice.

    This also pins what truncation is allowed to change: uncapped, USER_D and USER_E
    are the leaves that PlantUML auto-creates, and a capped build of the same corpus
    may not add to that set.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    uml = sources[0]
    assert len(arrows(uml)) == 4
    assert declared(uml) == {"USER_A", "USER_B", "USER_C"}
    assert auto_declared(uml) == {"USER_D", "USER_E"}
    assert NOTICE_CLASS not in index_html(app)
    assert "max_items" not in app._warning.getvalue()


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needsequence::\n   :start: USER_A\n   :max_items: 1\n",
            needs=SEQUENCE_NEEDS,
            plantuml=True,
        )
    ],
    indirect=True,
)
def test_needsequence_declares_the_receiver_at_the_cap(test_app: SphinxTestApp):
    """The participant the last drawn message points at keeps its declaration.

    The cap is exhausted *by* that message, so the receiver reaches its declaration
    with no room left. Suppressing it there would leave PlantUML to auto-create the
    lifeline and label it ``USER_B`` instead of ``User B`` -- truncation would have
    changed a participant that is still drawn, instead of only removing ones that are
    not. Uncapped, USER_B is declared, so this is exactly the set the cap may not grow.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    uml = sources[0]

    assert arrows(uml) == ["USER_A -> USER_B: Message 1"]
    assert declared(uml) == {"USER_A", "USER_B"}
    assert 'participant "User B" as USER_B' in uml
    # the declaration must precede the arrow's first mention of the id: PlantUML
    # auto-creates a lifeline on first mention, so a later declaration is dead
    assert uml.index('participant "User B" as USER_B') < uml.index("USER_A -> USER_B")
    # nothing is auto-created that would not have been uncapped
    assert auto_declared(uml) == set()
    assert notice_text(1, 4, "messages") in index_html(app)


@pytest.mark.parametrize(
    ("test_app", "cap", "expected_arrows", "expected_declared", "expected_auto"),
    [
        (
            params(
                ".. needsequence::\n   :start: USER_A\n   :max_items: 1\n",
                needs=DIAMOND_NEEDS,
                plantuml=True,
            ),
            1,
            ["USER_A -> USER_B: Message 1"],
            {"USER_A", "USER_B"},
            set(),
        ),
        (
            params(
                ".. needsequence::\n   :start: USER_A\n   :max_items: 3\n",
                needs=DIAMOND_NEEDS,
                plantuml=True,
            ),
            3,
            [
                "USER_A -> USER_B: Message 1",
                "USER_B -> USER_D: Message 2",
                "USER_D -> USER_E: Message 4",
            ],
            {"USER_A", "USER_B", "USER_D"},
            {"USER_E"},
        ),
    ],
    ids=["cap-1", "cap-3"],
    indirect=["test_app"],
)
def test_needsequence_restores_only_drawn_participants(
    test_app: SphinxTestApp,
    cap: int,
    expected_arrows: list[str],
    expected_declared: set[str],
    expected_auto: set[str],
):
    """Restoring a suppressed declaration is selective, not a blanket undo.

    On a walk that branches and re-converges, a cap of one suppresses USER_B, USER_D
    and USER_C in that order, and only USER_B is on the receiving end of the single
    message drawn -- so only USER_B comes back. At a cap of three, USER_C is still
    suppressed because its own message was dropped, whilst USER_D is declared because
    a drawn message points at it. In neither case is a participant declared that no
    drawn message refers to.
    """
    app = test_app
    sources = capture_diagrams(app)
    app.build()
    uml = sources[0]

    assert arrows(uml) == expected_arrows
    assert declared(uml) == expected_declared
    # USER_E is the only leaf, so it is auto-created uncapped as well
    assert auto_declared(uml) == expected_auto
    assert notice_text(cap, 5, "messages") in index_html(app)


# 9. the boundary between capped and not capped


@pytest.mark.parametrize(
    ("test_app", "expected_shown"),
    [
        (params(".. needlist::\n   :types: req\n   :max_items: 4\n"), 4),
        (params(".. needlist::\n   :types: req\n   :max_items: 5\n"), 5),
        (params(".. needlist::\n   :types: req\n   :max_items: 6\n"), 5),
    ],
    ids=["below", "equal", "above"],
    indirect=["test_app"],
)
def test_cap_boundary(test_app: SphinxTestApp, expected_shown: int):
    """Only a limit below the number of results truncates anything."""
    app = test_app
    app.build()
    html = index_html(app)
    assert len(shown_ids(app)) == expected_shown
    if expected_shown < 5:
        assert notice_text(expected_shown, 5) in html
    else:
        assert NOTICE_CLASS not in html


# 10. and 11. what the option refuses


@pytest.mark.parametrize(
    "test_app",
    [
        params(".. needlist::\n   :types: req\n   :max_items: many\n"),
        params(".. needlist::\n   :types: req\n   :max_items: -1\n"),
        params(".. needlist::\n   :types: req\n   :max_items: 1.5\n"),
        params(".. needlist::\n   :types: req\n   :max_items:\n"),
    ],
    ids=["not-a-number", "negative", "not-an-integer", "no-value"],
    indirect=True,
)
def test_invalid_option_value_is_an_error(test_app: SphinxTestApp):
    """A value that is not a non-negative integer is reported, and nothing is shown.

    ``max_items`` takes a value, so the flag-style spelling is refused as well, which
    is the same contract ``root_depth`` has carried since it was added.
    """
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    assert 'Error in "needlist" directive' in warnings
    assert shown_ids(app) == set()


# 12. an empty result is still an empty result


@pytest.mark.parametrize(
    "test_app",
    [params(".. needlist::\n   :types: test\n   :max_items: 2\n")],
    indirect=True,
)
def test_empty_result_with_a_cap(test_app: SphinxTestApp):
    """Nothing to truncate means the usual empty message, and no notice."""
    app = test_app
    app.build()
    html = index_html(app)
    assert "No needs passed the filters" in html
    assert NOTICE_CLASS not in html


# 13. the cap counts needs, not the rows they expand into


@pytest.mark.parametrize(
    "test_app",
    [
        params(
            ".. needtable::\n   :types: req\n   :show_parts:\n   :max_items: 2\n",
            needs=NEEDS_WITH_PARTS,
        )
    ],
    indirect=True,
)
def test_cap_counts_needs_not_rows(test_app: SphinxTestApp):
    """A capped table still expands every part of the needs it kept.

    The filtered list holds needs and need parts alike, and the cap counts those
    entries. Here it keeps REQ_1 and its first part out of six entries, and the rows
    that ``:show_parts:`` adds for a kept need are not counted, so the table renders
    four rows against a limit of two.
    """
    app = test_app
    app.build()
    html = index_html(app)
    assert "REQ_1" in html
    assert "REQ_2" not in html
    assert "REQ_3" not in html
    # part_b is not one of the two kept entries, it is expanded from the kept REQ_1
    assert "part_a" in html
    assert "part_b" in html
    assert "part_c" not in html

    rows = html_parser.fromstring(html).xpath("//table//tbody/tr")
    assert len(rows) == 4

    assert notice_text(2, 6) in html
