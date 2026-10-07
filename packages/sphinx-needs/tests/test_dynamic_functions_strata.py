"""Dynamic functions and variants resolve in dependency-ordered strata.

Once every ``needextend`` is applied, the ``[[…]]``, ``<<…>>`` and ``<{…}>`` of the
link fields are computed first (stratum 1), each after the link fields it reads and
your own functions last; then the back links are built; then every other field
(stratum 2), each after every value it reads, your own functions last again. So a
value no longer depends on document names, on ``-j``, on the order of the options in
a directive or on the order the fields are declared in. A value that reads itself is
a cycle (``needs.derive_cycle``, the field is left empty), and a read that cannot be
ordered is ``needs.derive_scope``.

Each project here is written so that the insertion-order pass of 8.x gives a
different value or warning; the ``-j 2`` layouts add padding documents so that the
documents really are read in parallel.
"""

import json
import os
import time
from pathlib import Path

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs.need_item import NeedItem
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_id_regex = "^.+$"
needs_fields = {
    "summary": {"nullable": True},
    "comment": {"nullable": True},
    "parent": {"nullable": True},
    "hours": {"schema": {"type": "number"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
    "incoming": {"schema": {"type": "array", "items": {"type": "string"}}, "nullable": True},
    "refs": {"schema": {"type": "array", "items": {"type": "string"}}, "nullable": False, "default": []},
    "dead": {"schema": {"type": "boolean"}, "nullable": True},
    "f1": {"nullable": True},
    "f2": {"nullable": True},
    "band": {"nullable": True, "parse_variants": True},
}
"""

PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


def _toctree(*pages: str) -> str:
    return "Index\n=====\n\n.. toctree::\n\n" + "".join(f"   {p}\n" for p in pages)


def _layouts(**layouts: list[tuple[Path, str]]) -> list:
    """Each named layout built serially and with ``-j 2``."""
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


def _needs(app) -> dict[str, dict]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _line(text: str, need_id: str) -> int:
    """The 1-based line of the directive whose ``:id:`` is ``need_id``."""
    lines = text.splitlines()
    index = lines.index(f"   :id: {need_id}")
    while not lines[index].startswith(".. "):
        index -= 1
    return index + 1


def _warning(page: str, text: str, need_id: str, message: str, subtype: str) -> str:
    return (
        f"<srcdir>/{page}.rst:{_line(text, need_id)}: WARNING: {message} "
        f"[needs.{subtype}]"
    )


# -- a chain across needs, in two layouts, serial and -j 2 ---------------------------

CHAIN_READER = '.. req:: T\n   :id: CH_A\n   :summary: [[copy("summary", "CH_B")]]\n'
CHAIN_MIDDLE = '.. req:: T\n   :id: CH_B\n   :summary: [[copy("summary", "CH_C")]]\n'
CHAIN_SOURCE = ".. req:: T\n   :id: CH_C\n   :summary: done\n"


def _page(title: str, body: str) -> str:
    return f"{title}\n{'=' * len(title)}\n\n{body}"


CHAIN_READER_FIRST = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), _toctree("a", "b", "c")),
    (Path("a.rst"), _page("a", CHAIN_READER)),
    (Path("b.rst"), _page("b", CHAIN_MIDDLE)),
    (Path("c.rst"), _page("c", CHAIN_SOURCE)),
]
CHAIN_SOURCE_FIRST = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), _toctree("a", "b", "c")),
    (Path("a.rst"), _page("a", CHAIN_SOURCE)),
    (Path("b.rst"), _page("b", CHAIN_MIDDLE)),
    (Path("c.rst"), _page("c", CHAIN_READER)),
]


@pytest.mark.parametrize(
    "test_app",
    _layouts(reader_first=CHAIN_READER_FIRST, source_first=CHAIN_SOURCE_FIRST),
    indirect=True,
)
def test_a_chain_gives_the_chained_value_in_every_layout(test_app):
    """``CH_A`` copies ``CH_B``, which copies ``CH_C``: both are ``done``, always.

    The insertion-order pass gave the reader written first the unresolved ``None``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert [needs[i]["summary"] for i in ("CH_A", "CH_B", "CH_C")] == ["done"] * 3
    assert build_warnings(app) == []


# -- a need's own fields, whatever their kind and declaration order --------------------

SAME_NEED_INDEX = """\
Same need
=========

.. req:: The title
   :id: SAME
   :status: [[copy("comment")]]
   :comment: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), SAME_NEED_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_core_field_reads_an_extra_field_of_its_own_need(test_app):
    """``status`` (a core field) is computed after the extra field ``comment`` it reads."""
    app = test_app
    app.build()
    need = _needs(app)["SAME"]
    assert (need["status"], need["comment"]) == ("The title", "The title")
    assert build_warnings(app) == []


DECLARED_CONF = """\
extensions = ["sphinx_needs"]
needs_id_regex = "^.+$"
needs_fields = {{
    "{first}": {{"nullable": True}},
    "{second}": {{"nullable": True}},
}}
"""

DECLARED_INDEX = """\
Declared
========

.. req:: T
   :id: F12
   :f1: [[copy("f2")]]
   :f2: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), DECLARED_CONF.format(first=a, second=b)),
                    (Path("index.rst"), DECLARED_INDEX),
                ],
            },
            id=f"{a}-declared-first",
        )
        for a, b in (("f1", "f2"), ("f2", "f1"))
    ],
    indirect=True,
)
def test_extra_fields_in_either_declaration_order(test_app):
    """``f1`` copies ``f2``: the order the two are declared in does not matter."""
    app = test_app
    app.build()
    need = _needs(app)["F12"]
    assert (need["f1"], need["f2"]) == ("T", "T")
    assert build_warnings(app) == []


# -- a sum over sums ----------------------------------------------------------------

SUM_H1 = '.. req:: T\n   :id: H1\n   :hours: [[calc_sum("hours", links_only=True)]]\n   :links: H2\n'
SUM_H4 = '.. req:: T\n   :id: H4\n   :total: [[calc_sum("hours")]]\n'
SUM_H5 = '.. req:: T\n   :id: H5\n   :hours: [[calc_sum("hours", links_only=True)]]\n   :links: H2\n'
SUM_H2 = ".. req:: T\n   :id: H2\n   :hours: 5\n"


def _sum_files(*bodies: str) -> list[tuple[Path, str]]:
    pages = ["a", "b", "c", "d"]
    return [
        (Path("conf.py"), CONF),
        (Path("index.rst"), _toctree(*pages)),
        *(
            (Path(f"{p}.rst"), _page(p, body))
            for p, body in zip(pages, bodies, strict=True)
        ),
    ]


@pytest.mark.parametrize(
    "test_app",
    _layouts(
        sums_around=_sum_files(SUM_H1, SUM_H4, SUM_H5, SUM_H2),
        total_first=_sum_files(SUM_H4, SUM_H1, SUM_H2, SUM_H5),
    ),
    indirect=True,
)
def test_a_sum_over_every_need_reads_computed_summands(test_app):
    """``H4`` sums every need's ``hours``, two of which are ``links_only`` sums of ``H2``."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert [needs[i]["hours"] for i in ("H1", "H2", "H5")] == [5.0, 5.0, 5.0]
    assert needs["H4"]["total"] == 15.0
    assert build_warnings(app) == []


OWN_LINKS_INDEX = """\
Own links
=========

.. req:: Hours three
   :id: HRS_3
   :hours: 3

.. req:: Literal one
   :id: LIT_1
   :hours: 4

.. req:: Sums over its own links, which carry a call
   :id: OWN_LINKS
   :parent: LIT_1
   :links: HRS_3, [[copy("parent")]]
   :total: [[calc_sum("hours", links_only=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), OWN_LINKS_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_links_only_sum_reads_its_own_computed_links(test_app):
    """The link field is computed in stratum 1, so the sum reads both targets: 3 + 4."""
    app = test_app
    app.build()
    need = _needs(app)["OWN_LINKS"]
    assert (need["links"], need["total"]) == (["HRS_3", "LIT_1"], 7.0)
    assert build_warnings(app) == []


# -- variants ----------------------------------------------------------------------

VARIANT_CONF = CONF.replace(
    "needs_fields = {\n", 'needs_fields = {\n    "status": {"parse_variants": True},\n'
)

VARIANT_INDEX = """\
Variant
=======

.. req:: T
   :id: VAR
   :f1: [[copy("title")]]
   :status: <<[f1 == "T"]:matched, unmatched>>
   :band: <<[f1 == "T"]:matched, unmatched>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), VARIANT_CONF),
                (Path("index.rst"), VARIANT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_variant_condition_sees_the_computed_field_it_names(test_app):
    """A core and an extra variant both see ``f1`` computed."""
    app = test_app
    app.build()
    need = _needs(app)["VAR"]
    assert (need["status"], need["band"]) == ("matched", "matched")
    assert build_warnings(app) == []


SELF_VARIANT_CONF = (
    VARIANT_CONF + 'needs_variants = {"is_open": "status == \'open\'"}\n'
)

SELF_VARIANT_INDEX = """\
Self-reading variant
====================

.. req:: T
   :id: VS
   :status: <<is_open:open, closed>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), SELF_VARIANT_CONF),
                (Path("index.rst"), SELF_VARIANT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_variant_condition_reading_the_field_it_sets_is_a_cycle(test_app):
    """The condition of ``status`` reads ``status``: a cycle, with its own sentence."""
    app = test_app
    app.build()
    assert _needs(app)["VS"]["status"] is None
    assert build_warnings(app) == [
        _warning(
            "index",
            SELF_VARIANT_INDEX,
            "VS",
            "variant condition for option 'status' is on a cycle: 'status' on need 'VS'; "
            "its condition reads the field it sets; the field is left empty",
            "derive_cycle",
        )
    ]


# -- cycles ------------------------------------------------------------------------

CYCLE_A = """\
a
=

.. req:: T
   :id: CY_A
   :summary: [[copy("summary", "CY_B")]]
"""

CYCLE_B = """\
b
=

.. req:: T
   :id: CY_B
   :summary: [[copy("summary", "CY_A")]]

.. req:: T
   :id: CY_S
   :summary: [[copy("summary")]]
"""

CYCLE_FILES = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), _toctree("a", "b")),
    (Path("a.rst"), CYCLE_A),
    (Path("b.rst"), CYCLE_B),
]

PAIR = (
    "dynamic function 'copy' for option 'summary' is on a cycle: "
    "'summary' on 2 needs (CY_A, CY_B); the field is left empty"
)


@pytest.mark.parametrize("test_app", _layouts(cycle=CYCLE_FILES), indirect=True)
def test_a_cycle_is_left_empty_and_reported_once_per_member(test_app):
    """``CY_A`` and ``CY_B`` copy each other, ``CY_S`` copies itself.

    Each member takes its typed empty value (``None``: the field is nullable) and gets
    one ``needs.derive_cycle`` naming the members, in need-id order.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert [needs[i]["summary"] for i in ("CY_A", "CY_B", "CY_S")] == [None] * 3
    assert build_warnings(app) == [
        _warning("a", CYCLE_A, "CY_A", PAIR, "derive_cycle"),
        _warning("b", CYCLE_B, "CY_B", PAIR, "derive_cycle"),
        _warning(
            "b",
            CYCLE_B,
            "CY_S",
            "dynamic function 'copy' for option 'summary' is on a cycle: "
            "'summary' on need 'CY_S'; the field is left empty",
            "derive_cycle",
        ),
    ]


SELF_SUM_INDEX = """\
Self sum
========

.. req:: T
   :id: SP
   :hours: [[calc_sum("hours")]]

.. req:: T
   :id: SQ
   :hours: 1

.. req:: T
   :id: SR
   :hours: 2

.. req:: Open work
   :id: P2
   :total: [[calc_sum("total", filter="status == 'open'")]]

.. req:: open
   :id: ST
   :status: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), SELF_SUM_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_sum_whose_candidates_include_its_own_need_is_a_cycle(test_app):
    """``SP`` sums every need's ``hours``, its own included; ``P2``'s filter names ``status``,
    which ``ST`` computes, so every need is a candidate of its sum of ``total``, ``P2`` too.

    Both say what made them a cycle.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["SP"]["hours"], needs["P2"]["total"]) == (None, None)
    assert build_warnings(app) == [
        _warning(
            "index",
            SELF_SUM_INDEX,
            "SP",
            "dynamic function 'calc_sum' for option 'hours' is on a cycle: "
            "'hours' on need 'SP', through a sum over every need; the field is left empty",
            "derive_cycle",
        ),
        # after ``ST``, whose ``status`` its filter reads
        _warning(
            "index",
            SELF_SUM_INDEX,
            "P2",
            "dynamic function 'calc_sum' for option 'total' is on a cycle: "
            "'total' on need 'P2', through the filter \"status == 'open'\", which names "
            "a computed field, so every need is a candidate; the field is left empty",
            "derive_cycle",
        ),
    ]


MEMBER_COLUMN_INDEX = """\
Each member's column
====================

.. req:: A sum whose filter names a computed field
   :id: FILT
   :comment: [[copy("title")]]
   :total: [[calc_sum("total", "comment == 'x'")]]

.. req:: A sum over every need
   :id: SELF_SUM
   :total: [[calc_sum("total")]]

.. req:: A sum whose filter on final values keeps its own need
   :id: S_SUM
   :hours: [[calc_sum("hours", "type == 'req'")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), MEMBER_COLUMN_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_each_cycle_member_says_what_made_it_one(test_app):
    """Each member of a cycle through a sum names its own sum, not another member's.

    ``FILT`` and ``SELF_SUM`` are one cycle over ``total``: ``FILT``'s through its
    filter, which names a computed field, ``SELF_SUM``'s through a sum over every need.
    ``S_SUM``'s filter is on final values, and keeps ``S_SUM``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (
        needs["FILT"]["total"],
        needs["SELF_SUM"]["total"],
        needs["S_SUM"]["hours"],
    ) == (None, None, None)
    members = "'total' on 2 needs (FILT, SELF_SUM)"
    assert build_warnings(app) == [
        _warning(
            "index",
            MEMBER_COLUMN_INDEX,
            "FILT",
            f"dynamic function 'calc_sum' for option 'total' is on a cycle: {members}, "
            "through the filter \"comment == 'x'\", which names a computed field, so "
            "every need is a candidate; the field is left empty",
            "derive_cycle",
        ),
        _warning(
            "index",
            MEMBER_COLUMN_INDEX,
            "SELF_SUM",
            f"dynamic function 'calc_sum' for option 'total' is on a cycle: {members}, "
            "through a sum over every need; the field is left empty",
            "derive_cycle",
        ),
        _warning(
            "index",
            MEMBER_COLUMN_INDEX,
            "S_SUM",
            "dynamic function 'calc_sum' for option 'hours' is on a cycle: 'hours' on "
            "need 'S_SUM', through the filter \"type == 'req'\", which keeps a need on "
            "the cycle; the field is left empty",
            "derive_cycle",
        ),
    ]


FILTERED_SUM_INDEX = """\
Filtered sum
============

.. req:: The specs' hours
   :id: P
   :hours: [[calc_sum("hours", filter="type == 'spec'")]]

.. spec:: Two
   :id: S_2
   :hours: 2

.. spec:: Three
   :id: S_3
   :hours: [[copy("total")]]
   :total: 3
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), FILTERED_SUM_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_filter_on_final_values_keeps_its_own_need_out_of_the_sum(test_app):
    """``P`` sums the ``hours`` it also holds, but its filter excludes it: no cycle.

    The filter names only ``type``, which nothing computes, so its candidates are known
    before the stratum and ``P`` is not one of them.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["P"]["hours"], needs["S_3"]["hours"]) == (5.0, 3.0)
    assert build_warnings(app) == []


NEEDEXTEND_CYCLE_INDEX = """\
Extended cycle
==============

.. req:: NX A
   :id: NX_A
   :summary: before

.. req:: NX B
   :id: NX_B
   :summary: [[copy("summary", "NX_A")]]

.. needextend:: NX_A
   :summary: [[copy("summary", "NX_B")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), NEEDEXTEND_CYCLE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_cycle_through_a_call_a_needextend_sets_is_left_empty(test_app):
    """The call ``NX_A`` gets from the ``needextend`` makes a cycle with ``NX_B``.

    Its value written before the extend (``before``) is not what either member holds.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["NX_A"]["summary"], needs["NX_B"]["summary"]) == (None, None)
    message = (
        "dynamic function 'copy' for option 'summary' is on a cycle: "
        "'summary' on 2 needs (NX_A, NX_B); the field is left empty"
    )
    assert build_warnings(app) == [
        _warning("index", NEEDEXTEND_CYCLE_INDEX, "NX_A", message, "derive_cycle"),
        _warning("index", NEEDEXTEND_CYCLE_INDEX, "NX_B", message, "derive_cycle"),
    ]


HISTORY_READER = """\
a
=

.. req:: T
   :id: HA
   :summary: [[copy("summary", "HB")]]
"""

HISTORY_SOURCE = """\
b
=

.. req:: T
   :id: HB
   :summary: done
"""

HISTORY_CYCLE = """\
b
=

.. req:: T
   :id: HB
   :summary: [[copy("summary", "HA")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), _toctree("a", "b")),
                (Path("a.rst"), HISTORY_READER),
                (Path("b.rst"), HISTORY_SOURCE),
            ],
        }
    ],
    indirect=True,
)
def test_a_cycle_member_holds_nothing_from_an_earlier_build(test_app):
    """A rebuild in the same process that turns ``HA``'s read into a cycle empties ``HA``.

    ``a.rst`` is not re-read, so ``HA`` is the need the first build resolved to
    ``done``; as a cycle member it is set to its empty value, not left as it was.
    """
    app = test_app
    app.build()
    assert _needs(app)["HA"]["summary"] == "done"
    first = build_warnings(app)
    assert first == []

    Path(app.srcdir, "b.rst").write_text(HISTORY_CYCLE, encoding="utf-8")
    # newer than the time the first build read it, whatever the file system's clock
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "b.rst"), ns=(later, later))
    app.build()
    needs = _needs(app)
    assert (needs["HA"]["summary"], needs["HB"]["summary"]) == (None, None)
    message = (
        "dynamic function 'copy' for option 'summary' is on a cycle: "
        "'summary' on 2 needs (HA, HB); the field is left empty"
    )
    assert build_warnings(app) == [
        _warning("a", HISTORY_READER, "HA", message, "derive_cycle"),
        _warning("b", HISTORY_CYCLE, "HB", message, "derive_cycle"),
    ]


# -- what a field that is not computed holds ---------------------------------------

PLACEHOLDER_INDEX = """\
Placeholder
===========

.. req:: Literal one
   :id: LIT_1

.. req:: A mixed link list on a cycle
   :id: C_LINKS
   :links: LIT_1, [[copy("links")]]

.. req:: A mixed array on a cycle
   :id: X_ARR
   :incoming: a, [[copy("incoming", "Y_ARR")]]

.. req:: Closes the cycle
   :id: Y_ARR
   :incoming: [[copy("incoming", "X_ARR")]]

.. req:: Written items, then a call appended, on a cycle
   :id: X_ITEMS
   :incoming: a, b

.. needextend:: X_ITEMS
   :+incoming: [[copy("incoming", "Y_ITEMS")]]

.. req:: Closes the cycle
   :id: Y_ITEMS
   :incoming: [[copy("incoming", "X_ITEMS")]]

.. req:: Written items, then replaced by a call, on a cycle
   :id: X_REP
   :incoming: a

.. needextend:: X_REP
   :incoming: [[copy("incoming", "Y_REP")]]

.. req:: Closes the cycle
   :id: Y_REP
   :incoming: [[copy("incoming", "X_REP")]]

.. req:: A mixed string on a cycle
   :id: X_STR
   :summary: lead [[copy("summary", "Y_STR")]]

.. req:: Closes the cycle
   :id: Y_STR
   :summary: [[copy("summary", "X_STR")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), PLACEHOLDER_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_list_field_on_a_cycle_keeps_its_written_items(test_app):
    """A link or array field that is not computed keeps the items written in it.

    Its calls and variants are dropped: ``C_LINKS`` keeps ``LIT_1`` (so ``LIT_1`` has
    its back link), ``X_ARR`` keeps ``a``, and ``X_ITEMS`` keeps the items written
    before a ``needextend`` appended the call. A list with no written item, and any
    other field (``X_STR``'s string, written part and all), takes its typed empty
    value, as does ``X_REP``, whose written items the extend replaced.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["C_LINKS"]["links"] == ["LIT_1"]
    assert needs["LIT_1"]["links_back"] == ["C_LINKS"]
    assert {
        need_id: needs[need_id]["incoming"]
        for need_id in ("X_ARR", "Y_ARR", "X_ITEMS", "Y_ITEMS", "X_REP", "Y_REP")
    } == {
        "X_ARR": ["a"],
        "Y_ARR": None,
        "X_ITEMS": ["a", "b"],
        "Y_ITEMS": None,
        "X_REP": None,
        "Y_REP": None,
    }
    assert (needs["X_STR"]["summary"], needs["Y_STR"]["summary"]) == (None, None)

    def cycle(need_id: str, field: str, members: str, kept: bool) -> str:
        return _warning(
            "index",
            PLACEHOLDER_INDEX,
            need_id,
            f"dynamic function 'copy' for option '{field}' is on a cycle: "
            f"'{field}' on {members}; the field "
            + ("keeps only its written items" if kept else "is left empty"),
            "derive_cycle",
        )

    assert build_warnings(app) == [
        cycle("C_LINKS", "links", "need 'C_LINKS'", True),
        cycle("X_ARR", "incoming", "2 needs (X_ARR, Y_ARR)", True),
        cycle("Y_ARR", "incoming", "2 needs (X_ARR, Y_ARR)", False),
        cycle("X_ITEMS", "incoming", "2 needs (X_ITEMS, Y_ITEMS)", True),
        cycle("Y_ITEMS", "incoming", "2 needs (X_ITEMS, Y_ITEMS)", False),
        cycle("X_REP", "incoming", "2 needs (X_REP, Y_REP)", False),
        cycle("Y_REP", "incoming", "2 needs (X_REP, Y_REP)", False),
        cycle("X_STR", "summary", "2 needs (X_STR, Y_STR)", False),
        cycle("Y_STR", "summary", "2 needs (X_STR, Y_STR)", False),
    ]


# -- what a filter reads ------------------------------------------------------------
#
# A filter reads the needs themselves, not through the record of the reads, so the
# check at run time cannot see a filter read too early: only these builds can. In
# each, the reader's node sorts before the node its filter reads, so the reader is
# right only if the order puts it after that node.

FILTER_CONF = """\
extensions = ["sphinx_needs"]
needs_id_regex = "^.+$"
needs_fields = {
    "summary": {"nullable": True},
    "aout": {"nullable": True},
    "zgrp": {"nullable": True},
    "team": {"nullable": True},
}
needs_links = {"links": {}, "refs": {}}
"""

CURRENT_NEED_OF_NAMED_INDEX = """\
current_need of the need named
==============================

.. req:: Reader, sorts first
   :id: A_RD
   :aout: [[copy("summary", "B_OTHER", filter='current_need["zgrp"] == title')]]

.. req:: Reader, sorts last
   :id: Z_RD
   :aout: [[copy("summary", "B_OTHER", filter='current_need["zgrp"] == title')]]

.. req:: The need the filter's current_need is
   :id: B_OTHER
   :zgrp: [[copy("title", "Z_GSRC")]]

.. req:: one
   :id: Z_GSRC

.. req:: one
   :id: M_ONE
   :summary: matched one
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), FILTER_CONF),
                (Path("index.rst"), CURRENT_NEED_OF_NAMED_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_copy_filter_current_need_is_the_need_named(test_app):
    """``copy(x, "ID", filter=…)`` evaluates the filter with ``ID`` as ``current_need``.

    So ``current_need["zgrp"]`` is ``B_OTHER``'s computed ``zgrp``, and both readers
    wait for it: the same call gives the same value whatever the reader's id.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["A_RD"]["aout"], needs["Z_RD"]["aout"]) == (
        "matched one",
        "matched one",
    )
    assert build_warnings(app) == []


CURRENT_NEED_KEY_INDEX = """\
current_need of the caller
==========================

.. req:: Reader
   :id: A_RD
   :team: rd
   :zgrp: [[copy("title", "G_SRC")]]
   :aout: [[copy("summary", filter='team == "t1" and current_need["zgrp"] == title')]]

.. req:: one
   :id: G_SRC

.. req:: one
   :id: M_ONE
   :team: t1
   :summary: matched one
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), FILTER_CONF),
                (Path("index.rst"), CURRENT_NEED_KEY_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_copy_filter_reads_the_current_need_key(test_app):
    """``current_need["zgrp"]`` in ``copy``'s filter reads the caller's computed ``zgrp``.

    ``aout`` sorts before ``zgrp``, so it is right only when it waits for it.
    """
    app = test_app
    app.build()
    assert _needs(app)["A_RD"]["aout"] == "matched one"
    assert build_warnings(app) == []


COMPUTED_NAME_INDEX = """\
A filter naming a computed field
================================

.. req:: copy
   :id: A_CP
   :aout: [[copy("summary", filter='zgrp == "one"')]]

.. req:: check_linked_values, a filter
   :id: A_FLT
   :aout: [[check_linked_values("ok", "summary", "done", 'zgrp != "y"')]]
   :links: B_Y

.. req:: check_linked_values, every target
   :id: A_TWO
   :aout: [[check_linked_values("ok", "summary", "done")]]
   :links: B_DONE, C_DONE

.. req:: links_from_content, a filter on a computed link
   :id: A_LFC
   :links: [[links_from_content(filter='"LIT" in refs')]]

   See :need:`M_REF` and :need:`LIT`.

.. req:: links_from_content, a filter on another computed field
   :id: A_LFL
   :refs: LIT, [[links_from_content(filter='zgrp == "one"')]]

   See :need:`M_ONE`.

.. req:: Computes a link
   :id: M_REF
   :refs: [[copy("refs", "W_REF")]]

.. req:: Writes a link
   :id: W_REF
   :refs: LIT

.. req:: one
   :id: G_SRC

.. req:: Match one
   :id: M_ONE
   :zgrp: [[copy("title", "G_SRC")]]
   :summary: matched one

.. req:: y
   :id: B_Y
   :zgrp: [[copy("title")]]
   :summary: not done

.. req:: Done, written
   :id: B_DONE
   :summary: done

.. req:: done
   :id: C_DONE
   :summary: [[copy("title")]]

.. req:: A literal link
   :id: LIT
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), FILTER_CONF),
                (Path("index.rst"), COMPUTED_NAME_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_filter_on_a_computed_field_waits_for_it(test_app):
    """Each built-in's filter (and ``check_linked_values``' targets) is read when final.

    ``copy``'s filter names ``zgrp``, which ``M_ONE`` computes; ``check_linked_values``
    excludes ``B_Y`` by its computed ``zgrp`` and checks ``C_DONE``'s computed
    ``summary`` though it is not the first target; ``links_from_content`` keeps the
    referenced need its filter matches on its computed link ``refs``. Every reader sorts
    before what it reads. A link field's filter naming another field is a read out of
    scope.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert {
        need_id: needs[need_id]["aout"] for need_id in ("A_CP", "A_FLT", "A_TWO")
    } == {"A_CP": "matched one", "A_FLT": "ok", "A_TWO": "ok"}
    assert needs["A_LFC"]["links"] == ["M_REF"]
    assert needs["A_LFL"]["refs"] == ["LIT"]
    assert build_warnings(app) == [
        _warning(
            "index",
            COMPUTED_NAME_INDEX,
            "A_LFL",
            "dynamic function 'links_from_content' for option 'refs' reads 'zgrp' on "
            "need 'M_ONE', which is final only after the link fields are computed: "
            "the call is not run and the field keeps only its written items",
            "derive_scope",
        )
    ]


SHADOWED_BUILTIN_CONF = (
    FILTER_CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled
suppress_warnings = ["config.cache"]


def copy(app, need, needs, option, *args, **kwargs):
    # your own function, registered under a built-in's name: it reads another need
    return needs["Z_SRC"]["summary"]


needs_functions = [copy]
"""
)

SHADOWED_BUILTIN_INDEX = """\
A function named like a built-in
================================

.. req:: Reader
   :id: A_RD
   :aout: [[copy("anything")]]

.. req:: Source
   :id: Z_SRC
   :summary: [[echo("done")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), SHADOWED_BUILTIN_CONF),
                (Path("index.rst"), SHADOWED_BUILTIN_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_your_function_named_like_a_builtin_runs_last(test_app):
    """A function registered under ``copy``'s name is yours: it runs last in its stratum.

    The order knows the reads of the built-in functions themselves, not of a name.
    """
    app = test_app
    app.build()
    assert _needs(app)["A_RD"]["aout"] == "done"
    assert build_warnings(app) == [
        "WARNING: Dynamic function copy already registered. [needs.config]"
    ]


# -- back links and link fields --------------------------------------------------------

BACKLINKS_A = """\
a
=

.. req:: T
   :id: P
   :incoming: [[copy("links_back")]]
   :summary: [[copy("links_back")]]

.. req:: T
   :id: Q

   :np:`(1) a part`

.. req:: T
   :id: QR
   :incoming: [[part_back("Q", "1")]]
"""

BACKLINKS_CONF = (
    CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled
suppress_warnings = ["config.cache"]


def part_back(app, need, needs, need_id, part_id):
    # a part's back links, in the order they are stored (no filter reaches a part)
    part = needs[need_id].get_part(part_id)
    return [link.id for link in part.backlinks.get("links", [])]


needs_functions = [part_back]
"""
)

BACKLINKS_B = """\
b
=

.. req:: T
   :id: C2
   :links: P, Q.1

.. req:: T
   :id: C1
   :links: P, Q.1

.. req:: T
   :id: DL
   :links: NOPE
   :dead: [[copy("has_dead_links")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), BACKLINKS_CONF),
                (Path("index.rst"), _toctree("a", "b")),
                (Path("a.rst"), BACKLINKS_A),
                (Path("b.rst"), BACKLINKS_B),
            ],
        }
    ],
    indirect=True,
)
def test_back_links_are_built_before_the_other_fields(test_app):
    """``copy("links_back")`` reads the back links, in need-id order.

    ``C2`` links to ``P`` before ``C1`` does; the list ``P`` reads is ``C1, C2``, and so
    is the list of ``Q``'s part ``1`` (read by a function of your own, as no built-in
    reads a part). A list into a string field still fails the type check.
    ``has_dead_links`` is final too.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["P"]["incoming"] == ["C1", "C2"]
    assert needs["QR"]["incoming"] == ["C1", "C2"]
    assert needs["DL"]["dead"] is True
    assert build_warnings(app) == [
        _warning(
            "a",
            BACKLINKS_A,
            "P",
            "Error while resolving dynamic values for field 'summary', of need 'P': "
            "dynamic function value <class 'list'> is not of type 'string'",
            "dynamic_function",
        ),
        _warning(
            "b",
            BACKLINKS_B,
            "DL",
            "Need 'DL' has unknown outgoing link 'NOPE' in field 'links'",
            "link_outgoing",
        ),
    ]


REBUILD_TARGET = """\
a
=

.. req:: T
   :id: P
   :incoming: [[copy("links_back")]]
"""

REBUILD_LINKED = """\
b
=

.. req:: T
   :id: C1
   :links: P

.. req:: T
   :id: C2
   :links: P
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), _toctree("a", "b")),
                (Path("a.rst"), REBUILD_TARGET),
                (Path("b.rst"), REBUILD_LINKED),
            ],
        }
    ],
    indirect=True,
)
def test_a_rebuild_drops_a_removed_back_link(test_app):
    """A rebuild in the same process builds the back links afresh.

    ``a.rst`` is not re-read, so ``P`` is the need of the first build, back links
    and all; once ``C1`` no longer links to it, neither its back links nor the copy of
    them name ``C1``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["P"]["links_back"], needs["P"]["incoming"]) == (
        ["C1", "C2"],
        ["C1", "C2"],
    )

    Path(app.srcdir, "b.rst").write_text(
        REBUILD_LINKED.replace("   :id: C1\n   :links: P\n", "   :id: C1\n"),
        encoding="utf-8",
    )
    # newer than the time the first build read it, whatever the file system's clock
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "b.rst"), ns=(later, later))
    app.build()
    needs = _needs(app)
    assert (needs["P"]["links_back"], needs["P"]["incoming"]) == (["C2"], ["C2"])
    assert build_warnings(app) == []


STALE_CONF = (
    CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled
suppress_warnings = ["config.cache"]


def back_of(app, need, needs, need_id=None):
    # your own link function reading a need's back links: it runs in the link step
    return list((needs[need_id] if need_id else need)["links_back"])


needs_functions = [back_of]
"""
)

STALE_READERS = """\
a
=

.. req:: T
   :id: P
   :links: [[back_of()]]

.. req:: T
   :id: U_RD
   :links: [[back_of("P")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), STALE_CONF),
                (Path("index.rst"), _toctree("a", "b")),
                (Path("a.rst"), STALE_READERS),
                (Path("b.rst"), REBUILD_LINKED),
            ],
        }
    ],
    indirect=True,
)
def test_a_link_function_reads_no_back_link_of_an_earlier_build(test_app, monkeypatch):
    """The back links are emptied at the start of the pass, once, before the link fields.

    Your own function in a link field runs before the back links are built, so it
    reads none: not those of the first build either, when a rebuild in the same
    process keeps ``P`` and ``U_RD`` (``a.rst`` is not re-read) and ``C1`` stops
    linking to ``P``. Every need is reset exactly once per build.
    """
    resets: list[str] = []
    reset = NeedItem.reset_backlinks

    def counted(self: NeedItem) -> None:
        resets.append(self.id)
        reset(self)

    monkeypatch.setattr(NeedItem, "reset_backlinks", counted)
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["P"]["links"], needs["U_RD"]["links"]) == ([], [])
    assert sorted(resets) == ["C1", "C2", "P", "U_RD"]

    resets.clear()
    Path(app.srcdir, "b.rst").write_text(
        REBUILD_LINKED.replace("   :id: C1\n   :links: P\n", "   :id: C1\n"),
        encoding="utf-8",
    )
    # newer than the time the first build read it, whatever the file system's clock
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "b.rst"), ns=(later, later))
    app.build()
    needs = _needs(app)
    assert (needs["P"]["links"], needs["U_RD"]["links"]) == ([], [])
    assert needs["P"]["links_back"] == ["C2"]
    assert sorted(resets) == ["C1", "C2", "P", "U_RD"]


LINK_SCOPE_INDEX = """\
Link scope
==========

.. req:: T
   :id: X
   :tags: tag_a
   :refs: [[copy("tags")]]

.. req:: T
   :id: R
   :links: HRS_3, [[copy("refs", "X")]]

.. req:: T
   :id: B
   :links: [[copy("links_back")]]

.. req:: T
   :id: HRS_3
   :links: B
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), LINK_SCOPE_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_link_field_reading_a_later_value_is_out_of_scope(test_app):
    """A link field is computed before the other fields and before the back links.

    ``R``'s call reads ``X``'s computed ``refs``, ``B``'s its back links, not built yet:
    neither call is run, and each field keeps only its written links.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["R"]["links"], needs["B"]["links"]) == (["HRS_3"], [])
    assert needs["X"]["refs"] == ["tag_a"]
    assert build_warnings(app) == [
        _warning(
            "index",
            LINK_SCOPE_INDEX,
            "B",
            "dynamic function 'copy' for option 'links' reads 'links_back' on need 'B', "
            "which is final only after the link fields are computed: the call is not "
            "run and the field is left empty",
            "derive_scope",
        ),
        _warning(
            "index",
            LINK_SCOPE_INDEX,
            "R",
            "dynamic function 'copy' for option 'links' reads 'refs' on need 'X', "
            "which is final only after the link fields are computed: the call is not "
            "run and the field keeps only its written items",
            "derive_scope",
        ),
    ]


SINK_CONF = (
    CONF
    + """needs_fields["label"] = {"nullable": False, "default": ""}
needs_links = {"links": {"parse_variants": True}}
"""
)

SINK_INDEX = """Sinks
=====

.. req:: Source
   :id: SRC
   :status: open

.. req:: Literal one
   :id: LIT_1

.. req:: Literal two
   :id: LIT_2

.. req:: A link list reading its own computed status
   :id: LIT_CALL
   :status: [[copy("status", "SRC")]]
   :links: LIT_1, [[copy("status")]]

.. req:: Computes a label naming a need
   :id: OTHER
   :label: [[copy("id", "LIT_2")]]

.. req:: A link list reading another need's computed label
   :id: OTHER_RD
   :links: [[copy("label", "OTHER")]]

.. req:: Computes a summary
   :id: NOTE_SRC
   :summary: [[copy("id")]]

.. req:: A link list reading another need's computed summary
   :id: NOTE_RD
   :links: LIT_1, [[copy("summary", "NOTE_SRC")]]

.. req:: A link list reading its own back links
   :id: BACK_RD
   :links: [[copy("links_back")]]

.. req:: Links to BACK_RD
   :id: TO_BACK
   :links: BACK_RD

.. req:: A variant in a link list reading a computed status
   :id: V_LINK
   :status: [[copy("status", "SRC")]]
   :links: <<[status == "open"]:LIT_1, LIT_2>>

.. req:: Computes an array
   :id: Z_ARR
   :incoming: a, [[copy("id")]]

.. req:: A link list reading another need's computed array
   :id: L_RD
   :links: [[copy("incoming", "Z_ARR")]]

.. req:: A link list selecting its source by a computed field
   :id: SEL_LATE
   :parent: [[copy("id", "LIT_2")]]
   :links: [[copy("links", need.parent)]]

.. req:: Selects by a field computed in the same step, which reads it back
   :id: BLK
   :parent: [[copy("summary")]]
   :summary: [[copy("summary", need.parent)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), SINK_CONF), (Path("index.rst"), SINK_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_call_that_cannot_be_ordered_is_not_run(test_app):
    """A call (or variant) reading a value its stratum cannot wait for is not run.

    A link field's call or variant reading another field or a back link, and a call
    whose ``need.<field>`` selector is computed in the same step: each field keeps its
    written links (``LIT_1`` has its back links from them) or is empty, with one
    ``needs.derive_scope`` and nothing else, never a dead link to ``''`` (``OTHER_RD``),
    a type error (``NOTE_RD``, ``L_RD``) or a no-match arm (``V_LINK``). Such a field
    reads nothing, so it is on no cycle: ``BLK``'s ``parent`` reads its empty
    ``summary`` without a ``needs.derive_cycle``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert {
        need_id: needs[need_id]["links"]
        for need_id in (
            "LIT_CALL",
            "OTHER_RD",
            "NOTE_RD",
            "BACK_RD",
            "V_LINK",
            "L_RD",
            "SEL_LATE",
        )
    } == {
        "LIT_CALL": ["LIT_1"],
        "OTHER_RD": [],
        "NOTE_RD": ["LIT_1"],
        "BACK_RD": [],
        "V_LINK": [],
        "L_RD": [],
        "SEL_LATE": [],
    }
    assert (needs["LIT_1"]["links_back"], needs["LIT_2"]["links_back"]) == (
        ["LIT_CALL", "NOTE_RD"],
        [],
    )
    assert (needs["OTHER_RD"]["has_dead_links"], needs["OTHER"]["label"]) == (
        False,
        "LIT_2",
    )
    assert (needs["LIT_CALL"]["status"], needs["V_LINK"]["status"]) == ("open", "open")
    assert needs["Z_ARR"]["incoming"] == ["a", "Z_ARR"]
    assert needs["SEL_LATE"]["parent"] == "LIT_2"
    assert (needs["BLK"]["parent"], needs["BLK"]["summary"]) == (None, None)

    def scope(need_id: str, what: str, read: str, kept: bool) -> str:
        not_run = (
            "the condition is not evaluated"
            if what == "variant condition"
            else "the call is not run"
        )
        return _warning(
            "index",
            SINK_INDEX,
            need_id,
            f"{what} for option 'links' reads {read}, which is final only after the "
            f"link fields are computed: {not_run} and the field "
            + ("keeps only its written items" if kept else "is left empty"),
            "derive_scope",
        )

    copy = "dynamic function 'copy'"
    assert build_warnings(app) == [
        scope("BACK_RD", copy, "'links_back' on need 'BACK_RD'", False),
        scope("LIT_CALL", copy, "'status' on need 'LIT_CALL'", True),
        scope("L_RD", copy, "'incoming' on need 'Z_ARR'", False),
        scope("NOTE_RD", copy, "'summary' on need 'NOTE_SRC'", True),
        scope("OTHER_RD", copy, "'label' on need 'OTHER'", False),
        scope("SEL_LATE", copy, "'parent' on need 'SEL_LATE'", False),
        scope("V_LINK", "variant condition", "'status' on need 'V_LINK'", False),
        _warning(
            "index",
            SINK_INDEX,
            "BLK",
            "dynamic function 'copy' for option 'summary' names its target by "
            "'need.parent', which is computed in the same step: the call is not run "
            "and the field is left empty",
            "derive_scope",
        ),
    ]


DEAD_FLAG_INDEX = """\
Dead-link flag
==============

.. req:: Literal one
   :id: LIT_1

.. req:: Literal two
   :id: LIT_2

.. req:: A variant in a link field reading the dead-link flag
   :id: V_DEAD
   :links: NOPE, <<[has_dead_links]:LIT_1, LIT_2>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), SINK_CONF),
                (Path("index.rst"), DEAD_FLAG_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_link_field_reading_the_dead_link_flags_is_out_of_scope(test_app):
    """``has_dead_links`` and ``has_forbidden_dead_links`` are set with the back links.

    A link field's variant reading one is not evaluated, as for a back link: the field
    keeps its written ``NOPE`` (itself a dead link), and does not take the no-match arm
    on the flag's value from before the links are computed.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["V_DEAD"]["links"] == ["NOPE"]
    assert needs["V_DEAD"]["has_dead_links"] is True
    assert build_warnings(app) == [
        _warning(
            "index",
            DEAD_FLAG_INDEX,
            "V_DEAD",
            "variant condition for option 'links' reads 'has_dead_links' on need "
            "'V_DEAD', which is final only after the link fields are computed: the "
            "condition is not evaluated and the field keeps only its written items",
            "derive_scope",
        ),
        _warning(
            "index",
            DEAD_FLAG_INDEX,
            "V_DEAD",
            "Need 'V_DEAD' has unknown outgoing link 'NOPE' in field 'links'",
            "link_outgoing",
        ),
    ]


CONDITION_A = """\
A
=

.. req:: A
   :id: REQ_A
   :links: REQ_B[len(links_back) >= 2]
"""

CONDITION_B = """\
B
=

.. req:: C1
   :id: REQ_C1
   :links: REQ_B

.. req:: C2
   :id: REQ_C2
   :links: REQ_B

.. req:: B
   :id: REQ_B
"""


@pytest.mark.parametrize(
    "test_app",
    _layouts(
        condition_first=[
            (Path("conf.py"), CONF),
            (Path("index.rst"), _toctree("a", "b")),
            (Path("a.rst"), CONDITION_A),
            (Path("b.rst"), CONDITION_B),
        ],
        condition_last=[
            (Path("conf.py"), CONF),
            (Path("index.rst"), _toctree("a", "b")),
            (Path("a.rst"), CONDITION_B),
            (Path("b.rst"), CONDITION_A),
        ],
    ),
    indirect=True,
)
def test_a_link_condition_reads_complete_back_links(test_app):
    """A condition on the target's back links is checked once they are all built."""
    app = test_app
    app.build()
    assert build_warnings(app) == []


# -- your own functions -----------------------------------------------------------------

USER_CONF = (
    CONF
    + """\
needs_links = {"tests": {}}
# Sphinx's own warning that a function in the configuration is not pickled
suppress_warnings = ["config.cache"]


def linked_to(app, need, needs, target):
    # shaped like sphinx-test-reports' tr_link: reads a field of every need
    return sorted(other["id"] for other in needs.values() if target in other["links"])


def jira(app, need, needs):
    # a value from elsewhere
    return 7.0


needs_functions = [linked_to, jira]
"""
)

USER_LINKS_INDEX = """\
User links
==========

.. req:: Target
   :id: TGT

.. req:: User links
   :id: U
   :tests: [[linked_to("TGT")]]

.. req:: Built-in links
   :id: B1
   :links: [[copy("links", "SRC")]]
   :incoming: [[copy("tests_back")]]

.. req:: Source
   :id: SRC
   :links: TGT

.. req:: Reader
   :id: RD
   :refs: [[copy("tests", "U")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), USER_CONF),
                (Path("index.rst"), USER_LINKS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_user_function_in_a_link_field_runs_last_in_its_stratum(test_app):
    """``linked_to`` runs after the built-in link calls, before the back links are built.

    It sees ``B1``'s computed link, its links are in the targets' back links, and a
    built-in reading its link field afterwards reads a final value: no warning.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["U"]["tests"] == ["B1", "SRC"]
    assert needs["B1"]["incoming"] == ["U"]
    assert needs["SRC"]["tests_back"] == ["U"]
    assert needs["RD"]["refs"] == ["B1", "SRC"]
    assert build_warnings(app) == []


USER_VALUE_INDEX = """\
User value
==========

.. req:: Sum
   :id: SUM_U
   :total: [[calc_sum("hours")]]

.. req:: From the tracker
   :id: U_1
   :hours: [[jira()]]

.. req:: Authored
   :id: LIT_2
   :hours: 2
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), USER_CONF),
                (Path("index.rst"), USER_VALUE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_builtin_reading_a_user_function_field_is_out_of_scope(test_app):
    """``jira`` runs after the built-in functions, so the sum reads ``U_1`` before it."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["SUM_U"]["total"], needs["U_1"]["hours"]) == (2.0, 7.0)
    assert build_warnings(app) == [
        _warning(
            "index",
            USER_VALUE_INDEX,
            "SUM_U",
            "dynamic function 'calc_sum' for option 'total' read 'hours' on need 'U_1' "
            "before it was computed: it is computed by your own function 'jira', "
            "which runs after the built-in functions",
            "derive_scope",
        )
    ]


# -- needextend filters ---------------------------------------------------------------

EXTEND_NEEDS = "".join(
    f'\n.. req:: open\n   :id: EXT_{i}\n   :status: [[copy("title")]]\n'
    for i in range(1, 5)
)

EXTEND_A = "a\n=\n" + EXTEND_NEEDS

EXTEND_B = """\
b
=

.. needextend:: status == "open"
   :+tags: matched

.. needextend:: type == "req"
   :+tags: typed

.. needextend:: status == "open" and "x" in tags
   :+tags: both
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), _toctree("a", "b")),
                (Path("a.rst"), EXTEND_A),
                (Path("b.rst"), EXTEND_B),
            ],
        }
    ],
    indirect=True,
)
def test_a_needextend_filter_naming_a_computed_field_is_out_of_scope(test_app):
    """Each ``needextend`` whose filter names ``status``, computed on four needs, warns.

    The filter still sees the value from before it is computed, so it matches nothing.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["EXT_1"]["status"] == "open"
    assert [needs[f"EXT_{i}"]["tags"] for i in range(1, 5)] == [["typed"]] * 4
    tail = (
        "names 'status', which a dynamic function or variant computes on "
        "4 needs (EXT_1, EXT_2, EXT_3 and 1 more): the filter sees the value "
        "from before it is computed [needs.derive_scope]"
    )
    assert build_warnings(app) == [
        f"<srcdir>/b.rst:4: WARNING: needextend filter 'status == \"open\"' {tail}",
        "<srcdir>/b.rst:10: WARNING: needextend filter "
        f'\'status == "open" and "x" in tags\' {tail}',
    ]


# -- ``need.<attr>`` in field and link values ----------------------------------------

NEED_ATTR_INDEX = """\
Need attributes
===============

.. req:: Source
   :id: SRC
   :summary: from source
   :links: TGT

.. req:: Target
   :id: TGT

.. req:: Reads through need.parent
   :id: QA
   :parent: SRC
   :summary: [[copy("summary", need.parent)]]
   :links: [[copy("links", need_id=need.parent)]]

.. req:: Selects by a computed field
   :id: NA
   :comment: SRC
   :parent: [[copy("comment")]]
   :summary: [[copy("summary", need.parent)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), NEED_ATTR_INDEX)],
        }
    ],
    indirect=True,
)
def test_need_attributes_in_field_and_link_values(test_app):
    """``need.<field>`` selects the need a call reads; it must be final before the call.

    ``QA``'s ``parent`` is written, so both calls run. ``NA``'s is computed in the same
    step as the call that selects by it: the call is not run, and its field is empty.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["QA"]["summary"], needs["QA"]["links"]) == ("from source", ["TGT"])
    assert (needs["NA"]["parent"], needs["NA"]["summary"]) == ("SRC", None)
    assert build_warnings(app) == [
        _warning(
            "index",
            NEED_ATTR_INDEX,
            "NA",
            "dynamic function 'copy' for option 'summary' names its target by "
            "'need.parent', which is computed in the same step: the call is not run "
            "and the field is left empty",
            "derive_scope",
        )
    ]


VALUE_SLOT_INDEX = """\
Value slots
===========

.. req:: Target title
   :id: T_SRC

.. req:: search_value
   :id: V_SV
   :summary: [[copy("title", "T_SRC")]]
   :comment: [[check_linked_values("ok", "title", need.summary)]]
   :links: T_SRC

.. req:: result
   :id: V_RES
   :summary: [[copy("title", "T_SRC")]]
   :comment: [[check_linked_values(need.summary, "title", "Target title")]]
   :links: T_SRC

.. req:: upper
   :id: V_UP
   :summary: [[copy("title")]]
   :comment: [[copy("title", "T_SRC", upper=need.summary)]]

.. req:: echo
   :id: V_ECHO
   :summary: [[copy("title", "T_SRC")]]
   :comment: [[echo(need.summary)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), VALUE_SLOT_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_need_attribute_value_chains(test_app):
    """A ``need.<field>`` passed as a value is read like the field: after it is computed.

    Only an argument that selects what a call reads must be final before the call;
    ``check_linked_values``' ``search_value`` and ``result`` and ``copy``'s ``upper``
    are values, so each ``comment`` waits for its ``summary`` (which sorts after it).
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert {
        need_id: needs[need_id]["comment"]
        for need_id in ("V_SV", "V_RES", "V_UP", "V_ECHO")
    } == {
        "V_SV": "ok",
        "V_RES": "Target title",
        "V_UP": "TARGET TITLE",
        "V_ECHO": "Target title",
    }
    assert build_warnings(app) == []


APPENDED_USER_CONF = (
    CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled
suppress_warnings = ["config.cache"]


def later(app, need, needs):
    return "later"


needs_functions = [later]
"""
)

APPENDED_USER_INDEX = """\
Appended call
=============

.. req:: Written, then your own function's call appended
   :id: X
   :summary: written
   :incoming: a, b

.. needextend:: X
   :+summary: [[later()]]
   :+incoming: [[later()]]

.. req:: Reads X before your function computes it
   :id: Y
   :comment: [[copy("summary", "X")]]
   :refs: [[copy("incoming", "X")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), APPENDED_USER_CONF),
                (Path("index.rst"), APPENDED_USER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_field_an_extend_appends_a_call_to_holds_its_placeholder(test_app):
    """Until its call is computed, a field a ``needextend`` appended a call to holds the
    value a cycle member would: an array its written items, a string its empty value.

    Your own function runs after the built-in ones, so ``Y``'s copies read ``X``'s
    fields before they are computed (and say so): ``summary`` is not its written
    ``written``, which is now part of the call's value, and ``incoming`` is ``a, b``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert (needs["X"]["summary"], needs["X"]["incoming"]) == (
        "written later",
        ["a", "b", "later"],
    )
    assert (needs["Y"]["comment"], needs["Y"]["refs"]) == (None, ["a", "b"])

    def read(field: str, name: str) -> str:
        return _warning(
            "index",
            APPENDED_USER_INDEX,
            "Y",
            f"dynamic function 'copy' for option '{field}' read '{name}' on need 'X' "
            "before it was computed: it is computed by your own function 'later', "
            "which runs after the built-in functions",
            "derive_scope",
        )

    assert build_warnings(app) == [read("comment", "summary"), read("refs", "incoming")]


UNSET_SELECTOR_CONF = (
    CONF
    + """\
needs_fields["src"] = {"nullable": True}
needs_fields["defaulted"] = {
    "nullable": True,
    "default": "[[copy('title', need.src)]]",
}
"""
)

UNSET_SELECTOR_INDEX = """\
Unset selector
==============

.. req:: Target title
   :id: T_SRC

.. req:: Selects its source
   :id: D_ALL
   :src: T_SRC
   :summary: [[copy("title", need.src)]]

.. req:: Selector unset
   :id: D_UNSET
   :summary: [[copy("title", need.src)]]

.. req:: Value unset
   :id: V_NONE
   :summary: [[copy("title", "T_SRC", upper=need.src)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), UNSET_SELECTOR_CONF),
                (Path("index.rst"), UNSET_SELECTOR_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_an_unset_need_attribute_selector_fails_the_call(test_app):
    """A ``need.<field>`` that selects what a call reads, unset, fails the call.

    ``copy("title", need.src)`` with no ``src`` is a ``needs.dynamic_function`` naming
    ``need.src``, the field keeping its value: not a copy of the need's own title, as
    if no need had been named. That holds for the configured ``default`` of every need
    without ``src`` too. In a value argument (``upper``), unset is ``None``.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert {
        need_id: (needs[need_id]["summary"], needs[need_id]["defaulted"])
        for need_id in ("T_SRC", "D_ALL", "D_UNSET", "V_NONE")
    } == {
        "T_SRC": (None, None),
        "D_ALL": ("Target title", "Target title"),
        "D_UNSET": (None, None),
        "V_NONE": ("Target title", None),
    }

    def unset(need_id: str, field: str) -> str:
        return _warning(
            "index",
            UNSET_SELECTOR_INDEX,
            need_id,
            f"Error while resolving dynamic values for field '{field}', of need "
            f"'{need_id}': Error while applying need to function 'copy': need.src "
            "selects what the call reads, and is not set",
            "dynamic_function",
        )

    assert build_warnings(app) == [
        unset("D_UNSET", "defaulted"),
        unset("D_UNSET", "summary"),
        unset("T_SRC", "defaulted"),
        unset("V_NONE", "defaulted"),
    ]


UNSET_ROLE_INDEX = """\
Unset selector in a role
========================

.. req:: Selector unset, in a field and in the need's content
   :id: D_UNSET
   :summary: [[copy("title", need.src)]]

   ndf says: :ndf:`copy("title", need.src)`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), UNSET_SELECTOR_CONF),
                (Path("index.rst"), UNSET_ROLE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_an_unset_need_attribute_selector_fails_the_role_too(test_app):
    """The ``ndf`` role in a need's content fails like the field does, with ``??``.

    It does not render the need's own title, as a ``copy`` that names no need would.
    """
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "ndf says: ??" in html
    assert "ndf says: Selector unset" not in html
    unset = (
        "Error while applying need to function 'copy': need.src selects what the "
        "call reads, and is not set"
    )
    warnings = build_warnings(app)
    assert any(
        f"WARNING: {unset} [needs.dynamic_function]" in warning for warning in warnings
    ), warnings
    assert any(
        f"of need 'D_UNSET': {unset} [needs.dynamic_function]" in warning
        for warning in warnings
    ), warnings


FAILED_CALL_INDEX = """\
Failed calls
============

.. req:: Literal one
   :id: LIT_1

.. req:: A link list whose call returns a number
   :id: LL_NUM
   :hours: 3
   :links: LIT_1, [[copy("hours")]]

.. req:: An array whose call returns a number
   :id: LA_NUM
   :hours: 3
   :tags: a, [[copy("hours")]]

.. req:: A link list whose call fails
   :id: LL_MISS
   :links: LIT_1, [[copy("title", "MISSING")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), FAILED_CALL_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_failed_call_leaves_its_field_at_its_placeholder(test_app):
    """A call that fails, or whose result the field cannot hold, computes nothing.

    The field holds what a cycle member would: a link or array field its written
    items (``LIT_1``, ``a``), not the empty list, and the call is one
    ``needs.dynamic_function`` warning.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert {
        "LL_NUM": needs["LL_NUM"]["links"],
        "LA_NUM": needs["LA_NUM"]["tags"],
        "LL_MISS": needs["LL_MISS"]["links"],
    } == {"LL_NUM": ["LIT_1"], "LA_NUM": ["a"], "LL_MISS": ["LIT_1"]}
    assert needs["LIT_1"]["links_back"] == ["LL_MISS", "LL_NUM"]

    def failed(need_id: str, field: str, error: str) -> str:
        return _warning(
            "index",
            FAILED_CALL_INDEX,
            need_id,
            f"Error while resolving dynamic values for field '{field}', of need "
            f"'{need_id}': {error}",
            "dynamic_function",
        )

    not_a_list = (
        "dynamic function value <class 'float'> is not of type 'array' or item type "
        "'string'"
    )
    assert build_warnings(app) == [
        failed("LL_MISS", "links", "Error while executing function 'copy': 'MISSING'"),
        failed("LL_NUM", "links", not_a_list),
        failed("LA_NUM", "tags", not_a_list),
    ]


# -- a ``None`` result -------------------------------------------------------------

NONE_RESULT_INDEX = """\
None result
===========

.. req:: Unset source
   :id: SRC0

.. req:: T
   :id: N1
   :summary: [[copy("comment", "SRC0")]]
   :parent: prefix [[copy("comment", "SRC0")]]
   :incoming: [[copy("comment", "SRC0")]]
   :refs: [[copy("comment", "SRC0")]]

.. req:: T
   :id: N2
   :incoming: [[copy("refs", "SRC0")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), NONE_RESULT_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_none_result_adds_nothing_to_a_nullable_field(test_app):
    """``copy`` of an unset field returns ``None``, which adds nothing to the value.

    Alone in a nullable string or array field it leaves the field unset (``None``);
    beside a literal, the literal is the value. It used to be stored as the text
    ``"None"``, and as a ``[None]`` that schema validation then refused. In a field
    that is not nullable it is still refused by the type check. An empty list is a
    value: ``N2``'s copy of ``SRC0``'s empty ``refs`` stores ``[]``, not ``None``.
    """
    app = test_app
    app.build()
    need = _needs(app)["N1"]
    assert (need["summary"], need["parent"]) == (None, "prefix ")
    assert (need["incoming"], need["refs"]) == (None, [])
    assert _needs(app)["N2"]["incoming"] == []
    assert build_warnings(app) == [
        _warning(
            "index",
            NONE_RESULT_INDEX,
            "N1",
            "Error while resolving dynamic values for field 'refs', of need 'N1': "
            "dynamic function value <class 'NoneType'> is not of type 'array' "
            "or item type 'string'",
            "dynamic_function",
        )
    ]
