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


@pytest.mark.xfail(
    strict=True,
    reason="pinned ahead of the change: a link type need types alone declare can be a summary",
)
@pytest.mark.parametrize(
    "test_app", [_project(CONF_SHAPES, INDEX_SHAPES)], indirect=True
)
def test_summary_is_a_boolean_of_the_link_types_entry(test_app):
    """``summary = true`` marks a link type, and it alone; a value that is not a
    boolean, and a need type's ``summary`` on a link type ``needs_links`` declares,
    are ``needs.config`` findings, ignored; a union naming a summary link type is
    refused."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_links['tagged'] has a 'summary' that is not a boolean (got "
        "str); the key is ignored [needs.config]",
        "WARNING: Invalid derive of link type 'trace': kind 'union': the role "
        "'fields' names 'mitigates', a summary link type, which a union cannot read: "
        "a union is read as one set of edges, and a summary link is a shortcut, not "
        "an edge; the link type cannot be set in a need or by a needextend, and holds "
        "no links [needs.derive_invalid]",
        "WARNING: needs_types['spec'].links['satisfies'] sets 'summary', which a need "
        "type gives only a link type declared on need types alone; 'satisfies' keeps "
        "its own on every need type and the key is ignored [needs.config]",
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

#: the same, chain a summary declared on need types alone (``impl``'s bare entry
#: narrows the default type)
CONF_FLOW_TYPES = """\
extensions = ["sphinx_needs"]
needs_flow_engine = "graphviz"
needs_links = {"satisfies": {}}
needs_types = [{"directive": "impl", "links": {"chain": {"summary": True}}}]
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
    "test_app",
    [
        pytest.param(_project(CONF_FLOW, INDEX_FLOW, "html"), id="needs_links"),
        pytest.param(
            _project(CONF_FLOW_TYPES, INDEX_FLOW, "html"),
            id="need_types",
            marks=pytest.mark.xfail(
                strict=True,
                reason="pinned ahead of the change: a link type need types alone declare can be a summary",
            ),
        ),
    ],
    indirect=True,
)
def test_a_needflow_without_link_types_leaves_summary_link_types_out(test_app):
    """A needflow without ``:link_types:`` draws every link type but the summaries,
    and walks from ``:root_id:`` along the same; one naming a summary link type draws
    it and walks it -- a summary declared on need types alone as one ``needs_links``
    declares."""
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


CONF_PER_TYPE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"satisfies": {}, "implements": {}, "mitigates": {"summary": True}}
_COUNTS = {
    "chain": {"schema": {"minItems": 1}, "severity": "warning"},
    "mitigates": {"schema": {"minItems": 1}, "severity": "warning"},
}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_", "back_links": _COUNTS},
    {"directive": "sysreq", "title": "System", "prefix": "SR_", "inherits": "req"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "chain": {
                "summary": True,
                "derive": {
                    "kind": "copy",
                    "field": "id",
                    "over": "satisfies",
                    "where": "c.is_a('req')",
                },
            }
        },
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "I_",
        "links": {
            "chain": {
                "derive": {"kind": "collect", "field": "chain", "over": "implements"}
            }
        },
    },
]
"""

INDEX_PER_TYPE = """\
Chain
=====

.. req:: Reached and mitigated
   :id: REQ_1

.. sysreq:: Reached through inherits
   :id: SYS_1

.. req:: Neither reached nor mitigated
   :id: REQ_2

.. spec:: Satisfies
   :id: SPEC_1
   :satisfies: REQ_1, SYS_1, SPEC_2
   :mitigates: REQ_1, SYS_1

.. spec:: A specification satisfied
   :id: SPEC_2

.. impl:: Implements
   :id: IMPL_1
   :implements: SPEC_1
"""


def _count_failed(field: str) -> str:
    return (
        "WARNING: Need 'REQ_2' has schema warnings:\n"
        "  Severity:       warning\n"
        f"  Field:          {field}\n"
        "  Need path:      REQ_2\n"
        f"  Schema path:    links > schema > properties > {field} > minItems\n"
        "  Schema message: [] has less than 1 item [sn_schema_warning.link_fail]"
    )


@pytest.mark.xfail(
    strict=True,
    reason="pinned ahead of the change: a link type need types alone declare can be a summary",
)
@pytest.mark.parametrize(
    "test_app", [_project(CONF_PER_TYPE, INDEX_PER_TYPE)], indirect=True
)
def test_a_summary_link_type_on_need_types(test_app):
    """A summary link type is read where it is named, and a need type's declarations
    name it as any link type: a ``back_links`` count of it counts its links, those a
    ``copy`` or ``collect`` computes included (REQ_1 and SYS_1 are reached, REQ_2 is not
    and fails both counts). A ``copy`` and a ``collect`` may be declared on need types
    alone, the link type a summary all the same, and a ``where`` reads ``c.is_a``
    (``sysreq`` inherits ``req``; a satisfied specification is not copied). The first
    root's ``summary = true`` says what the rule implies: no finding."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _count_failed("mitigates_back"),
        _count_failed("chain_back"),
    ]
    version = _version(app)
    needs = version["needs"]
    assert needs["SPEC_1"]["chain"] == ["REQ_1", "SYS_1"]
    assert needs["IMPL_1"]["chain"] == ["REQ_1", "SYS_1"]
    assert needs["REQ_1"]["chain_back"] == ["IMPL_1", "SPEC_1"]
    assert needs["SYS_1"]["chain_back"] == ["IMPL_1", "SPEC_1"]
    assert needs["SYS_1"]["mitigates_back"] == ["SPEC_1"]
    assert needs["REQ_2"]["chain_back"] == needs["REQ_2"]["mitigates_back"] == []
    properties = version["needs_schema"]["properties"]
    for name in ("chain", "chain_back", "mitigates", "mitigates_back"):
        assert properties[name]["summary"] is True, name


CONF_TYPE_LOCAL = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {"evid": {"summary": True}, "rel": {}},
    },
    {
        "directive": "test",
        "title": "Test",
        "prefix": "T_",
        "links": {"evid": {"summary": True}, "rel": {"summary": True}},
    },
    {"directive": "impl", "title": "Implementation", "prefix": "I_", "links": {"evid": {}}},
    {
        "directive": "sub",
        "title": "Sub-specification",
        "prefix": "SU_",
        "inherits": "spec",
        "links": {"evid": {"summary": False}},
    },
]
"""

INDEX_TYPE_LOCAL = """\
On need types
=============

.. req:: Requirement
   :id: REQ_1

.. spec:: Sets the shapes: evid a summary, rel none
   :id: SPEC_1
   :evid: REQ_1
   :rel: REQ_1

.. test:: Repeats evid's, refused for rel's
   :id: TEST_1
   :evid: REQ_1
   :rel: REQ_1

.. impl:: Leaves evid's out
   :id: IMPL_1
   :evid: REQ_1

.. sub:: Refused child, still declaring evid through its parent
   :id: SUB_1
   :evid: REQ_1
"""


@pytest.mark.xfail(
    strict=True,
    reason="pinned ahead of the change: a link type need types alone declare can be a summary",
)
@pytest.mark.parametrize(
    "test_app", [_project(CONF_TYPE_LOCAL, INDEX_TYPE_LOCAL)], indirect=True
)
def test_a_summary_link_type_declared_on_need_types_alone(test_app):
    """``summary`` is part of the shape of a link type need types alone declare: its
    first root declaration sets it, a silent one too (``false``), and every other
    declaration may repeat it or leave it out; another value is a
    ``needs.type_conflict``, which refuses a root's entry and leaves a child declaring
    the link type through its parent. needs.json marks a summary, and its back links,
    as one ``needs_links`` declares."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['sub'].links['evid'] cannot be declared with summary "
        "False: its summary is True on every need type, as need type 'spec' declares "
        "it; the entry is ignored [needs.type_conflict]",
        "WARNING: needs_types['test'].links['rel'] cannot be declared with summary "
        "True: its summary is False on every need type, as need type 'spec' declares "
        "it; the entry is ignored [needs.type_conflict]",
        "<srcdir>/index.rst:12: WARNING: Link type 'rel' is not declared on need type "
        "'test' and cannot be set in need 'TEST_1'; the value 'REQ_1' is ignored "
        "[needs.undeclared_for_type]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    evid, rel = schema.get_link_field("evid"), schema.get_link_field("rel")
    assert evid is not None and evid.summary
    assert rel is not None and not rel.summary
    for need_type in ("spec", "test", "impl", "sub"):
        declared = schema.for_type(need_type).get_link_field("evid")
        assert declared is not None and declared.summary, need_type
    version = _version(app)
    properties = version["needs_schema"]["properties"]
    assert properties["evid"]["summary"] is True
    assert properties["evid_back"]["summary"] is True
    assert "summary" not in properties["rel"]
    assert "summary" not in properties["rel_back"]
    needs = version["needs"]
    for need_id in ("SPEC_1", "TEST_1", "IMPL_1", "SUB_1"):
        assert needs[need_id]["evid"] == ["REQ_1"], need_id
    assert needs["REQ_1"]["evid_back"] == ["IMPL_1", "SPEC_1", "SUB_1", "TEST_1"]
    assert needs["TEST_1"]["rel"] == []


CONF_TYPE_PATH = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"satisfies": {}}
_COPY = {"kind": "copy", "field": "id", "over": "satisfies"}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "reach": {"summary": False, "derive": _COPY},
            "chain": {"derive": _COPY},
            "mitigates": {"summary": True, "copy": True},
        },
    },
    {
        "directive": "test",
        "title": "Test",
        "prefix": "T_",
        "links": {"chain": {"summary": False, "derive": _COPY}},
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "I_",
        "links": {"chain": {"summary": True, "derive": _COPY}},
    },
]
"""

INDEX_TYPE_PATH = """\
Paths
=====

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1
   :mitigates: REQ_1

.. test:: Test
   :id: TEST_1
   :satisfies: REQ_1

.. impl:: Implementation
   :id: IMPL_1
   :satisfies: REQ_1
"""


@pytest.mark.xfail(
    strict=True,
    reason="pinned ahead of the change: a link type need types alone declare can be a summary",
)
@pytest.mark.parametrize(
    "test_app", [_project(CONF_TYPE_PATH, INDEX_TYPE_PATH)], indirect=True
)
def test_a_path_on_need_types_is_a_summary_whatever_a_declaration_says(test_app):
    """A copy or collect makes a link type need types alone declare a summary, as on
    ``needs_links``: a declaration may say so, and ``summary = false`` beside the rule
    is a ``needs.derive_invalid`` finding at the entry giving it -- the first root's or
    a later root's -- the key ignored and the rule applied there, not a conflict of the
    link type's shape. ``copy = true`` beside ``summary = true`` on an authored one is
    a ``needs.config`` finding at its first root's entry, ignored, and so not
    deprecated: nothing is copied into ``links``."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['spec'].links['mitigates'] has 'copy = true' beside "
        "'summary = true': a copy in links would make a summary link an edge; copy is "
        "ignored [needs.config]",
        "WARNING: Invalid derive of link type 'chain': needs_types['test'].links"
        "['chain']: 'summary' cannot be given beside derive, and is ignored (a link a "
        "copy or collect computes is a path, not an edge); the rule applies "
        "[needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'reach': needs_types['spec'].links"
        "['reach']: 'summary' cannot be given beside derive, and is ignored (a link a "
        "copy or collect computes is a path, not an edge); the rule applies "
        "[needs.derive_invalid]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    for name in ("chain", "reach", "mitigates"):
        link = schema.get_link_field(name)
        assert link is not None and link.summary, name
    mitigates = schema.get_link_field("mitigates")
    assert mitigates is not None and not mitigates.copy
    version = _version(app)
    properties = version["needs_schema"]["properties"]
    for name in ("chain", "chain_back", "reach", "reach_back"):
        assert properties[name]["summary"] is True, name
    needs = version["needs"]
    assert needs["SPEC_1"]["reach"] == ["REQ_1"]
    for need_id in ("SPEC_1", "TEST_1", "IMPL_1"):
        assert needs[need_id]["chain"] == ["REQ_1"], need_id
    assert needs["SPEC_1"]["mitigates"] == ["REQ_1"]
    assert needs["SPEC_1"]["links"] == []


CONF_TYPE_GLOBAL = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"evid": {"summary": True}}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {"evid": {"summary": True, "description": "Its evidence"}},
    },
]
"""

INDEX_TYPE_GLOBAL = """\
Global
======

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :evid: REQ_1
"""


@pytest.mark.xfail(
    strict=True,
    reason="pinned ahead of the change: a link type need types alone declare can be a summary",
)
@pytest.mark.parametrize(
    "test_app", [_project(CONF_TYPE_GLOBAL, INDEX_TYPE_GLOBAL)], indirect=True
)
def test_a_need_type_gives_no_summary_of_a_link_type_declared_otherwise(test_app):
    """On a link type ``needs_links`` declares, ``summary`` is its entry's: a need
    type's entry giving it is a ``needs.config`` finding even where it repeats the
    link type's own, the key ignored and the rest of the entry used."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['spec'].links['evid'] sets 'summary', which a need type "
        "gives only a link type declared on need types alone; 'evid' keeps its own on "
        "every need type and the key is ignored [needs.config]",
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    evid = schema.for_type("spec").get_link_field("evid")
    assert evid is not None and evid.summary
    assert evid.description == "Its evidence"
    assert _version(app)["needs"]["SPEC_1"]["evid"] == ["REQ_1"]
