"""Tests for the PlantUML source ``needsequence`` writes for its participants.

A need id is not a PlantUML name: an id holding ``::`` (which the default
``needs_id_regex`` accepts, as in ``SUPPLIER::USER_A``) written raw as a participant
alias or an arrow end is a PlantUML syntax error. The aliases go through the same
entity-name mapping as needflow's PlantUML engine, computed over the participants of
one diagram; what the reader sees -- participant titles and message labels -- is
unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinxcontrib.plantuml import plantuml

from sphinx_needs_testkit import assert_no_warnings

CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
"""
"""The default ``needs_id_regex`` throughout: every id below is accepted by it."""


def params(index: str, *, render: bool = False) -> dict[str, object]:
    """The ``test_app`` parameters of a one-page project."""
    param: dict[str, object] = {
        "buildername": "html",
        "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), index)],
    }
    if render:
        param["plantuml"] = True
    return param


def capture_sequences(app: SphinxTestApp) -> list[str]:
    """Collect the PlantUML source of every diagram on the resolved pages."""
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

    app.connect("doctree-resolved", collect, priority=900)
    return sources


NAMESPACED = """\
Namespaced
==========

.. req:: User::A
   :id: SUPPLIER::USER_A
   :links: SUPPLIER::ACT_1

.. spec:: Act::1
   :id: SUPPLIER::ACT_1
   :links: SUPPLIER::USER_B

.. req:: User::B
   :id: SUPPLIER::USER_B
   :links: SUPPLIER::ACT_2

.. spec:: Act::2
   :id: SUPPLIER::ACT_2
   :links: USER_C

.. req:: User C
   :id: USER_C

.. needsequence::
   :start: SUPPLIER::USER_A
"""


@pytest.mark.parametrize("test_app", [params(NAMESPACED, render=True)], indirect=True)
def test_ids_holding_colons_render(test_app: SphinxTestApp):
    """A sequence over ids holding ``::`` renders, with no PlantUML syntax error."""
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert_no_warnings(app)
    assert len(sources) == 1
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "<object" in html


@pytest.mark.parametrize("test_app", [params(NAMESPACED)], indirect=True)
def test_aliases_and_arrow_ends_are_entity_names(test_app: SphinxTestApp):
    """Aliases and arrow ends are mapped; titles and labels keep their text."""
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert sources == [
        "@startuml\n"
        "\n' Nodes definition \n\n"
        'participant "User::A" as SUPPLIER__USER_A\n'
        'participant "User::B" as SUPPLIER__USER_B\n'
        "\n' Connection definition \n\n"
        "SUPPLIER__USER_A -> SUPPLIER__USER_B: Act::1\n"
        "SUPPLIER__USER_B -> USER_C: Act::2\n"
        "\n@enduml"
    ]


PLAIN = """\
Plain
=====

.. req:: User A
   :id: USER_A
   :links: MSG_1

.. spec:: Message 1
   :id: MSG_1
   :links: USERS_B, USER_C

.. req:: User B
   :id: USERS_B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_D

.. req:: User C
   :id: USER_C

.. req:: User D
   :id: USER_D

.. req:: Not drawn
   :id: USERS:B

.. needsequence::
   :start: USER_A
"""


@pytest.mark.parametrize("test_app", [params(PLAIN)], indirect=True)
def test_plain_ids_are_written_as_before(test_app: SphinxTestApp):
    """A sequence over ids holding no folded character is written byte for byte as before.

    The project also holds ``USERS:B``, which folds to ``USERS_B`` and sorts before
    it, but is no participant of this diagram: the mapping is made over the
    diagram's own participants, so it does not rename ``USERS_B``.
    """
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert sources == [
        "@startuml\n"
        "\n' Nodes definition \n\n"
        'participant "User A" as USER_A\n'
        'participant "User B" as USERS_B\n'
        "\n' Connection definition \n\n"
        "USER_A -> USER_C: Message 1\n"
        "USER_A -> USERS_B: Message 1\n"
        "USERS_B -> USER_D: Message 2\n"
        "\n@enduml"
    ]


COLLIDING = """\
Colliding
=========

.. req:: User A
   :id: USER_A
   :links: MSG_1

.. spec:: Message 1
   :id: MSG_1
   :links: SUPPLIER::B, SUPPLIER__B

.. req:: Colons
   :id: SUPPLIER::B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_C

.. req:: Underscores
   :id: SUPPLIER__B
   :links: MSG_3

.. spec:: Message 3
   :id: MSG_3
   :links: USER_C

.. req:: User C
   :id: USER_C

.. needsequence::
   :start: USER_A
"""


@pytest.mark.parametrize("test_app", [params(COLLIDING)], indirect=True)
def test_ids_folding_alike_stay_two_participants(test_app: SphinxTestApp):
    """``SUPPLIER::B`` and ``SUPPLIER__B`` fold alike, and are two participants.

    As in needflow, the ids are mapped in sorted order: ``SUPPLIER::B`` keeps the
    folded name and ``SUPPLIER__B`` is given a numeric suffix.
    """
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert len(sources) == 1
    lines = sources[0].splitlines()
    assert 'participant "Colons" as SUPPLIER__B' in lines
    assert 'participant "Underscores" as SUPPLIER__B_2' in lines
    assert "USER_A -> SUPPLIER__B: Message 1" in lines
    assert "USER_A -> SUPPLIER__B_2: Message 1" in lines
    assert "SUPPLIER__B -> USER_C: Message 2" in lines
    assert "SUPPLIER__B_2 -> USER_C: Message 3" in lines


TWO_STARTS = """\
Two starts
==========

.. req:: Colons
   :id: SUPPLIER::B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_C

.. req:: Underscores
   :id: SUPPLIER__B
   :links: MSG_3

.. spec:: Message 3
   :id: MSG_3
   :links: USER_C

.. req:: User C
   :id: USER_C

.. needsequence::
   :start: SUPPLIER::B, SUPPLIER__B
"""


@pytest.mark.parametrize("test_app", [params(TWO_STARTS)], indirect=True)
def test_one_mapping_per_diagram(test_app: SphinxTestApp):
    """Ids that fold alike from two start needs are still two participants.

    The names are made once for the diagram, not once per start need.
    """
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert len(sources) == 1
    lines = sources[0].splitlines()
    assert 'participant "Colons" as SUPPLIER__B' in lines
    assert 'participant "Underscores" as SUPPLIER__B_2' in lines
    assert "SUPPLIER__B -> USER_C: Message 2" in lines
    assert "SUPPLIER__B_2 -> USER_C: Message 3" in lines


CAPPED = """\
Capped
======

.. req:: User A
   :id: USER_A
   :links: MSG_1

.. spec:: Message 1
   :id: MSG_1
   :links: SUPPLIER::USER_B

.. req:: User B
   :id: SUPPLIER::USER_B
   :links: MSG_2

.. spec:: Message 2
   :id: MSG_2
   :links: USER_C

.. req:: User C
   :id: USER_C

.. needsequence::
   :start: USER_A
   :max_items: 1
"""


@pytest.mark.parametrize("test_app", [params(CAPPED)], indirect=True)
def test_restored_declaration_is_an_entity_name(test_app: SphinxTestApp):
    """The declaration ``max_items`` restores for the last receiver is mapped too."""
    app = test_app
    sources = capture_sequences(app)
    app.build()

    assert len(sources) == 1
    lines = sources[0].splitlines()
    assert 'participant "User B" as SUPPLIER__USER_B' in lines
    assert "USER_A -> SUPPLIER__USER_B: Message 1" in lines
    assert not any("SUPPLIER::" in line for line in lines)
