"""``:show_parts:`` on a needflow draws each need it draws with every part it has.

With the option a needflow's result holds needs alone, whatever
``needs_views_include_parts`` says: a part its filter selects is left out before the
``max_items`` cap, so the cap and its notice count needs, and a result holding parts
alone is empty. Every need it draws is drawn with every part it has, inside it, in the
need's stored order (the parts its content writes, in the order written, then the parts
its record states), whether anything links the part or not; a part's node is the one
``True`` draws for a part its filter selects. A link of a drawn need naming a live part of
a drawn need is an edge ending on the part's node, in the link type's ``style_part``,
labelled with no part id; a link naming the need whole is the edge to the need; a link to
a part the need lacks, to a part of a need that does not exist, or to a part of a need
the needflow does not draw is no edge, on both engines. So what it draws does not depend
on the value: its source is the same under ``True``, unset and ``False`` (but where its
filter reads ``needs`` itself, as a filter string, filter code or a ``:filter-func:``
can: that is handed needs and parts under ``True`` and needs alone under ``False``), and
it makes no ``needs.views_include_parts`` report.

A needflow without the option draws what it drew before, under each value; while the
value is unset its report names the option.

One project, built once under each value (:func:`built`): ``plain.rst`` holds each
needflow of :data:`FLOWS` without the option and ``shown.rst`` with it, each needflow in
a container named after it and its engine. Two small projects of their own, each built
once under each value too: a filter reading ``needs`` itself (:data:`READS_NEEDS`), and a
child need with a part (:data:`CHILD_PARTS`).
"""

from __future__ import annotations

import functools
import io
import json
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from docutils import nodes
from lxml import etree
from lxml import html as html_parser
from sphinx.testing.util import SphinxTestApp
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needflow import _model
from sphinx_needs.directives.needflow._directive import (
    NeedflowGraphiz,
    NeedflowPlantuml,
)
from sphinx_needs.filter_common import _views_include_parts_text
from sphinx_needs_testkit import (
    assert_no_warnings,
    build_warnings,
    create_src_files_in_tmpdir,
    make_plantuml_inert,
)

#: The line each arm adds to ``conf.py``.
VALUES = {
    "true": "needs_views_include_parts = True\n",
    "unset": "",
    "false": "needs_views_include_parts = False\n",
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

   plain
   shown

.. req:: Parts written out of id order
   :id: REQ_1
   :status: open

   First :np:`(zeta) the zeta text`, then :np:`(alpha) the alpha text`,
   and :np:`(mid) a part nobody links`.

.. req:: A need that links its own part
   :id: REQ_2
   :links: REQ_2.own

   :np:`(own) its own part`

.. req:: A hidden need with a part
   :id: REQ_3
   :hide:

   :np:`(h1) hidden text`

.. req:: A need with a part and a child need
   :id: REQ_4

   :np:`(p4) the part of the parent`

   .. req:: A child need, linking its parent's part
      :id: REQ_5
      :links: REQ_4.p4

.. req:: A need whose id holds a dot
   :id: REQ_9.x

.. needimport:: imported.json

.. spec:: One part link
   :id: SPEC_1
   :links: REQ_1.zeta

.. spec:: Two part links to one need
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

.. spec:: A link to the hidden need's part
   :id: SPEC_6
   :links: REQ_3.h1

.. spec:: A link to the need whose id holds a dot
   :id: SPEC_7
   :links: REQ_9.x

.. test:: Links to the stated parts of an imported and an external need
   :id: TEST_1
   :tests: IMP_1.rp, EXT_1.rp

.. test:: Two link types to one part
   :id: TEST_2
   :links: REQ_1.zeta
   :tests: REQ_1.zeta
"""

#: The needs of the project, its hidden one among them.
NEEDS = 17

#: Each needflow of the project, by the name its container takes before its engine.
FLOWS = {
    # every need (the recon's V3)
    "all": "",
    "names": ":show_link_names:",
    # needs alone, REQ_1 among them (V9)
    "needs": ':filter: id in ["SPEC_1", "SPEC_2", "SPEC_3", "TEST_2", "REQ_1"]',
    # parts and needs
    "mixed": ':filter: is_part or id in ["REQ_1", "SPEC_1", "SPEC_2"]',
    # parts whose needs the filter does not select (V10)
    "parts": ':filter: type == "spec" or is_part',
    # parts alone
    "partsonly": ":filter: is_part",
    # walked from a need, and from a part (V5), each way
    **{
        f"{at}-{direction}": f":root_id: {root}\n:root_direction: {way}"
        for at, root in (("need", "REQ_1"), ("part", "REQ_1.zeta"))
        for direction, way in (
            ("in", "incoming"),
            ("out", "outgoing"),
            ("both", "both"),
        )
    },
    "depth": ":root_id: SPEC_3\n:root_depth: 1",
    # a cap at the number of needs, and below it
    "capall": f":max_items: {NEEDS}",
    "cap": ":max_items: 4",
    "types": ":link_types: tests",
    "highlight": ':highlight: id_complete == "REQ_1.alpha" or id == "SPEC_1"',
    "border": (
        ':border_color: [id_complete == "REQ_1.zeta"]:00AA00, [is_part]:0000FF, FFAA00'
    ),
    # a need holding a part and a child need
    "children": ':filter: id in ["REQ_4", "REQ_5"]',
}


def _page(title: str, option: str) -> str:
    """A page holding each needflow of :data:`FLOWS` on each engine, with *option*."""
    return f"{title}\n{'=' * len(title)}\n" + "".join(
        f"\n.. container:: {name}-{engine}\n\n   .. needflow::\n"
        f"      :engine: {engine}\n"
        + option
        + "".join(f"      {line}\n" for line in options.splitlines())
        for name, options in FLOWS.items()
        for engine in ENGINES
    )


PLAIN = _page("Plain", "")
SHOWN = _page("Shown", "      :show_parts:\n")


def files(value: str, *, shown: bool = True) -> list[tuple[Path, str]]:
    """The project, with the line of the arm *value* added to ``conf.py``; without
    ``shown``, ``shown.rst`` holds its title alone (the project as the base commit could
    build it, for :func:`before`)."""
    return [
        (Path("conf.py"), CONF + VALUES[value]),
        (Path("index.rst"), INDEX),
        (Path("plain.rst"), PLAIN),
        (Path("shown.rst"), SHOWN if shown else "Shown\n=====\n"),
        (Path("imported.json"), json.dumps(IMPORTED)),
        (Path("external.json"), json.dumps(EXTERNAL)),
    ]


def capture(app: SphinxTestApp) -> dict[str, str | None]:
    """The source of each needflow, by page and container (``plain/all-plantuml``), as
    the page is written; ``None`` for a needflow that wrote no source."""
    sources: dict[str, str | None] = {}

    def collect(_app: Any, doctree: nodes.document, docname: str) -> None:
        for container in doctree.findall(nodes.container):
            name = f"{docname}/{container['classes'][0]}"
            sources.setdefault(name, None)
            for node in container.findall(NeedflowGraphiz):
                sources[name] = node["resolved_content"]
            for node in container.findall(plantuml):
                sources[name] = node["uml"]

    app.connect("doctree-resolved", collect, priority=900)
    return sources


@dataclass
class Build:
    """One build of the project."""

    sources: dict[str, str | None]
    """Each needflow's source, by page and container (:func:`capture`)."""
    warnings: list[str]
    """The build's warnings."""
    texts: dict[str, str]
    """The text of each container of a page, as written, by page and container."""
    show_parts: dict[str, bool]
    """Each needflow node's ``show_parts``, as stored, by page and container."""
    needs: int
    """How many needs the project has."""
    dot: str
    """The ``dot`` the build is configured with (``graphviz_dot``)."""


def build(
    srcdir: Path,
    value: str,
    events: Any = (),
    *,
    pages: tuple[str, ...] = ("plain", "shown"),
) -> Build:
    """Build the project in *srcdir*, written for the arm *value*, reading the
    containers and the needflow nodes of *pages*."""
    app = SphinxTestApp(
        "html",
        srcdir=srcdir,
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    try:
        if getattr(app.config, "plantuml", None) == "plantuml":
            make_plantuml_inert(app)
        for event, handler, priority in events:
            app.connect(event, handler, priority=priority)
        sources = capture(app)
        app.build()
        texts: dict[str, str] = {}
        show_parts: dict[str, bool] = {}
        for docname in pages:
            page = html_parser.fromstring(
                Path(app.outdir, f"{docname}.html").read_text(encoding="utf-8")
            )
            for div in page.xpath('//div[contains(@class, "docutils container")]'):
                texts[f"{docname}/{div.get('class').split()[0]}"] = " ".join(
                    div.text_content().split()
                )
            for node in app.env.get_doctree(docname).findall():
                if isinstance(node, NeedflowPlantuml | NeedflowGraphiz):
                    container = node.parent
                    while not isinstance(container, nodes.container):
                        container = container.parent
                    show_parts[f"{docname}/{container['classes'][0]}"] = (
                        node.attributes.get("show_parts")
                    )
        return Build(
            sources=sources,
            warnings=build_warnings(app),
            texts=texts,
            show_parts=show_parts,
            needs=len(SphinxNeedsData(app.env).get_needs_view()),
            dot=app.config.graphviz_dot,
        )
    finally:
        app.cleanup()


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
    test_app_events: Any,
) -> Iterator[dict[str, Build]]:
    """The project, built once under each value."""
    builds = {}
    for value in VALUES:
        root = tmp_path_factory.mktemp(f"show_parts_{value}")
        srcdir = create_src_files_in_tmpdir(files(value), root)
        builds[value] = build(srcdir, value, test_app_events)
    yield builds


def build_each_value(
    tmp_path_factory: pytest.TempPathFactory,
    events: Any,
    name: str,
    project: dict[str, str],
) -> dict[str, Build]:
    """A small project of its own, its needflows on ``index.rst``, built once under each
    value: *project* is its files but ``conf.py``, which is *project*'s ``conf.py`` and
    the line of the arm."""
    builds = {}
    for value in VALUES:
        written = [
            (Path(path), content + VALUES[value] if path == "conf.py" else content)
            for path, content in project.items()
        ]
        srcdir = create_src_files_in_tmpdir(
            written, tmp_path_factory.mktemp(f"{name}_{value}")
        )
        builds[value] = build(srcdir, value, events, pages=("index",))
    return builds


def needflows(names: list[str], options: dict[str, str]) -> str:
    """A needflow with the option in a container named after each of *names* and its
    engine, on each engine, written with the lines of *options* for its name."""
    return "".join(
        f"\n.. container:: {name}-{engine}\n\n   .. needflow::\n"
        f"      :engine: {engine}\n      :show_parts:\n{options.get(name, '')}"
        for name in names
        for engine in ENGINES
    )


# --- reading a source --------------------------------------------------------------------


@dataclass
class Drawn:
    """What a needflow's source draws, read from either engine's text."""

    nodes: list[str]
    """Every node it defines, in the order written (a need's cluster by its need)."""
    containers: dict[str, list[str]]
    """The parts drawn inside each need, in the order written."""
    children: dict[str, list[str]]
    """The child needs drawn inside each need, in the order written."""
    links: dict[str, str | None]
    """The link of each node."""
    colors: dict[str, str | None]
    """The outline colour of each node: ``red`` for a highlight, else a border colour."""
    edges: list[tuple[str, str, str, str | None]]
    """Each edge, in the order written: its ends, its style (``""`` for none) and its
    label (``None`` for none)."""


_PUML_NODE = re.compile(
    r'^(\w+) "[^"]*" as (\S+?)(?: \[\[([^\]]*)\]\])?(?: #(\S+?))?(\{)?$'
)
_PUML_EDGE = re.compile(r"^(\S+) -(?:\[([^\]]*)\])?-> (\S+?)(?:: (.*)\\n)?$")
_DOT_CLUSTER = re.compile(r'^\s*subgraph "cluster_([^"]+)" \{$')
_DOT_CLUSTER_PARAM = re.compile(r"^\s*(href|color)=(.*);$")
_DOT_NODE = re.compile(r'^\s*"([^"]+)" \[(label=.*)\];$')
_DOT_EDGE = re.compile(r'^"([^"]+)" -> "([^"]+)" \[(.*)\];$')
_DOT_LABEL = re.compile(r'label="((?:[^"\\]|\\.)*)"')
_DOT_STYLE = re.compile(r'style="([^"]*)"')
_DOT_HREF = re.compile(r'href="([^"]*)"')
_DOT_COLOR = re.compile(r'(?:^|, )color=("#[0-9A-Fa-f]+"|red)')


def drawn(source: str) -> Drawn:
    """What a needflow's *source* draws, on either engine."""
    result = Drawn([], {}, {}, {}, {}, [])
    if source.startswith("@startuml"):
        definitions, connections = source.split("' Nodes definition \n", 1)[1].split(
            "' Connection definition \n", 1
        )
        # each open block: its need, and whether its parts or its children are listed
        stack: list[list[str]] = []
        for line in definitions.splitlines():
            if line == "}":
                stack.pop()
            elif line in ("'parts:", "'child needs:"):
                stack[-1][1] = line
            elif (match := _PUML_NODE.match(line)) is not None:
                _style, entity, link, color, opens = match.groups()
                result.nodes.append(entity)
                result.links[entity] = link
                result.colors[entity] = (
                    color.split("line:")[1] if color and "line:" in color else None
                )
                if stack:
                    into = (
                        result.containers
                        if stack[-1][1] == "'parts:"
                        else result.children
                    )
                    into.setdefault(stack[-1][0], []).append(entity)
                if opens:
                    stack.append([entity, ""])
        for line in connections.splitlines():
            if (match := _PUML_EDGE.match(line)) is not None:
                tail, style, head, label = match.groups()
                result.edges.append((tail, head, style or "", label))
        return result
    stack = []
    for line in source.split("\n// edge definitions\n", 1)[0].splitlines():
        if (match := _DOT_CLUSTER.match(line)) is not None:
            result.nodes.append(match[1])
            result.links[match[1]] = result.colors[match[1]] = None
            if stack:
                # a need drawn as a cluster of its own, nested in its parent's
                result.children.setdefault(stack[-1][0], []).append(match[1])
            stack.append([match[1], ""])
        elif stack and (match := _DOT_CLUSTER_PARAM.match(line)) is not None:
            # the need's own attributes, at the head of its cluster
            key, value = match.groups()
            if key == "href":
                result.links[stack[-1][0]] = value.strip('"')
            else:
                result.colors[stack[-1][0]] = value.strip('"#')
        elif line.strip() == "};":
            stack.pop()
        elif line.strip() in ("// parts:", "// child needs:"):
            stack[-1][1] = line.strip()
        elif (match := _DOT_NODE.match(line)) is not None:
            node_id, attributes = match.groups()
            href = _DOT_HREF.search(attributes)
            color = _DOT_COLOR.search(attributes)
            result.nodes.append(node_id)
            result.links[node_id] = href[1] if href else None
            result.colors[node_id] = color[1].strip('"#') if color else None
            if stack:
                into = (
                    result.containers
                    if stack[-1][1] == "// parts:"
                    else result.children
                )
                into.setdefault(stack[-1][0], []).append(node_id)
    for line in source.splitlines():
        if (match := _DOT_EDGE.match(line)) is not None:
            tail, head, attributes = match.groups()
            style = _DOT_STYLE.search(attributes)
            label = _DOT_LABEL.search(attributes)
            result.edges.append(
                (tail, head, style[1] if style else "", label[1] if label else None)
            )
    return result


def shown(built: dict[str, Build], value: str, name: str, engine: str) -> Drawn:
    """What the needflow *name* with the option draws under *value*, on *engine*."""
    source = built[value].sources[f"shown/{name}-{engine}"]
    assert source is not None, name
    return drawn(source)


ARMS = pytest.mark.parametrize("value", list(VALUES))
ON_ENGINES = pytest.mark.parametrize("engine", ENGINES)

#: The parts drawn inside each need where the needflow draws every need: each part of
#: the need in its stored order, whether anything links it or not (``REQ_1.mid``), its
#: content's (in the order written, not by id) before its record's (``IMP_1``); an
#: external need's stated part; none for the hidden need, which has none.
CONTAINERS = {
    "REQ_1": ["REQ_1.zeta", "REQ_1.alpha", "REQ_1.mid"],
    "REQ_2": ["REQ_2.own"],
    "REQ_4": ["REQ_4.p4"],
    "IMP_1": ["IMP_1.sc", "IMP_1.rp"],
    "EXT_1": ["EXT_1.rp"],
}

#: The edges where the needflow draws every need, sorted: a live part link ends on the
#: part's node, dotted (``style_part``) and labelled with no part id; a whole link on the
#: need; one edge per link and per link type (``TEST_2``); a need's link to its own part
#: (``REQ_2``), and a child's to its parent's part (``REQ_5``); the link to the need whose
#: id holds a dot as before. No edge for a part the need lacks (``SPEC_4``), a part of a
#: need that does not exist (``SPEC_5``) or of the hidden need, which has none
#: (``SPEC_6``).
ALL_EDGES = [
    ("REQ_2", "REQ_2.own", "dotted", None),
    ("REQ_5", "REQ_4.p4", "dotted", None),
    ("SPEC_1", "REQ_1.zeta", "dotted", None),
    ("SPEC_2", "REQ_1.alpha", "dotted", None),
    ("SPEC_2", "REQ_1.zeta", "dotted", None),
    ("SPEC_3", "REQ_1", "", None),
    ("SPEC_3", "REQ_1.alpha", "dotted", None),
    ("SPEC_7", "REQ_9.x", "dotted", None),
    ("TEST_1", "EXT_1.rp", "dotted", None),
    ("TEST_1", "IMP_1.rp", "dotted", None),
    ("TEST_2", "REQ_1.zeta", "dotted", None),
    ("TEST_2", "REQ_1.zeta", "dotted", None),
]

#: The ids of the parts of :data:`CONTAINERS`.
PARTS = [part for parts in CONTAINERS.values() for part in parts]

#: The needs of the project.
ALL_NEEDS = [
    "EXT_1",
    "IMP_1",
    "REQ_1",
    "REQ_2",
    "REQ_3",
    "REQ_4",
    "REQ_5",
    "REQ_9.x",
    *(f"SPEC_{i}" for i in range(1, 8)),
    "TEST_1",
    "TEST_2",
]


def test_the_project_has_the_needs_it_counts(built: dict[str, Build]) -> None:
    """The cap ``capall`` is written at the number of needs."""
    assert len(ALL_NEEDS) == NEEDS
    assert {value: build.needs for value, build in built.items()} == dict.fromkeys(
        VALUES, NEEDS
    )


@ARMS
def test_the_option_is_stored_as_given(built: dict[str, Build], value: str) -> None:
    """The flag is stored on the node, ``True`` where it is written and ``False``
    where it is not."""
    stored = built[value].show_parts
    assert stored == {
        f"{page}/{name}-{engine}": page == "shown"
        for page in ("plain", "shown")
        for name in FLOWS
        for engine in ENGINES
    }


@ARMS
@ON_ENGINES
def test_every_need_is_drawn_with_every_part_inside_it_in_stored_order(
    built: dict[str, Build], value: str, engine: str
) -> None:
    graph = shown(built, value, "all", engine)
    assert graph.containers == CONTAINERS
    assert sorted(graph.nodes) == sorted([*ALL_NEEDS, *PARTS])
    assert sorted(graph.edges) == ALL_EDGES


@ARMS
@ON_ENGINES
def test_a_part_node_links_the_parts_anchor(
    built: dict[str, Build], value: str, engine: str
) -> None:
    """A content part and a stated part of an imported need link their anchors on the
    page; an external need's stated part the part's anchor at its URL, not the need's."""
    graph = shown(built, value, "all", engine)
    page = "../index.html" if engine == "plantuml" else "index.html"
    assert {part: graph.links[part] for part in ("IMP_1.sc", "IMP_1.rp")} == {
        "IMP_1.sc": f"{page}#IMP_1.sc",
        "IMP_1.rp": f"{page}#IMP_1.rp",
    }
    assert graph.links["EXT_1.rp"] == "http://example.org/ext.html#EXT_1.rp"


@ARMS
@ON_ENGINES
def test_the_parts_drawn_come_from_the_need_not_the_filter(
    built: dict[str, Build], value: str, engine: str
) -> None:
    """A filter selecting needs alone (V9): the need is drawn with all its parts, and
    each of the seven part and whole links of the needs drawn is an edge."""
    graph = shown(built, value, "needs", engine)
    assert graph.containers == {"REQ_1": CONTAINERS["REQ_1"]}
    assert sorted(graph.nodes) == sorted(
        ["REQ_1", *CONTAINERS["REQ_1"], "SPEC_1", "SPEC_2", "SPEC_3", "TEST_2"]
    )
    assert sorted(graph.edges) == [
        ("SPEC_1", "REQ_1.zeta", "dotted", None),
        ("SPEC_2", "REQ_1.alpha", "dotted", None),
        ("SPEC_2", "REQ_1.zeta", "dotted", None),
        ("SPEC_3", "REQ_1", "", None),
        ("SPEC_3", "REQ_1.alpha", "dotted", None),
        ("TEST_2", "REQ_1.zeta", "dotted", None),
        ("TEST_2", "REQ_1.zeta", "dotted", None),
    ]


@ARMS
@ON_ENGINES
def test_a_part_the_filter_selects_of_a_need_it_does_not_is_not_drawn(
    built: dict[str, Build], value: str, engine: str
) -> None:
    """V10: the parts the filter selects are left out, and no need it draws has one,
    so there is no part node, and no edge to any (PlantUML writes no connection to an
    entity it did not define)."""
    graph = shown(built, value, "parts", engine)
    assert graph.nodes == [f"SPEC_{i}" for i in range(1, 8)]
    assert graph.containers == {}
    assert graph.edges == []


@ARMS
@ON_ENGINES
def test_a_result_of_parts_alone_is_empty(
    built: dict[str, Build], value: str, engine: str
) -> None:
    """The result holds needs alone: the parts a filter selects make no diagram."""
    assert built[value].sources[f"shown/partsonly-{engine}"] is None
    assert built[value].texts[f"shown/partsonly-{engine}"] == (
        "No needs passed the filters"
    )


@ARMS
@ON_ENGINES
def test_parts_and_needs_selected_draw_the_needs_with_their_parts(
    built: dict[str, Build], value: str, engine: str
) -> None:
    graph = shown(built, value, "mixed", engine)
    assert graph.containers == {"REQ_1": CONTAINERS["REQ_1"]}
    assert sorted(graph.edges) == [
        ("SPEC_1", "REQ_1.zeta", "dotted", None),
        ("SPEC_2", "REQ_1.alpha", "dotted", None),
        ("SPEC_2", "REQ_1.zeta", "dotted", None),
    ]


#: What each walk from a ``:root_id:`` draws besides ``REQ_1`` and its parts, and its
#: edges: from the need, against its links its back links (``SPEC_4``'s dead part link
#: counts among them, as it does for the need, and draws no edge); from the part,
#: against its links the part's own back links; out of the need nothing, as it links
#: nothing.
WALKS = {
    "need-in": (
        ["SPEC_1", "SPEC_2", "SPEC_3", "SPEC_4", "TEST_2"],
        [
            ("SPEC_1", "REQ_1.zeta", "dotted", None),
            ("SPEC_2", "REQ_1.alpha", "dotted", None),
            ("SPEC_2", "REQ_1.zeta", "dotted", None),
            ("SPEC_3", "REQ_1", "", None),
            ("SPEC_3", "REQ_1.alpha", "dotted", None),
            ("TEST_2", "REQ_1.zeta", "dotted", None),
            ("TEST_2", "REQ_1.zeta", "dotted", None),
        ],
    ),
    "need-out": ([], []),
    "part-in": (
        ["SPEC_1", "SPEC_2", "TEST_2"],
        [
            ("SPEC_1", "REQ_1.zeta", "dotted", None),
            ("SPEC_2", "REQ_1.alpha", "dotted", None),
            ("SPEC_2", "REQ_1.zeta", "dotted", None),
            ("TEST_2", "REQ_1.zeta", "dotted", None),
            ("TEST_2", "REQ_1.zeta", "dotted", None),
        ],
    ),
    "part-out": ([], []),
    "depth": (
        ["SPEC_3"],
        [
            ("SPEC_3", "REQ_1", "", None),
            ("SPEC_3", "REQ_1.alpha", "dotted", None),
        ],
    ),
}
WALKS["need-both"] = WALKS["need-in"]
WALKS["part-both"] = WALKS["part-in"]


@ARMS
@ON_ENGINES
@pytest.mark.parametrize("name", sorted(WALKS))
def test_a_walk_from_a_root_draws_the_needs_it_reaches_with_their_parts(
    built: dict[str, Build], value: str, engine: str, name: str
) -> None:
    others, edges = WALKS[name]
    graph = shown(built, value, name, engine)
    assert graph.containers == {"REQ_1": CONTAINERS["REQ_1"]}
    assert sorted(graph.nodes) == sorted(["REQ_1", *CONTAINERS["REQ_1"], *others])
    assert sorted(graph.edges) == edges


@ARMS
@ON_ENGINES
def test_the_cap_counts_needs(built: dict[str, Build], value: str, engine: str) -> None:
    """At the number of needs the cap cuts nothing, and there is no notice; below it the
    window is the first needs, each with its parts, and the notice counts needs."""
    whole = built[value].texts[f"shown/capall-{engine}"]
    assert "due to the max_items limit" not in whole
    assert shown(built, value, "capall", engine).containers == CONTAINERS
    capped = built[value].texts[f"shown/cap-{engine}"]
    assert f"Showing the first 4 of {NEEDS} needs" in capped
    graph = shown(built, value, "cap", engine)
    needs = [node for node in graph.nodes if node in ALL_NEEDS]
    assert len(needs) == 4
    assert [node for node in graph.nodes if node not in ALL_NEEDS] == [
        part for need in needs for part in CONTAINERS.get(need, [])
    ]


@ARMS
@ON_ENGINES
def test_link_types_select_the_edges(
    built: dict[str, Build], value: str, engine: str
) -> None:
    graph = shown(built, value, "types", engine)
    assert graph.containers == CONTAINERS
    assert sorted(graph.edges) == [
        ("TEST_1", "EXT_1.rp", "dotted", None),
        ("TEST_1", "IMP_1.rp", "dotted", None),
        ("TEST_2", "REQ_1.zeta", "dotted", None),
    ]


@ARMS
@ON_ENGINES
def test_a_part_edge_is_labelled_with_the_link_types_name_alone(
    built: dict[str, Build], value: str, engine: str
) -> None:
    graph = shown(built, value, "names", engine)
    assert sorted(graph.edges) == sorted(
        [
            *(
                (tail, head, style, "tests" if tail == "TEST_1" else "links outgoing")
                for tail, head, style, _ in ALL_EDGES
                if tail != "TEST_2"
            ),
            ("TEST_2", "REQ_1.zeta", "dotted", "links outgoing"),
            ("TEST_2", "REQ_1.zeta", "dotted", "tests"),
        ]
    )


@ARMS
@ON_ENGINES
def test_a_part_node_is_highlighted_and_bordered_as_the_part(
    built: dict[str, Build], value: str, engine: str
) -> None:
    """``:highlight:`` and ``:border_color:`` are tested on the part itself, as for a
    part the filter selects without the option: ``REQ_1.alpha`` is highlighted and its
    need is not; ``REQ_1.zeta`` takes the colour of its own address, the other parts that
    of a part, and the needs the default."""
    highlight = shown(built, value, "highlight", engine).colors
    assert {node for node, color in highlight.items() if color} == {
        "REQ_1.alpha",
        "SPEC_1",
    }
    assert highlight["REQ_1.alpha"] == ("FF0000" if engine == "plantuml" else "red")
    border = shown(built, value, "border", engine).colors
    assert border["REQ_1.zeta"] == "00AA00"
    assert {border[part] for part in PARTS if part != "REQ_1.zeta"} == {"0000FF"}
    assert {border[need] for need in ALL_NEEDS} - {None} == {"FFAA00"}


@ARMS
@ON_ENGINES
def test_a_need_holds_its_parts_then_its_child_needs(
    built: dict[str, Build], value: str, engine: str
) -> None:
    graph = shown(built, value, "children", engine)
    assert graph.containers == {"REQ_4": ["REQ_4.p4"]}
    assert graph.children == {"REQ_4": ["REQ_5"]}
    assert graph.edges == [("REQ_5", "REQ_4.p4", "dotted", None)]


#: A project of its own: a need nested in its parent, with a part a link names.
CHILD_PARTS = {
    "conf.py": 'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n',
    "index.rst": """\
Child
=====

.. req:: A parent need
   :id: REQ_P

   .. req:: A child need with a part
      :id: REQ_C

      :np:`(c1) the child's part`

.. spec:: Links the child's part
   :id: SPEC_C
   :links: REQ_C.c1
"""
    + needflows(["child"], {}),
}


@pytest.fixture(scope="module")
def child_parts(
    tmp_path_factory: pytest.TempPathFactory, test_app_events: Any
) -> dict[str, Build]:
    """:data:`CHILD_PARTS`, built once under each value."""
    return build_each_value(
        tmp_path_factory, test_app_events, "child_parts", CHILD_PARTS
    )


@ARMS
@ON_ENGINES
def test_a_child_need_is_drawn_with_its_parts_inside_it(
    child_parts: dict[str, Build], value: str, engine: str
) -> None:
    """A need nested in its parent is a need it draws: its part is drawn inside it, and
    the link to the part ends on the part's node."""
    source = child_parts[value].sources[f"index/child-{engine}"]
    assert source is not None
    graph = drawn(source)
    assert graph.children == {"REQ_P": ["REQ_C"]}
    assert graph.containers == {"REQ_C": ["REQ_C.c1"]}
    assert graph.edges == [("SPEC_C", "REQ_C.c1", "dotted", None)]


@ARMS
def test_graphviz_draws_a_needs_edge_to_its_own_part_without_ltail(
    built: dict[str, Build], value: str
) -> None:
    """The edge from ``REQ_2`` to its own part, inside its cluster: no ``ltail``, and
    the ``dot`` the build is configured with does not warn that its head is inside the
    tail's cluster."""
    source = built[value].sources["shown/all-graphviz"]
    assert source is not None
    assert '"REQ_2" -> "REQ_2.own" [style="dotted", arrowhead=vee];' in source.split(
        "\n"
    )
    dot = subprocess.run(
        [built[value].dot, "-Tsvg"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "head is inside tail cluster" not in dot.stderr


@ON_ENGINES
@pytest.mark.parametrize("name", list(FLOWS))
def test_what_it_draws_does_not_depend_on_the_value(
    built: dict[str, Build], engine: str, name: str
) -> None:
    """With the option a needflow's source is the same under ``True``, unset and
    ``False``, whatever it selects, but for a filter that reads ``needs`` itself (a
    filter string, filter code or a ``:filter-func:``), which is handed needs and parts
    under ``True`` and needs alone under ``False``: none is here, and
    :func:`test_a_filter_reading_needs_itself_selects_by_the_value` pins them. So is
    what the page shows beside it."""
    key = f"shown/{name}-{engine}"
    sources = {value: build.sources[key] for value, build in built.items()}
    # a diagram is drawn, but where the result holds parts alone
    assert (sources["true"] is None) == (name == "partsonly")
    assert sources["unset"] == sources["true"]
    assert sources["false"] == sources["true"]
    texts = {value: build.texts[key] for value, build in built.items()}
    assert texts["unset"] == texts["true"]
    assert texts["false"] == texts["true"]


#: A project of its own: two needs with parts and one without, and a needflow with the
#: option whose filter reads ``needs`` itself, in each of the three forms, each
#: selecting the needs that have a part among the needs it is handed.
READS_NEEDS = {
    "conf.py": (
        "import os\nimport sys\n\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n'
    ),
    "show_parts_funcs.py": """\
def with_parts(needs, results, **kwargs):
    owners = {need["id_parent"] for need in needs if need["is_part"]}
    results.extend(need for need in needs if need["is_need"] and need["id"] in owners)
""",
    "index.rst": """\
Reads needs
===========

.. req:: A need with two parts
   :id: REQ_1

   :np:`(zeta) the zeta text` and :np:`(alpha) the alpha text`.

.. req:: A need with no part
   :id: REQ_2

.. req:: A need with one part
   :id: REQ_3

   :np:`(p3) the third need's part`
"""
    + needflows(
        ["string", "code", "func"],
        {
            "string": (
                '      :filter: id in [n["id_parent"] for n in needs if n["is_part"]]\n'
            ),
            "code": (
                '\n      results = [n for n in needs if n["is_need"] and any('
                'm["is_part"] and m["id_parent"] == n["id"] for m in needs)]\n'
            ),
            "func": "      :filter-func: show_parts_funcs.with_parts\n",
        },
    ),
}


@pytest.fixture(scope="module")
def reads_needs(
    tmp_path_factory: pytest.TempPathFactory, test_app_events: Any
) -> dict[str, Build]:
    """:data:`READS_NEEDS`, built once under each value."""
    return build_each_value(
        tmp_path_factory, test_app_events, "reads_needs", READS_NEEDS
    )


@ON_ENGINES
@pytest.mark.parametrize("form", ["string", "code", "func"])
def test_a_filter_reading_needs_itself_selects_by_the_value(
    reads_needs: dict[str, Build], engine: str, form: str
) -> None:
    """The exception to the equation, the selection's own rule: a filter that reads
    ``needs`` itself is handed needs and parts under ``True`` and unset, and needs
    alone under ``False``, so what the needflow selects, and so draws, can differ by
    value. Each filter here does: under ``True`` and unset it selects the needs that
    have parts, each drawn with its parts; under ``False`` no need."""
    key = f"index/{form}-{engine}"
    sources = {value: build.sources[key] for value, build in reads_needs.items()}
    assert sources["true"] is not None
    assert sources["unset"] == sources["true"]
    assert sources["false"] != sources["true"]
    graph = drawn(sources["true"])
    assert graph.containers == {
        "REQ_1": ["REQ_1.zeta", "REQ_1.alpha"],
        "REQ_3": ["REQ_3.p3"],
    }
    assert sorted(graph.nodes) == [
        "REQ_1",
        "REQ_1.alpha",
        "REQ_1.zeta",
        "REQ_3",
        "REQ_3.p3",
    ]
    assert sources["false"] is None
    assert reads_needs["false"].texts[key] == "No needs passed the filters"


#: The needflows whose filter selects, under ``True`` and without the option, every
#: part of every need it selects, and which no cap cuts: the recon's V3, V5 and V6.
EVERY_PART = ("all", "part-in", "part-both", "names")


@ON_ENGINES
@pytest.mark.parametrize("name", EVERY_PART)
def test_where_the_filter_selects_every_part_the_option_draws_the_same(
    built: dict[str, Build], engine: str, name: str
) -> None:
    """Under ``True``, a needflow whose filter selects every part of every need it
    selects draws, with the option, what it draws without it, byte for byte."""
    sources = built["true"].sources
    assert sources[f"shown/{name}-{engine}"] == sources[f"plain/{name}-{engine}"]


#: The sources of the needflows of ``plain.rst`` and the warnings of the project as the
#: base commit wrote them, under each value (``shown.rst`` holding no needflow):
#: :func:`before`.
BEFORE_PATH = Path(__file__).parent / "fixtures" / "needflow_show_parts_before.json"


@functools.cache
def before() -> dict[str, Any]:
    return json.loads(BEFORE_PATH.read_text(encoding="utf-8"))


#: The clause the report of a needflow without the option gains, in both its forms.
CLAUSE = (
    "; or add :show_parts: to draw each need the needflow draws with its parts inside "
    "it, whatever the value"
)


SUPPRESS = "; or suppress needs.views_include_parts."


def _with_clause(warning: str) -> str:
    """A warning as the base wrote it, with the clause a needflow's report gains."""
    if "needflow" not in warning or "[needs.views_include_parts]" not in warning:
        return warning
    return warning.replace(SUPPRESS, CLAUSE + SUPPRESS)


def _line(page: str, container: str) -> int:
    """The line of ``page``'s needflow in *container*."""
    lines = page.splitlines()
    return lines.index(f".. container:: {container}") + 3


#: The warnings the needflows with the option make, under each value: the notice of the
#: one whose cap cuts the needs, counting needs; no ``needs.views_include_parts`` report,
#: and no part's entity name left unmapped.
SHOWN_WARNINGS = [
    f"<srcdir>/shown.rst:{_line(SHOWN, f'cap-{engine}')}: WARNING: needflow: showing "
    f"the first 4 of {NEEDS} needs, due to the max_items limit. [needs.max_items]"
    for engine in ENGINES
]


@ARMS
def test_without_the_option_nothing_moves(built: dict[str, Build], value: str) -> None:
    """Each needflow without the option writes the source the base wrote, under each
    value; the project's warnings are the base's, a needflow's report but for its
    clause, and those of the needflows with the option, which report nothing but a
    cap's notice."""
    plain = before()["sources"][value]
    assert {key: built[value].sources[key] for key in plain} == plain
    assert sorted(built[value].warnings) == sorted(
        [
            *(_with_clause(warning) for warning in before()["warnings"][value]),
            *SHOWN_WARNINGS,
        ]
    )


def test_the_fixture_holds_every_plain_needflow_under_every_value() -> None:
    assert set(before()["sources"]) == set(VALUES)
    for sources in before()["sources"].values():
        assert set(sources) == {
            f"plain/{name}-{engine}" for name in FLOWS for engine in ENGINES
        }


@pytest.mark.parametrize(
    ("parts", "links", "before"),
    [
        (
            7,
            16,
            "This needflow's filter selects 7 need parts, and from Sphinx-Needs 10.0 it "
            "draws 16 links to need parts as edges to the parts' needs: a view's filter "
            "then selects needs only, and a needflow draws a link to a part of a need it "
            "shows as an edge to that need. Set needs_views_include_parts = True to keep "
            "the needflow as it is, or False to draw needs only now",
        ),
        (
            0,
            1,
            "From Sphinx-Needs 10.0 this needflow draws 1 link to a need part as an edge "
            "to the part's need, which it draws no edge for now: a view's filter then "
            "selects needs only, and a needflow draws a link to a part of a need it "
            "shows as an edge to that need. Set needs_views_include_parts = True to keep "
            "the needflow as it is, or False to draw those edges now",
        ),
        (
            2,
            0,
            "This needflow's filter selects 2 need parts: from Sphinx-Needs 10.0 a "
            "view's filter selects needs only. Set needs_views_include_parts = True to "
            "keep drawing them, or False to draw needs only now",
        ),
    ],
    ids=["links-and-parts", "links", "parts"],
)
def test_a_needflows_report_names_the_option(
    parts: int, links: int, before: str
) -> None:
    """Both forms of a needflow's report, the one counting links and the one counting
    the parts its filter selects, name the lasting way to keep parts in the diagram;
    the counts do not change."""
    assert _views_include_parts_text("needflow", parts, links, counts=False) == (
        f"{before}{CLAUSE}; or suppress needs.views_include_parts."
    )


def test_no_other_views_report_moves() -> None:
    """needgantt shares the needflow's "drawing" words, and not the clause."""
    assert _views_include_parts_text("needgantt", 2, 0, counts=False) == (
        "This needgantt's filter selects 2 need parts: from Sphinx-Needs 10.0 a "
        "view's filter selects needs only. Set needs_views_include_parts = True to "
        "keep drawing them, or False to draw needs only now; or suppress "
        "needs.views_include_parts."
    )
    assert _views_include_parts_text("needlist", 1, 0, counts=False) == (
        "This needlist's filter selects 1 need part: from Sphinx-Needs 10.0 a "
        "view's filter selects needs only. Set needs_views_include_parts = True to "
        "keep listing them, or False to list needs only now; or suppress "
        "needs.views_include_parts."
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "html", "files": files("true")},
    ],
    indirect=True,
    ids=["true"],
)
def test_the_model_holds_needs_alone(test_app: SphinxTestApp) -> None:
    """With the option the graph's needs are needs alone, its total counts needs, and
    the parts drawn are each drawn need's (the filter of ``mixed`` selects every part
    of the project, under ``True``)."""
    test_app.build()
    [node] = [
        node
        for node in test_app.env.get_doctree("shown").findall()
        if isinstance(node, NeedflowPlantuml)
        and node.parent["classes"] == ["mixed-plantuml"]
    ]
    link_types = _model.resolve_link_types(
        node.attributes,
        schema=SphinxNeedsData(test_app.env).get_schema(),
        config=NeedsSphinxConfig(test_app.config),
        location=node,
    )
    graph = _model.build_graph(
        test_app, node.attributes, link_types, location=node, variant_location=node
    )
    assert [need["id"] for need in graph.needs] == ["REQ_1", "SPEC_1", "SPEC_2"]
    assert all(need["is_need"] for need in graph.needs)
    assert graph.total_needs == 3
    assert [part.need["id_complete"] for part in graph.nodes["REQ_1"].parts] == (
        CONTAINERS["REQ_1"]
    )


RENDER_INDEX = """\
Render
======

.. req:: Parts written out of id order
   :id: REQ_1

   First :np:`(zeta) the zeta text`, then :np:`(alpha) the alpha text`,
   and :np:`(mid) a part nobody links`.

.. req:: A need that links its own part
   :id: REQ_2
   :links: REQ_2.own

   :np:`(own) its own part`

.. spec:: Two part links and a whole link
   :id: SPEC_2
   :links: REQ_1, REQ_1.zeta, REQ_1.alpha

.. needflow::
   :show_parts:
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
def test_a_needflow_with_the_option_renders(test_app: SphinxTestApp) -> None:
    """Each engine renders the parts inside their need and the edges ending on them,
    with no warning: every part's text is drawn, ``REQ_1.mid`` too."""
    test_app.build()
    assert_no_warnings(test_app)
    [svg_path] = Path(test_app.outdir, "_images").glob("*.svg")
    svg = etree.fromstring(svg_path.read_bytes())
    texts = " ".join(
        " ".join("".join(element.itertext()).split())
        for element in svg.iter("{http://www.w3.org/2000/svg}text")
    )
    for text in (
        "the zeta text",
        "the alpha text",
        "a part nobody links",
        "its own part",
    ):
        assert text in texts, text
