"""A need part's ``title`` is its text, on every route a part is read (#2356).

A part has no title of its own. A needtable row of a part, ``:show_parts:`` and ``:need:``
showed its text in the title's place, while a filter, a join, a sort and a needlist line
read the title of the part's NEED. Each test below reads one of those routes on one
project: ``REQ_A``, titled ``Alpha``, with the parts ``p1`` "steer well" and ``p2`` "brake
fast" (written in that order, so that a sort by title differs from a sort by id).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from docutils import nodes
from lxml import html as html_parser
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_fields = {
    "owner": {"schema": {"type": "string"}, "nullable": True},
    "duration": {"schema": {"type": "integer"}, "nullable": True},
}
needs_links = {
    "lff": {},
    "lfm": {},
    "by_title": {
        "derive": {
            "kind": "links",
            "join": {"field": "title", "equals": "owner"},
            "include_parts": True,
        }
    },
}
"""

INDEX = """\
Parts
=====

.. toctree::

   views

.. req:: Alpha
   :id: REQ_A
   :status: open
   :duration: 2

   First :np:`(p1) steer well` and :np:`(p2) brake fast`.

.. spec:: By the part's text
   :id: SPEC_TEXT
   :owner: brake fast
   :lff: [[links_from_filter("title == 'brake fast'", include_parts=True)]]
   :lfm: [[links_from_match("title", "owner", include_parts=True)]]

.. spec:: By the need's title
   :id: SPEC_TITLE
   :owner: Alpha
   :lff: [[links_from_filter("title == 'Alpha'", include_parts=True)]]
   :lfm: [[links_from_match("title", "owner", include_parts=True)]]
"""

VIEWS = """\
Views
=====

.. container:: list-of-parts

   .. needlist::
      :filter: id_parent == "REQ_A"

.. container:: sorted-by-title

   .. needtable::
      :filter: id_parent == "REQ_A"
      :columns: id;title
      :sort: title
      :style: table

.. needgantt:: Gantt
   :filter: id_parent == "REQ_A"
"""


def project() -> list[dict[str, object]]:
    return [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("views.rst"), VIEWS),
            ],
        }
    ]


def _container(app: Sphinx, name: str) -> html_parser.HtmlElement:
    """The ``.. container::`` of class *name* on the built page ``views.html``."""
    page = Path(app.outdir, "views.html").read_text(encoding="utf-8")
    (found,) = html_parser.fromstring(page).xpath(
        f'//div[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'
    )
    return found


def _links(app: Sphinx, need_id: str, link_type: str) -> list[str]:
    return list(SphinxNeedsData(app.env).get_needs_view()[need_id][link_type])


@pytest.fixture
def built(test_app: Sphinx) -> tuple[Sphinx, list[str]]:
    """The project built, with no warning, and the PlantUML source of its gantt."""
    uml: list[str] = []

    def collect(_app: Sphinx, doctree: nodes.document, _docname: str) -> None:
        uml.extend(node["uml"] for node in doctree.findall(plantuml))

    test_app.connect("doctree-resolved", collect, priority=900)
    test_app.build()
    assert build_warnings(test_app) == []
    return test_app, uml


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_needlist_line_of_a_part_shows_its_text(
    built: tuple[Sphinx, list[str]],
) -> None:
    """A needlist lists a part as its id and its text, linking the part's need."""
    lines = _container(built[0], "list-of-parts").xpath('.//div[@class="line"]')
    assert [line.text_content() for line in lines] == [
        "REQ_A: Alpha",
        "p1: steer well",
        "p2: brake fast",
    ]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_sort_by_title_sorts_a_part_by_its_text(
    built: tuple[Sphinx, list[str]],
) -> None:
    """``Alpha`` < ``brake fast`` (``p2``) < ``steer well`` (``p1``): not the id order."""
    rows = _container(built[0], "sorted-by-title").xpath(".//tr[@data-need-id]")
    assert [row.get("data-need-id") for row in rows] == [
        "REQ_A",
        "REQ_A.p2",
        "REQ_A.p1",
    ]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_needgantt_part_element_is_labelled_by_its_text(
    built: tuple[Sphinx, list[str]],
) -> None:
    (uml,) = built[1]
    declared = re.findall(r"^\[(.*)\] as \[([^\]]*)\] lasts ", uml, re.MULTILINE)
    assert {alias: label for label, alias in declared} == {
        "REQ_A": "Alpha",
        "p1": "steer well",
        "p2": "brake fast",
    }


#: The three routes a join or a filter on ``title`` reads a part with ``include_parts``:
#: ``links_from_filter``, ``links_from_match`` and a declared ``links`` rule with ``join``.
LINK_ROUTES = pytest.mark.parametrize("link_type", ["lff", "lfm", "by_title"])


@LINK_ROUTES
@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_title_test_with_include_parts_matches_a_part_by_its_text(
    built: tuple[Sphinx, list[str]], link_type: str
) -> None:
    """``SPEC_TEXT`` asks for the title ``brake fast``: the part ``p2`` is its text."""
    assert _links(built[0], "SPEC_TEXT", link_type) == ["REQ_A.p2"]


@LINK_ROUTES
@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_need_title_with_include_parts_no_longer_links_its_parts(
    built: tuple[Sphinx, list[str]], link_type: str
) -> None:
    """``SPEC_TITLE`` asks for the title ``Alpha``: the need alone, not its parts."""
    assert _links(built[0], "SPEC_TITLE", link_type) == ["REQ_A"]


@pytest.mark.parametrize("test_app", project(), indirect=True)
def test_a_need_keeps_its_own_title(built: tuple[Sphinx, list[str]]) -> None:
    """Only a part's ``title`` is its text: the need's, read directly or through
    ``id_parent``, is the need's."""
    view = SphinxNeedsData(built[0].env).get_needs_view()
    need = view["REQ_A"]
    assert need["title"] == "Alpha"
    parts = {part["id"]: part for part in need.iter_part_items()}
    assert {pid: part["title"] for pid, part in parts.items()} == {
        "p1": "steer well",
        "p2": "brake fast",
    }
    assert view[parts["p1"]["id_parent"]]["title"] == "Alpha"
