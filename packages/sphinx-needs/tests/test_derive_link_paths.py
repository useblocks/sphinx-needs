"""``copy`` and ``collect`` on a link type: a chain's far ends as links.

``derive = {kind = "copy", field = "id", over = "satisfies"}`` on a link type links each
need ``over`` names, and ``{kind = "collect", field = "chain", over = "implements"}`` the
links ``field`` holds on each of them, so a chain is carried down rung by rung as links,
with back links. Such a link type is a summary. The shared corpus pins the values, the
cycles, the density and the ``needs.derive_invalid`` findings
(``tests/fixtures/derive_conformance.toml``); this module pins what it does not compare:
the rules as read, the messages, that dead links are left to the link type collected,
and the order on a need whose ``over`` a call computes with the link types.
"""

import json
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


def _version(app) -> dict:
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
            {"kind": "copy", "field": "id", "over": "satisfies"},
            DeriveRule(
                kind="copy", field="id", over="satisfies", select="list", on_link=True
            ),
            id="copy-id",
        ),
        pytest.param(
            {"kind": "collect", "field": "chain", "over": "refines", "where": "x"},
            DeriveRule(
                kind="collect",
                field="chain",
                over="refines",
                where="x",
                select="list",
                on_link=True,
            ),
            id="collect",
        ),
        pytest.param(
            {"kind": "copy", "field": "title", "over": "satisfies"},
            DeriveInvalid(
                "copy",
                "kind 'copy' on a link type: the role 'field' names 'title'; a copy on "
                "a link type copies 'id', linking each need 'over' names",
            ),
            id="copy-a-field",
        ),
        pytest.param(
            {"kind": "copy", "field": "id", "over": "satisfies", "select": "unique"},
            DeriveInvalid(
                "copy",
                "kind 'copy' on a link type: the role 'select' is 'unique'; a link "
                'list holds every target, so it is "list"',
            ),
            id="select",
        ),
        pytest.param(
            {"kind": "copy", "field": "id", "join": {"field": "a", "equals": "b"}},
            DeriveInvalid(
                "copy", "kind 'copy' on a link type does not take the role 'join'"
            ),
            id="join",
        ),
        pytest.param(
            {"kind": "collect", "field": "chain"},
            DeriveInvalid(
                "collect", "kind 'collect' on a link type requires the role 'over'"
            ),
            id="no-over",
        ),
        pytest.param(
            {"kind": "sum", "field": "hours", "over": "links"},
            DeriveInvalid(
                "sum",
                "kind 'sum' computes a value, so it is declared on a field "
                "(needs_fields), not on a link type",
            ),
            id="a-value-kind",
        ),
    ],
)
def test_parse_a_path(raw, expected):
    """On a link type ``copy`` takes ``field = "id"`` and ``over``, and ``collect`` a
    ``field`` and ``over``, each ``where`` besides; ``select`` is ``"list"``."""
    assert parse_derive(raw, on_link=True) == expected


def test_a_copy_on_a_field_is_no_path():
    """The same table on a field is the value kind, as before."""
    rule = parse_derive({"kind": "copy", "field": "id", "over": "links"}, on_link=False)
    assert rule == DeriveRule(kind="copy", field="id", over="links")
    assert isinstance(rule, DeriveRule)
    assert not rule.path and not rule.link_valued


CONF_REFUSALS = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"req_ids": {"schema": {"type": "array", "items": {"type": "string"}}}}
needs_links = {
    "satisfies": {},
    "chain": {"derive": {"kind": "copy", "field": "id", "over": "satisfies"}},
    "over_back": {
        "derive": {"kind": "collect", "field": "satisfies", "over": "satisfies_back"}
    },
    "over_derived": {
        "derive": {"kind": "collect", "field": "satisfies", "over": "chain"}
    },
    "value_field": {
        "derive": {"kind": "collect", "field": "req_ids", "over": "satisfies"}
    },
    "field_back": {
        "derive": {"kind": "collect", "field": "satisfies_back", "over": "satisfies"}
    },
    "not_summary": {
        "summary": False,
        "derive_by_type": {
            "spec": {"kind": "copy", "field": "id", "over": "satisfies"}
        },
    },
}
"""

INDEX_REFUSALS = """\
Refusals
========

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_REFUSALS, INDEX_REFUSALS)], indirect=True
)
def test_what_a_path_cannot_read_is_refused_at_load(test_app):
    """A path is computed with the link types: what they cannot wait for is refused
    once, at load, not on every need; ``summary = false`` beside it is ignored."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _invalid_link(
            "field_back",
            "kind 'collect': the role 'field' names the back links 'satisfies_back', "
            "which a link type's rule cannot read: they are built after the link types",
        ),
        "WARNING: Invalid derive of link type 'not_summary': 'summary' cannot "
        "be given beside derive_by_type, and is ignored (a link a copy or collect "
        "computes is a path, not an edge); the rules apply [needs.derive_invalid]",
        _invalid_link(
            "over_back",
            "kind 'collect': the role 'over' names the back links 'satisfies_back', "
            "which a link type's rule cannot read: they are built after the link types",
        ),
        _invalid_link(
            "over_derived",
            "kind 'collect': the role 'over' names 'chain', a link type a rule "
            "computes; a link type's rule walks a link type written in the needs, as "
            "the link types are computed together",
        ),
        _invalid_link(
            "value_field",
            "kind 'collect': the role 'field' names 'req_ids', which is not a link "
            "type; a collect on a link type gathers the links of a link type (a copy "
            "of 'id' links the needs themselves)",
        ),
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    for name in ("chain", "not_summary", "over_back"):
        link = schema.get_link_field(name)
        assert link is not None and link.summary, name
    satisfies = schema.get_link_field("satisfies")
    assert satisfies is not None and not satisfies.summary
    needs = _version(app)["needs"]
    assert needs["SPEC_1"]["not_summary"] == ["REQ_1"]
    assert needs["REQ_1"]["not_summary"] == []


CONF_DEAD = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "satisfies": {},
    "implements": {},
    "seen": {"derive": {"kind": "collect", "field": "satisfies", "over": "implements"}},
}
"""

INDEX_DEAD = """\
Dead links
==========

.. spec:: Specification
   :id: SPEC_1
   :satisfies: DEAD_1

.. impl:: Implementation
   :id: IMPL_1
   :implements: SPEC_1
"""


@pytest.mark.parametrize("test_app", [_project(CONF_DEAD, INDEX_DEAD)], indirect=True)
def test_a_collected_dead_link_is_reported_where_it_is_written(test_app):
    """A dead link a collect carries is the collected link type's: reported once, at
    the need writing it, and it makes no dead link forbidden on the collecting need."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'DEAD_1' in field 'satisfies' [needs.link_outgoing]",
    ]
    needs = _version(app)["needs"]
    assert needs["IMPL_1"]["seen"] == ["DEAD_1"]
    assert needs["IMPL_1"]["has_dead_links"] is True
    assert needs["IMPL_1"]["has_forbidden_dead_links"] is False
    assert needs["SPEC_1"]["has_forbidden_dead_links"] is True


CONF_COMPUTED_OVER = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "satisfies": {},
    "implements": {},
    "chain": {
        "derive_by_type": {
            "spec": {"kind": "copy", "field": "id", "over": "satisfies"},
            "impl": {"kind": "collect", "field": "chain", "over": "implements"},
        }
    },
    "specs": {"derive": {"kind": "copy", "field": "id", "over": "implements"}},
    "seen": {"derive": {"kind": "collect", "field": "satisfies", "over": "implements"}},
}
"""

INDEX_COMPUTED_OVER = """\
Computed over
=============

.. req:: Requirement
   :id: REQ_1

.. spec:: Specification
   :id: SPEC_1
   :satisfies: REQ_1

.. impl:: Implementation
   :id: IMPL_1
   :implements: [[links_from_filter("type == 'spec'")]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_COMPUTED_OVER, INDEX_COMPUTED_OVER)], indirect=True
)
def test_a_path_waits_for_an_over_a_call_computes(test_app):
    """Where a call computes the need's ``over`` with the link types, which needs it
    names is known only once it is computed: the path waits for it, and reads its
    ``field`` on every need computing it, as ``check_linked_values`` reads the fields
    of the ``links`` a call computes. A ``collect`` of its own link type there reads
    itself, and is a cycle; one of another link type, and a ``copy``, are computed."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:11: WARNING: derive rule 'collect' for option 'chain' is on "
        "a cycle: 'chain' on need 'IMPL_1', through its implements, which are computed "
        "in the same step, so every need is a candidate; the field is left empty "
        "[needs.derive_cycle]",
    ]
    needs = _version(app)["needs"]
    assert needs["IMPL_1"]["implements"] == ["SPEC_1"]
    assert needs["IMPL_1"]["specs"] == ["SPEC_1"]
    assert needs["IMPL_1"]["seen"] == ["REQ_1"]
    assert needs["IMPL_1"]["chain"] == []
    assert needs["SPEC_1"]["specs_back"] == ["IMPL_1"]
