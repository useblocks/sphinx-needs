"""The ``union`` kind: a link type holding the links of other link types.

``derive = {kind = "union", fields = [...]}`` on a link type gives each need the links of
its members, in the order ``fields`` names them, each link once by its target, part and
condition. The shared corpus pins its values and its ``needs.derive_invalid`` findings
(``tests/fixtures/derive_conformance.toml``); this module pins what the corpus does not
compare: the messages, that the union leaves dead links and link conditions to its
members, the density check, the export's schema, and the order the pass computes in.
"""

import json
import re
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
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
        "cannot be given beside derive_by_type, and is ignored (a union's dead links "
        "are its members'); the rules apply [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'dead_ok': kind 'union': "
        "'allow_dead_links' cannot be given beside derive, and is ignored (a union's "
        "dead links are its members'); the rule applies [needs.derive_invalid]",
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


CONF_MIXED = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "blocks": {},
    "mentions": {
        "allow_dead_links": True,
        "derive_by_type": {
            "spec": {"kind": "union", "fields": ["blocks"]},
            "req": {"kind": "content_links"},
        },
    },
}
"""

INDEX_MIXED = """\
Mixed
=====

.. req:: Mentions a dead need
   :id: REQ_1

   Mentions :need:`DEAD_1`.

.. spec:: Blocks a dead need
   :id: SPEC_1
   :blocks: DEAD_2
"""


@pytest.mark.parametrize("test_app", [_project(CONF_MIXED, INDEX_MIXED)], indirect=True)
def test_allow_dead_links_beside_rules_not_all_unions_is_kept(test_app):
    """``allow_dead_links`` is refused only where every rule of the link type is a
    union: beside a ``content_links`` rule for another need type it is that rule's,
    so the dead reference it computes on ``req`` is allowed; on ``spec`` the union
    leaves its dead link to ``blocks``, which reports it once."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:9: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'DEAD_2' in field 'blocks' [needs.link_outgoing]",
    ]
    needs = _built(app)["needs"]
    assert needs["REQ_1"]["mentions"] == ["DEAD_1"]
    assert needs["REQ_1"]["has_forbidden_dead_links"] is False
    assert needs["SPEC_1"]["mentions"] == ["DEAD_2"]
    assert needs["SPEC_1"]["has_forbidden_dead_links"] is True


CONF_TYPE_ENTRY = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"blocks": {"allow_dead_links": True}}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "tl": {
                "derive": {"kind": "union", "fields": ["blocks"]},
                "allow_dead_links": True,
            }
        },
    },
]
"""

INDEX_TYPE_ENTRY = """\
Type entry
==========

.. spec:: Blocks a dead need
   :id: S_001
   :blocks: DEAD_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_TYPE_ENTRY, INDEX_TYPE_ENTRY)], indirect=True
)
def test_allow_dead_links_beside_a_union_in_a_need_types_entry(test_app):
    """The refusal of ``allow_dead_links`` beside a union a need type's entry declares
    names that entry, and the ``derive`` beside it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of link type 'tl': needs_types['spec'].links['tl']: "
        "'allow_dead_links' cannot be given beside derive, and is ignored (a union's "
        "dead links are its members'); the rule applies [needs.derive_invalid]",
    ]
    assert _built(app)["needs"]["S_001"]["tl"] == ["DEAD_1"]


CONF_IMPORTED = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "blocks": {"allow_dead_links": True},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
}
"""

IMPORTED_JSON = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "EXP_1": {
                        "id": "EXP_1",
                        "type": "spec",
                        "title": "Its union names a dead need its members do not",
                        "blocks": [],
                        "all_links": ["DEAD_9"],
                    }
                }
            }
        },
    }
)

INDEX_IMPORTED = """\
Imported
========

.. needimport:: exp.json

.. spec:: Blocks a dead need, which blocks allows
   :id: LOC_1
   :blocks: DEAD_1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_IMPORTED),
                (Path("exp.json"), IMPORTED_JSON),
                (Path("index.rst"), INDEX_IMPORTED),
            ],
        }
    ],
    indirect=True,
)
def test_an_imported_union_is_checked_as_any_link_type(test_app):
    """A union leaves its dead links to its members only where its rule computed it:
    an imported need keeps the union its file gives, which no member holds, so it is
    checked as any link type, under the union's own allow_dead_links (none): its dead
    link is reported and forbidden. ``has_dead_links`` counts every link type, a
    union's too, as before; on a computed need only the member decides what is
    forbidden."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Need 'EXP_1' has unknown outgoing link "
        "'DEAD_9' in field 'all_links' [needs.link_outgoing]",
    ]
    needs = _built(app)["needs"]
    imported, local = needs["EXP_1"], needs["LOC_1"]
    assert (imported["all_links"], imported["blocks"]) == (["DEAD_9"], [])
    assert (imported["has_dead_links"], imported["has_forbidden_dead_links"]) == (
        True,
        True,
    )
    assert local["all_links"] == ["DEAD_1"]
    assert (local["has_dead_links"], local["has_forbidden_dead_links"]) == (
        True,
        False,
    )


CONF_UNREADABLE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "blocks": {},
    "bad_member": {
        "derive": {"kind": "union", "fields": ["links", "nope"]},
        "allow_dead_links": True,
    },
    "cyc_a": {
        "derive": {"kind": "union", "fields": ["links", "cyc_b"]},
        "allow_dead_links": True,
    },
    "cyc_b": {"derive": {"kind": "union", "fields": ["cyc_a"]}},
    "bad_entry": {
        "derive": {"kind": "union", "fields": ["blocks"]},
        "derive_by_type": {"spec": {"kind": "union", "fields": ["nope"]}},
        "allow_dead_links": True,
    },
    "bad_entry_targets": {
        "derive": {"kind": "union", "fields": ["blocks"]},
        "derive_by_type": {"spec": {"kind": "union", "fields": ["nope"]}},
        "allow_dead_links": True,
        "target_types": ["req"],
    },
}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "links": {
            "tl": {
                "derive": {"kind": "union", "fields": ["nope"]},
                "allow_dead_links": True,
            }
        },
    },
]
"""

UNREADABLE_JSON = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "IMP_1": {
                        "id": "IMP_1",
                        "type": "spec",
                        "title": "A dead link in each union that cannot be read",
                        "bad_member": ["DEAD_1"],
                        "cyc_a": ["DEAD_2"],
                        "bad_entry": ["DEAD_3"],
                        "tl": ["DEAD_4"],
                    }
                }
            }
        },
    }
)


def _invalid_on_spec(name: str, reason: str) -> str:
    return (
        f"WARNING: Invalid derive of link type {name!r}: {reason}; the link type cannot "
        "be set in a need or by a needextend, and on need type 'spec' holds no links "
        "[needs.derive_invalid]"
    )


#: the link types beside whose unions that cannot be read allow_dead_links is kept
UNREADABLE = ("bad_member", "cyc_a", "bad_entry", "bad_entry_targets", "tl")


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_UNREADABLE),
                (Path("imp.json"), UNREADABLE_JSON),
                (
                    Path("index.rst"),
                    "Unreadable\n==========\n\n.. needimport:: imp.json\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_allow_dead_links_beside_a_union_that_cannot_be_read_is_kept(test_app):
    """A union refused for a member, on a cycle, or in an entry for one need type, is
    no union: it holds no links where it is computed, and ``allow_dead_links`` beside
    it is kept, as beside any rule -- decided from the rules once checked, not from
    the kinds as written. Its refusal is withdrawn, the other keys beside the rule
    still reported; a dead link an imported need carries in such a link type is
    allowed. In ``derive_by_type``, the readable ``derive`` beside the entry does not
    make every rule a union."""
    app = test_app
    app.build()
    union = "kind 'union': the role 'fields'"
    nope = f"{union} names 'nope', which is not a link type"
    assert build_warnings(app) == [
        _invalid_on_spec("bad_entry", "derive_by_type.spec: " + nope),
        "WARNING: Invalid derive of link type 'bad_entry_targets': kind 'union': "
        "'target_types' cannot be given beside derive, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        _invalid_on_spec("bad_entry_targets", "derive_by_type.spec: " + nope),
        _invalid_link("bad_member", nope),
        _invalid_link(
            "cyc_a",
            f"{union} reads 'cyc_b', whose rule reads this field back "
            "(cyc_a -> cyc_b -> cyc_a), so no need can compute it",
        ),
        _invalid_link(
            "cyc_b",
            f"{union} reads 'cyc_a', whose rule reads this field back "
            "(cyc_b -> cyc_a -> cyc_b), so no need can compute it",
        ),
        _invalid_on_spec("tl", "needs_types['spec'].links['tl'].derive: " + nope),
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    for name in UNREADABLE:
        link = schema.global_declaration(name)
        assert link is not None and link.allow_dead_links is True, name
    imported = _built(app)["needs"]["IMP_1"]
    assert (imported["has_dead_links"], imported["has_forbidden_dead_links"]) == (
        True,
        False,
    )


CONF_CYCLE_ON_ONE_TYPE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "fx": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "fy"},
        "default": "d",
    },
    "fy": {
        "schema": {"type": "string"},
        "derive_by_type": {"spec": {"kind": "copy", "field": "fx"}},
    },
}
needs_links = {
    "a": {
        "derive": {"kind": "union", "fields": ["links", "b"]},
        "allow_dead_links": True,
        "target_types": ["req"],
    },
    "b": {"derive_by_type": {"spec": {"kind": "union", "fields": ["a"]}}},
    "e": {"derive": {"kind": "union", "fields": ["links", "f"]}, "copy": True},
    "f": {"derive_by_type": {"spec": {"kind": "union", "fields": ["e"]}}},
}
"""


#: the rules whose cycle findings carry the keys refused beside them
MINE = (("field", "fx"), ("link type", "a"), ("link type", "e"))


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF_CYCLE_ON_ONE_TYPE, "Cycle\n=====\n\n.. req:: One\n   :id: REQ_1\n")],
    indirect=True,
)
def test_allow_dead_links_beside_a_union_cycling_on_one_type_is_refused(test_app):
    """A ``derive`` closing a cycle on some need types only is still a union on every
    other type: the marker standing for it on those types is no rule of the link
    type's own, so ``allow_dead_links`` beside it is still refused -- and said, in the
    one finding of that ``derive``, the cycle's, as is every other key refused beside
    it (``target_types``; ``copy``; a field's ``default``)."""
    app = test_app
    app.build()
    applies = "on every other need type the rule applies"
    assert [
        w
        for w in build_warnings(app)
        if any(f"{kind} {name!r}" in w for kind, name in MINE)
    ] == [
        "WARNING: Invalid derive of field 'fx': on need type 'spec': kind 'copy': the "
        "role 'field' reads 'fy', whose rule reads this field back (fx -> fy -> fx), "
        "so no need can compute it; the field cannot be set in a need or by a "
        f"needextend, and on that need type holds its empty value; {applies}; "
        "'default' cannot be given beside derive, and is ignored [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'a': on need type 'spec': kind 'union': "
        "the role 'fields' reads 'b', whose rule reads this field back (a -> b -> a), "
        "so no need can compute it; the link type cannot be set in a need or by a "
        f"needextend, and on that need type holds no links; {applies}; "
        "'target_types' and 'allow_dead_links' cannot be given beside derive, and are "
        "ignored (a union's dead links are its members') [needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'e': on need type 'spec': kind 'union': "
        "the role 'fields' reads 'f', whose rule reads this field back (e -> f -> e), "
        "so no need can compute it; the link type cannot be set in a need or by a "
        f"needextend, and on that need type holds no links; {applies}; 'copy' cannot "
        "be given beside derive, and is ignored [needs.derive_invalid]",
    ]
    link = SphinxNeedsData(app.env).get_schema().global_declaration("a")
    assert link is not None and link.allow_dead_links is False
    assert isinstance(link.derive_by_type["spec"], DeriveInvalid)
    assert link.derive_by_type["spec"].fallback


CONF_PER_TYPE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "blocks": {},
    "tests": {"allow_dead_links": True},
    "all_links": {
        "derive_by_type": {
            "spec": {"kind": "union", "fields": ["blocks", "tests"]},
        },
        "allow_dead_links": True,
    },
}
"""

INDEX_PER_TYPE = """\
Per type
========

.. req:: A closed requirement
   :id: REQ_0
   :status: closed

.. req:: No union: a forbidden dead link, a failed condition
   :id: REQ_1
   :blocks: DEAD_1, REQ_0[status == 'open']

.. req:: No union: an allowed dead link
   :id: REQ_2
   :tests: DEAD_2

.. spec:: The union: a forbidden dead link, a failed condition
   :id: SPEC_1
   :blocks: DEAD_3, REQ_0[status == 'open']

.. spec:: The union: an allowed dead link
   :id: SPEC_2
   :tests: DEAD_4
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_PER_TYPE, INDEX_PER_TYPE)], indirect=True
)
def test_a_union_for_one_need_type(test_app):
    """A ``derive_by_type`` union is a union on its need type alone, read per need: on
    ``spec`` it reports no dead link and no condition of its own, and its dead links
    are forbidden as the member says; on ``req``, read first, it has no rule and holds
    no links. Every rule being a union, ``allow_dead_links`` beside it is refused."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of link type 'all_links': 'allow_dead_links' cannot "
        "be given beside derive_by_type, and is ignored (a union's dead links are its "
        "members'); the rules apply [needs.derive_invalid]",
        "<srcdir>/index.rst:8: WARNING: Need 'REQ_1' link 'REQ_0' in field 'blocks': "
        "condition \"status == 'open'\" not satisfied by target need 'REQ_0' "
        "[needs.link_condition_failed]",
        "<srcdir>/index.rst:8: WARNING: Need 'REQ_1' has unknown outgoing link "
        "'DEAD_1' in field 'blocks' [needs.link_outgoing]",
        "<srcdir>/index.rst:16: WARNING: Need 'SPEC_1' link 'REQ_0' in field 'blocks': "
        "condition \"status == 'open'\" not satisfied by target need 'REQ_0' "
        "[needs.link_condition_failed]",
        "<srcdir>/index.rst:16: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'DEAD_3' in field 'blocks' [needs.link_outgoing]",
    ]
    needs = _built(app)["needs"]
    assert {
        need_id: (
            need["all_links"],
            need["has_dead_links"],
            need["has_forbidden_dead_links"],
        )
        for need_id, need in needs.items()
        if need_id != "REQ_0"
    } == {
        "REQ_1": ([], True, True),
        "REQ_2": ([], True, False),
        "SPEC_1": (["DEAD_3", "REQ_0[status == 'open']"], True, True),
        "SPEC_2": (["DEAD_4"], True, False),
    }


CONF_OWN_FUNCTION = """\
extensions = ["sphinx_needs"]
needs_build_json = True


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


needs_functions = [my_links]
needs_links = {
    "blocks": {"copy": True},
    "flt": {},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
    "all_flt": {"derive": {"kind": "union", "fields": ["flt"]}},
}
"""

INDEX_OWN_FUNCTION = """\
Own function
============

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Its blocks are your own function's
   :id: SPEC_1
   :blocks: [[my_links()]]
   :links: REQ_1

.. spec:: Its flt is a call whose filter names needs
   :id: SPEC_2
   :flt: [[links_from_filter("len(needs) > 0 and id == 'REQ_1'")]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_OWN_FUNCTION, INDEX_OWN_FUNCTION)], indirect=True
)
def test_a_union_reads_a_member_computed_after_the_built_ins(test_app):
    """Your own functions run after the built-in ones of their step, and so does a
    built-in call whose filter cannot be read (it names ``needs``); a union over a
    member one of them computes is computed after them, so it holds the member's
    links -- and, with ``copy``, the copied call's in ``links`` too -- with no
    ``needs.derive_scope``. On the needs whose members are all built-in the union
    is computed with the built-ins, as before."""
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if "derive_scope" in w] == []
    needs = _built(app)["needs"]
    assert needs["SPEC_1"]["links"] == ["REQ_1", "REQ_2"]
    assert needs["SPEC_1"]["all_links"] == ["REQ_1", "REQ_2"]
    assert needs["REQ_2"]["all_links_back"] == ["SPEC_1"]
    assert needs["SPEC_2"]["flt"] == ["REQ_1"]
    assert needs["SPEC_2"]["all_flt"] == ["REQ_1"]
    assert needs["REQ_1"]["all_flt_back"] == ["SPEC_2"]


CONF_READ_AFTER_LAST = """\
extensions = ["sphinx_needs"]
needs_build_json = True


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


def read_union(app, need, needs, *args, **kwargs):
    return list(needs["SPEC_1"]["all_links"])


needs_functions = [my_links, read_union]
needs_links = {
    "blocks": {},
    "seen": {},
    "via": {},
    "me": {},
    "summed": {},
    "opq": {},
    "late_copy": {},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
    "again": {"derive": {"kind": "union", "fields": ["all_links"]}},
    "where_rule": {"derive": {"kind": "links", "where": "'REQ_2' in all_links"}},
}
"""

INDEX_READ_AFTER_LAST = """\
Read after last
===============

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Before every union, computed last
   :id: SPEC_0
   :seen: [[read_union()]]
   :opq: [[links_from_filter("len(needs) > 0 and 'REQ_2' in all_links")]]

.. spec:: Its blocks are your own function's
   :id: SPEC_1
   :blocks: [[my_links()]]
   :links: REQ_1
   :me: [[links_from_filter("'REQ_2' in current_need['all_links'] and type == 'req'")]]
   :summed: [[calc_sum("all_links", filter="type == 'spec'")]]

.. spec:: After SPEC_1's union, computed last
   :id: SPEC_2
   :via: REQ_1, [[links_from_filter("'REQ_2' in all_links")]]
   :seen: [[read_union()]]
   :late_copy: [[copy("all_links", filter="len(needs) > 0 and id == 'SPEC_1'")]]

.. spec:: A call whose filter cannot be read fills it, and names it
   :id: SPEC_4
   :blocks: [[links_from_filter("len(needs) > 0 and 'REQ_2' in all_links")]]

.. spec:: A copy whose filter cannot be read fills it, before SPEC_6's union
   :id: SPEC_5
   :blocks: [[copy("all_links", filter="len(needs) > 0 and id == 'SPEC_6'")]]

.. spec:: Its blocks are your own function's too
   :id: SPEC_6
   :blocks: [[my_links()]]

.. spec:: After every union, computed last
   :id: SPEC_9
   :opq: [[links_from_filter("len(needs) > 0 and 'REQ_2' in all_links")]]
"""

#: why a node computed last before a value computed after the nodes computed last it
#: reads cannot wait for it
_AFTER = (
    "computed after this call, among your own functions and the calls whose filter "
    "cannot be read, so this step cannot wait for them"
)


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF_READ_AFTER_LAST, INDEX_READ_AFTER_LAST)],
    indirect=True,
)
def test_a_union_computed_last_and_its_readers(test_app):
    """A union over a member your own function, or a call whose filter cannot be
    read, computes is computed right after the last such member, among the nodes
    computed last in need-id order, and a union of that union after that; so is every
    built-in function or rule reading such a union, or such a member, on any need:
    ``me`` (``current_need['all_links']``), ``via`` (a filter on every need),
    ``where_rule`` (a ``links`` rule, on every need computing it) hold the links they
    select, with no warning. ``summed`` (a sum written in a link field) is computed
    too, and its result is no link list (``needs.dynamic_function``).

    A node computed last after the union reads it complete (SPEC_2's ``seen`` and
    ``late_copy`` after SPEC_1's union, SPEC_9's ``opq`` after every union); one before
    it reads it empty (SPEC_0's own function ``seen``: the trade-off), but a call whose
    filter cannot be read and names the union cannot wait for it, and says so
    (SPEC_0's ``opq``, SPEC_4's ``blocks``, which fills a member); a call that records
    its reads reports reading it at run time (SPEC_5's ``copy`` of SPEC_6's union)."""
    app = test_app
    app.build()
    assert [
        w
        for w in build_warnings(app)
        if "config.cache" not in w and "cannot cache unpickable" not in w
    ] == [
        "<srcdir>/index.rst:10: WARNING: dynamic function 'links_from_filter' for "
        "option 'opq' reads 'all_links' on 3 needs (SPEC_1, SPEC_5, SPEC_6), which are "
        f"{_AFTER}: the call is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:28: WARNING: dynamic function 'links_from_filter' for "
        "option 'blocks' reads 'all_links' on 3 needs (SPEC_4, SPEC_5, SPEC_6), which "
        f"are {_AFTER}: the call is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:32: WARNING: dynamic function 'copy' for option 'blocks' "
        "read 'all_links' on need 'SPEC_6' before it was computed: it is computed after "
        "your own functions and the calls whose filter cannot be read that it reads, "
        "after this call [needs.derive_scope]",
        "<srcdir>/index.rst:15: WARNING: Error while resolving dynamic values for field "
        "'summed', of need 'SPEC_1': dynamic function value <class 'float'> is not of "
        "type 'array' or item type 'string' [needs.dynamic_function]",
    ]
    needs = _built(app)["needs"]
    spec_1, spec_2 = needs["SPEC_1"], needs["SPEC_2"]
    assert spec_1["all_links"] == spec_1["again"] == ["REQ_1", "REQ_2"]
    assert needs["SPEC_6"]["all_links"] == ["REQ_2"]
    # built-in readers, computed after what they read
    assert (spec_1["me"], spec_1["summed"]) == (["REQ_1", "REQ_2"], [])
    assert spec_2["via"] == ["REQ_1", "SPEC_1", "SPEC_6"]
    assert spec_1["where_rule"] == ["SPEC_6"]
    assert needs["SPEC_6"]["where_rule"] == ["SPEC_1"]
    assert all(
        need["where_rule"] == ["SPEC_1", "SPEC_6"]
        for need_id, need in needs.items()
        if need_id not in ("SPEC_1", "SPEC_6")
    )
    # computed last, after the union: complete
    assert spec_2["seen"] == spec_2["late_copy"] == ["REQ_1", "REQ_2"]
    assert needs["SPEC_9"]["opq"] == ["SPEC_1", "SPEC_6"]
    # computed last, before it: your own function reads it empty (the trade-off)
    assert (needs["SPEC_0"]["seen"], needs["SPEC_0"]["opq"]) == ([], [])
    assert needs["SPEC_4"]["blocks"] == needs["SPEC_5"]["blocks"] == []


CONF_LAST_ORDER = """\
extensions = ["sphinx_needs"]
needs_build_json = True


def first(app, need, needs, *args, **kwargs):
    return ["REQ_1"]


def second(app, need, needs, *args, **kwargs):
    return list(needs["SPEC_1"]["seen"])


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


def read_zz(app, need, needs, *args, **kwargs):
    return list(needs["SPEC_3"]["all_zz"])


needs_functions = [first, second, my_links, read_zz]
needs_links = {
    "seen": {},
    "blocks": {},
    "zz": {},
    "q_seen": {},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "blocks"]}},
    "all_zz": {"derive": {"kind": "union", "fields": ["blocks", "zz"]}},
}
"""

INDEX_LAST_ORDER = """\
Last order
==========

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Your own function, first
   :id: SPEC_1
   :seen: [[first()]]

.. spec:: Your own function reading it, filling a member of a union
   :id: SPEC_2
   :blocks: [[second()]]

.. spec:: A union over a member computed last and a built-in one
   :id: SPEC_3
   :blocks: [[my_links()]]
   :zz: [[links_from_filter("id == 'REQ_1'")]]
   :q_seen: [[read_zz()]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_LAST_ORDER, INDEX_LAST_ORDER)], indirect=True
)
def test_the_nodes_computed_last_keep_need_id_order(test_app):
    """A union computed last changes nothing in the order of the nodes computed last,
    need-id order, then by field: SPEC_2's own function, filling a member of a union,
    still reads SPEC_1's, computed before it, and the union holds what it computed.
    A union is computed right after its last member computed last, whatever its
    built-in members: SPEC_3's ``all_zz`` comes after ``blocks``, before ``q_seen``
    (whose field sorts before the built-in member ``zz``), which reads it complete."""
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if "derive_scope" in w] == []
    needs = _built(app)["needs"]
    assert needs["SPEC_2"]["blocks"] == needs["SPEC_2"]["all_links"] == ["REQ_1"]
    assert needs["SPEC_3"]["all_zz"] == needs["SPEC_3"]["q_seen"] == ["REQ_1", "REQ_2"]


CONF_HTML = """\
extensions = ["sphinx_needs"]
needs_links = {
    "blocks": {"allow_dead_links": True},
    "tests": {},
    "all_links": {
        "outgoing": "all links",
        "derive": {"kind": "union", "fields": ["blocks", "tests"]},
    },
    "inner": {
        "outgoing": "inner links",
        "derive": {"kind": "union", "fields": ["blocks"]},
    },
    "outer": {
        "outgoing": "outer links",
        "derive": {"kind": "union", "fields": ["inner", "tests"]},
    },
}
"""

IMPORTED_HTML_JSON = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "EXP_1": {
                        "id": "EXP_1",
                        "type": "spec",
                        "title": "Imported, a dead link in its union",
                        "all_links": ["DEAD_9"],
                    }
                }
            }
        },
    }
)

INDEX_HTML = """\
Rendered
========

.. spec:: Dead links
   :id: SPEC_1
   :blocks: DEAD_1, DEAD_3
   :tests: DEAD_2, DEAD_3

.. needimport:: exp.json
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_HTML),
                (Path("exp.json"), IMPORTED_HTML_JSON),
                (Path("index.rst"), INDEX_HTML),
            ],
        }
    ],
    indirect=True,
)
def test_a_unions_dead_links_are_drawn_as_its_members_allow(test_app):
    """In a need's layout, a dead link of a union's row is marked forbidden where a
    member holding it does not allow dead links, as the build reports it: through a
    member that is a union itself, and where any member holding it does not (``DEAD_3``,
    in an allowing and a forbidding member). On an imported need, whose union no rule
    computed, the union's own ``allow_dead_links`` (none) decides."""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text("utf8")
    rows = [
        (label, re.findall(r'class="([^"]*)">(DEAD_\d)', row))
        for label, row in re.findall(
            r"(all links|inner links|outer links):(.*?)</div>", html, re.S
        )
    ]
    allowed, forbidden = "needs_dead_link", "needs_dead_link forbidden"
    assert rows == [
        # SPEC_1
        (
            "all links",
            [(allowed, "DEAD_1"), (forbidden, "DEAD_2"), (forbidden, "DEAD_3")],
        ),
        ("inner links", [(allowed, "DEAD_1"), (allowed, "DEAD_3")]),
        (
            "outer links",
            [(allowed, "DEAD_1"), (forbidden, "DEAD_2"), (forbidden, "DEAD_3")],
        ),
        # EXP_1, imported
        ("all links", [(forbidden, "DEAD_9")]),
    ]


CONF_CURRENT_KEY = """\
extensions = ["sphinx_needs"]
needs_build_json = True


def t_fn(app, need, needs, *args, **kwargs):
    return ["REQ_3"]


needs_functions = [t_fn]
needs_links = {
    "tests": {},
    "c_cur": {},
    "z_cur": {},
    "a_own": {},
    "u": {"derive": {"kind": "union", "fields": ["links", "tests"]}},
}
"""

INDEX_CURRENT_KEY = """\
Current key
===========

.. req:: One
   :id: REQ_1

.. req:: Three
   :id: REQ_3

.. spec:: The union's need
   :id: SPEC_5
   :links: REQ_1
   :tests: [[t_fn()]]
   :c_cur: [[links_from_filter("len(needs) > 0 and 'REQ_3' in current_need['u'] and id == 'REQ_1'")]]
   :z_cur: [[links_from_filter("len(needs) > 0 and 'REQ_3' in current_need['u'] and id == 'REQ_1'")]]

.. spec:: An earlier need, whose own union is computed with the built-ins
   :id: SPEC_1
   :links: REQ_3
   :a_own: [[links_from_filter("len(needs) > 0 and 'REQ_3' in current_need['u'] and id == 'REQ_1'")]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_CURRENT_KEY, INDEX_CURRENT_KEY)], indirect=True
)
def test_a_filter_naming_a_union_by_current_need_key(test_app):
    """A filter that cannot be read (it names ``needs``) but reads a union computed
    last as ``current_need['u']``, a constant key, names it as a free name would:
    before the union (``c_cur``, whose field sorts before the union's last late member
    ``tests``) the call is not run and is reported; after it (``z_cur``) it reads the
    union complete. The key is read on the need's own union only: SPEC_1's ``a_own``,
    before SPEC_5's union, reads SPEC_1's, which is not computed last, and is run."""
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if "derive_scope" in w] == [
        "<srcdir>/index.rst:10: WARNING: dynamic function 'links_from_filter' for "
        "option 'c_cur' reads 'u' on need 'SPEC_5', which is computed after this call, "
        "among your own functions and the calls whose filter cannot be read, so this "
        "step cannot wait for it: the call is not run and the field is left empty "
        "[needs.derive_scope]",
    ]
    needs = _built(app)["needs"]
    spec = needs["SPEC_5"]
    assert (spec["u"], spec["c_cur"], spec["z_cur"]) == (
        ["REQ_1", "REQ_3"],
        [],
        ["REQ_1"],
    )
    assert (needs["SPEC_1"]["u"], needs["SPEC_1"]["a_own"]) == (["REQ_3"], ["REQ_1"])
