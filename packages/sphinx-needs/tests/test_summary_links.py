"""Summary link types: ``summary = true`` on a ``needs_links`` entry.

A summary link type materialises a path rather than an edge. It is read where it is
named -- a filter, a needtable column, a rule's ``over``, a needflow's ``:link_types:``,
a schema rule -- and in a need's links and back links, and it is left out of every view
that reads all link types: in sphinx-needs, a needflow without ``:link_types:``, its
drawing and its ``:root_id:`` walk. The shared corpus pins the key's shapes, the schema
marker and the union's refusal (``tests/fixtures/derive_conformance.toml``); this module
pins what the corpus does not compare: the messages, the configuration findings and the
needflow default.
"""

import json
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import DeriveInvalid, parse_derive
from sphinx_needs_testkit import build_warnings

CONF_SHAPES = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "satisfies": {},
    "mitigates": {"summary": True},
    "tagged": {"summary": "yes"},
    "trace": {"derive": {"kind": "union", "fields": ["satisfies", "mitigates"]}},
}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {"satisfies": {"summary": True}},
    },
]
"""

INDEX_SHAPES = """\
Summary links
=============

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1
   :mitigates: REQ_1
"""


def _project(conf: str, index: str, buildername: str = "needs") -> dict:
    return {
        "buildername": buildername,
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _version(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return data["versions"][data["current_version"]]


@pytest.mark.parametrize(
    "test_app", [_project(CONF_SHAPES, INDEX_SHAPES)], indirect=True
)
def test_summary_is_a_boolean_of_the_link_types_entry(test_app):
    """``summary = true`` marks a link type, and it alone; a value that is not a
    boolean, and a need type's ``summary``, are ``needs.config`` findings, ignored; a
    union naming a summary link type is refused."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types entry 2 ('spec').links['satisfies'] has 'summary', "
        "which a need type's entry cannot give: whether a link type is a summary is "
        "the same on every need type, and is given on its needs_links entry; the key "
        "is ignored [needs.config]",
        "WARNING: needs_links['tagged'] has a 'summary' that is not a boolean (got "
        "str); the key is ignored [needs.config]",
        "WARNING: Invalid derive of link type 'trace': kind 'union': the role "
        "'fields' names 'mitigates', a summary link type, which a union cannot read: "
        "a union is read as one set of edges, and a summary link is a shortcut, not "
        "an edge; the link type cannot be set in a need or by a needextend, and holds "
        "no links [needs.derive_invalid]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    summaries = {
        link.name: link.summary
        for link in schema.iter_link_fields()
        if link.name in {"satisfies", "mitigates", "tagged", "trace"}
    }
    assert summaries == {
        "satisfies": False,
        "mitigates": True,
        "tagged": False,
        "trace": False,
    }
    # the type's own declaration keeps the link type's stance
    spec = schema.for_type("spec").get_link_field("satisfies")
    assert spec is not None and spec.summary is False
    version = _version(app)
    properties = version["needs_schema"]["properties"]
    assert properties["mitigates"]["summary"] is True
    assert properties["mitigates_back"]["summary"] is True
    for name in ("satisfies", "satisfies_back", "tagged", "trace", "links"):
        assert "summary" not in properties[name], name
    # a summary link type holds its links and back links as any link type
    assert version["needs"]["SPEC_1"]["mitigates"] == ["REQ_1"]
    assert version["needs"]["REQ_1"]["mitigates_back"] == ["SPEC_1"]
    assert version["needs"]["SPEC_1"]["trace"] == []


def test_summary_is_no_role_of_a_rule():
    """A rule is no place for the stance: it is the link type's, beside its rules."""
    assert parse_derive(
        {"kind": "links", "where": "type == 'req'", "summary": True}, on_link=True
    ) == DeriveInvalid(
        "links",
        "kind 'links': 'summary' is not a role; whether a link type is a summary is "
        "given on its needs_links entry, beside derive",
    )


CONF_FLOW = """\
extensions = ["sphinx_needs"]
needs_flow_engine = "graphviz"
needs_links = {
    "satisfies": {},
    "chain": {"summary": True},
}
"""

INDEX_FLOW = """\
Flows
=====

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1

.. impl:: Implementation
   :id: IMPL_1
   :chain: REQ_1

.. test:: Test
   :id: TEST_1
   :links: IMPL_1

.. needflow::
   :debug:

.. needflow::
   :link_types: satisfies, chain
   :debug:

.. needflow::
   :root_id: REQ_1
   :debug:

.. needflow::
   :root_id: REQ_1
   :link_types: links, chain
   :debug:
"""


def _debug_sources(outdir: Path) -> list[str]:
    from lxml import html as html_parser

    tree = html_parser.parse(outdir / "index.html")
    return [pre.text_content() for pre in tree.xpath("//pre")]


@pytest.mark.parametrize(
    "test_app", [_project(CONF_FLOW, INDEX_FLOW, "html")], indirect=True
)
def test_a_needflow_without_link_types_leaves_summary_link_types_out(test_app):
    """A needflow without ``:link_types:`` draws every link type but the summaries,
    and walks from ``:root_id:`` along the same; one naming a summary link type draws
    it and walks it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    every, named, rooted, rooted_named = _debug_sources(Path(app.outdir))
    # every link type but the summary: links and satisfies
    assert '"SPEC_1" -> "REQ_1"' in every
    assert '"TEST_1" -> "IMPL_1"' in every
    assert '"IMPL_1" -> "REQ_1"' not in every
    # named, it is drawn
    assert '"SPEC_1" -> "REQ_1"' in named
    assert '"IMPL_1" -> "REQ_1"' in named
    assert '"TEST_1" -> "IMPL_1"' not in named
    # the root walk follows the same link types: IMPL_1 and TEST_1 are reached from
    # REQ_1 through chain alone
    assert '"SPEC_1"' in rooted
    assert '"IMPL_1"' not in rooted
    assert '"TEST_1"' not in rooted
    # naming it, the walk follows it: REQ_1 <- IMPL_1 <- TEST_1
    assert '"IMPL_1"' in rooted_named
    assert '"TEST_1"' in rooted_named
    assert '"SPEC_1"' not in rooted_named


CONF_COPY = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"mitigates": {"summary": True, "copy": True}}
"""

INDEX_COPY = """\
Copies
======

.. req:: Requirement
   :id: REQ_1

.. spec:: Risk
   :id: SPEC_1
   :mitigates: REQ_1
"""


@pytest.mark.parametrize("test_app", [_project(CONF_COPY, INDEX_COPY)], indirect=True)
def test_a_summary_link_type_copies_nothing_into_links(test_app):
    """``copy = true`` beside ``summary = true`` would make every summary link an edge
    of ``links``, which every view reads: it is a ``needs.config`` finding, and
    ignored (so it is not deprecated either: nothing is copied)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_links['mitigates'] has 'copy = true' beside 'summary = true': "
        "a copy in links would make a summary link an edge; copy is ignored "
        "[needs.config]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    mitigates = schema.get_link_field("mitigates")
    assert mitigates is not None and mitigates.summary and not mitigates.copy
    needs = _version(app)["needs"]
    assert needs["SPEC_1"]["mitigates"] == ["REQ_1"]
    assert needs["SPEC_1"]["links"] == []
    assert needs["REQ_1"]["links_back"] == []


CONF_FLOW_LINKS = """\
extensions = ["sphinx_needs"]
needs_flow_engine = "graphviz"
needs_links = {"links": {"summary": True}, "parent_needs": {"summary": True}}
"""

INDEX_FLOW_LINKS = """\
Flows
=====

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :links: REQ_1

.. needflow::
   :debug:

.. needflow::
   :link_types: links
   :debug:
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_FLOW_LINKS, INDEX_FLOW_LINKS, "html")], indirect=True
)
def test_a_summary_links_is_not_drawn_by_the_fallback(test_app):
    """With every link type a summary, a needflow without ``:link_types:`` is left
    with none: the ``needs_flow_link_types`` fallback (``links``) leaves summary link
    types out too; named, ``links`` is drawn."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    every, named = _debug_sources(Path(app.outdir))
    assert '"SPEC_1"' in every
    assert '"SPEC_1" -> "REQ_1"' not in every
    assert '"SPEC_1" -> "REQ_1"' in named
