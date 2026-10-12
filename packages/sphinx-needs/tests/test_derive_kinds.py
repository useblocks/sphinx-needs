"""Declared derived fields compute their values: one test per kind, then the findings.

A ``derive`` rule on a ``needs_fields`` / ``needs_links`` entry computes the field for
every need from the project's sources, in the step its kind belongs to: ``links`` and
``content_links`` with the link fields, every other kind with the other fields, and
``hash`` (and a rule with ``after = "derived"``) after every other field. The values
pinned here are the ones the build computes, each checked against the contract of the
kinds shared with ubCode (candidates, order, duplicates, unset values, the empty value
over no candidate).
"""

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs.functions import common
from sphinx_needs_testkit import build_warnings

KINDS = {"buildername": "needs", "srcdir": "doc_test/doc_derive_kinds"}


def _needs(app) -> dict[str, dict]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_the_kinds_project_warns_only_what_it_should(test_app):
    """One ``needs.derive_unique`` (two parents set ``owner``), and the two dead links."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:34: WARNING: derive rule 'copy' for option 'c_unique' "
        "found 2 needs setting 'owner' (REQ_A, REQ_B); the lowest id, 'REQ_A', is "
        "copied [needs.derive_unique]",
        "<srcdir>/index.rst:34: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'NOPE_2' in field 'l_mentions' [needs.link_outgoing]",
        "<srcdir>/index.rst:34: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'NOPE_1' in field 'links' [needs.link_outgoing]",
    ]


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_copy(test_app):
    """``copy``: the own field, the need ``from`` names, and over a link type.

    ``SPEC_1``'s ``parent`` names ``REQ_B``, then ``REQ_A``: ``select = "first"`` takes
    the lowest id among the targets that set ``owner`` (``REQ_A``), as does ``unique``
    (which reports the two); ``list`` takes every value in the order written, a list
    field's items flattened and nothing removed.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert spec["c_title"] == "Spec 1"
    assert needs["REQ_C"]["c_title"] == "Größe"
    assert {needs[i]["c_from"] for i in needs} == {"alice"}
    assert spec["c_first"] == "alice"
    assert spec["c_unique"] == "alice"
    assert spec["c_list"] == ["bob", "alice"]
    assert spec["c_labels"] == ["y", "z", "x", "y"]
    # no target: the empty value (nullable string: unset; array: [])
    assert needs["REQ_A"]["c_first"] is None
    assert needs["REQ_A"]["c_list"] == []


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_sum_and_count(test_app):
    """``sum`` reads each link in the order written: ``SPEC_1``'s ``links`` are
    ``REQ_B, REQ_A, REQ_A, REQ_A.p, NOPE_1``, so ``REQ_A`` is read three times (twice by
    id, once through its part) and the dead ``NOPE_1`` is skipped: ``5 + 2 + 2 + 2``.

    A sum of an ``integer`` field is an integer. ``count`` over ``tests_back`` counts
    the tests that pass ``where``, or with ``field`` those that set it.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert spec["s_hours"] == 11.0
    assert isinstance(spec["s_points"], int)
    assert spec["s_points"] == 13
    assert spec["s_open"] == 6.0
    assert spec["n_passed"] == 1
    assert spec["n_hours"] == 1
    # no candidate: 0.0, 0, 0
    assert (needs["REQ_A"]["s_hours"], needs["REQ_A"]["s_points"]) == (0.0, 0)
    assert needs["REQ_A"]["n_passed"] == 0


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_a_result_takes_the_type_of_its_field(test_app):
    """A result is stored, exported and hashed in the type of the field holding it.

    ``points`` is an ``integer`` field: its sum, maximum, copy and items are integers,
    and so is a ``count``, but in a ``number`` field each is a float (``13.0``, and
    ``0.0`` over no candidate), as an authored value of that field is; in an
    ``integer`` field it stays an integer (``s_points``). The hash writes the float.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    spec, req_a, req_c = needs["SPEC_1"], needs["REQ_A"], needs["REQ_C"]
    floats = [
        (spec["t_sum_n"], 13.0),
        (req_a["t_sum_n"], 0.0),
        (spec["t_count_n"], 2.0),
        (req_a["t_count_n"], 0.0),
        (req_a["t_copy_n"], 3.0),
        (spec["t_max_n"], 4.0),
        *zip(spec["t_collect_n"], [4.0, 3.0], strict=True),
    ]
    for value, expected in floats:
        assert type(value) is float and value == expected, (value, expected)
    assert req_c["t_copy_n"] is None
    assert type(spec["s_points"]) is int
    assert spec["t_hash_n"] == _sha256("[13.0,2.0,null]")
    assert req_a["t_hash_n"] == _sha256("[0.0,0.0,3]")


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_any_and_all(test_app):
    """``any`` / ``all`` over the tests of ``SPEC_1``; over none, ``all`` is true and
    ``any`` false."""
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert (spec["a_all"], spec["a_any"], spec["a_field"]) == (False, True, True)
    other = needs["REQ_A"]
    assert (other["a_all"], other["a_any"], other["a_field"]) == (True, False, False)


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_min_max_and_collect(test_app):
    """``min`` / ``max`` of a number, and of an enum in its declared order;
    ``collect`` is a set, in the order of the candidates, a list's items each."""
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert (spec["m_min"], spec["m_max"]) == (2.0, 5.0)
    # REQ_B is A, REQ_A is B: B is the greater, in the enum's order QM, A, B, C, D
    assert spec["m_asil"] == "B"
    assert spec["k_owners"] == ["bob", "alice"]
    assert spec["k_labels"] == ["y", "z", "x"]
    # no candidate: unset, and []
    assert (needs["REQ_A"]["m_min"], needs["REQ_A"]["k_owners"]) == (None, [])


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_max_transitive(test_app):
    """``max`` closed over ``satisfies``: ``TRANS_2`` and ``TRANS_3`` satisfy each other.

    ``TRANS_1`` (QM) satisfies ``TRANS_2`` (A), which satisfies ``TRANS_3`` (C) and back;
    ``TRANS_4`` (D) satisfies ``TRANS_1``. Each member of the cycle reaches the other
    and itself, so both are C even without ``include_self``; ``TRANS_4`` is D with
    ``include_self`` and C without. A need that satisfies nothing is its own level with
    ``include_self``, and unset without.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    with_self = {
        i: needs[i]["t_asil"] for i in ("TRANS_1", "TRANS_2", "TRANS_3", "TRANS_4")
    }
    without = {
        i: needs[i]["t_asil_out"] for i in ("TRANS_1", "TRANS_2", "TRANS_3", "TRANS_4")
    }
    assert with_self == {"TRANS_1": "C", "TRANS_2": "C", "TRANS_3": "C", "TRANS_4": "D"}
    assert without == {"TRANS_1": "C", "TRANS_2": "C", "TRANS_3": "C", "TRANS_4": "C"}
    assert (needs["REQ_A"]["t_asil"], needs["REQ_A"]["t_asil_out"]) == ("B", None)


#: the JSON text each pinned hash is the SHA-256 of, written out by hand
HASHED = {
    ("SPEC_1", "h_digest"): '["Spec 1",null,11.0,["NOPE_1","REQ_A","REQ_A.p","REQ_B"]]',
    ("REQ_C", "h_digest"): '["Größe","open",0.0,[]]',
    ("REQ_A", "h_numbers"): "[3,0.5]",
    ("REQ_B", "h_numbers"): "[4,1e+16]",
    ("REQ_A", "h_list"): '[["x","y"],"alice"]',
    ("REQ_C", "h_list"): '[null,"carol"]',
}


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_hash(test_app):
    """``hash``: the SHA-256 of one compact JSON array of the listed fields.

    Each value as ``needs.json`` holds it (``SPEC_1``'s ``links`` sorted and without
    duplicates, an unset field ``null``, the derived ``s_hours`` computed before),
    with no whitespace, ``Größe`` not escaped, a float as Python writes it (``0.5``,
    ``1e+16``). A copy with ``after = "derived"`` reads the hash after it is computed.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    for (need_id, field), text in HASHED.items():
        assert needs[need_id][field] == _sha256(text), (need_id, field, text)
    # the hex, pinned for ubCode to compute byte for byte
    assert needs["SPEC_1"]["h_digest"] == (
        "ec9eb469e9b4f36b7912cc510376dd5a13fd3269b1976eb0b583bb3764fdc180"
    )
    assert needs["REQ_B"]["h_numbers"] == (
        "fe64a22116ee2e8b583fd00ad07e35e5977f3a4e21402f09417fa312a3b3d498"
    )
    assert needs["REQ_C"]["h_list"] == (
        "20a10551bd6fe84d2d780847e01f7f48df36ab6bb60d60a1c02b2762e2cfd121"
    )
    for need_id, need in needs.items():
        assert need["l_digest"] == need["h_digest"], need_id


CONDITIONAL_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_links = {"covers": {}}
needs_fields = {
    "digest": {"schema": {"type": "string"}, "derive": {"kind": "hash", "fields": ["covers"]}},
}
"""

CONDITIONAL_INDEX = """\
Conditional links
=================

.. req:: Two
   :id: R_2
   :status: open

.. req:: Ten
   :id: R_10
   :status: open

.. spec:: With and without a condition
   :id: S_1
   :covers: R_2[status == 'open'], R_2

.. spec:: Two conditions
   :id: S_2
   :covers: R_2[status == 'open'], R_2[status != 'closed']

.. spec:: And another target
   :id: S_3
   :covers: R_10, R_2[status == 'open'], R_2
"""

#: the JSON text each pinned hash is the SHA-256 of, and the hex, written out by hand
HASHED_CONDITIONAL = {
    "S_1": (
        '[["R_2"]]',
        "5d82d655c789b1715e46e424e599e1f5110ecaf22c082e32bae73cb7cd97369d",
    ),
    "S_2": (
        '[["R_2"]]',
        "5d82d655c789b1715e46e424e599e1f5110ecaf22c082e32bae73cb7cd97369d",
    ),
    "S_3": (
        '[["R_2","R_10"]]',
        "c59e839489078b248d34520275684e04a3454b44fd2d36c815ed174dd1e415f0",
    ),
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONDITIONAL_CONF),
                (Path("index.rst"), CONDITIONAL_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_hash_drops_link_conditions_then_duplicates(test_app):
    """``hash`` writes a link list as its targets' ids: the conditions dropped, then
    each id once, sorted as ``needs.json`` sorts (``R_2`` before ``R_10``).

    So a target named with and without a condition (``S_1``), or under two conditions
    (``S_2``), is hashed once, although ``needs.json`` keeps each condition's text.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    for need_id, (text, hexdigest) in HASHED_CONDITIONAL.items():
        values = json.loads(text)
        assert json.dumps(values, separators=(",", ":"), ensure_ascii=False) == text
        assert _sha256(text) == hexdigest, need_id
        assert needs[need_id]["digest"] == hexdigest, (need_id, text)
    assert sorted(needs["S_1"]["covers"]) == ["R_2", "R_2[status == 'open']"]


CONDITIONS_INDEX = """\
Conditions
==========

.. req:: Two
   :id: R_2
   :status: open

.. spec:: One target under three conditions
   :id: S_1
   :covers: R_2[status == 'open'], R_2, R_2[status == 'closed']
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONDITIONAL_CONF),
                (Path("index.rst"), CONDITIONS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_one_target_under_several_conditions_exports_in_one_order(test_app):
    """``needs.json`` keeps each link's condition, so three links to ``R_2`` share one id
    and one natural key: the link with its condition, compared as a string, orders them
    (``R_2``, then ``[status == 'closed']``, then ``[status == 'open']``), in every
    build. The hash drops the conditions and writes ``R_2`` once."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Need 'S_1' link 'R_2' in field 'covers': "
        "condition \"status == 'closed'\" not satisfied by target need 'R_2' "
        "[needs.link_condition_failed]",
    ]
    need = _needs(app)["S_1"]
    assert need["covers"] == [
        "R_2",
        "R_2[status == 'closed']",
        "R_2[status == 'open']",
    ]
    assert (
        need["digest"]
        == _sha256('[["R_2"]]')
        == ("5d82d655c789b1715e46e424e599e1f5110ecaf22c082e32bae73cb7cd97369d")
    )


TIE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_links = {"covers": {}}
needs_fields = {
    "digest": {"schema": {"type": "string"}, "derive": {"kind": "hash", "fields": ["covers"]}},
}
"""

TIE_INDEX = """\
Ties
====

.. req:: Two
   :id: R_2

.. req:: Two, in lower case
   :id: r_2

.. req:: Two, with a leading zero
   :id: R_02

.. spec:: Covers all three
   :id: S_1
   :covers: r_2, R_2, R_02
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), TIE_CONF), (Path("index.rst"), TIE_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_sorted_link_list_breaks_ties_by_the_id(test_app):
    """``R_02``, ``R_2`` and ``r_2`` have one natural key (digits as a number, letters
    case-folded), so the natural order alone leaves them tied, and the build's set order
    picked among them. The tie is broken by the id, compared as a string: ``R_02`` before
    ``R_2`` before ``r_2``, in ``needs.json`` and in a ``hash``, in every build.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    need = _needs(app)["S_1"]
    assert need["covers"] == ["R_02", "R_2", "r_2"]
    text = '[["R_02","R_2","r_2"]]'
    assert (
        json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False) == text
    )
    assert _sha256(text) == (
        "8e8a04b379e6aaf000b15b26eacb95b9707feb96b35ae16ed01bfe36cff2e1cf"
    )
    assert need["digest"] == (
        "8e8a04b379e6aaf000b15b26eacb95b9707feb96b35ae16ed01bfe36cff2e1cf"
    )


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_links_and_content_links(test_app):
    """``links``: every need passing ``where``, the need itself (and its parts) left out
    unless ``include_self``, parts tested only with ``include_parts``.
    ``content_links``: the ``:need:`` references of the content, a part reference kept as
    a part link, a dead one kept, the need itself kept; under ``where`` only the
    referenced needs that pass (a part through its need). ``from`` reads another need's
    content. (Link lists are written sorted.)
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["SPEC_1"]["l_open"] == ["REQ_A", "REQ_C"]
    assert needs["REQ_A"]["l_open"] == ["REQ_C"]
    assert needs["SPEC_1"]["l_specs"] == ["SPEC_1"]
    assert needs["REQ_A"]["l_specs"] == ["SPEC_1"]
    assert needs["SPEC_1"]["l_parts"] == ["REQ_A.p"]
    assert needs["REQ_A"]["l_parts"] == []
    assert needs["SPEC_1"]["l_mentions"] == ["NOPE_2", "REQ_A.p", "REQ_B", "SPEC_1"]
    assert needs["SPEC_1"]["l_mentioned_reqs"] == ["REQ_A.p", "REQ_B"]
    assert needs["REQ_A"]["l_mentions"] == ["REQ_B"]
    assert needs["REQ_B"]["l_mentions"] == []
    assert {i: needs[i]["l_from"] for i in ("REQ_A", "SPEC_1")} == {
        "REQ_A": ["REQ_B"],
        "SPEC_1": ["REQ_B"],
    }
    # the derived links are back links like any other
    assert "SPEC_1" in needs["REQ_C"]["l_open_back"]
    assert "REQ_C" not in needs["REQ_C"]["l_open_back"]


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_a_links_rule_tests_each_candidate_once(test_app, monkeypatch):
    """A ``links`` rule's ``where`` is tested once on each candidate per build, not once
    per need holding the rule: it reads the candidate only, so every need gets the
    same candidates, less itself (and its parts) unless ``include_self``.

    The project has 10 needs and one part: ``l_open`` tests the 10 needs once each,
    and ``l_parts`` (``include_parts``) the 10 needs and the part, where testing per
    reader made it 10 times as many.
    """
    calls: Counter[str | None] = Counter()
    passes = common._passes

    def counting(candidate, predicate, config, reads):
        calls[predicate] += 1
        return passes(candidate, predicate, config, reads)

    monkeypatch.setattr(common, "_passes", counting)
    app = test_app
    app.build()
    needs = _needs(app)
    assert len(needs) == 10
    assert calls["type == 'req' and status == 'open'"] == 10
    assert calls["is_part and id_parent == 'REQ_A'"] == 11
    assert needs["SPEC_1"]["l_open"] == ["REQ_A", "REQ_C"]


SURVEY_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_external_needs = [{"base_url": "http://example.org/", "json_path": "external.json"}]
needs_links = {
    "tests": {},
    "parent": {},
    "own_parts": {
        "derive": {
            "kind": "links",
            "where": "is_part and id_parent == 'REQ_1'",
            "include_parts": True,
        }
    },
}
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "who": {"schema": {"type": "string"}},
    "level": {"schema": {"type": "string", "enum": ["low", "mid", "high"]}},
    "total": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
    "parts_in_order": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "copy", "field": "own_parts"},
    },
    "open_max": {
        "schema": {"type": "string", "enum": ["low", "mid", "high"]},
        "derive": {
            "kind": "max",
            "field": "level",
            "over": "parent",
            "transitive": True,
            "where": "status == 'open'",
        },
    },
    "testers": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "collect", "field": "who", "over": "tests_back"},
    },
    "ext_total": {"schema": {"type": "number"}},
}
"""

SURVEY_INDEX = """\
Survey
======

.. req:: Parts holder
   :id: REQ_1
   :hours: 1
   :ext_total: [[copy("total", "EXT_1")]]

   :np:`(c) part c`, :np:`(a) part a` and :np:`(b) part b`.

.. req:: Closed, high
   :id: P_1
   :status: closed
   :level: high

.. req:: Open, mid
   :id: P_2
   :status: open
   :level: mid
   :parent: P_1

.. spec:: Child
   :id: C_1
   :parent: P_2, P_1

.. test:: Nine
   :id: T_9
   :who: nine
   :tests: C_1

.. test:: Two
   :id: T_2
   :who: two
   :tests: C_1

.. test:: Ten
   :id: T_10
   :who: ten
   :tests: C_1

.. needextend:: total == 99
   :who: nobody
"""

SURVEY_EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "EXT_1": {
                    "id": "EXT_1",
                    "type": "req",
                    "title": "External",
                    "links": ["REQ_1"],
                    "total": 42.0,
                }
            }
        }
    },
}

SURVEY = {
    "buildername": "needs",
    "files": [
        (Path("conf.py"), SURVEY_CONF),
        (Path("index.rst"), SURVEY_INDEX),
        (Path("external.json"), json.dumps(SURVEY_EXTERNAL)),
    ],
}


@pytest.mark.parametrize("test_app", [SURVEY], indirect=True)
def test_a_needextend_filter_naming_a_derived_field_is_reported(test_app):
    """A ``needextend`` filter naming a derived field sees the value from before it is
    computed (the field's empty value): ``needs.derive_scope``, once, naming the field
    and every need of the project's sources, as for a field a ``[[…]]`` computes."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:41: WARNING: needextend filter 'total == 99' names 'total', "
        "which a dynamic function or variant computes on 7 needs (C_1, P_1, P_2 and 4 "
        "more): the filter sees the value from before it is computed "
        "[needs.derive_scope]",
    ]


@pytest.mark.parametrize("test_app", [SURVEY], indirect=True)
def test_links_lists_parts_in_part_id_order(test_app):
    """``links`` with ``include_parts`` lists a need's parts in part-id order: ``REQ_1``
    writes ``(c)``, ``(a)``, ``(b)``, so part-id order is neither the order written nor
    its reverse. ``needs.json`` sorts every link list, so the order is read through a
    ``copy`` of the link type into an array field."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["C_1"]["parts_in_order"] == ["REQ_1.a", "REQ_1.b", "REQ_1.c"]
    # REQ_1's own parts are left out of its own list
    assert needs["REQ_1"]["parts_in_order"] == []


@pytest.mark.parametrize("test_app", [SURVEY], indirect=True)
def test_a_transitive_max_reads_only_the_needs_passing_where(test_app):
    """``max`` with ``transitive`` and ``where``: ``C_1`` reaches ``P_2`` (open, mid)
    and ``P_1`` (closed, high), and only ``P_2`` passes ``status == 'open'``, so ``mid``.
    ``P_2`` reaches only the closed ``P_1``: no value."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["C_1"]["open_max"] == "mid"
    assert needs["P_2"]["open_max"] is None


@pytest.mark.parametrize("test_app", [SURVEY], indirect=True)
def test_no_rule_runs_on_an_external_need(test_app):
    """An external need keeps the value it carries (``total`` 42.0), where the rule
    would give 1.0 (``REQ_1``'s ``hours``): a ``copy`` of it reads 42.0. (``needs.json``
    does not write an external need.)"""
    app = test_app
    app.build()
    assert _needs(app)["REQ_1"]["ext_total"] == 42.0


@pytest.mark.parametrize("test_app", [SURVEY], indirect=True)
def test_back_link_candidates_in_need_id_order(test_app):
    """``over = "<t>_back"`` reads the needs linking to this one in need-id order, the
    ids compared as strings: ``T_10``, ``T_2``, ``T_9``, although the document writes
    ``T_9``, ``T_2``, ``T_10`` (and ``needs.json`` writes ``T_2``, ``T_9``, ``T_10``)."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["C_1"]["testers"] == ["ten", "two", "nine"]
    assert needs["C_1"]["tests_back"] == ["T_2", "T_9", "T_10"]


HIDDEN_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_links = {
    "mentions": {"derive": {"kind": "content_links"}},
    "inline": {},
}
"""

HIDDEN_INDEX = """\
Hidden
======

.. req:: One
   :id: R_1

.. req:: Hidden
   :id: H_1
   :hide:

   Mentions :need:`R_1`.

.. spec:: Reads the hidden one
   :id: S_1
   :inline: [[links_from_content("H_1")]]

   Mentions :need:`R_1`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), HIDDEN_CONF),
                (Path("index.rst"), HIDDEN_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_content_links_of_a_hidden_need_is_deferred(test_app):
    """A ``:hide:`` need keeps no content node, so its ``content_links`` rule and a
    ``links_from_content`` naming it give no links and the warning the call has always
    given for it ("no stored node", at the hidden need). How a hidden need's content is
    processed is left to a follow-up of its own; this pins the behaviour until then.
    """
    app = test_app
    app.build()
    no_node = (
        "<srcdir>/index.rst:7: WARNING: links_from_content: no stored node for need "
        "'H_1' [needs.dynamic_function]"
    )
    assert build_warnings(app) == [no_node, no_node]
    needs = _needs(app)
    assert needs["H_1"]["mentions"] == []
    assert needs["S_1"]["inline"] == []
    assert needs["S_1"]["mentions"] == ["R_1"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_id_regex = "^.+$"\n',
                ),
                (
                    Path("index.rst"),
                    "Hidden\n======\n\n.. req:: One\n   :id: R_1\n\n"
                    ".. req:: Hidden\n   :id: H_1\n   :hide:\n\n"
                    "   Mentions :need:`R_1` and has a footnote [#]_.\n\n"
                    "   .. [#] The hidden footnote.\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_hidden_need_without_a_rule_is_untouched(test_app):
    """A hidden need in a project declaring no rule, and calling no function, gives no
    warning: nothing of the derived fields reads a hidden need's content."""
    app = test_app
    app.build()
    assert build_warnings(app) == []


INLINE_TYPE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True


def five(app, need, needs):
    return 5


needs_functions = [five]
needs_variant_data = {"n": 3}
needs_fields = {
    "n_int": {"schema": {"type": "integer"}},
    "ints": {"schema": {"type": "array", "items": {"type": "integer"}}},
    "n_num": {"schema": {"type": "number"}},
    "from_fn": {"schema": {"type": "number"}},
    "nums": {"schema": {"type": "array", "items": {"type": "number"}}},
    "still_int": {"schema": {"type": "integer"}},
    "from_var": {"schema": {"type": "number"}, "parse_variants": True},
    "from_variant": {"schema": {"type": "number"}, "parse_variants": True},
    "digest": {
        "schema": {"type": "string"},
        "derive": {"kind": "hash", "fields": ["n_num", "from_fn", "nums"]},
    },
}
"""

INLINE_TYPE_INDEX = """\
Inline result types
===================

.. req:: Integers
   :id: REQ_1
   :n_int: 3
   :ints: 1, 2
   :n_num: [[copy("n_int")]]
   :from_fn: [[five()]]
   :nums: [[copy("ints")]]
   :still_int: [[copy("n_int")]]
   :from_var: <{ var.n }>
   :from_variant: <<type == 'req':3, 2>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), INLINE_TYPE_CONF),
                (Path("index.rst"), INLINE_TYPE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_an_inline_result_takes_the_type_of_its_field(test_app):
    """An integer a ``[[…]]`` returns (a built-in's or your own), or a variant gives
    (``<{ var.n }>`` from the variant data, a ``<<…>>``'s value), is stored in a
    ``number`` field as a float, as an authored value of the field is, and so exported
    and hashed as one; an ``integer`` field keeps it an integer."""
    app = test_app
    app.build()
    # Sphinx's own ``config.cache`` note for a function in conf.py aside
    assert [w for w in build_warnings(app) if "[needs." in w] == []
    need = _needs(app)["REQ_1"]
    for value, expected in [
        (need["n_num"], 3.0),
        (need["from_fn"], 5.0),
        (need["from_var"], 3.0),
        (need["from_variant"], 3.0),
        *zip(need["nums"], [1.0, 2.0], strict=True),
    ]:
        assert type(value) is float and value == expected, (value, expected)
    assert type(need["still_int"]) is int and need["still_int"] == 3
    assert need["digest"] == _sha256("[3.0,5.0,[1.0,2.0]]")


SET_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "owner": {"schema": {"type": "string"}, "nullable": False, "default": ""},
    "who": {"schema": {"type": "string"}},
    "labels": {"schema": {"type": "array", "items": {"type": "string"}}},
    "n_owner": {
        "schema": {"type": "integer"},
        "derive": {"kind": "count", "over": "parent", "field": "owner"},
    },
    "n_tests": {
        "schema": {"type": "integer"},
        "derive": {"kind": "count", "over": "parent", "field": "tests"},
    },
    "first_owner": {
        "schema": {"type": "string"},
        "nullable": False,
        "derive": {"kind": "copy", "field": "owner", "over": "parent"},
    },
    "unique_owner": {
        "schema": {"type": "string"},
        "nullable": False,
        "derive": {"kind": "copy", "field": "owner", "over": "parent", "select": "unique"},
    },
    "unique_who": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "who", "over": "parent", "select": "unique"},
    },
    "owners": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "collect", "field": "owner", "over": "parent"},
    },
    "all_labels": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "collect", "field": "labels", "over": "parent"},
    },
}
needs_links = {"parent": {}, "tests": {}}
"""

SET_INDEX = """\
Set
===

.. req:: Owner left at its default, ""
   :id: P_1

.. req:: Owned by bob
   :id: P_2
   :owner: bob
   :who: zed
   :labels: x, y

.. req:: Owned by bob too
   :id: P_3
   :owner: bob
   :labels: y

.. spec:: Three parents
   :id: C_1
   :parent: P_2, P_1, P_3

.. spec:: One parent, twice
   :id: C_2
   :parent: P_2, P_2

.. spec:: A parent setting who, one not
   :id: C_3
   :parent: P_2, P_1

.. spec:: Two parents, both owned by bob
   :id: C_4
   :parent: P_3, P_2
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), SET_CONF),
                (Path("index.rst"), SET_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_set_means_not_null(test_app):
    """A candidate sets a field when its value is not null: an empty value (``""``, an
    empty list, a link type with no links) is set.

    So ``count`` with a ``field`` counts ``P_1``, whose ``owner`` is ``""``, and every
    parent's empty ``tests``; ``copy`` takes the lowest id among the setters, ``P_1``'s
    ``""``; ``unique`` warns when more than one distinct target need sets the field,
    equal values included (``C_4``, whose two parents both hold ``bob``; and ``C_1``
    and ``C_3``, whose ``P_1`` sets ``""``), not for one need linked twice (``C_2``) or
    a setter beside a need leaving the field unset (``C_3``'s ``who``); ``collect``
    keeps ``""`` and each item of a list.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:18: WARNING: derive rule 'copy' for option 'unique_owner' "
        "found 3 needs setting 'owner' (P_1, P_2, P_3); the lowest id, 'P_1', is "
        "copied [needs.derive_unique]",
        # P_1's "" is set: C_3's two parents both set owner
        "<srcdir>/index.rst:26: WARNING: derive rule 'copy' for option 'unique_owner' "
        "found 2 needs setting 'owner' (P_1, P_2); the lowest id, 'P_1', is copied "
        "[needs.derive_unique]",
        # two distinct needs holding the same value are two
        "<srcdir>/index.rst:30: WARNING: derive rule 'copy' for option 'unique_owner' "
        "found 2 needs setting 'owner' (P_2, P_3); the lowest id, 'P_2', is copied "
        "[needs.derive_unique]",
    ]
    needs = _needs(app)
    c_1, c_2, c_3 = needs["C_1"], needs["C_2"], needs["C_3"]
    assert (c_1["n_owner"], c_1["n_tests"]) == (3, 3)
    assert (c_1["first_owner"], c_1["unique_owner"]) == ("", "")
    assert c_1["owners"] == ["bob", ""]
    assert c_1["all_labels"] == ["x", "y"]
    assert c_2["unique_owner"] == "bob"
    assert c_3["unique_who"] == "zed"
    assert needs["C_4"]["unique_owner"] == "bob"


NO_VALUE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "owner": {"schema": {"type": "string"}},
    "labels": {"schema": {"type": "array", "items": {"type": "string"}}},
    "hours": {"schema": {"type": "number"}},
    "c_list": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "copy", "field": "owner", "over": "parent", "select": "list"},
    },
    "c_labels": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "copy", "field": "labels", "over": "parent", "select": "list"},
    },
    "k_owners": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "derive": {"kind": "collect", "field": "owner", "over": "parent"},
    },
    "c_first": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "over": "parent"},
    },
    "c_unique": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "over": "parent", "select": "unique"},
    },
    "m_max": {
        "schema": {"type": "number"},
        "derive": {"kind": "max", "field": "hours", "over": "parent"},
    },
}
needs_links = {"parent": {}}
"""

NO_VALUE_INDEX = """\
No value
========

.. req:: Sets nothing
   :id: P_1

.. req:: Sets nothing either
   :id: P_2

.. spec:: No parent
   :id: C_0

.. spec:: Parents, none setting a value
   :id: C_1
   :parent: P_2, P_1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), NO_VALUE_CONF),
                (Path("index.rst"), NO_VALUE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_list_copy_of_no_value_is_an_empty_list(test_app):
    """A ``copy`` with ``select = "list"`` is a list: over no candidate (``C_0``), and
    over candidates none of which sets the field (``C_1``), it is ``[]``, as ``collect``
    is, in a nullable field too. ``copy`` with ``select = "first"`` or ``"unique"``, and
    ``max``, find no value there, and leave the field at its empty value, ``None``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    for need_id in ("C_0", "C_1"):
        need = needs[need_id]
        assert (need["c_list"], need["c_labels"], need["k_owners"]) == ([], [], [])
        assert (need["c_first"], need["c_unique"], need["m_max"]) == (None, None, None)


NEGATIVE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "owner": {"schema": {"type": "string"}},
    "summary": {"schema": {"type": "string"}},
    "reads_total": {"schema": {"type": "number"}},
    "cyc": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "cyc", "over": "links"},
    },
    "digest": {"schema": {"type": "string"}, "derive": {"kind": "hash", "fields": ["title"]}},
    "from_missing": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "from": "NOPE_9"},
    },
    "raising": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links", "where": "hours > 1"},
    },
    "total": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
}
needs_links = {
    "big": {"derive": {"kind": "links", "where": "total is not None and total > 1"}},
}
"""

NEGATIVE_INDEX = """\
Negative
========

.. req:: A
   :id: A
   :links: B
   :hours: 2
   :summary: [[copy("digest")]]
   :reads_total: [[copy("total")]]

.. req:: B
   :id: B
   :links: A
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), NEGATIVE_CONF),
                (Path("index.rst"), NEGATIVE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_what_a_rule_cannot_compute(test_app):
    """The findings of a rule at run time, each leaving its field empty.

    - ``cyc`` copies ``cyc`` over ``links``, and ``A`` and ``B`` link each other: a cycle
      of the two needs (``needs.derive_cycle``).
    - ``big`` (a link type, computed with the link fields) filters on ``total``, which
      is computed after them: not run (``needs.derive_scope``).
    - ``summary`` copies the ``hash`` ``digest``, computed in the late step: not run
      (``needs.derive_scope``).
    - ``from`` names no need: ``needs.dynamic_function``.
    - ``where`` cannot be evaluated on ``B`` (no ``hours``): ``B`` does not pass, and
      ``A``'s sum is of no candidate, without a finding.
    A copy of a derived value of the same step waits for it (``reads_total``).
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: derive rule 'links' for option 'big' reads "
        "'total' on 2 needs (A, B), which are final only after the link fields are "
        "computed: the rule is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:11: WARNING: derive rule 'links' for option 'big' reads "
        "'total' on 2 needs (A, B), which are final only after the link fields are "
        "computed: the rule is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:4: WARNING: derive rule 'copy' for option 'cyc' is on a "
        "cycle: 'cyc' on 2 needs (A, B); the field is left empty [needs.derive_cycle]",
        "<srcdir>/index.rst:11: WARNING: derive rule 'copy' for option 'cyc' is on a "
        "cycle: 'cyc' on 2 needs (A, B); the field is left empty [needs.derive_cycle]",
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
        "'from_missing', of need 'A': 'from' names no need: 'NOPE_9' "
        "[needs.dynamic_function]",
        "<srcdir>/index.rst:4: WARNING: dynamic function 'copy' for option 'summary' "
        "reads 'digest' on need 'A', which is computed in the late step, after every "
        "other field (a derive rule of the kind 'hash' or with after = \"derived\"): "
        "the call is not run and the field is left empty [needs.derive_scope]",
        "<srcdir>/index.rst:11: WARNING: Error while resolving dynamic values for field "
        "'from_missing', of need 'B': 'from' names no need: 'NOPE_9' "
        "[needs.dynamic_function]",
    ]
    needs = _needs(app)
    a, b = needs["A"], needs["B"]
    assert (a["cyc"], b["cyc"], a["big"], b["big"]) == (None, None, [], [])
    assert (a["from_missing"], a["raising"], b["raising"]) == (None, 0.0, 2.0)
    assert (a["total"], b["total"], a["reads_total"]) == (0.0, 2.0, 0.0)
    assert a["summary"] is None
    assert a["digest"] == _sha256('["A"]')


UNEVALUABLE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "n_big": {
        "schema": {"type": "integer"},
        "nullable": False,
        "derive": {"kind": "count", "over": "links", "where": "hours > 1"},
    },
    "all_big": {
        "schema": {"type": "boolean"},
        "nullable": False,
        "derive": {"kind": "all", "over": "links", "test": "hours > 1"},
    },
    "any_big": {
        "schema": {"type": "boolean"},
        "nullable": False,
        "derive": {"kind": "any", "over": "links", "test": "hours > 1"},
    },
}
needs_links = {
    "big": {"derive": {"kind": "links", "where": "hours > 1"}},
    "mentioned_big": {"derive": {"kind": "content_links", "where": "hours > 1"}},
    "inline_big": {},
}
"""

UNEVALUABLE_INDEX = """\
Unevaluable
===========

.. req:: Two hours
   :id: R_2
   :hours: 2

.. req:: No hours
   :id: R_0

.. req:: Half an hour
   :id: R_H
   :hours: 0.5

.. spec:: Reads them
   :id: S_1
   :links: R_2, R_0, R_H
   :inline_big: [[links_from_filter("hours > 1")]]

   Mentions :need:`R_2`, :need:`R_0` and :need:`R_H`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), UNEVALUABLE_CONF),
                (Path("index.rst"), UNEVALUABLE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_predicate_that_cannot_be_evaluated_is_false(test_app):
    """A ``where`` or ``test`` that cannot be evaluated on a candidate is false for it.

    ``hours > 1`` cannot be evaluated on a need without ``hours`` (``R_0``, and
    ``S_1``): that candidate does not pass, silently, and the rule computes with the
    others, in every kind, as in ``links_from_filter``, which so gives what the
    ``links`` kind gives.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    s_1, r_0 = needs["S_1"], needs["R_0"]
    assert (s_1["n_big"], s_1["all_big"], s_1["any_big"]) == (1, False, True)
    assert (r_0["n_big"], r_0["all_big"], r_0["any_big"]) == (0, True, False)
    for need_id, need in needs.items():
        assert need["big"] == ([] if need_id == "R_2" else ["R_2"]), need_id
    assert s_1["mentioned_big"] == ["R_2"]
    assert s_1["inline_big"] == s_1["big"] == ["R_2"]


# -- a chain of rules across documents, in two layouts, serial and -j 2 ---------------

CHAIN_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "sub": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
    "subsub": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "sub", "over": "links"},
    },
    "top": {
        "schema": {"type": "number"},
        "derive": {"kind": "copy", "field": "subsub", "over": "parent", "select": "first"},
    },
}
needs_links = {"parent": {}}
"""

PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


def _chain(order: list[str]) -> list[tuple[Path, str]]:
    pages = {
        "x": ".. req:: X\n   :id: CH_X\n   :links: CH_Y\n",
        "y": ".. req:: Y\n   :id: CH_Y\n   :links: CH_Z\n",
        "z": ".. req:: Z\n   :id: CH_Z\n   :hours: 0.1\n",
        "w": ".. req:: W\n   :id: CH_W\n   :parent: CH_X\n",
    }
    toctree = "Index\n=====\n\n.. toctree::\n\n" + "".join(f"   {p}\n" for p in order)
    return [
        (Path("conf.py"), CHAIN_CONF),
        (Path("index.rst"), toctree),
        *((Path(f"{p}.rst"), f"{p}\n=\n\n{pages[p]}") for p in order),
    ]


def _layouts(**layouts: list[tuple[Path, str]]) -> list:
    params = []
    for name, files in layouts.items():
        params.append(
            pytest.param({"buildername": "needs", "files": files}, id=f"{name}-serial")
        )
        params.append(
            pytest.param(
                {"buildername": "needs", "files": [*files, *PADDING], "parallel": 2},
                id=f"{name}-j2",
                marks=pytest.mark.skipif(
                    not parallel_available, reason="Parallel execution not supported"
                ),
            )
        )
    return params


@pytest.mark.parametrize(
    "test_app",
    _layouts(
        readers_first=_chain(["w", "x", "y", "z"]),
        sources_first=_chain(["z", "y", "x", "w"]),
    ),
    indirect=True,
)
def test_a_chain_of_rules_in_every_layout(test_app):
    """``CH_W`` copies ``CH_X``'s ``subsub``, the sum of ``CH_Y``'s ``sub``, the sum of
    ``CH_Z``'s ``hours``: computed in dependency order whatever the document order and
    ``-j``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert needs["CH_Y"]["sub"] == 0.1
    assert needs["CH_X"]["subsub"] == 0.1
    assert needs["CH_W"]["top"] == 0.1


# -- a configuration change reaches the needs of unchanged documents ------------------

RECONF_CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

RECONF_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.owner]
schema = { type = "string" }

[needs.fields.total]
schema = { type = "number" }
"""

RECONF_ADDED = """
[needs.fields.total.derive]
kind = "sum"
field = "hours"
over = "links"
"""

RECONF_INDEX = """\
Reconfigured
============

.. req:: Hours
   :id: REQ_001
   :hours: 3

.. req:: Total
   :id: REQ_002
   :links: REQ_001
   :total: 5
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), RECONF_CONF),
                (Path("ubproject.toml"), RECONF_TOML),
                (Path("index.rst"), RECONF_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_changed_field_configuration_rereads_every_document(test_app, make_app):
    """A ``derive`` rule, or a ``default``, added between two builds applies at once.

    The field configuration is read by every need as it is created, so a change to it
    re-reads every document: before, the second build kept the needs of the unchanged
    document as the first build created them (``total`` 5, no default ``owner``).
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["REQ_002"]["total"] == 5.0

    toml = Path(app.srcdir, "ubproject.toml")
    text = toml.read_text(encoding="utf-8").replace(
        '[needs.fields.owner]\nschema = { type = "string" }\n',
        '[needs.fields.owner]\nschema = { type = "string" }\ndefault = "alice"\n',
    )
    toml.write_text(text + RECONF_ADDED, encoding="utf-8")
    # newer than the first build, whatever the file system's clock resolution
    later = time.time_ns() + 60_000_000_000
    os.utime(toml, ns=(later, later))

    second = make_app(buildername="needs", srcdir=app.srcdir)
    second.build()
    # a second application in one process re-registers Sphinx's own nodes, with
    # warnings of its own; the needs' warnings are these
    assert [w for w in build_warnings(second) if "[needs." in w] == [
        "<srcdir>/index.rst:8: WARNING: Field 'total' is derived (kind 'sum') and "
        "cannot be set in a need; the value '5' is ignored [needs.derive_authored]",
    ]
    needs = _needs(second)
    assert needs["REQ_002"]["total"] == 3.0
    assert needs["REQ_001"]["owner"] == "alice"


PER_BUILD_CONF = """\
from sphinx_needs.api import add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "hrs": {"schema": {"type": "number"}},
    "pts": {"schema": {"type": "number"}},
}
#: not a confval: editing it re-reads no document
SUMMED = "hrs"


def setup(app):
    add_field(
        "tot",
        "The total of the linked needs",
        schema={"type": "number"},
        derive={"kind": "sum", "field": SUMMED, "over": "links"},
    )
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), PER_BUILD_CONF),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. toctree::\n\n   other\n\n"
                    ".. req:: A\n   :id: A_001\n   :hrs: 2\n   :pts: 3\n",
                ),
                (
                    Path("other.rst"),
                    "Other\n=====\n\n.. req:: B\n   :id: B_001\n   :links: A_001\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_rule_is_read_from_the_schema_of_each_build(test_app, make_app):
    """A rule's value is computed from the rule of the build, on every build, never
    from the rule the need was created under.

    An extension's ``add_field`` changes the rule without a confval changing, so the
    second build re-reads no document ("0 added, 0 changed"), and ``B_001``'s ``tot``
    still follows the rule: the sum of ``pts`` (3.0), no longer of ``hrs`` (2.0).
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["B_001"]["tot"] == 2.0

    conf = Path(app.srcdir, "conf.py")
    conf.write_text(
        PER_BUILD_CONF.replace('SUMMED = "hrs"', 'SUMMED = "pts"'), encoding="utf-8"
    )
    later = time.time_ns() + 60_000_000_000
    os.utime(conf, ns=(later, later))

    second = make_app(buildername="needs", srcdir=app.srcdir)
    second.build()
    assert "0 added, 0 changed, 0 removed" in second._status.getvalue()
    assert _needs(second)["B_001"]["tot"] == 3.0


REFUSED_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "fruit": {"schema": {"type": "string"}},
    "hours": {"schema": {"type": "number"}},
    "pick": {
        "schema": {"type": "string", "enum": ["apple", "pear"]},
        "nullable": False,
        "derive": {"kind": "copy", "field": "fruit"},
    },
    "code": {
        "schema": {"type": "string", "pattern": "^[a-z]+$"},
        "derive": {"kind": "copy", "field": "fruit"},
    },
    "total": {
        "schema": {"type": "number", "minimum": 0},
        "nullable": False,
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
    "n": {
        "schema": {"type": "integer", "minimum": 1},
        "nullable": False,
        "derive": {"kind": "count", "over": "links"},
    },
    "ok": {
        "schema": {"type": "boolean", "const": True},
        "nullable": False,
        "derive": {"kind": "all", "over": "links", "test": "hours > 0"},
    },
    "low": {
        "schema": {"type": "number", "minimum": 1},
        "nullable": False,
        "derive": {"kind": "min", "field": "hours", "over": "links"},
    },
    "fruits": {
        "schema": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "derive": {"kind": "copy", "field": "fruit", "over": "links", "select": "list"},
    },
}
"""

REFUSED_INDEX = """\
Refused
=======

.. req:: Banana
   :id: REQ_1
   :fruit: Banana
   :hours: -2

.. req:: Apple
   :id: REQ_2
   :fruit: apple
   :hours: 3

.. spec:: Sums REQ_1
   :id: SPEC_1
   :links: REQ_1

.. spec:: Sums REQ_2
   :id: SPEC_2
   :links: REQ_2
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), REFUSED_CONF),
                (Path("index.rst"), REFUSED_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_result_the_field_schema_refuses(test_app):
    """A computed result the field's ``schema`` refuses (an ``enum``, a ``pattern``, a
    ``minimum``) is not stored: it is one ``needs.dynamic_function``, and the field
    keeps its empty value, which its schema does not check; so no schema violation.

    A result equal to the empty value is checked too, where it is computed: a ``count``
    of 0 under ``minimum = 1``, an ``all`` of false under ``const = true``, are refused,
    though the field then holds that value as its empty value (which the schema
    validation of the stored values does not check). So is a rule that ran over no
    candidate: ``REQ_1``'s ``count`` of 0, and its ``select = "list"`` copy's ``[]`` under
    ``minItems = 1``, which leaves the nullable field ``None``. A rule that found no
    value leaves the empty value, unchecked: ``REQ_1``'s ``min`` over no link, 0.0
    under ``minimum = 1``, and ``SPEC_1``'s copy of no ``fruit`` into ``pick``.
    """
    app = test_app
    app.build()
    refused = (
        "WARNING: Error while resolving dynamic values for field '{}', of need '{}': "
        "derive rule '{}' value {} is refused by the field's schema: {} "
        "[needs.dynamic_function]"
    )
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: "
        + refused.format(
            "code", "REQ_1", "copy", "'Banana'", '"Banana" does not match "^[a-z]+$"'
        ),
        "<srcdir>/index.rst:4: "
        + refused.format("fruits", "REQ_1", "copy", [], "[] has less than 1 item"),
        "<srcdir>/index.rst:4: "
        + refused.format("n", "REQ_1", "count", 0, "0 is less than the minimum of 1"),
        "<srcdir>/index.rst:4: "
        + refused.format(
            "pick",
            "REQ_1",
            "copy",
            "'Banana'",
            '"Banana" is not one of "apple" or "pear"',
        ),
        "<srcdir>/index.rst:9: "
        + refused.format("fruits", "REQ_2", "copy", [], "[] has less than 1 item"),
        "<srcdir>/index.rst:9: "
        + refused.format("n", "REQ_2", "count", 0, "0 is less than the minimum of 1"),
        "<srcdir>/index.rst:14: "
        + refused.format(
            "low", "SPEC_1", "min", -2.0, "-2.0 is less than the minimum of 1"
        ),
        "<srcdir>/index.rst:14: "
        + refused.format("ok", "SPEC_1", "all", False, "true was expected"),
        "<srcdir>/index.rst:14: "
        + refused.format(
            "total", "SPEC_1", "sum", -2.0, "-2.0 is less than the minimum of 0"
        ),
    ]
    needs = _needs(app)
    # SPEC_1 and SPEC_2 have no fruit: the copy finds no value, and the empty value
    # is held without a finding
    assert (needs["SPEC_1"]["pick"], needs["SPEC_1"]["code"]) == ("", None)
    assert (needs["REQ_1"]["pick"], needs["REQ_1"]["code"]) == ("", None)
    assert (needs["REQ_2"]["pick"], needs["REQ_2"]["code"]) == ("apple", "apple")
    assert (needs["SPEC_1"]["total"], needs["SPEC_2"]["total"]) == (0.0, 3.0)
    assert (needs["REQ_1"]["n"], needs["SPEC_1"]["n"]) == (0, 1)
    assert (needs["SPEC_1"]["ok"], needs["SPEC_2"]["ok"], needs["REQ_1"]["ok"]) == (
        False,
        True,
        True,
    )
    # a rule that ran over no candidate: its [] is refused, the field keeps None
    assert (needs["REQ_1"]["fruits"], needs["SPEC_2"]["fruits"]) == (None, ["apple"])
    # a rule that found no value: the empty value 0.0, which minimum = 1 does not check
    assert (needs["REQ_1"]["low"], needs["SPEC_1"]["low"], needs["SPEC_2"]["low"]) == (
        0.0,
        0.0,
        3.0,
    )


IMPORT_SOURCE = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_001": {
                    "id": "IMP_001",
                    "type": "req",
                    "title": "Imported",
                    "links": ["REQ_001"],
                    "total": 42.0,
                }
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'
                    "needs_fields = {\n"
                    '    "hours": {"schema": {"type": "number"}},\n'
                    '    "total": {"schema": {"type": "number"}, '
                    '"derive": {"kind": "sum", "field": "hours", "over": "links"}},\n'
                    "}\n",
                ),
                (Path("imported.json"), json.dumps(IMPORT_SOURCE)),
                (
                    Path("index.rst"),
                    "Import\n======\n\n.. req:: Hours\n   :id: REQ_001\n   :hours: 3\n\n"
                    ".. req:: Sums\n   :id: REQ_002\n   :links: REQ_001\n\n"
                    ".. needimport:: imported.json\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_no_rule_runs_on_an_imported_need(test_app):
    """An imported need keeps the value it carries; a need of the project computes it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert needs["IMP_001"]["total"] == 42.0
    assert needs["REQ_002"]["total"] == 3.0


ADD_FIELD_CONF = """\
from sphinx_needs.api import add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"hours": {"schema": {"type": "number"}}}


def setup(app):
    add_field(
        "total",
        "The hours of the linked needs",
        schema={"type": "number"},
        derive={"kind": "sum", "field": "hours", "over": "links"},
    )
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), ADD_FIELD_CONF),
                (
                    Path("index.rst"),
                    "API\n===\n\n.. req:: Hours\n   :id: REQ_001\n   :hours: 3\n\n"
                    ".. req:: Sums\n   :id: REQ_002\n   :links: REQ_001\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_add_field_declares_a_derived_field(test_app):
    """An extension declares a derived field through the ``add_field`` API."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["REQ_002"]["total"] == 3.0
