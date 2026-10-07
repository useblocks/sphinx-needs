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


# -- back links and link fields --------------------------------------------------------

BACKLINKS_A = """\
a
=

.. req:: T
   :id: P
   :incoming: [[copy("links_back")]]
   :summary: [[copy("links_back")]]
"""

BACKLINKS_B = """\
b
=

.. req:: T
   :id: C2
   :links: P

.. req:: T
   :id: C1
   :links: P

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
                (Path("conf.py"), CONF),
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

    ``C2`` links to ``P`` before ``C1`` does; the list ``P`` reads is ``C1, C2``. A list
    into a string field still fails the type check. ``has_dead_links`` is final too.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["P"]["incoming"] == ["C1", "C2"]
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

    ``R``'s call reads ``X``'s computed ``refs`` before it is computed (the empty list,
    so ``R`` keeps its literal link); ``B``'s reads its back links, not built yet.
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
            "dynamic function 'copy' for option 'links' read 'links_back' on need 'B' "
            "before it was computed: a link field is computed before the other fields, "
            "and before the back links",
            "derive_scope",
        ),
        _warning(
            "index",
            LINK_SCOPE_INDEX,
            "R",
            "dynamic function 'copy' for option 'links' read 'refs' on need 'X' "
            "before it was computed: a link field is computed before the other fields, "
            "and before the back links",
            "derive_scope",
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
    that is not nullable it is still refused by the type check.
    """
    app = test_app
    app.build()
    need = _needs(app)["N1"]
    assert (need["summary"], need["parent"]) == (None, "prefix ")
    assert (need["incoming"], need["refs"]) == (None, [])
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
