"""needsequence and needgantt read a link as this project's dead-link check reads it.

A link to a part the need has (``USER_B.p1``) is a link to the need owning the part. A
link to a need that does not exist, or to a part the need does not have
(``USER_B.nope``), is a dead link: it is skipped, as needflow draws no edge for it, and
the dead-link check reports it, once. Both directives looked a link up as a whole need
id and ended the build with a ``KeyError`` (#2336).

needsequence's ``:link_types:`` walks a back-link type (``links_back``) as it did, and
skips a name that is no link type after its own report, where it ended the build;
needgantt reports a name in its link options that is no link type, and skips it, where
it ended the build.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_fields = {"duration": {"schema": {"type": "integer"}, "nullable": True}}
"""

NAMESPACED_CONF = CONF + "needs_namespaced_ids = True\n"


def _project(conf: str, index: str) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _capture(app: Sphinx) -> list[str]:
    """The PlantUML source of every diagram on the resolved pages."""
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

    app.connect("doctree-resolved", collect, priority=900)
    return sources


def _dead(source: str, line: int, link: str, field: str = "links") -> str:
    """The dead-link check's report of ``link`` on the need ``source``."""
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Need {source!r} has unknown outgoing "
        f"link {link!r} in field {field!r} [needs.link_outgoing]"
    )


# --- needsequence ----------------------------------------------------------------------

SEQUENCE = """\
Sequence
========

.. req:: User A
   :id: {ns}USER_A
   :links: {to_message}

.. spec:: Message 1
   :id: {ns}MSG_1
   :links: {to_receiver}

   The message, with :np:`(m1) a part`.

.. req:: User B
   :id: {ns}USER_B

   The receiver, with :np:`(p1) a part`.

.. needsequence::
   :start: {ns}USER_A
"""


def _sequence(to_message: str, to_receiver: str, ns: str = "") -> str:
    return SEQUENCE.format(ns=ns, to_message=to_message, to_receiver=to_receiver)


def _arrows(uml: str) -> list[str]:
    return [line for line in uml.splitlines() if " -> " in line]


SEQUENCE_CASES = [
    pytest.param(
        _project(CONF, _sequence("MSG_1.m1", "USER_B.p1")),
        ["USER_A -> USER_B: Message 1"],
        [],
        id="part-link",
    ),
    pytest.param(
        _project(CONF, _sequence("MSG_1, NO_MSG", "USER_B, MISSING")),
        ["USER_A -> USER_B: Message 1"],
        [_dead("USER_A", 4, "NO_MSG"), _dead("MSG_1", 8, "MISSING")],
        id="dead-link",
    ),
    pytest.param(
        _project(CONF, _sequence("MSG_1, NO_MSG.m1", "USER_B, MISSING.p1")),
        ["USER_A -> USER_B: Message 1"],
        [_dead("USER_A", 4, "NO_MSG.m1"), _dead("MSG_1", 8, "MISSING.p1")],
        id="part-of-a-missing-need",
    ),
    pytest.param(
        _project(CONF, _sequence("MSG_1.nope", "USER_B")),
        [],
        [_dead("USER_A", 4, "MSG_1.nope")],
        id="unknown-part-of-a-message",
    ),
    pytest.param(
        _project(CONF, _sequence("MSG_1", "USER_B.nope")),
        [],
        [_dead("MSG_1", 8, "USER_B.nope")],
        id="unknown-part-of-a-receiver",
    ),
    pytest.param(
        _project(NAMESPACED_CONF, _sequence("nc::MSG_1.m1", "nc::USER_B.p1", "nc::")),
        ["nc__USER_A -> nc__USER_B: Message 1"],
        [],
        id="namespaced-part-link",
    ),
]


@pytest.mark.parametrize(
    ("test_app", "arrows", "warnings"), SEQUENCE_CASES, indirect=["test_app"]
)
def test_needsequence(test_app: Sphinx, arrows: list[str], warnings: list[str]):
    app = test_app
    sources = _capture(app)
    app.build()

    assert sorted(build_warnings(app)) == sorted(warnings)
    # a diagram with no message may be no diagram ("No needs passed the filters")
    assert len(sources) <= 1
    assert [arrow for uml in sources for arrow in _arrows(uml)] == arrows


LINK_TYPES = """\
Index
=====

.. req:: S
   :id: SEQ_S
   :links: SEQ_M

.. req:: M
   :id: SEQ_M
   :links: SEQ_R

.. req:: R
   :id: SEQ_R

.. needsequence::
   :start: {start}
   :link_types: {link_types}
"""

LINK_TYPES_CONF = CONF + "needs_links = {'triggers': {}, 'blocks': {}}\n"


def _unknown_link_type(name: str) -> str:
    """needsequence's own report of a name in ``:link_types:``, as it was."""
    return (
        f"<srcdir>/index.rst:15: WARNING: Unknown link type {name} in needsequence "
        "needsequence-index-0. Allowed values: TRIGGERS,BLOCKS,LINKS,PARENT_NEEDS "
        "[needs.needsequence]"
    )


EMPTY_SEQUENCE = (
    "@startuml\n\n' Nodes definition \n\n\n' Connection definition \n\n\n@enduml"
)

FORWARD_SEQUENCE = (
    "@startuml\n\n' Nodes definition \n\n"
    'participant "S" as SEQ_S\n'
    "\n' Connection definition \n\n"
    "SEQ_S -> SEQ_R: M\n"
    "\n@enduml"
)


@pytest.mark.parametrize(
    ("test_app", "uml", "warnings"),
    [
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_R", link_types="links_back"),
            ),
            "@startuml\n\n' Nodes definition \n\n"
            'participant "R" as SEQ_R\n'
            "\n' Connection definition \n\n"
            "SEQ_R -> SEQ_S: M\n"
            "\n@enduml",
            [_unknown_link_type("LINKS_BACK")],
            id="back-links",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_S", link_types="links, links_back"),
            ),
            "@startuml\n\n' Nodes definition \n\n"
            'participant "S" as SEQ_S\n'
            'participant "R" as SEQ_R\n'
            "\n' Connection definition \n\n"
            "SEQ_S -> SEQ_R: M\n"
            "SEQ_R -> SEQ_R: M\n"
            "SEQ_R -> SEQ_S: M\n"
            "SEQ_S -> SEQ_S: M\n"
            "\n@enduml",
            [_unknown_link_type("LINKS_BACK")],
            id="links-and-back-links",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_R", link_types="triggers_back"),
            ),
            EMPTY_SEQUENCE,
            [_unknown_link_type("TRIGGERS_BACK")],
            id="other-back-links",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_S", link_types="nonexistent"),
            ),
            EMPTY_SEQUENCE,
            [_unknown_link_type("NONEXISTENT")],
            id="no-link-type",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_S", link_types="links, nonexistent"),
            ),
            FORWARD_SEQUENCE,
            [_unknown_link_type("NONEXISTENT")],
            id="links-and-no-link-type",
        ),
    ],
    indirect=["test_app"],
)
def test_needsequence_link_types(test_app: Sphinx, uml: str, warnings: list[str]):
    """A back-link type is walked, as it was; a name that is no link type is skipped
    after the directive's report, where the build ended. The diagram of a link type
    that works is the one it was."""
    app = test_app
    sources = _capture(app)
    app.build()

    assert build_warnings(app) == warnings
    assert sources == [uml]


# --- needgantt ---------------------------------------------------------------------------

GANTT = """\
Gantt
=====

.. req:: Task A
   :id: {ns}TASK_A
   :duration: 2

   The first task, with :np:`(p1) a part`.

.. req:: Task B
   :id: {ns}TASK_B
   :duration: 3
   :links: {to_a}

.. needgantt:: Chart
   :starts_after_links: {after}
"""


def _gantt(to_a: str, ns: str = "", after: str = "links") -> str:
    return GANTT.format(ns=ns, to_a=to_a, after=after)


def _constraints(uml: str) -> list[str]:
    return [line for line in uml.splitlines() if " at [" in line]


def _no_link_type(name: str) -> str:
    """needgantt's report of a name in a link option that is no link type: the text
    with which it ended the build."""
    return (
        f"<srcdir>/index.rst:15: WARNING: {name} does not exist in configuration "
        "option needs_links [needs.needgantt]"
    )


GANTT_CASES = [
    pytest.param(
        _project(CONF, _gantt("TASK_A.p1")),
        ["[TASK_B] starts at [TASK_A]'s end"],
        [],
        id="part-link",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A, MISSING")),
        ["[TASK_B] starts at [TASK_A]'s end"],
        [_dead("TASK_B", 10, "MISSING")],
        id="dead-link",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A, MISSING.p1")),
        ["[TASK_B] starts at [TASK_A]'s end"],
        [_dead("TASK_B", 10, "MISSING.p1")],
        id="part-of-a-missing-need",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A.nope")),
        [],
        [_dead("TASK_B", 10, "TASK_A.nope")],
        id="unknown-part-of-a-need",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A", after="links_back")),
        [],
        [_no_link_type("links_back")],
        id="back-links",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A", after="nonexistent")),
        [],
        [_no_link_type("nonexistent")],
        id="no-link-type",
    ),
    pytest.param(
        _project(CONF, _gantt("TASK_A", after="links, nonexistent")),
        ["[TASK_B] starts at [TASK_A]'s end"],
        [_no_link_type("nonexistent")],
        id="links-and-no-link-type",
    ),
    pytest.param(
        _project(NAMESPACED_CONF, _gantt("nc::TASK_A.p1", "nc::")),
        ["[nc::TASK_B] starts at [nc::TASK_A]'s end"],
        [],
        id="namespaced-part-link",
    ),
]


@pytest.mark.parametrize(
    ("test_app", "constraints", "warnings"), GANTT_CASES, indirect=["test_app"]
)
def test_needgantt(test_app: Sphinx, constraints: list[str], warnings: list[str]):
    app = test_app
    sources = _capture(app)
    app.build()

    assert sorted(build_warnings(app)) == sorted(warnings)
    assert len(sources) == 1
    assert _constraints(sources[0]) == constraints
