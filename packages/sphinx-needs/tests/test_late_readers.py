"""Built-in functions and rules reading what is computed last.

Your own functions, and the built-in calls whose filter cannot be read (it names
``needs``), are computed after every other node of their step, in need-id order. A
built-in function or rule reading one of them -- as an argument, through a filter on
any need, a join, a ``where`` -- and one reading such a reader, is computed among
them, right after the last it reads (#2354). These tests compare each reader with the
same project whose late values are written out (the *oracle*), pin the cascade and a
cycle among moved nodes, the trade-off (your own function before a moved node reads
it empty, unreported), and the order the nodes computed last are decided in when one
of them cannot wait for a moved node.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

TITLE = "Case\n====\n\n"


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, conf: str, index: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    srcdir.mkdir(parents=True)
    (srcdir / "conf.py").write_text(conf, encoding="utf-8")
    (srcdir / "index.rst").write_text(TITLE + index, encoding="utf-8")
    app = make_app("needs", srcdir=srcdir)
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    warnings = [w for w in build_warnings(app) if "config.cache" not in w]
    app.cleanup()
    return data["versions"][data["current_version"]]["needs"], warnings


MATRIX_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


def my_hours(app, need, needs, *args, **kwargs):
    return 5


def my_tag(app, need, needs, *args, **kwargs):
    return "T1"


needs_functions = [my_links, my_hours, my_tag]
needs_fields = {
    "hours": {"schema": {"type": "integer"}, "nullable": True},
    "cost": {"schema": {"type": "integer"}, "nullable": True},
    "s_all": {"schema": {"type": "number"}, "nullable": True},
    "s_f": {"schema": {"type": "number"}, "nullable": True},
    "clv": {"nullable": True},
    "clv_f": {"nullable": True},
    "cp2": {"schema": {"type": "integer"}, "nullable": True},
    "cp_same": {"schema": {"type": "integer"}, "nullable": True},
    "cpf2": {"nullable": True},
    "var": {"nullable": True, "parse_variants": True},
    "r_join": {"nullable": True, "derive": {"kind": "copy", "field": "title", "join": {"field": "tag", "equals": "want"}}},
    "tag": {"nullable": True},
    "want": {"nullable": True},
    "r_count": {"schema": {"type": "integer"}, "nullable": True,
                "derive": {"kind": "count", "over": "links", "where": "hours is not None and hours > 1"}},
}
needs_links = {
    "blocks": {},
    "opq": {},
    "via": {},
    "via_opq": {},
    "cont": {},
    "cp": {},
    "cpf": {},
    "via_rule": {"derive": {"kind": "links", "where": "'REQ_2' in blocks"}},
    "cont_rule": {"derive": {"kind": "content_links", "where": "'REQ_2' in blocks"}},
}
"""

MATRIX_INDEX = """\
.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Late feeder
   :id: SPEC_1
   :blocks: [[my_links()]]
   :opq: [[links_from_filter("len(needs) > 0 and id == 'REQ_1'")]]
   :hours: [[my_hours()]]
   :cost: 7
   :tag: [[my_tag()]]
   :cp_same: [[copy("hours")]]
   :var: <<[hours is not None and hours > 1]:big, small>>

.. spec:: Readers
   :id: SPEC_2
   :links: SPEC_1
   :via: [[links_from_filter("'REQ_2' in blocks")]]
   :via_opq: [[links_from_filter("'REQ_1' in opq")]]
   :cont: [[links_from_content(filter="'REQ_2' in blocks")]]
   :cp: [[copy("blocks", "SPEC_1")]]
   :cpf: [[copy("blocks", filter="'REQ_2' in blocks")]]
   :s_all: [[calc_sum("hours")]]
   :s_f: [[calc_sum("cost", filter="hours is not None and hours > 1")]]
   :clv: [[check_linked_values("yes", "hours", [5])]]
   :clv_f: [[check_linked_values("yes", "cost", [99], filter_string="hours is not None and hours > 1")]]
   :cp2: [[copy("hours", "SPEC_1")]]
   :cpf2: [[copy("title", filter="hours is not None and hours > 1")]]
   :want: T1
   :var: <<[hours is not None and hours > 1]:big, small>>

   Refers :need:`SPEC_1`.
"""

#: the same project, its late values written out
ORACLE_INDEX = """\
.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Late feeder
   :id: SPEC_1
   :blocks: REQ_2
   :opq: REQ_1
   :hours: 5
   :cost: 7
   :tag: T1
   :cp_same: [[copy("hours")]]
   :var: <<[hours is not None and hours > 1]:big, small>>

.. spec:: Readers
   :id: SPEC_2
   :links: SPEC_1
   :via: [[links_from_filter("'REQ_2' in blocks")]]
   :via_opq: [[links_from_filter("'REQ_1' in opq")]]
   :cont: [[links_from_content(filter="'REQ_2' in blocks")]]
   :cp: [[copy("blocks", "SPEC_1")]]
   :cpf: [[copy("blocks", filter="'REQ_2' in blocks")]]
   :s_all: [[calc_sum("hours")]]
   :s_f: [[calc_sum("cost", filter="hours is not None and hours > 1")]]
   :clv: [[check_linked_values("yes", "hours", [5])]]
   :clv_f: [[check_linked_values("yes", "cost", [99], filter_string="hours is not None and hours > 1")]]
   :cp2: [[copy("hours", "SPEC_1")]]
   :cpf2: [[copy("title", filter="hours is not None and hours > 1")]]
   :want: T1
   :var: <<[hours is not None and hours > 1]:big, small>>

   Refers :need:`SPEC_1`.
"""

#: every reader of the matrix, of a late value on SPEC_1
READERS = (
    "via",
    "via_opq",
    "cont",
    "cp",
    "cpf",
    "via_rule",
    "cont_rule",
    "s_all",
    "s_f",
    "clv",
    "clv_f",
    "cp2",
    "cp_same",
    "cpf2",
    "var",
    "r_count",
    "r_join",
)


def test_every_built_in_reader_reads_the_late_value(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Each built-in reader of a value your own function, or a call whose filter cannot
    be read, computes -- a filter of ``links_from_filter``, ``links_from_content``,
    ``copy``, ``calc_sum`` and ``check_linked_values``, a ``links`` and a
    ``content_links`` rule's ``where``, a call's argument, an over-rule's ``where``, a
    join, a variant -- holds what it holds where the value is written out, with no
    warning. Before #2354, the reads through a filter or a ``where`` read the value
    empty, silently, and the others were reported."""
    needs, warnings = _build(make_app, tmp_path / "late", MATRIX_CONF, MATRIX_INDEX)
    oracle, oracle_warnings = _build(
        make_app, tmp_path / "oracle", MATRIX_CONF, ORACLE_INDEX
    )
    assert (warnings, oracle_warnings) == ([], [])
    assert {
        need_id: {name: need[name] for name in READERS}
        for need_id, need in needs.items()
    } == {
        need_id: {name: need[name] for name in READERS}
        for need_id, need in oracle.items()
    }
    assert needs["SPEC_2"]["via"] == ["SPEC_1"]
    assert needs["SPEC_2"]["s_f"] == 7.0


CASCADE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def mine(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


def peek(app, need, needs, *args, **kwargs):
    # your own function reading a moved field before its slot, and one after
    return list(needs["SPEC_3"]["a"])


needs_functions = [mine, peek]
needs_links = {
    "blocks": {}, "a": {}, "b": {}, "pk": {},
    "c": {"derive": {"kind": "union", "fields": ["b"]}},
    "r1": {"derive": {"kind": "links", "where": "'REQ_2' in blocks or len(r2) > 0"}},
    "r2": {"derive": {"kind": "links", "where": "len(r1) > 5"}},
}
"""

CASCADE_INDEX = """\
.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Your own function before the slot reads a moved field
   :id: SPEC_0
   :pk: [[peek()]]

.. spec:: Late
   :id: SPEC_1
   :blocks: [[mine()]]

.. spec:: A reads blocks through a filter
   :id: SPEC_3
   :a: [[links_from_filter("'REQ_2' in blocks")]]

.. spec:: B copies A, C is a union over B
   :id: SPEC_4
   :b: [[copy("a", "SPEC_3")]]

.. spec:: After the slot
   :id: SPEC_9
   :pk: [[peek()]]
"""


def test_a_cascade_and_a_cycle_among_moved_nodes(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A built-in reading a moved node is moved too: ``a`` reads ``blocks`` (your own
    function's), ``b`` copies ``a``, the union ``c`` is over ``b``. Two ``links`` rules
    naming each other, one also naming ``blocks``, are moved together and are still a
    cycle (``needs.derive_cycle``). Your own function before the slot reads the moved
    ``a`` empty, one after it complete."""
    needs, warnings = _build(make_app, tmp_path / "src", CASCADE_CONF, CASCADE_INDEX)
    assert needs["SPEC_3"]["a"] == ["SPEC_1"]
    assert needs["SPEC_4"]["b"] == needs["SPEC_4"]["c"] == ["SPEC_1"]
    assert (needs["SPEC_0"]["pk"], needs["SPEC_9"]["pk"]) == ([], ["SPEC_1"])
    # the two rules, on every need, are one cycle, as when nothing is computed last
    assert all(need["r1"] == need["r2"] == [] for need in needs.values())
    assert len(warnings) == 14
    assert all(
        "is on a cycle: 'r1' on 7 needs (REQ_1, REQ_2, SPEC_0 and 4 more) and 'r2' on "
        "7 needs (REQ_1, REQ_2, SPEC_0 and 4 more)"
        in w
        and "[needs.derive_cycle]" in w
        for w in warnings
    )


REGRESSION_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def hours(app, need, needs, *args, **kwargs):
    return 5


def read_total(app, need, needs, *args, **kwargs):
    return needs["SPEC_5"]["total"]


needs_functions = [hours, read_total]
needs_fields = {
    "hours": {"schema": {"type": "integer"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
    "seen": {"schema": {"type": "number"}, "nullable": True},
}
"""

REGRESSION_INDEX = """\
.. spec:: Your own function reading SPEC_5's total, before SPEC_9's hours
   :id: SPEC_0
   :seen: [[read_total()]]

.. spec:: Written
   :id: SPEC_1
   :hours: 2

.. spec:: The sum
   :id: SPEC_5
   :total: [[calc_sum("hours")]]

.. spec:: Your own function's hours
   :id: SPEC_9
   :hours: [[hours()]]
"""


def test_your_own_function_before_a_moved_node_reads_it_empty(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The trade-off: ``SPEC_5``'s sum reads ``SPEC_9``'s ``hours``, which your own
    function computes, so it is computed after it, and right; your own function on
    ``SPEC_0``, computed before ``SPEC_9`` in need-id order, reads the sum before it is
    computed, empty, and nothing reports it (your own functions do not say what they
    read)."""
    needs, warnings = _build(
        make_app, tmp_path / "src", REGRESSION_CONF, REGRESSION_INDEX
    )
    assert warnings == []
    assert needs["SPEC_5"]["total"] == 7.0
    assert needs["SPEC_0"]["seen"] is None


SWEEP_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def mine(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


needs_functions = [mine]
needs_links = {
    "c1": {}, "c2": {}, "c3": {}, "rd": {},
    "u1": {"derive": {"kind": "union", "fields": ["c2"]}},
    "u2": {"derive": {"kind": "union", "fields": ["c3"]}},
}
"""

SWEEP_INDEX = """\
.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: L1, opaque, names u1
   :id: SPEC_1
   :c1: [[links_from_filter("len(needs) > 0 and 'REQ_1' in u1")]]

.. spec:: L2, opaque, names u2; u1 is over c2
   :id: SPEC_2
   :c2: REQ_1, [[links_from_filter("len(needs) > 0 and 'REQ_2' in u2")]]

.. spec:: L3, your own function; u2 is over c3
   :id: SPEC_3
   :c3: [[mine()]]

.. spec:: A built-in reader of u1
   :id: SPEC_4
   :rd: [[links_from_filter("'REQ_1' in u1")]]
"""


def test_the_nodes_computed_last_are_decided_from_the_last_down(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A call whose filter cannot be read cannot wait for a node it names that is moved
    by itself or by a node computed after it: it is not run, and is reported. Deciding
    from the last node down makes that exact: ``c2`` names ``u2``, moved by ``c3``,
    computed after it, so it is a sink; ``u1`` over ``c2`` is then over a sink, and not
    moved, so ``c1``, naming ``u1``, is run, after the built-ins, and reads it complete,
    as does ``rd``, a built-in reader of ``u1``."""
    needs, warnings = _build(make_app, tmp_path / "src", SWEEP_CONF, SWEEP_INDEX)
    assert warnings == [
        "<srcdir>/index.rst:14: WARNING: dynamic function 'links_from_filter' for "
        "option 'c2' reads 'u2' on need 'SPEC_3', which is computed after your own "
        "functions and the calls whose filter cannot be read that it reads, so this "
        "step cannot wait for it: the call is not run and the field keeps only its "
        "written items [needs.derive_scope]",
    ]
    assert (needs["SPEC_2"]["c2"], needs["SPEC_2"]["u1"]) == (["REQ_1"], ["REQ_1"])
    assert needs["SPEC_3"]["u2"] == ["REQ_2"]
    assert needs["SPEC_1"]["c1"] == needs["SPEC_4"]["rd"] == ["SPEC_2"]


FEEDER_SINK_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "flt": {},
    "lm": {},
    "opq": {},
    "all_flt": {"derive": {"kind": "union", "fields": ["links", "flt"]}},
}
"""

FEEDER_SINK_INDEX = """\
.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Its call names the union it feeds
   :id: SPEC_1
   :links: REQ_2
   :flt: REQ_1, [[links_from_filter("len(needs) > 0 and 'REQ_2' in all_flt")]]

.. spec:: Reads the union
   :id: SPEC_2
   :lm: [[links_from_filter("'REQ_2' in all_flt")]]
   :opq: [[links_from_filter("len(needs) > 0 and 'REQ_2' in all_flt")]]
"""


def test_a_feeder_made_a_sink_leaves_its_union_in_place(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``flt``'s call names the union it fills a member of, which it cannot wait for:
    it is not run, and is reported, holding its written ``REQ_1``. The union, no member
    of which is computed last then, is computed with the built-ins, so its readers --
    a built-in (``lm``) and a call computed last (``opq``) -- read it complete, with no
    warning of their own."""
    needs, warnings = _build(
        make_app, tmp_path / "src", FEEDER_SINK_CONF, FEEDER_SINK_INDEX
    )
    assert warnings == [
        "<srcdir>/index.rst:10: WARNING: dynamic function 'links_from_filter' for "
        "option 'flt' reads 'all_flt' on need 'SPEC_1', which is computed after your "
        "own functions and the calls whose filter cannot be read that it reads, so "
        "this step cannot wait for it: the call is not run and the field keeps only its "
        "written items [needs.derive_scope]",
    ]
    assert needs["SPEC_1"]["flt"] == ["REQ_1"]
    assert needs["SPEC_1"]["all_flt"] == ["REQ_1", "REQ_2"]
    assert needs["SPEC_2"]["lm"] == needs["SPEC_2"]["opq"] == ["SPEC_1"]


TR_LINK_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def tr_like(app, need, needs, *args, **kwargs):
    # shaped like sphinx-test-reports' tr_link: links by what the other needs hold
    return sorted(
        n["id"]
        for n in needs.values()
        if n["type"] == "req" and n["title"] in need["title"]
    )


needs_functions = [tr_like]
needs_links = {
    "tests": {},
    "tested_by": {},
    "verified": {"derive": {"kind": "links", "where": "'REQ_1' in tests"}},
}
"""

TR_LINK_INDEX = """\
.. req:: login
   :id: REQ_1
   :tested_by: [[links_from_filter("'REQ_1' in tests")]]

.. req:: logout
   :id: REQ_2

.. test:: test login works
   :id: TEST_1
   :tests: [[tr_like()]]

.. test:: test login fails
   :id: TEST_2
   :tests: [[tr_like()]]
"""


def test_links_your_own_function_computes_are_read_by_filters_and_rules(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A link type filled by your own function, as sphinx-test-reports' ``tr_link``
    fills one, is read complete by a ``links`` rule's ``where`` (on every need) and by
    a ``links_from_filter`` naming it: both are computed after it. Before #2354 both
    read it empty, silently."""
    needs, warnings = _build(make_app, tmp_path / "src", TR_LINK_CONF, TR_LINK_INDEX)
    assert warnings == []
    assert needs["TEST_1"]["tests"] == needs["TEST_2"]["tests"] == ["REQ_1"]
    assert needs["REQ_1"]["tested_by"] == ["TEST_1", "TEST_2"]
    assert all(
        need["verified"] == ["TEST_1", "TEST_2"]
        for need_id, need in needs.items()
        if need_id not in ("TEST_1", "TEST_2")
    )
    assert (needs["TEST_1"]["verified"], needs["TEST_2"]["verified"]) == (
        ["TEST_2"],
        ["TEST_1"],
    )
