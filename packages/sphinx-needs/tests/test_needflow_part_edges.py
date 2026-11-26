"""A needflow's edge to a need names the parts it links; an external part links its anchor.

With ``needs_views_include_parts = False`` a needflow holds needs alone, and a link to a
part of a need it draws ends on that need. The links of one source need, of one link
type, that name live parts of one need it draws are ONE edge to that need, in the link
type's ``style_part``, labelled with those part ids: bare, in the need's stored order (the
order its content writes them, then the parts its record states), each once, joined
``", "``. A whole link of the same source, link type and need stays its own unlabelled
edge in ``style``; each link type draws its own edge; a dead part link draws nothing and
names nothing. With ``:show_link_names:`` the label is the link type's name and the part
ids, on two lines.

Under ``True`` and unset a needflow draws what it drew but for two kinds of line: an
external need's part node links the part's anchor, and graphviz writes no ``ltail`` on a
need's edge to its own part, inside it. A needtable's row and link cell of an external need's part, and
needuml's ``ref()`` of one, link the part's anchor too.

One project, built with the value ``True``, ``False`` and unset; each view sits in a
container named after it on ``views.rst``.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes
from lxml import etree
from lxml import html as html_parser
from sphinx.testing.util import SphinxTestApp
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs.directives.needflow._model import collect_edges
from sphinx_needs_testkit import assert_no_warnings, build_warnings

#: The line each arm adds to ``conf.py``.
VALUES = {
    "true": "needs_views_include_parts = True\n",
    "false": "needs_views_include_parts = False\n",
    "unset": "",
}

#: The two needflow engines; every needflow of the project is written once for each.
ENGINES = ("plantuml", "graphviz")

CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_links = {"tests": {}}
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "external.json"},
]
needs_build_json = True
needs_reproducible_json = True
"""

IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "req",
                    "title": "Imported",
                    "content": "Marks :np:`(sc) content one`.",
                    "parts": {"rp": {"id": "rp", "content": "an imported record part"}},
                }
            }
        }
    },
}

EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_1": {
                    "id": "EXT_1",
                    "type": "req",
                    "title": "External",
                    "docname": "ext",
                    "content": "",
                    "parts": {"rp": {"id": "rp", "content": "an external record part"}},
                }
            }
        }
    },
}

INDEX = """\
Parts
=====

.. toctree::

   views

.. req:: Parts written out of id order
   :id: REQ_1
   :status: open

   First :np:`(zeta) the zeta text`, then :np:`(alpha) the alpha text`,
   and :np:`(mid) a part nobody links`.

.. req:: A need that links its own part
   :id: REQ_2
   :links: REQ_2.own

   :np:`(own) its own part`

.. req:: A need whose id holds a dot
   :id: REQ_9.x

.. needimport:: imported.json

.. spec:: One part link
   :id: SPEC_1
   :links: REQ_1.zeta

.. spec:: Two part links, in the need's order
   :id: SPEC_2
   :links: REQ_1.zeta, REQ_1.alpha

.. spec:: A whole link and a part link to one need
   :id: SPEC_3
   :links: REQ_1, REQ_1.alpha

.. spec:: A link to a part the need does not have
   :id: SPEC_4
   :links: REQ_1.nope

.. spec:: A link to a part of a need that does not exist
   :id: SPEC_5
   :links: MISSING.p1

.. spec:: A link to the need whose id holds a dot
   :id: SPEC_6
   :links: REQ_9.x

.. spec:: Two part links, in the other order
   :id: SPEC_7
   :links: REQ_1.alpha, REQ_1.zeta

.. spec:: A live and a dead part of one need
   :id: SPEC_8
   :links: REQ_1.zeta, REQ_1.nope, REQ_1.zz

.. spec:: One part named twice, the second time with a condition
   :id: SPEC_9
   :links: REQ_1.alpha, REQ_1.alpha[status == "open"]

.. test:: Links to the stated parts of an imported and an external need
   :id: TEST_1
   :tests: IMP_1.rp, EXT_1.rp

.. test:: Two link types to one part
   :id: TEST_2
   :links: REQ_1.zeta
   :tests: REQ_1.zeta

.. test:: A stated part, then a content part, of one need
   :id: TEST_3
   :links: IMP_1.rp, IMP_1.sc
"""

#: Each needflow of the project, by the name its container takes after its engine.
FLOWS = {
    # every need
    "flow": "",
    "names": "   :show_link_names:\n",
    # walked from a part, against its links
    "root": "   :root_id: REQ_1.zeta\n   :root_direction: incoming\n",
    # needs alone, REQ_1 among them
    "needs": '   :filter: id in ["SPEC_1", "SPEC_2", "SPEC_3", "TEST_2", "REQ_1"]\n',
    # the specs, and every part
    "parts": '   :filter: type == "spec" or is_part\n',
    # needs linking parts of REQ_1, which it does not draw
    "shown": ('   :filter: id in ["SPEC_1", "SPEC_2", "SPEC_3", "SPEC_4", "TEST_2"]\n'),
}

VIEWS = """\
Views
=====

.. container:: table

   .. needtable::
      :show_parts:
      :columns: ID;TITLE;STATUS;TYPE;LINKS;TESTS;LINKS_BACK;TESTS_BACK
      :style: table

.. container:: table-plain

   .. needtable::
      :filter: id_parent == "EXT_1" or id == "TEST_1"
      :columns: ID;TESTS
      :style: table

.. container:: uml

   .. needuml::

      card "{{ref("EXT_1.rp", text="the external part")}}" as c
""" + "".join(
    f"\n.. container:: {name}-{engine}\n\n   .. needflow::\n"
    f"      :engine: {engine}\n"
    + "".join(f"   {line}\n" for line in options.splitlines())
    for name, options in FLOWS.items()
    for engine in ENGINES
)


def files(value: str) -> list[tuple[Path, str]]:
    """The project, with the line of the arm *value* added to ``conf.py``."""
    return [
        (Path("conf.py"), CONF + VALUES[value]),
        (Path("index.rst"), INDEX),
        (Path("views.rst"), VIEWS),
        (Path("imported.json"), json.dumps(IMPORTED)),
        (Path("external.json"), json.dumps(EXTERNAL)),
    ]


def project(value: str, **kwargs: Any) -> dict[str, Any]:
    return {"buildername": "html", "files": files(value), **kwargs}


ARMS = pytest.mark.parametrize(
    "test_app", [project(value) for value in VALUES], indirect=True, ids=list(VALUES)
)


def capture(app: SphinxTestApp) -> dict[str, str]:
    """The source of each needflow and needuml, by the class of its container, as the
    page is written."""
    sources: dict[str, str] = {}

    def collect(_app: Any, doctree: nodes.document, _docname: str) -> None:
        for container in doctree.findall(nodes.container):
            for node in container.findall(NeedflowGraphiz):
                sources[container["classes"][0]] = node["resolved_content"]
            for node in container.findall(plantuml):
                sources[container["classes"][0]] = node["uml"]

    app.connect("doctree-resolved", collect, priority=900)
    return sources


#: An edge as either engine writes it: its ends, its style (``""`` for none) and its
#: label (``None`` for none), the label as written, a ``\n`` in it being the two
#: characters PlantUML and dot both read as a line break.
Edge = tuple[str, str, str, str | None]

_PUML_EDGE = re.compile(r"^(\S+) -(?:\[([^\]]*)\])?-> (\S+?)(?:: (.*)\\n)?$")
_DOT_EDGE = re.compile(r'^"([^"]+)" -> "([^"]+)" \[(.*)\];$')
_DOT_LABEL = re.compile(r'label="((?:[^"\\]|\\.)*)"')
_DOT_STYLE = re.compile(r'style="([^"]*)"')


def edges(source: str) -> list[Edge]:
    """Every edge a needflow's source writes, in the order written."""
    found: list[Edge] = []
    if source.startswith("@startuml"):
        connections = source.split("' Connection definition \n", 1)[1]
        for line in connections.splitlines():
            if (match := _PUML_EDGE.match(line)) is not None:
                tail, style, head, label = match.groups()
                found.append((tail, head, style or "", label))
        return found
    for line in source.splitlines():
        if (match := _DOT_EDGE.match(line)) is not None:
            tail, head, attributes = match.groups()
            style = _DOT_STYLE.search(attributes)
            label = _DOT_LABEL.search(attributes)
            found.append(
                (
                    tail,
                    head,
                    style[1] if style else "",
                    label[1] if label else None,
                )
            )
    return found


def _page(app: SphinxTestApp) -> Any:
    return html_parser.fromstring(
        Path(app.outdir, "views.html").read_text(encoding="utf-8")
    )


def _container(app: SphinxTestApp, name: str) -> Any:
    (container,) = _page(app).xpath(
        f'//div[contains(concat(" ", normalize-space(@class), " "), " {name} ")]'
    )
    return container


def _row(app: SphinxTestApp, table: str, need_id: str) -> Any:
    (row,) = _container(app, table).xpath(f'.//tr[@data-need-id="{need_id}"]')
    return row


def _cell(row: Any, key: str) -> Any:
    (cell,) = row.xpath(f'./td[contains(concat(" ", @class, " "), " needs_{key} ")]')
    return cell


def _links(cell: Any) -> dict[str, str]:
    """What a cell links, by the text of each link."""
    return {a.text_content(): a.get("href") for a in cell.xpath(".//a")}


#: The edges ``flow`` draws under ``False``, on either engine: one edge per source, link
#: type and need for the links naming parts of the need, labelled with them in the
#: need's stored order (``zeta`` before ``alpha``; the content's ``sc`` before the stated
#: ``rp``), each once; a whole link its own unlabelled edge; a link to the need whose id
#: holds a ``.`` as it was; no edge for a dead part link or a part of a missing need.
FALSE_FLOW: list[Edge] = [
    ("REQ_2", "REQ_2", "dotted", "own"),
    ("SPEC_1", "REQ_1", "dotted", "zeta"),
    ("SPEC_2", "REQ_1", "dotted", "zeta, alpha"),
    ("SPEC_3", "REQ_1", "", None),
    ("SPEC_3", "REQ_1", "dotted", "alpha"),
    ("SPEC_6", "REQ_9.x", "dotted", None),
    ("SPEC_7", "REQ_1", "dotted", "zeta, alpha"),
    ("SPEC_8", "REQ_1", "dotted", "zeta"),
    ("SPEC_9", "REQ_1", "dotted", "alpha"),
    ("TEST_1", "EXT_1", "dotted", "rp"),
    ("TEST_1", "IMP_1", "dotted", "rp"),
    # one edge per link type: `tests`, then `links`
    ("TEST_2", "REQ_1", "dotted", "zeta"),
    ("TEST_2", "REQ_1", "dotted", "zeta"),
    ("TEST_3", "IMP_1", "dotted", "sc, rp"),
]

#: The same with ``:show_link_names:``: the link type's name, then the part ids, on two
#: lines; a whole edge, and the edge to the need whose id holds a ``.``, the name alone.
FALSE_NAMES: list[Edge] = [
    ("REQ_2", "REQ_2", "dotted", r"links outgoing\nown"),
    ("SPEC_1", "REQ_1", "dotted", r"links outgoing\nzeta"),
    ("SPEC_2", "REQ_1", "dotted", r"links outgoing\nzeta, alpha"),
    ("SPEC_3", "REQ_1", "", "links outgoing"),
    ("SPEC_3", "REQ_1", "dotted", r"links outgoing\nalpha"),
    ("SPEC_6", "REQ_9.x", "dotted", "links outgoing"),
    ("SPEC_7", "REQ_1", "dotted", r"links outgoing\nzeta, alpha"),
    ("SPEC_8", "REQ_1", "dotted", r"links outgoing\nzeta"),
    ("SPEC_9", "REQ_1", "dotted", r"links outgoing\nalpha"),
    ("TEST_1", "EXT_1", "dotted", r"tests\nrp"),
    ("TEST_1", "IMP_1", "dotted", r"tests\nrp"),
    ("TEST_2", "REQ_1", "dotted", r"tests\nzeta"),
    ("TEST_2", "REQ_1", "dotted", r"links outgoing\nzeta"),
    ("TEST_3", "IMP_1", "dotted", r"links outgoing\nsc, rp"),
]

#: The other needflows under ``False``: walked from ``REQ_1.zeta`` against its links
#: (in the walk's order); needs alone with ``REQ_1``; and two that draw no edge, one
#: holding no part (its filter selects needs alone) and one not drawing ``REQ_1``.
FALSE_OTHERS: dict[str, list[Edge]] = {
    "root": [
        ("SPEC_8", "REQ_1", "dotted", "zeta"),
        ("SPEC_7", "REQ_1", "dotted", "zeta, alpha"),
        ("SPEC_2", "REQ_1", "dotted", "zeta, alpha"),
        ("SPEC_1", "REQ_1", "dotted", "zeta"),
        ("TEST_2", "REQ_1", "dotted", "zeta"),
        ("TEST_2", "REQ_1", "dotted", "zeta"),
    ],
    "needs": [
        ("SPEC_1", "REQ_1", "dotted", "zeta"),
        ("SPEC_2", "REQ_1", "dotted", "zeta, alpha"),
        ("SPEC_3", "REQ_1", "", None),
        ("SPEC_3", "REQ_1", "dotted", "alpha"),
        ("TEST_2", "REQ_1", "dotted", "zeta"),
        ("TEST_2", "REQ_1", "dotted", "zeta"),
    ],
    "parts": [],
    "shown": [],
}


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("test_app", [project("false")], indirect=True, ids=["false"])
def test_false_draws_one_labelled_edge_per_source_link_type_and_need(
    test_app: SphinxTestApp, engine: str
) -> None:
    sources = capture(test_app)
    test_app.build()
    assert edges(sources[f"flow-{engine}"]) == FALSE_FLOW
    assert edges(sources[f"names-{engine}"]) == FALSE_NAMES
    for name, expected in FALSE_OTHERS.items():
        assert edges(sources[f"{name}-{engine}"]) == expected, name


#: The sources of the project's needflows under ``True`` (and unset) as sphinx-needs
#: wrote them before; the test holds today's to them but for the lines named below.
BEFORE = json.loads(
    (Path(__file__).parent / "fixtures" / "needflow_part_links_before.json").read_text(
        encoding="utf-8"
    )
)["sources"]


def _today(before: str) -> str:
    """A source as written before, with the two kinds of line that change today: the
    external need's part node links the part's anchor, and graphviz writes no ``ltail``
    on the edge from a need to its own part inside it."""
    lines = []
    for line in before.split("\n"):
        if " as EXT_1.rp [[" in line or line.lstrip().startswith('"EXT_1.rp" ['):
            line = line.replace("#EXT_1]]", "#EXT_1.rp]]").replace(
                '#EXT_1"', '#EXT_1.rp"'
            )
        if line.startswith('"REQ_2" -> "REQ_2.own" ['):
            line = line.replace(', ltail="cluster_REQ_2"', "")
        lines.append(line)
    return "\n".join(lines)


#: How many lines of each needflow change, by its name: the external part's node where
#: one is drawn, and on graphviz the edge from ``REQ_2`` to its own part.
MOVED = {
    "flow-plantuml": 1,
    "flow-graphviz": 2,
    "names-plantuml": 1,
    "names-graphviz": 2,
    "root-plantuml": 0,
    "root-graphviz": 0,
    "needs-plantuml": 0,
    "needs-graphviz": 0,
    "parts-plantuml": 0,
    "parts-graphviz": 0,
    "shown-plantuml": 0,
    "shown-graphviz": 0,
}


def test_the_lines_named_are_the_lines_that_move() -> None:
    """The premise of the next test: :func:`_today` moves exactly the lines it names."""
    assert set(BEFORE) == set(MOVED)
    for name, source in BEFORE.items():
        moved = [
            (old, new)
            for old, new in zip(
                source.split("\n"), _today(source).split("\n"), strict=True
            )
            if old != new
        ]
        assert len(moved) == MOVED[name], name


@pytest.mark.parametrize(
    "test_app",
    [project("true"), project("unset")],
    indirect=True,
    ids=["true", "unset"],
)
def test_true_and_unset_draw_what_they_drew_but_two_kinds_of_line(
    test_app: SphinxTestApp,
) -> None:
    """Nothing is labelled and no node or edge moves: the part nodes are the parts the
    filter selects, a link to a part ends on its node. Two kinds of line change
    (:func:`_today`): an external part's node links the part's anchor, and graphviz's
    edge from a need to its own part names no ``ltail``."""
    sources = capture(test_app)
    test_app.build()
    assert {name: sources[name] for name in BEFORE} == {
        name: _today(source) for name, source in BEFORE.items()
    }


@pytest.mark.parametrize("test_app", [project("true")], indirect=True, ids=["true"])
def test_graphviz_draws_a_needs_edge_to_its_own_part_without_ltail(
    test_app: SphinxTestApp,
) -> None:
    """The edge leaves the need's cluster for a part inside it: ``ltail`` would name the
    cluster holding its head, which ``dot`` warns about and ignores."""
    sources = capture(test_app)
    test_app.build()
    source = sources["flow-graphviz"]
    assert '"REQ_2" -> "REQ_2.own" [style="dotted", arrowhead=vee];' in source.split(
        "\n"
    )
    dot = subprocess.run(
        [test_app.config.graphviz_dot, "-Tsvg"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "head is inside tail cluster" not in dot.stderr


LTAIL_INDEX = """\
Ltail
=====

.. req:: A need with a part, linking it, another need and that need's part
   :id: REQ_A
   :links: REQ_A.own, REQ_B, REQ_B.p

   :np:`(own) its own part`

.. req:: Another need with a part
   :id: REQ_B

   :np:`(p) its part`

.. needflow::
   :engine: graphviz
   :filter: id_parent in ["REQ_A", "REQ_B"]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF + VALUES["true"]),
                (Path("index.rst"), LTAIL_INDEX),
                (Path("imported.json"), json.dumps(IMPORTED)),
                (Path("external.json"), json.dumps(EXTERNAL)),
            ],
        }
    ],
    indirect=True,
    ids=["true"],
)
def test_graphviz_keeps_ltail_on_an_edge_leaving_a_need_for_another(
    test_app: SphinxTestApp,
) -> None:
    """Only the edge to the need's own part loses ``ltail``: an edge from the need's
    cluster to another need, or to another need's part, still leaves the cluster."""
    sources: list[str] = []

    def collect(_app: Any, doctree: nodes.document, _docname: str) -> None:
        sources.extend(
            node["resolved_content"] for node in doctree.findall(NeedflowGraphiz)
        )

    test_app.connect("doctree-resolved", collect, priority=900)
    test_app.build()
    [source] = sources
    lines = source.split("\n")
    assert [line for line in lines if line.startswith('"REQ_A" -> ')] == [
        '"REQ_A" -> "REQ_A.own" [style="dotted", arrowhead=vee];',
        '"REQ_A" -> "REQ_B" [arrowhead=vee, ltail="cluster_REQ_A", lhead="cluster_REQ_B"];',
        '"REQ_A" -> "REQ_B.p" [style="dotted", arrowhead=vee, ltail="cluster_REQ_A"];',
    ]


#: An external source whose ids carry a prefix, and its need's parts, one with a ``.``
#: in its id.
PREFIXED_CONF = """\
extensions = ["sphinx_needs"]
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "external.json", "id_prefix": "P_"},
]
needs_views_include_parts = False
"""

PREFIXED_EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_1": {
                    "id": "EXT_1",
                    "type": "req",
                    "title": "External",
                    "docname": "ext",
                    "content": "",
                    "parts": {
                        "rp": {"id": "rp", "content": "a part"},
                        "a.b": {"id": "a.b", "content": "a part whose id holds a dot"},
                    },
                }
            }
        }
    },
}

PREFIXED_INDEX = """\
Prefixed
========

.. spec:: Links a prefixed external need's parts
   :id: SPEC_1
   :links: P_EXT_1.rp, P_EXT_1.a.b

.. needtable::
   :show_parts:
   :filter: id in ["P_EXT_1", "SPEC_1"]
   :columns: ID;LINKS
   :style: table
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PREFIXED_CONF),
                (Path("index.rst"), PREFIXED_INDEX),
                (Path("external.json"), json.dumps(PREFIXED_EXTERNAL)),
            ],
        }
    ],
    indirect=True,
    ids=["false"],
)
def test_an_external_part_links_its_anchor_through_the_sources_prefix(
    test_app: SphinxTestApp,
) -> None:
    """The source's ``id_prefix`` is not in the URL's fragment: the part's anchor is the
    fragment with ``.<part>`` added, a part id holding a ``.`` too, in its row and in a
    cell naming it."""
    test_app.build()
    page = html_parser.fromstring(
        Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
    )

    def row(need_id: str) -> Any:
        (found,) = page.xpath(f'//tr[@data-need-id="{need_id}"]')
        return found

    anchor = "http://example.org/ext.html#EXT_1"
    assert _links(_cell(row("P_EXT_1"), "id")) == {"P_EXT_1": anchor}
    assert _links(_cell(row("P_EXT_1.rp"), "id_complete")) == {
        "→\xa0P_EXT_1.rp": f"{anchor}.rp"
    }
    assert _links(_cell(row("P_EXT_1.a.b"), "id_complete")) == {
        "→\xa0P_EXT_1.a.b": f"{anchor}.a.b"
    }
    assert _links(_cell(row("SPEC_1"), "links")) == {
        "P_EXT_1.rp": f"{anchor}.rp",
        "P_EXT_1.a.b": f"{anchor}.a.b",
    }


DOTTED_EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_9": {
                    "id": "EXT_9",
                    "type": "req",
                    "title": "A need whose id begins another's",
                    "docname": "ext",
                    "content": "",
                },
                "EXT_9.x": {
                    "id": "EXT_9.x",
                    "type": "req",
                    "title": "A need whose id holds a dot",
                    "docname": "ext",
                    "content": "",
                },
            }
        }
    },
}

DOTTED_INDEX = """\
Dotted
======

.. spec:: Links the external need whose id holds a dot
   :id: SPEC_1
   :links: EXT_9.x

.. needtable::
   :filter: id == "SPEC_1"
   :columns: ID;LINKS
   :style: table
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\n'
                    "needs_external_needs = [\n"
                    '    {"base_url": "http://example.org", "json_path": "external.json"},\n'
                    "]\n",
                ),
                (Path("index.rst"), DOTTED_INDEX),
                (Path("external.json"), json.dumps(DOTTED_EXTERNAL)),
            ],
        }
    ],
    indirect=True,
    ids=["unset"],
)
def test_a_cell_naming_an_external_need_whose_id_holds_a_dot_links_as_before(
    test_app: SphinxTestApp,
) -> None:
    """A link naming such a need whole is not a part's: the cell links what it linked
    before, never a part's anchor (what such a link means is not settled)."""
    test_app.build()
    page = html_parser.fromstring(
        Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
    )
    (spec,) = page.xpath('//tr[@data-need-id="SPEC_1"]')
    assert _links(_cell(spec, "links")) == {
        "EXT_9.x": "http://example.org/ext.html#EXT_9"
    }


@ARMS
def test_an_external_part_links_its_anchor(test_app: SphinxTestApp) -> None:
    """A needtable's row of an external need's part, and its cell naming one, link the
    part's anchor, as ``:need:`` does; so does needuml's ``ref()``. Under ``True`` and
    unset the filter selects the part, which gets a row of its own."""
    value = test_app.config.needs_views_include_parts
    sources = capture(test_app)
    test_app.build()
    anchor = "http://example.org/ext.html#EXT_1.rp"
    row = _row(test_app, "table", "EXT_1.rp")
    assert _links(_cell(row, "id_complete")) == {"→\xa0EXT_1.rp": anchor}
    assert _links(_cell(_row(test_app, "table", "TEST_1"), "tests")) == {
        "EXT_1.rp": anchor,
        "IMP_1.rp": "index.html#IMP_1.rp",
    }
    plain = _container(test_app, "table-plain")
    assert [r.get("data-need-id") for r in plain.xpath(".//tr[@data-need-id]")] == (
        ["EXT_1", "TEST_1"] if value is False else ["EXT_1", "EXT_1.rp", "TEST_1"]
    )
    if value is not False:
        own_row = _row(test_app, "table-plain", "EXT_1.rp")
        assert _links(_cell(own_row, "id")) == {"→\xa0EXT_1.rp": anchor}
    # the need itself links the need's anchor
    assert _links(_cell(_row(test_app, "table", "EXT_1"), "id")) == {
        "EXT_1": "http://example.org/ext.html#EXT_1"
    }
    assert f"[[{anchor} the external part]]" in sources["uml"]


@ARMS
def test_a_part_row_lists_no_link_of_its_own_and_its_own_back_links(
    test_app: SphinxTestApp,
) -> None:
    """A part has no links out: its row's outgoing cells are empty where its need's
    list the need's links; its incoming cells are the part's own back links, not its
    need's."""
    test_app.build()
    need = _row(test_app, "table", "REQ_2")
    part = _row(test_app, "table", "REQ_2.own")
    assert _cell(need, "links").text_content() == "REQ_2.own"
    assert _cell(part, "links").text_content() == ""
    assert _cell(part, "tests").text_content() == ""
    zeta = _row(test_app, "table", "REQ_1.zeta")
    assert _cell(zeta, "links_back").text_content() == (
        "SPEC_1; SPEC_2; SPEC_7; SPEC_8; TEST_2"
    )
    assert _cell(zeta, "tests_back").text_content() == "TEST_2"
    assert (
        _cell(_row(test_app, "table", "REQ_1.mid"), "links_back").text_content() == ""
    )
    assert _cell(_row(test_app, "table", "REQ_1"), "links_back").text_content() == (
        "SPEC_1; SPEC_2; SPEC_3; SPEC_4; SPEC_7; SPEC_8; SPEC_9; TEST_2"
    )


def _report(line: int, text: str) -> str:
    return (
        f"<srcdir>/views.rst:{line}: WARNING: {text}; or suppress "
        "needs.views_include_parts. [needs.views_include_parts]"
    )


#: What a needflow's report adds before its last clause: the option that keeps its parts
#: whatever the value.
SHOW_PARTS = (
    "; or add :show_parts: to draw each need the needflow draws with its parts inside "
    "it, whatever the value"
)


def _flow_report(line: int, parts: int, links: int) -> str:
    return _report(
        line,
        f"This needflow's filter selects {parts} need parts, and from Sphinx-Needs 10.0 "
        f"it draws {links} links to need parts as edges to the parts' needs: a view's "
        "filter then selects needs only, and a needflow draws a link to a part of a "
        "need it shows as an edge to that need. Set needs_views_include_parts = True to "
        "keep the needflow as it is, or False to draw needs only now" + SHOW_PARTS,
    )


DEAD = [
    f"<srcdir>/index.rst:{line}: WARNING: Need {need!r} has unknown outgoing link "
    f"{link!r} in field 'links' [needs.link_outgoing]"
    for line, need, link in (
        (38, "SPEC_4", "REQ_1.nope"),
        (42, "SPEC_5", "MISSING.p1"),
        (46, "SPEC_6", "REQ_9.x"),
        (54, "SPEC_8", "REQ_1.nope"),
        # a dead part whose id sorts after the live one's, as the links are stored
        (54, "SPEC_8", "REQ_1.zz"),
    )
]


def _unset_reports() -> list[str]:
    """The reports while the value is unset, as before: a needflow's count is of the
    LINKS it draws to the parts' needs under ``False`` (16 in ``flow``, drawn as 12
    edges); each needflow is written once per engine."""
    reports = [
        _report(
            13,
            "This needtable's filter selects 1 need part: from Sphinx-Needs 10.0 a "
            "view's filter selects needs only, and a needtable lists a need's parts "
            "under it only with :show_parts:. Set needs_views_include_parts = True to "
            "keep listing them, or False to list needs only now",
        )
    ]
    for lines, parts, links in (
        ((26, 31), 7, 16),
        ((36, 42), 7, 16),
        ((48, 55), 3, 8),
    ):
        reports += [_flow_report(line, parts, links) for line in lines]
    reports += [
        _report(
            line,
            "From Sphinx-Needs 10.0 this needflow draws 6 links to need parts as edges "
            "to the parts' needs, which it draws no edge for now: a view's filter then "
            "selects needs only, and a needflow draws a link to a part of a need it "
            "shows as an edge to that need. Set needs_views_include_parts = True to "
            "keep the needflow as it is, or False to draw those edges now" + SHOW_PARTS,
        )
        for line in (62, 68)
    ]
    reports += [
        _report(
            line,
            "This needflow's filter selects 7 need parts: from Sphinx-Needs 10.0 a "
            "view's filter selects needs only. Set needs_views_include_parts = True to "
            "keep drawing them, or False to draw needs only now" + SHOW_PARTS,
        )
        for line in (74, 80)
    ]
    return reports


@ARMS
def test_the_warnings_are_the_ones_before(
    test_app: SphinxTestApp, request: pytest.FixtureRequest
) -> None:
    """The dead links, under every value; and while unset the reports as they were,
    each needflow's count of links unchanged though it draws fewer edges."""
    value = request.node.callspec.id
    test_app.build()
    expected = DEAD + (_unset_reports() if value == "unset" else [])
    assert sorted(build_warnings(test_app)) == sorted(expected)


@pytest.mark.parametrize("test_app", [project("false")], indirect=True, ids=["false"])
def test_the_model_groups_what_the_engines_draw(test_app: SphinxTestApp) -> None:
    """The engine-independent edges under ``False``: a part named twice by one link type
    is named once (two links reading as the same address, as a link with a condition
    and one without do); a part the result holds itself (a filter function may build
    parts) keeps its node; the order of the links does not order the label."""
    test_app.build()
    data = SphinxNeedsData(test_app.env)
    links = data.get_schema().get_link_field("links")
    assert links is not None
    view = data.get_needs_view()
    source: Any = {
        "id_complete": "SRC",
        "links": [
            "REQ_1.alpha",
            "REQ_1.mid",
            "REQ_1.alpha",
            "REQ_1",
            "REQ_1.zeta",
            "REQ_1.nope",
            "IMP_1.sc",
        ],
    }
    part = view.to_list_with_parts()
    imp_sc = next(item for item in part if item["id_complete"] == "IMP_1.sc")
    found = [view["REQ_1"], view["IMP_1"], imp_sc, source]
    drawn = {"REQ_1", "IMP_1", "IMP_1.sc", "SRC"}
    assert [
        (edge.source_id, edge.target_id, edge.is_part, edge.part_ids)
        for edge in collect_edges(found, [links], drawn, part_links_to_needs=True)
    ] == [
        # where its first part link is
        ("SRC", "REQ_1", True, ("zeta", "alpha", "mid")),
        ("SRC", "REQ_1", False, ()),
        # the result holds the part: the link ends on it, unlabelled, as before
        ("SRC", "IMP_1.sc", True, ()),
    ]
    # with parts as candidates, nothing is grouped and nothing labelled
    assert [
        (edge.source_id, edge.target_id, edge.part_ids)
        for edge in collect_edges(found, [links], drawn)
    ] == [("SRC", "REQ_1", ()), ("SRC", "IMP_1.sc", ())]


EMPTY_STYLE_CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_links = {"plain": {"style_part": ""}}
"""

EMPTY_STYLE_INDEX = """\
Empty style
===========

.. req:: Parts
   :id: REQ_1

   :np:`(zeta) the zeta text`

.. spec:: A part link of a link type with no part style
   :id: SPEC_1
   :plain: REQ_1.zeta

.. needflow::
   :engine: plantuml
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), EMPTY_STYLE_CONF + VALUES[value]),
                (Path("index.rst"), EMPTY_STYLE_INDEX),
            ],
        }
        for value in ("true", "false")
    ],
    indirect=True,
    ids=["true", "false"],
)
def test_plantuml_writes_no_empty_style(test_app: SphinxTestApp) -> None:
    """A link type whose ``style_part`` is empty draws its part edge as a plain arrow:
    ``-[]->`` is a PlantUML syntax error."""
    sources: list[str] = []

    def collect(_app: Any, doctree: nodes.document, _docname: str) -> None:
        sources.extend(node["uml"] for node in doctree.findall(plantuml))

    test_app.connect("doctree-resolved", collect, priority=900)
    test_app.build()
    assert_no_warnings(test_app)
    [source] = sources
    assert "-[]->" not in source
    assert edges(source) == (
        [("SPEC_1", "REQ_1", "", "zeta")]
        if test_app.config.needs_views_include_parts is False
        else [("SPEC_1", "REQ_1.zeta", "", None)]
    )


RENDER_INDEX = """\
Render
======

.. req:: Parts
   :id: REQ_1

   First :np:`(zeta) the zeta text`, then :np:`(alpha) the alpha text`.

.. spec:: Two part links
   :id: SPEC_2
   :links: REQ_1.zeta, REQ_1.alpha

.. needflow::
   :show_link_names:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n'
                    f'needs_flow_engine = "{engine}"\n'
                    'plantuml_output_format = "svg"\n'
                    'graphviz_output_format = "svg"\n' + VALUES["false"],
                ),
                (Path("index.rst"), RENDER_INDEX),
            ],
            "plantuml": engine == "plantuml",
        }
        for engine in ENGINES
    ],
    indirect=True,
    ids=list(ENGINES),
)
def test_a_labelled_edge_renders(test_app: SphinxTestApp) -> None:
    """Each engine renders the edge's label, two lines, with no warning: the link
    type's name, then the part ids, never the two characters of the line break."""
    test_app.build()
    assert_no_warnings(test_app)
    [svg_path] = Path(test_app.outdir, "_images").glob("*.svg")
    svg = etree.fromstring(svg_path.read_bytes())
    texts = [
        " ".join("".join(element.itertext()).split())
        for element in svg.iter("{http://www.w3.org/2000/svg}text")
    ]
    assert "links outgoing" in texts
    assert "zeta, alpha" in texts
    assert not any("\\n" in text for text in texts)


#: Part ids holding backslashes, as a record may state them: one ending in one, one that
#: is one, the two characters ``\n``, and one ending in two.
BACKSLASH_IDS = ["a\\", "\\", "\\n", "x\\\\"]

BACKSLASH_EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_A": {
                    "id": "EXT_A",
                    "type": "req",
                    "title": "Parts whose ids hold backslashes",
                    "docname": "ext",
                    "content": "",
                    "parts": {
                        part_id: {"id": part_id, "content": f"part {index}"}
                        for index, part_id in enumerate(BACKSLASH_IDS)
                    },
                },
                **{
                    f"EXT_S{index}": {
                        "id": f"EXT_S{index}",
                        "type": "spec",
                        "title": f"Links part {index}",
                        "docname": "ext",
                        "content": "",
                        "links": [f"EXT_A.{part_id}"],
                    }
                    for index, part_id in enumerate(BACKSLASH_IDS)
                },
            }
        }
    },
}

#: The edge each engine writes for each part, by engine: each backslash of the id
#: doubled, which both read as one (PlantUML's label then ends in the ``\n`` it ends in
#: for every label).
BACKSLASH_LINES = {
    "plantuml": [
        r"EXT_S0 -[dotted]-> EXT_A: a\\\n",
        r"EXT_S1 -[dotted]-> EXT_A: \\\n",
        r"EXT_S2 -[dotted]-> EXT_A: \\n\n",
        r"EXT_S3 -[dotted]-> EXT_A: x\\\\\n",
    ],
    "graphviz": [
        r'"EXT_S0" -> "EXT_A" [label="a\\", style="dotted", arrowhead=vee];',
        r'"EXT_S1" -> "EXT_A" [label="\\", style="dotted", arrowhead=vee];',
        r'"EXT_S2" -> "EXT_A" [label="\\n", style="dotted", arrowhead=vee];',
        r'"EXT_S3" -> "EXT_A" [label="x\\\\", style="dotted", arrowhead=vee];',
    ],
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n'
                    "needs_external_needs = [\n"
                    '    {"base_url": "http://example.org", "json_path": "external.json"},\n'
                    "]\n"
                    f'needs_flow_engine = "{engine}"\n'
                    'plantuml_output_format = "svg"\n'
                    'graphviz_output_format = "svg"\n' + VALUES["false"],
                ),
                (Path("index.rst"), "Backslashes\n===========\n\n.. needflow::\n"),
                (Path("external.json"), json.dumps(BACKSLASH_EXTERNAL)),
            ],
            "plantuml": engine == "plantuml",
        }
        for engine in ENGINES
    ],
    indirect=True,
    ids=list(ENGINES),
)
def test_a_part_id_in_a_label_is_drawn_as_written(test_app: SphinxTestApp) -> None:
    """A part id ending in a backslash would escape the label's closing quote, and dot
    would draw no needflow at all; ``\\n`` would draw a line break. Each engine draws
    each id as its record writes it, and the build warns of nothing."""
    engine = test_app.config.needs_flow_engine
    sources: list[str] = []

    def collect(_app: Any, doctree: nodes.document, _docname: str) -> None:
        for node in doctree.findall(NeedflowGraphiz):
            sources.append(node["resolved_content"])
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

    test_app.connect("doctree-resolved", collect, priority=900)
    test_app.build()
    assert_no_warnings(test_app)
    [source] = sources
    assert [
        line
        for line in source.split("\n")
        if line.lstrip('"').startswith("EXT_S") and "->" in line
    ] == BACKSLASH_LINES[engine]
    [svg_path] = Path(test_app.outdir, "_images").glob("*.svg")
    svg = etree.fromstring(svg_path.read_bytes())
    texts = [
        "".join(element.itertext()).strip()
        for element in svg.iter("{http://www.w3.org/2000/svg}text")
    ]
    for part_id in BACKSLASH_IDS:
        assert part_id in texts, part_id


#: A part id ending in a backslash, and one that is a double quote: the two characters an
#: edge's label escapes (the model doubles a backslash, graphviz's writer escapes a quote),
#: each of which loses the whole graphviz needflow when escaped once too few or once too
#: many.
ESCAPED_IDS = ["a\\", '"']

ESCAPED_EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_A": {
                    "id": "EXT_A",
                    "type": "req",
                    "title": "Parts",
                    "docname": "ext",
                    "content": "",
                    "parts": {
                        part_id: {"id": part_id, "content": f"part {index}"}
                        for index, part_id in enumerate(ESCAPED_IDS)
                    },
                },
                **{
                    f"EXT_S{index}": {
                        "id": f"EXT_S{index}",
                        "type": "spec",
                        "title": f"Links part {index}",
                        "docname": "ext",
                        "content": "",
                        "links": [f"EXT_A.{part_id}"],
                    }
                    for index, part_id in enumerate(ESCAPED_IDS)
                },
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\n'
                    "needs_external_needs = [\n"
                    '    {"base_url": "http://example.org", "json_path": "external.json"},\n'
                    "]\n"
                    'needs_flow_engine = "graphviz"\n'
                    'graphviz_output_format = "svg"\n' + VALUES["false"],
                ),
                (
                    Path("index.rst"),
                    f"Escaped\n=======\n\n.. needflow::\n{options}",
                ),
                (Path("external.json"), json.dumps(ESCAPED_EXTERNAL)),
            ],
        }
        for options in ("", "   :show_link_names:\n")
    ],
    indirect=True,
    ids=["plain", "names"],
)
def test_graphviz_draws_a_backslash_and_a_quote_with_and_without_link_names(
    test_app: SphinxTestApp,
) -> None:
    """A part id ending in a backslash, and one that is a double quote, are each drawn as
    written by graphviz, on a one-line label and on the two-line label of
    ``:show_link_names:``, and the needflow renders: the escape holds for both labels,
    and a quote is escaped once (by the writer), not twice."""
    test_app.build()
    assert_no_warnings(test_app)
    [svg_path] = Path(test_app.outdir, "_images").glob("*.svg")
    svg = etree.fromstring(svg_path.read_bytes())
    texts = [
        "".join(element.itertext()).strip()
        for element in svg.iter("{http://www.w3.org/2000/svg}text")
    ]
    for part_id in ESCAPED_IDS:
        assert part_id in texts, part_id
