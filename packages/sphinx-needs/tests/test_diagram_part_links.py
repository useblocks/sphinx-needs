"""needsequence and needgantt take a link to a need part, or to no need, as needflow does.

A link to a part (``USER_B.p1``) is a link to the need owning the part, and a link to a
need that does not exist is skipped: the dead-link check reports it, once, as it reports
every dead link. Both directives looked the link up as a whole need id and ended the
build with a ``KeyError`` (#2336).
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
    assert len(sources) == 1
    assert _arrows(sources[0]) == arrows


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
   :starts_after_links: links
"""


def _gantt(to_a: str, ns: str = "") -> str:
    return GANTT.format(ns=ns, to_a=to_a)


def _constraints(uml: str) -> list[str]:
    return [line for line in uml.splitlines() if " at [" in line]


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
