"""The ``union`` kind: a link type holding the links of other link types.

``derive = {kind = "union", fields = [...]}`` on a link type gives each need the links of
its members, in the order ``fields`` names them, each link once by its target, part and
condition. The shared corpus pins its values and its ``needs.derive_invalid`` findings
(``tests/fixtures/derive_conformance.toml``); this module pins what the corpus does not
compare: the messages, that the union leaves dead links and link conditions to its
members, the density check, the export's schema, and the order the pass computes in.
"""

import json
from pathlib import Path

import pytest

from sphinx_needs.derive import DeriveInvalid, DeriveRule, parse_derive
from sphinx_needs_testkit import build_warnings

_CLOSED_LINK = (
    "the link type cannot be set in a need or by a needextend, and holds no links"
)


def _invalid_link(name: str, reason: str) -> str:
    return (
        f"WARNING: Invalid derive of link type {name!r}: {reason}; {_CLOSED_LINK} "
        "[needs.derive_invalid]"
    )


def _built(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return data["versions"][data["current_version"]]


def _project(conf: str, index: str) -> dict:
    return {
        "buildername": "needs",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(
            {"kind": "union", "fields": ["links", "blocks"]},
            DeriveRule(kind="union", fields=("links", "blocks")),
            id="members",
        ),
        pytest.param(
            {"kind": "union", "fields": ["blocks", "blocks"]},
            DeriveInvalid(
                "union", "kind 'union': the role 'fields' names 'blocks' twice"
            ),
            id="twice",
        ),
        pytest.param(
            {"kind": "union"},
            DeriveInvalid("union", "kind 'union' requires the role 'fields'"),
            id="no-members",
        ),
        pytest.param(
            {"kind": "union", "fields": ["links"], "where": "True"},
            DeriveInvalid("union", "kind 'union' does not take the role 'where'"),
            id="a-filter",
        ),
    ],
)
def test_parse_a_union(raw, expected):
    """A union takes its members in ``fields``, each named once, and no other role."""
    assert parse_derive(raw, on_link=True) == expected


def test_a_union_is_declared_on_a_link_type():
    assert parse_derive({"kind": "union", "fields": ["links"]}, on_link=False) == (
        DeriveInvalid(
            "union",
            "kind 'union' computes a link list, so it is declared on a link type "
            "(needs_links), not on a field",
        )
    )


CONF_REFUSALS = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"owner": {"schema": {"type": "string"}}}
needs_links = {
    "blocks": {},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
    "bad_back": {"derive": {"kind": "union", "fields": ["blocks_back"]}},
    "bad_field": {"derive": {"kind": "union", "fields": ["owner"]}},
    "bad_none": {"derive": {"kind": "union", "fields": ["nope"]}},
    "bad_parent": {"derive": {"kind": "union", "fields": ["parent_needs"]}},
    "bad_self": {"derive": {"kind": "union", "fields": ["links", "bad_self"]}},
    "dead_ok": {
        "derive": {"kind": "union", "fields": ["blocks"]},
        "allow_dead_links": True,
    },
    "dead_by_type": {
        "derive_by_type": {"spec": {"kind": "union", "fields": ["blocks"]}},
        "allow_dead_links": True,
    },
    "dead_kept": {
        "derive": {"kind": "links", "where": "type == 'req'"},
        "allow_dead_links": True,
    },
}
"""

INDEX_REFUSALS = """\
Refusals
========

.. req:: One
   :id: REQ_1

.. spec:: Links it
   :id: SPEC_1
   :links: REQ_1
   :blocks: REQ_1, DEAD_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_REFUSALS, INDEX_REFUSALS)], indirect=True
)
def test_the_refusals(test_app):
    """Each member that is no link type, ``parent_needs``, and the union itself are
    refused at load, one ``needs.derive_invalid`` each; ``allow_dead_links`` beside a
    union says nothing, as the union reports no dead link, so it is refused and
    ignored, and the rule applies -- beside a ``links`` rule it still counts."""
    app = test_app
    app.build()
    union = "kind 'union': the role 'fields'"
    assert build_warnings(app) == [
        _invalid_link(
            "bad_back",
            f"{union} names the back links 'blocks_back', which a union cannot read: "
            "they are built after the link types",
        ),
        _invalid_link("bad_field", f"{union} names 'owner', which is not a link type"),
        _invalid_link("bad_none", f"{union} names 'nope', which is not a link type"),
        _invalid_link(
            "bad_parent",
            f"{union} names 'parent_needs', which a union cannot read in this release",
        ),
        _invalid_link(
            "bad_self",
            f"{union} reads 'bad_self', whose rule reads this field back "
            "(bad_self -> bad_self), so no need can compute it",
        ),
        "WARNING: Invalid derive of link type 'dead_by_type': 'allow_dead_links' "
        "cannot be given beside derive_by_type, and is ignored; the rules apply "
        "[needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'dead_ok': kind 'union': "
        "'allow_dead_links' cannot be given beside derive, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        "<srcdir>/index.rst:7: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'DEAD_1' in field 'blocks' [needs.link_outgoing]",
    ]
    spec = _built(app)["needs"]["SPEC_1"]
    assert spec["all_links"] == ["DEAD_1", "REQ_1"]
    assert spec["dead_ok"] == spec["dead_by_type"] == ["DEAD_1", "REQ_1"]
    for name in ("bad_back", "bad_field", "bad_none", "bad_parent", "bad_self"):
        assert spec[name] == [], name


CONF_DEAD = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "blocks": {"allow_dead_links": %s},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
}
"""

INDEX_DEAD = """\
Dead links
==========

.. req:: Open
   :id: REQ_1
   :status: open

.. spec:: Links a dead need, and a need its condition refuses
   :id: SPEC_1
   :blocks: DEAD_1, REQ_1[status == 'closed']
"""


@pytest.mark.parametrize(
    ("test_app", "dead"),
    [
        pytest.param(_project(CONF_DEAD % "True", INDEX_DEAD), [], id="allowed"),
        pytest.param(
            _project(CONF_DEAD % "False", INDEX_DEAD),
            [
                "<srcdir>/index.rst:8: WARNING: Need 'SPEC_1' has unknown outgoing "
                "link 'DEAD_1' in field 'blocks' [needs.link_outgoing]"
            ],
            id="forbidden",
        ),
    ],
    indirect=["test_app"],
)
def test_dead_links_and_conditions_are_the_members(test_app, dead):
    """A union holds its members' dead links and conditions, and reports neither: a
    dead link is reported once, at the member, as the member allows dead links (not a
    second time under the union, which allows none), and only the member decides
    ``has_forbidden_dead_links``; a failed condition is reported once, at the member."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Need 'SPEC_1' link 'REQ_1' in field 'blocks': "
        "condition \"status == 'closed'\" not satisfied by target need 'REQ_1' "
        "[needs.link_condition_failed]",
        *dead,
    ]
    spec = _built(app)["needs"]["SPEC_1"]
    assert spec["all_links"] == ["DEAD_1", "REQ_1[status == 'closed']"]
    assert spec["has_dead_links"] is True
    assert spec["has_forbidden_dead_links"] is bool(dead)


CONF_DENSE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_derive_max_links_per_need = 1
needs_links = {
    "l_reqs": {"derive": {"kind": "links", "where": "type == 'req'"}},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "l_reqs"]}},
}
"""

INDEX_DENSE = """\
Dense
=====

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. req:: Three
   :id: REQ_3

.. spec:: Links them
   :id: SPEC_1
   :links: REQ_1, REQ_2, REQ_3
"""


@pytest.mark.parametrize("test_app", [_project(CONF_DENSE, INDEX_DENSE)], indirect=True)
def test_a_union_is_not_counted_as_dense(test_app):
    """``needs.derive_dense`` counts the links a rule computes; a union's are its
    members' links, counted where they are computed (``l_reqs``, 2 + 2 + 2 + 3 = 9
    links on 4 needs), so the union, which stores 9 + 3, is not reported."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith(
        "WARNING: Link type 'l_reqs' stores 9 links computed by its derive rule "
        "(kind 'links')"
    )
    assert _built(app)["needs"]["SPEC_1"]["all_links"] == ["REQ_1", "REQ_2", "REQ_3"]


CONF_ORDER = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "in_order": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "copy", "field": "all_links"},
    },
}
needs_links = {
    "blocks": {},
    "all_links": {"derive": {"kind": "union", "fields": ["blocks", "links"]}},
}
"""

INDEX_ORDER = """\
Order
=====

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. req:: Three
   :id: REQ_3

.. spec:: Links them
   :id: SPEC_1
   :links: REQ_1, REQ_2
   :blocks: REQ_3, REQ_1
"""


@pytest.mark.parametrize("test_app", [_project(CONF_ORDER, INDEX_ORDER)], indirect=True)
def test_the_order_a_union_is_computed_in(test_app):
    """In the pass, the union lists its members in the order ``fields`` names them,
    each in its own order, a link the second time it comes left out: a copy into an
    array field reads ``REQ_3, REQ_1, REQ_2``. ``needs.json`` writes the union sorted,
    as every link type; the readOnly mark and the back links are a derived link type's.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    version = _built(app)
    spec = version["needs"]["SPEC_1"]
    assert spec["in_order"] == ["REQ_3", "REQ_1", "REQ_2"]
    assert spec["all_links"] == ["REQ_1", "REQ_2", "REQ_3"]
    assert version["needs"]["REQ_1"]["all_links_back"] == ["SPEC_1"]
    properties = version["needs_schema"]["properties"]
    assert properties["all_links"]["field_type"] == "links"
    assert properties["all_links"]["readOnly"] is True
    assert properties["all_links_back"]["field_type"] == "backlinks"
