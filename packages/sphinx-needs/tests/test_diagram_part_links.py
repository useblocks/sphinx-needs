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

import re
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.directives.needsequence import NeedSequenceException
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


BACK_LINKS_IN_ORDER = """\
Index
=====

.. req:: S1
   :id: BACK_S1
   :links: BACK_M1

.. req:: S2
   :id: BACK_S2
   :links: BACK_M2

.. req:: S3
   :id: BACK_S3
   :links: BACK_M1

.. spec:: M1
   :id: BACK_M1
   :links: BACK_R

.. spec:: M2
   :id: BACK_M2
   :links: BACK_R

.. req:: R
   :id: BACK_R

.. needsequence::
   :start: BACK_R
   :link_types: links_back
"""
"""Two messages back to ``BACK_R``, the first from two senders: the walk over the back
links meets them in need-id order, as it did."""


def _unknown_link_type(name: str, line: int = 15) -> str:
    """needsequence's own report of a name in ``:link_types:``, as it was."""
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Unknown link type {name} in needsequence "
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
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_S", link_types="LINKS"),
            ),
            FORWARD_SEQUENCE,
            [],
            id="link-type-upper-case",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_S", link_types="Links"),
            ),
            FORWARD_SEQUENCE,
            [],
            id="link-type-mixed-case",
        ),
        pytest.param(
            _project(
                LINK_TYPES_CONF,
                LINK_TYPES.format(start="SEQ_R", link_types="LINKS_BACK"),
            ),
            EMPTY_SEQUENCE,
            [_unknown_link_type("LINKS_BACK")],
            id="back-links-upper-case",
        ),
        pytest.param(
            _project(LINK_TYPES_CONF, BACK_LINKS_IN_ORDER),
            "@startuml\n\n' Nodes definition \n\n"
            'participant "R" as BACK_R\n'
            "\n' Connection definition \n\n"
            "BACK_R -> BACK_S1: M1\n"
            "BACK_R -> BACK_S3: M1\n"
            "BACK_R -> BACK_S2: M2\n"
            "\n@enduml",
            [_unknown_link_type("LINKS_BACK", 27)],
            id="back-links-in-order",
        ),
    ],
    indirect=["test_app"],
)
def test_needsequence_link_types(test_app: Sphinx, uml: str, warnings: list[str]):
    """A back-link type is walked, as it was; a name that is no link type is skipped
    after the directive's report, where the build ended. A link type written in
    another case, which the directive's check accepts, is walked as the link type it
    names. The diagram of a link type that works is the one it was."""
    app = test_app
    sources = _capture(app)
    app.build()

    assert build_warnings(app) == warnings
    assert sources == [uml]


# --- needsequence starts ----------------------------------------------------------------
#
# Where a need is expected, a part address reads as its need (design/parts-contract.md): a
# start ``USER_A.a1`` draws the sequence of ``USER_A``. A part the need does not have ends
# the build as a need that does not exist does, naming the start as written; the part
# address of a need that has the part ended it too.

STARTS = """\
Starts
======

.. req:: User A
   :id: {ns}USER_A
   :links: {ns}MSG_1

   The sender, with :np:`(a1) a part`.

.. spec:: Message 1
   :id: {ns}MSG_1
   :links: {ns}USER_B

.. req:: User B
   :id: {ns}USER_B

.. needsequence::
   :start: {start}
"""


def _starts(start: str, conf: str = CONF, ns: str = "") -> dict[str, object]:
    return _project(conf, STARTS.format(start=start, ns=ns))


def _sequence_of_user_a(ns: str = "") -> str:
    name = ns.replace("::", "__")
    # a receiver whose name is not its id is declared, with its id as its title
    receiver = f'participant "{ns}USER_B" as {name}USER_B\n' if ns else ""
    return (
        "@startuml\n\n' Nodes definition \n\n"
        f'participant "User A" as {name}USER_A\n'
        f"{receiver}"
        "\n' Connection definition \n\n"
        f"{name}USER_A -> {name}USER_B: Message 1\n"
        "\n@enduml"
    )


@pytest.mark.parametrize(
    ("test_app", "ns"),
    [
        pytest.param(_starts("USER_A"), "", id="the-need"),
        pytest.param(_starts("USER_A.a1"), "", id="a-part-of-it"),
        pytest.param(
            _starts("nc::USER_A.a1", NAMESPACED_CONF, "nc::"),
            "nc::",
            id="a-part-of-a-namespaced-need",
        ),
    ],
    indirect=["test_app"],
)
def test_needsequence_start_a_part_address_reads_as_its_need(test_app: Sphinx, ns: str):
    app = test_app
    sources = _capture(app)
    app.build()
    assert build_warnings(app) == []
    assert sources == [_sequence_of_user_a(ns)]


@pytest.mark.parametrize(
    ("test_app", "start"),
    [
        pytest.param(_starts("USER_A.zz"), "USER_A.zz", id="part-missing"),
        pytest.param(_starts("NOPE_1"), "NOPE_1", id="need-missing"),
        pytest.param(_starts("NOPE_1.a1"), "NOPE_1.a1", id="part-of-a-missing-need"),
    ],
    indirect=["test_app"],
)
def test_needsequence_start_that_does_not_resolve(test_app: Sphinx, start: str):
    with pytest.raises(
        NeedSequenceException,
        match=re.escape(f"Given {start} in needsequence unknown. File index:"),
    ) as excinfo:
        test_app.build()
    # raised on its own, not while handling a failed lookup
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None


# --- needflow ----------------------------------------------------------------------------
#
# A ``:root_id:`` naming a part starts the walk at the part's need, and the walk follows a
# link to a part to the part's need; a dead part link is not followed. An edge is a part
# edge when its link names a part; the id of the need the link starts at plays no part.

FLOW_CONF = CONF + 'needs_flow_engine = "plantuml"\n'

ROOTS = """\
Roots
=====

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one` and :np:`(p2) two`

.. spec:: Links a part
   :id: SPEC_1
   :links: REQ_1.p1

.. req:: Unconnected
   :id: REQ_2

.. impl:: Links a part its need does not have
   :id: IMPL_1
   :links: REQ_2.zz

.. needflow::
   :root_id: REQ_1

.. needflow::
   :root_id: REQ_1.p1

.. needflow::
   :root_id: SPEC_1
   :root_direction: outgoing

.. needflow::
   :root_id: IMPL_1
"""


def _drawn(uml: str) -> tuple[set[str], set[str]]:
    """The names a diagram draws a node as, and its edges, each as written."""
    names = set(re.findall(r'^\s*(?:node|rectangle) ".*" as (\S+)', uml, re.M))
    edges = {line.strip() for line in uml.splitlines() if "->" in line}
    return names, edges


@pytest.mark.parametrize(
    "test_app", [_project(FLOW_CONF, ROOTS)], ids=["roots"], indirect=True
)
def test_needflow_root_id_a_part_address_reads_as_its_need(test_app: Sphinx):
    app = test_app
    sources = _capture(app)
    app.build()
    assert build_warnings(app) == [_dead("IMPL_1", 16, "REQ_2.zz")]

    assert len(sources) == 4
    of_the_need, of_the_part, outgoing_from_spec, from_a_dead_link = sources
    # the root REQ_1.p1 draws what the root REQ_1 draws
    assert of_the_part == of_the_need
    assert _drawn(of_the_need) == (
        {"REQ_1", "REQ_1.p1", "REQ_1.p2", "SPEC_1"},
        {"SPEC_1 -[dotted]-> REQ_1.p1"},
    )
    # the walk follows SPEC_1's link to REQ_1.p1 to REQ_1
    assert _drawn(outgoing_from_spec) == _drawn(of_the_need)
    # and does not follow a link to a part REQ_2 does not have
    assert _drawn(from_a_dead_link) == ({"IMPL_1"}, set())


EXTERNAL_CONF = (
    FLOW_CONF
    + "needs_external_needs = [{'base_url': 'http://example.org/', "
    + "'json_path': 'external.json', 'id_prefix': ''}]\n"
)

EXTERNAL_JSON = """\
{"current_version": "1.0", "versions": {"1.0": {"needs": {"EXT_1": {
  "id": "EXT_1", "type": "req", "title": "External", "docname": "ext",
  "parts": {"rp": {"id": "rp", "content": "a record part"}}
}}}}}
"""

EXTERNAL_ROOT = """\
External
========

.. spec:: Links an external part
   :id: SPEC_1
   :links: EXT_1.rp

.. needflow::
   :root_id: EXT_1.rp

.. needflow::
   :root_id: EXT_1.zz
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), EXTERNAL_CONF),
                (Path("external.json"), EXTERNAL_JSON),
                (Path("index.rst"), EXTERNAL_ROOT),
            ],
        }
    ],
    ids=["external"],
    indirect=True,
)
def test_needflow_root_id_a_part_of_an_external_need(test_app: Sphinx):
    """The part an external need's record states is a part of it: the root
    ``EXT_1.rp`` starts at ``EXT_1``; ``EXT_1.zz``, a part it does not have, draws
    nothing."""
    app = test_app
    sources = _capture(app)
    app.build()
    assert build_warnings(app) == []
    [of_the_part] = sources
    assert _drawn(of_the_part) == (
        {"EXT_1", "EXT_1.rp", "SPEC_1"},
        {"SPEC_1 -[dotted]-> EXT_1.rp"},
    )


EDGES = """\
Edges
=====

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one`

.. req:: A need whose id holds a dot
   :id: REQ_9.x
   :links: REQ_1

.. spec:: Links
   :id: SPEC_1
   :links: REQ_1, REQ_1.p1, REQ_9.x

.. needflow::
"""


@pytest.mark.parametrize(
    "test_app", [_project(FLOW_CONF, EDGES)], ids=["edges"], indirect=True
)
def test_needflow_a_part_edge_is_one_whose_link_names_a_part(test_app: Sphinx):
    """``REQ_9.x`` is a need, and there is no need ``REQ_9``. Its link to ``REQ_1`` is
    drawn as a link between needs; it was drawn as a part edge because its id holds a
    ``.``. ``SPEC_1``'s link to ``REQ_9.x`` names the part ``x`` of ``REQ_9`` as a link is
    read, which resolution reports dead: what a link to a need whose id holds a ``.``
    means is not settled, and its edge is drawn as in 9.3.0."""
    app = test_app
    sources = _capture(app)
    app.build()
    assert build_warnings(app) == [_dead("SPEC_1", 13, "REQ_9.x")]

    [uml] = sources
    assert _drawn(uml)[1] == {
        "REQ_9.x --> REQ_1",
        "SPEC_1 --> REQ_1",
        "SPEC_1 -[dotted]-> REQ_1.p1",
        "SPEC_1 -[dotted]-> REQ_9.x",
    }


EMPTY_PART = """\
Empty part
==========

.. req:: Parts
   :id: REQ_1

   :np:`(p1) one`

.. impl:: Links the empty part
   :id: IMPL_1
   :links: REQ_1.

.. needflow::

.. needflow::
   :root_id: IMPL_1
   :root_direction: outgoing
"""


@pytest.mark.parametrize(
    "test_app", [_project(FLOW_CONF, EMPTY_PART)], ids=["empty-part"], indirect=True
)
def test_needflow_a_link_to_the_empty_part_is_dead(test_app: Sphinx):
    """``REQ_1.`` names the empty part, which no need has: a dead link, so no edge is
    drawn for it and the walk does not follow it. Both read it as ``REQ_1``, which it
    was stored as."""
    app = test_app
    sources = _capture(app)
    app.build()
    assert build_warnings(app) == [_dead("IMPL_1", 9, "REQ_1.")]

    every_need, from_the_link = sources
    assert _drawn(every_need) == ({"REQ_1", "REQ_1.p1", "IMPL_1"}, set())
    assert _drawn(from_the_link) == ({"IMPL_1"}, set())


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
