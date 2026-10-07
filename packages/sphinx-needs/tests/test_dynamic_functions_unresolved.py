"""Reads of a value computed in the same pass, in dependency order.

Phase 0 reported each read of a field that another ``[[…]]``, ``<<…>>`` or ``<{…}>``
computes in the same pass as ``needs.derive_unresolved``, because the insertion-order
pass gave such a read the computed value or the unresolved one by the order the needs
reached the environment (document names, the documents the last build re-read,
``-j``). The dependency-ordered pass computes every value after the values it reads,
so the same projects now give the chained value and no warning; the tests below are
phase 0's, kept on their projects with the values the ordered pass gives. A value that
reads itself is a cycle (``needs.derive_cycle``), and a read the pass cannot order is
``needs.derive_scope``; ``needs.derive_unresolved`` is retired. The record of a call's
reads (``reads=``) is kept, as the check that the order covers every read a built-in
makes: a read of a value not computed yet is reported as ``needs.derive_scope``.
The last build test runs ubCode's own fixture for the same contract.
"""

import inspect
import json
import os
import re
import time
from pathlib import Path
from typing import get_args

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.functions.common import calc_sum, check_linked_values, copy
from sphinx_needs.functions.functions import execute_func
from sphinx_needs.logging import WarningSubTypeDescription, WarningSubTypes
from sphinx_needs_testkit import assert_no_warnings, build_warnings

#: a cause, as the message builder appends it
CAUSE = "the cause"


def _warning(location: str, message: str, subtype: str) -> str:
    """One warning, as ``build_warnings`` normalises it."""
    return f"<srcdir>/{location}: WARNING: {message} [needs.{subtype}]"


def _built_needs(app) -> dict[str, dict]:
    """The needs of the ``needs.json`` the last build wrote, by id."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "summary": {"nullable": False, "default": ""},
    "comment": {"nullable": True},
    "hours": {"schema": {"type": "number"}, "nullable": True},
    "h0": {"schema": {"type": "number"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
}
"""

SUPPRESSED = {"suppress_warnings": ["needs.derive_cycle", "needs.derive_scope"]}


# -- the message --------------------------------------------------------------
#
# A ``needs.derive_scope`` message for the reads of one call: ubCode's head
# (``{what} for option '{option}' read {read}``), then when, then the cause.


@pytest.mark.parametrize(
    ("what", "option", "reads", "expected"),
    [
        pytest.param(
            "dynamic function 'copy'",
            "summary",
            [("summary", ["CHAIN_B"])],
            "dynamic function 'copy' for option 'summary' read 'summary' on need 'CHAIN_B' "
            f"before it was computed: {CAUSE}",
            id="one-id",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["HRS_2", "HRS_1"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 2 needs (HRS_1, HRS_2) "
            f"before they were computed: {CAUSE}",
            id="two-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["HRS_1", "HRS_2", "LIT_3"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 3 needs (HRS_1, HRS_2, LIT_3) "
            f"before they were computed: {CAUSE}",
            id="three-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["A_1", "A_2", "A_3", "A_4"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 4 needs (A_1, A_2, A_3 and 1 more) "
            f"before they were computed: {CAUSE}",
            id="four-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", [f"A_{i}" for i in range(1, 11)])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 10 needs (A_1, A_10, A_2 and 7 more) "
            f"before they were computed: {CAUSE}",
            id="ten-ids",
        ),
        pytest.param(
            "dynamic function 'check_linked_values'",
            "summary",
            [("links", ["GATE"]), ("status", ["WORK_1"])],
            "dynamic function 'check_linked_values' for option 'summary' "
            "read 'links' on need 'GATE' and 'status' on need 'WORK_1' "
            f"before they were computed: {CAUSE}",
            id="two-names",
        ),
        pytest.param(
            "variant condition",
            "band",
            [("f1", ["V"]), ("f2", ["V"]), ("f3", ["W", "V"])],
            "variant condition for option 'band' "
            "read 'f1' on need 'V', 'f2' on need 'V' and 'f3' on 2 needs (V, W) "
            f"before they were computed: {CAUSE}",
            id="three-names-variant",
        ),
        pytest.param(
            "variant condition",
            "band",
            [("f1", ["VAR_COND"])],
            "variant condition for option 'band' read 'f1' on need 'VAR_COND' "
            f"before it was computed: {CAUSE}",
            id="variant-one-id",
        ),
    ],
)
def test_message_shape(what, option, reads, expected):
    """The message names each name once, with its one need or a count and the first three.

    Several names are joined as ubCode joins them (``a, b and c``); the needs of a name
    are named in need-id order, comparing ids as strings (``A_10`` before ``A_2``).
    ``it was`` is singular only for one name read on one need. Imported here rather
    than at the top so that, before the formatter exists, only these tests fail on the
    import and the build tests below fail on their own assertions.
    """
    from sphinx_needs.functions.functions import _derive_scope_message

    assert _derive_scope_message(what, option, reads, CAUSE) == expected


def test_message_needs_a_read():
    """A record with no read is never formatted: there is nothing to say."""
    from sphinx_needs.functions.functions import _derive_scope_message

    with pytest.raises(ValueError, match="no read"):
        _derive_scope_message("variant condition", "band", [], CAUSE)


# -- T1: a chain across needs, in both layouts --------------------------------
#
# ``CHAIN_A`` copies ``CHAIN_B``'s ``summary``, which ``CHAIN_B`` copies from its
# title. ``CHAIN_A`` is on ``index.rst``; ``CHAIN_B`` is on ``z.rst`` (read after
# ``index``, which gave ``CHAIN_A`` the unresolved ``""`` in the insertion-order
# pass) or on ``a.rst`` (read before, which gave it the computed ``"Middle"``).
# Ordered, both layouts give ``"Middle"`` and no warning, as does ``-j 2`` and an
# incremental build (T10).

CHAIN_INDEX = """\
Chain
=====

.. toctree::

   {page}

.. req:: Chain start
   :id: CHAIN_A
   :summary: [[copy("summary", "CHAIN_B")]]
"""

CHAIN_TARGET = """\
Target
======

.. req:: Middle
   :id: CHAIN_B
   :summary: [[copy("title")]]
"""

CHAIN_FORWARD = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), CHAIN_INDEX.format(page="z")),
    (Path("z.rst"), CHAIN_TARGET),
]
CHAIN_REVERSE = [
    (Path("conf.py"), CONF),
    (Path("index.rst"), CHAIN_INDEX.format(page="a")),
    (Path("a.rst"), CHAIN_TARGET),
]

PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {"buildername": "needs", "files": CHAIN_FORWARD}, id="target-later"
        ),
        pytest.param(
            {"buildername": "needs", "files": CHAIN_REVERSE}, id="target-earlier"
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [*CHAIN_FORWARD, *PADDING],
                "parallel": 2,
            },
            id="target-later-parallel",
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        ),
    ],
    indirect=True,
)
def test_chain_across_needs(test_app):
    """A ``copy`` of another need's computed field reads the computed value, always.

    The layout-independence test: the target authored later used to leave
    ``CHAIN_A`` the unresolved ``""``, the target authored earlier gave it
    ``"Middle"``, and under ``-j`` the order depended on which worker finished first
    (padding documents make the build really parallel). Now every layout gives
    ``"Middle"`` and no warning.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["CHAIN_A"]["summary"], needs["CHAIN_B"]["summary"]) == (
        "Middle",
        "Middle",
    )
    assert build_warnings(app) == []


# -- T2: a chain inside one need ----------------------------------------------
#
# ``status`` is a core field, which the insertion-order pass resolved before the
# extra field ``comment`` it copies, so it read the unresolved ``None`` (joined into
# the string ``"None"``). Ordered, ``comment`` is computed first.

SAME_NEED_INDEX = """\
Same need
=========

.. req:: The title
   :id: SAME_NEED
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
def test_chain_inside_one_need(test_app):
    """A ``copy`` of the need's own computed field reads the computed value."""
    app = test_app
    app.build()
    need = _built_needs(app)["SAME_NEED"]
    assert (need["status"], need["comment"]) == ("The title", "The title")
    assert build_warnings(app) == []


# -- T2b: ``copy`` with a ``filter`` reads the match it copies from ----------
#
# A filter matching several needs copies from the lowest id. The filter names only
# ``grp``, which nothing computes, so the match is known before the values are
# computed, and the reader waits for that match alone: ``RD_ONE``'s lowest-id match
# ``SRC_A1`` is authored, ``RD_TWO``'s is the computed ``SRC_A2``. Waiting instead for
# every need's ``summary`` (the filter's column) would put each reader on a cycle
# with itself, as both readers write ``summary`` too.

COPY_FILTER_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"summary": {"nullable": True}, "grp": {"nullable": True}}
"""

COPY_FILTER_INDEX = """\
Index
=====

.. req:: Reader one
   :id: RD_ONE
   :summary: [[copy("summary", filter="grp == 'one'")]]

.. req:: Second match, computed, written first
   :id: SRC_B1
   :grp: one
   :summary: [[copy("title")]]

.. req:: First match, authored
   :id: SRC_A1
   :grp: one
   :summary: authored

.. req:: Reader two
   :id: RD_TWO
   :summary: [[copy("summary", filter="grp == 'two'")]]

.. req:: Second match, authored, written first
   :id: SRC_B2
   :grp: two
   :summary: authored

.. req:: done
   :id: SRC_A2
   :grp: two
   :summary: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), COPY_FILTER_CONF),
                (Path("index.rst"), COPY_FILTER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_copy_filter_reads_the_match_it_copies_from(test_app):
    """``copy(filter=)`` waits for the lowest-id match it copies, and is no cycle."""
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["RD_ONE"]["summary"], needs["RD_TWO"]["summary"]) == (
        "authored",
        "done",
    )
    assert build_warnings(app) == []


# -- T3: a whole-project ``calc_sum`` -----------------------------------------
#
# The summands are written after the sum, in the reverse of need-id order: the
# insertion-order pass summed their unresolved ``None`` (dropped), the ordered pass
# sums them computed.

SUM_TWO_INDEX = """\
Sum
===

.. req:: Total
   :id: SUM_ALL
   :total: [[calc_sum("hours")]]

.. req:: Hours two
   :id: HRS_2
   :h0: 6
   :hours: [[copy("h0")]]

.. req:: Hours one
   :id: HRS_1
   :h0: 5
   :hours: [[copy("h0")]]

.. req:: Literal three
   :id: LIT_3
   :hours: 1
"""

SUM_FIVE_INDEX = (
    'Sum\n===\n\n.. req:: Total\n   :id: SUM_ALL\n   :total: [[calc_sum("hours")]]\n'
    + "".join(
        f'\n.. req:: Hours {i}\n   :id: HRS_{i}\n   :h0: {i}\n   :hours: [[copy("h0")]]\n'
        for i in range(5, 0, -1)
    )
)


@pytest.mark.parametrize(
    ("test_app", "total"),
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [(Path("conf.py"), CONF), (Path("index.rst"), SUM_TWO_INDEX)],
            },
            12.0,
            id="two-computed-summands",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [(Path("conf.py"), CONF), (Path("index.rst"), SUM_FIVE_INDEX)],
            },
            15.0,
            id="five-computed-summands",
        ),
    ],
    indirect=["test_app"],
)
def test_calc_sum_over_every_need(test_app, total):
    """A sum over every need runs after every summand it reads: 5 + 6 + 1, and 1 to 5."""
    app = test_app
    app.build()
    assert _built_needs(app)["SUM_ALL"]["total"] == total
    assert build_warnings(app) == []


# -- T4: ``calc_sum(links_only=True)`` ----------------------------------------

OWN_LINKS_INDEX = """\
Own links
=========

.. req:: Other
   :id: OTHER
   :links: HRS_3

.. req:: Hours three
   :id: HRS_3
   :hours: 3

.. req:: Own links
   :id: OWN_LINKS
   :links: [[copy("links", "OTHER")]]
   :total: [[calc_sum("hours", links_only=True)]]
"""

LINKED_SUMMANDS_INDEX = """\
Linked summands
===============

.. req:: Linked hours
   :id: SUM_LINKS
   :links: HRS_2, HRS_3, HRS_1
   :total: [[calc_sum("hours", links_only=True)]]

.. req:: Hours one
   :id: HRS_1
   :h0: 5
   :hours: [[copy("h0")]]

.. req:: Hours two
   :id: HRS_2
   :h0: 6
   :hours: [[copy("h0")]]

.. req:: Hours three
   :id: HRS_3
   :hours: 3
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
def test_calc_sum_links_only_reads_its_own_links(test_app):
    """A ``links_only`` sum reads the need's own ``links``, which a ``[[…]]`` computes.

    The insertion-order pass resolved link fields after the extra fields, so the sum
    read the unresolved empty list and totalled ``0.0``. Link fields are computed
    first now, so the sum reads ``HRS_3``.
    """
    app = test_app
    app.build()
    need = _built_needs(app)["OWN_LINKS"]
    assert (need["total"], need["links"]) == (3.0, ["HRS_3"])
    assert build_warnings(app) == []


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), LINKED_SUMMANDS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_calc_sum_links_only_names_its_computed_targets(test_app):
    """A ``links_only`` sum runs after its computed summands: 6 + 3 + 5."""
    app = test_app
    app.build()
    assert _built_needs(app)["SUM_LINKS"]["total"] == 14.0
    assert build_warnings(app) == []


# -- T5: ``check_linked_values`` ----------------------------------------------

LINKED_VALUES_INDEX = """\
Linked values
=============

.. req:: done
   :id: WORK_1
   :status: [[copy("title")]]

.. req:: Work two
   :id: WORK_2
   :status: done

.. req:: Gate
   :id: GATE_ALL
   :links: WORK_1, WORK_2
   :summary: [[check_linked_values("ready", "status", "done")]]

.. req:: Gate on one hit
   :id: GATE_HIT
   :links: WORK_2, WORK_1
   :summary: [[check_linked_values("ready", "status", "done", one_hit=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), LINKED_VALUES_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_check_linked_values(test_app):
    """``check_linked_values`` runs after every linked value it may read.

    ``GATE_ALL`` reads ``WORK_1``'s computed ``status``; ``GATE_HIT`` stops at its
    first hit, the authored ``WORK_2``, and waits for ``WORK_1`` all the same. Both
    gates open, and nothing is reported.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["GATE_ALL"]["summary"], needs["GATE_HIT"]["summary"]) == (
        "ready",
        "ready",
    )
    assert build_warnings(app) == []


GATE_OWN_LINKS_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"summary": {"nullable": True}}
"""

GATE_OWN_LINKS_INDEX = """\
Index
=====

.. req:: done
   :id: WORK_9

.. req:: Other
   :id: OTHER_9
   :links: WORK_9

.. req:: Gate on computed own links
   :id: GATE_OWN
   :links: [[copy("links", "OTHER_9")]]
   :summary: [[check_linked_values("ready", "status", "done")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), GATE_OWN_LINKS_CONF),
                (Path("index.rst"), GATE_OWN_LINKS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_check_linked_values_reads_its_own_links(test_app):
    """``check_linked_values`` reads the need's own ``links``, which a ``[[…]]`` computes.

    The insertion-order pass resolved link fields after the extra fields, so the check
    walked the unresolved empty list and passed vacuously. Link fields are computed
    first now: the check walks ``WORK_9``, whose ``status`` is unset, and fails. A
    failed check returns ``None``, which leaves the nullable ``summary`` unset (it was
    stored as the text ``"None"``).
    """
    app = test_app
    app.build()
    need = _built_needs(app)["GATE_OWN"]
    assert (need["summary"], need["links"]) == (None, ["WORK_9"])
    assert build_warnings(app) == []


# -- T6: variant conditions ---------------------------------------------------
#
# The insertion-order pass resolved a need's extra fields in the order they are
# declared, so declaring ``f1`` before ``band`` made the condition read the computed
# ``"T"`` (``matched``), declaring it after made it read the unresolved ``None``
# (``unmatched``). A variant is now computed after every field its conditions name.

VARIANT_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {{
    {first}: {{"nullable": True{first_opts}}},
    {second}: {{"nullable": True{second_opts}}},
}}
"""

VARIANT_INDEX = """\
Variant
=======

.. req:: T
   :id: VAR_COND
   :f1: [[copy("title")]]
   :band: <<[f1 == "a"]:early, [f1 == "T"]:matched, unmatched>>
"""


def _variant_conf(*, f1_first: bool) -> str:
    f1 = ('"f1"', "")
    band = ('"band"', ', "parse_variants": True')
    (first, first_opts), (second, second_opts) = (f1, band) if f1_first else (band, f1)
    return VARIANT_CONF.format(
        first=first, first_opts=first_opts, second=second, second_opts=second_opts
    )


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), _variant_conf(f1_first=True)),
                    (Path("index.rst"), VARIANT_INDEX),
                ],
            },
            id="f1-declared-first",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), _variant_conf(f1_first=False)),
                    (Path("index.rst"), VARIANT_INDEX),
                ],
            },
            id="band-declared-first",
        ),
    ],
    indirect=True,
)
def test_variant_condition(test_app):
    """A variant condition naming a computed field of its own need sees it computed.

    Whatever the order the two fields are declared in.
    """
    app = test_app
    app.build()
    assert _built_needs(app)["VAR_COND"]["band"] == "matched"
    assert build_warnings(app) == []


VARIANT_STOP_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "f1": {"nullable": True},
    "f2": {"nullable": True},
    "band": {"nullable": True, "parse_variants": True},
}
needs_variants = {"is_x": 'f2 == "x"'}
"""

VARIANT_STOP_INDEX = """\
Variant
=======

.. req:: x
   :id: VAR_STOP
   :f1: T
   :f2: [[copy("title")]]
   :band: <<[f1 == "T"]:first, [f2 == "x"]:second, neither>>

.. req:: x
   :id: VAR_ON
   :f1: U
   :f2: [[copy("title")]]
   :band: <<[f1 == "T"]:first, [f2 == "x"]:second, neither>>

.. req:: x
   :id: VAR_NAMED
   :f2: [[copy("title")]]
   :band: <<is_x:named, unnamed>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), VARIANT_STOP_CONF),
                (Path("index.rst"), VARIANT_STOP_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_variant_conditions_wait_for_every_field_they_name(test_app):
    """A variant waits for the fields of every condition, evaluated or not.

    ``VAR_STOP``'s first condition, on the authored ``f1``, holds, so its second, on
    the computed ``f2``, is never evaluated; ``VAR_ON``'s first condition does not
    hold, so the second reads ``f2``; ``VAR_NAMED`` names a ``needs_variants`` entry,
    whose expression reads ``f2``. Each is computed after its ``f2``, and nothing is
    reported: the conditions read the values they name, computed.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert [needs[i]["band"] for i in ("VAR_STOP", "VAR_ON", "VAR_NAMED")] == [
        "first",
        "second",
        "named",
    ]
    assert build_warnings(app) == []


# -- T7: a call that a ``needextend`` sets --------------------------------------

EXTENDED_SUMMAND_INDEX = """\
Extended summand
================

.. req:: Total
   :id: SUM_ALL
   :total: [[calc_sum("hours")]]

.. req:: Literal two
   :id: LIT_2
   :hours: 2

.. req:: Literal three
   :id: LIT_3
   :h0: 1
   :hours: 1

.. needextend:: LIT_3
   :hours: [[copy("h0")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), EXTENDED_SUMMAND_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_call_set_by_needextend_is_a_computed_value(test_app):
    """A field a ``needextend`` sets to a ``[[…]]`` is computed in the pass, and waited for.

    The sum reads ``LIT_3``'s computed ``1.0``, not the ``1`` it held before the extend
    (the same number here, so the total is ``3.0`` either way), and nothing is reported.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["SUM_ALL"]["total"], needs["LIT_3"]["hours"]) == (3.0, 1.0)
    assert build_warnings(app) == []


# -- T8: a call that fails because of what it read ----------------------------
#
# ``WORK_1`` and ``WORK_2`` copy each other's ``comment``: a cycle, so both are left
# at the empty value of the nullable ``comment``, ``None``, and each is reported.
# ``MIRROR`` copies ``WORK_1``'s ``comment`` once the cycle is settled, reads that
# ``None``, which the non-nullable string ``summary`` refuses: the existing
# ``needs.dynamic_function`` warning says the call failed, and the cycle's, emitted
# before it, says why. Each is suppressed on its own.

FAILING_READ_INDEX = """\
Failing read
============

.. req:: Mirror
   :id: MIRROR
   :summary: [[copy("comment", "WORK_1")]]

.. req:: Work one
   :id: WORK_1
   :comment: [[copy("comment", "WORK_2")]]

.. req:: Work two
   :id: WORK_2
   :comment: [[copy("comment", "WORK_1")]]
"""

FAILING_READ_FILES = [(Path("conf.py"), CONF), (Path("index.rst"), FAILING_READ_INDEX)]

TYPE_CHECK_WARNING = (
    "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
    "'summary', of need 'MIRROR': dynamic function value <class 'NoneType'> is not of "
    "type 'string' [needs.dynamic_function]"
)


WORK_CYCLE = (
    "dynamic function 'copy' for option 'comment' is on a cycle: "
    "'comment' on 2 needs (WORK_1, WORK_2); the field is left empty"
)


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            {"buildername": "needs", "files": FAILING_READ_FILES},
            [
                _warning("index.rst:8", WORK_CYCLE, "derive_cycle"),
                _warning("index.rst:12", WORK_CYCLE, "derive_cycle"),
                TYPE_CHECK_WARNING,
            ],
            id="both",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": FAILING_READ_FILES,
                "confoverrides": SUPPRESSED,
            },
            [TYPE_CHECK_WARNING],
            id="derive-cycle-suppressed",
        ),
    ],
    indirect=["test_app"],
)
def test_a_failing_call_still_says_what_it_read(test_app, expected):
    """A call that fails on a cycle's empty value is reported after the cycle.

    The two subtypes are separate: suppressing the cycle keeps the failure.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert [needs[i]["comment"] for i in ("WORK_1", "WORK_2")] == [None, None]
    assert needs["MIRROR"]["summary"] == ""
    assert build_warnings(app) == expected


# -- T9: what is not reported -------------------------------------------------

NEGATIVES_INDEX = """\
Negatives
=========

.. req:: Literal source
   :id: LIT_SRC
   :comment: authored
   :hours: 2

.. req:: Copies and sums authored values
   :id: READS_LIT
   :summary: [[copy("comment", "LIT_SRC")]]
   :total: [[calc_sum("hours")]]

.. req:: Computed source
   :id: DYN_SRC
   :comment: [[copy("title")]]

.. req:: Links from content
   :id: FROM_CONTENT
   :links: [[links_from_content()]]

   Realises :need:`DYN_SRC`.

.. req:: Renders a computed value
   :id: RENDERS

   Rendered: :ndf:`copy("comment", "DYN_SRC")`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), NEGATIVES_INDEX)],
        }
    ],
    indirect=True,
)
def test_reads_of_authored_or_final_values_are_not_reported(test_app):
    """Reads of authored values, and reads after the pass, are not reported.

    A ``copy`` of an authored field and a sum of authored summands read nothing
    computed. ``links_from_content`` reads the document, not fields. An ``ndf`` role
    runs when the page is written, after the pass, where every value is final:
    it renders ``DYN_SRC``'s computed ``comment`` and reports nothing.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Rendered: Computed source." in html


SHADOWED_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"band": {"nullable": True, "parse_variants": True}}
needs_filter_data = {"status": "x"}
"""

SHADOWED_INDEX = """\
Shadowed
========

.. req:: T
   :id: VAR_SHADOW
   :status: [[copy("title")]]
   :band: <<[status == "x"]:matched, unmatched>>
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), SHADOWED_CONF),
                (Path("index.rst"), SHADOWED_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_condition_name_given_by_filter_data_is_not_a_field_read(test_app):
    """A name ``needs_filter_data`` supplies is read from there, not from the need.

    In a variant condition, ``needs_filter_data`` (and ``build_tags``, and ``var``)
    take precedence over the need's own fields. The configuration refuses a filter
    name equal to an extra field, but not to a core field: ``status`` here is the
    configured ``"x"``, not the need's computed ``"T"``, so it is not a read of a
    computed value.
    """
    app = test_app
    app.build()
    need = _built_needs(app)["VAR_SHADOW"]
    assert (need["status"], need["band"]) == ("T", "matched")
    assert build_warnings(app) == [
        "WARNING: needs_filter_data is deprecated and will be removed in a future "
        "version. Use needs_variant_data instead. [needs.deprecated]"
    ]


SUPPRESSED_INDEX = """\
Suppressed
==========

.. req:: Work one
   :id: WORK_1
   :comment: [[copy("comment", "WORK_2")]]

.. req:: Work two
   :id: WORK_2
   :comment: [[copy("comment", "WORK_1")]]
   :links: [[copy("links_back")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), SUPPRESSED_INDEX),
                ],
                "confoverrides": SUPPRESSED,
            },
            id="cycle-and-scope",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": CHAIN_FORWARD,
                "confoverrides": {"suppress_warnings": ["needs.derive_unresolved"]},
            },
            id="retired-type-is-a-no-op",
        ),
    ],
    indirect=True,
)
def test_suppressed(test_app):
    """``suppress_warnings`` silences ``needs.derive_cycle`` and ``needs.derive_scope``.

    ``needs.derive_unresolved`` is retired: an entry naming it is a silent no-op (Sphinx
    does not warn about an unknown entry), and the chain it reported resolves.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)


def test_listed_with_the_build_warnings():
    """The subtypes are in the list the documentation renders for ``suppress_warnings``."""
    assert "derive_unresolved" not in get_args(WarningSubTypes)
    assert {"derive_cycle", "derive_scope"} <= set(get_args(WarningSubTypes))
    assert WarningSubTypeDescription["derive_cycle"] == (
        "A dynamic function or variant is on a cycle of computed values; "
        "the field is not computed"
    )
    assert WarningSubTypeDescription["derive_scope"] == (
        "A dynamic function, variant or needextend filter reads a value "
        "that cannot be computed before it"
    )


# -- T10: neither the value nor the warning depends on the build history -------


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "files": CHAIN_FORWARD}], indirect=True
)
def test_the_warning_does_not_depend_on_the_build_history(test_app):
    """An incremental build re-reading the reader gives the same value, and no warning.

    Re-reading ``index.rst`` purges ``CHAIN_A`` and inserts it again after
    ``CHAIN_B``, which made the insertion-order pass resolve ``CHAIN_B`` first only in
    the second build: the value flipped with the build history. Ordered, both builds
    give ``"Middle"``.
    """
    app = test_app
    app.build()
    first = build_warnings(app)
    first_value = _built_needs(app)["CHAIN_A"]["summary"]
    first_status_length = len(app._status.getvalue())

    # newer than the time the first build read it, whatever the file system's clock
    # resolution, so the second build re-reads ``index.rst`` and nothing else
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "index.rst"), ns=(later, later))
    app.build()
    assert (
        "0 added, 1 changed, 0 removed" in app._status.getvalue()[first_status_length:]
    )
    second = build_warnings(app)[len(first) :]
    second_value = _built_needs(app)["CHAIN_A"]["summary"]

    assert (first_value, second_value) == ("Middle", "Middle")
    assert first == second == []


# -- T10b: a filter that reads a computed field --------------------------------
#
# A filter on a computed field used to decide, by the order of the pass, which needs
# it kept. The ordered pass computes every need's value of each field a filter names
# before the filter runs, so the kept set, and the total, no longer depend on the
# build history. ``TGT_F``'s ``summary`` is ``"done"`` once computed.

FILTERED_INDEX = """\
Index
=====

.. toctree::

   a
   b
"""

FILTERED_READERS = """\
A
=

.. req:: Filtered sum
   :id: RD_FLT
   :total: [[calc_sum("hours", "summary == 'done'")]]

.. req:: Filtered gate
   :id: RD_GFLT
   :links: TGT_F
   :summary: [[check_linked_values("ready", "hours", 3, "summary == 'done'")]]
"""

FILTERED_TARGET = """\
B
=

.. req:: done
   :id: TGT_F
   :summary: [[copy("title")]]
   :h0: 3
   :hours: [[copy("h0")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), FILTERED_INDEX),
                (Path("a.rst"), FILTERED_READERS),
                (Path("b.rst"), FILTERED_TARGET),
            ],
        }
    ],
    indirect=True,
)
def test_a_filter_on_a_computed_field_does_not_decide_the_warning(test_app):
    """A filtered ``calc_sum`` gives the same total on every build, and no warning.

    The first build reads ``a.rst`` before ``b.rst``, which made the insertion-order
    filter see ``TGT_F``'s unresolved ``summary`` and drop it (the sum was ``0.0``),
    and re-reading ``a.rst`` keep it (``3.0``). Ordered, the filter sees the computed
    ``summary`` in both builds.
    """
    app = test_app
    app.build()
    first = build_warnings(app)
    first_total = _built_needs(app)["RD_FLT"]["total"]
    first_status_length = len(app._status.getvalue())

    # newer than the time the first build read it, whatever the file system's clock
    # resolution, so the second build re-reads ``a.rst`` and nothing else
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "a.rst"), ns=(later, later))
    app.build()
    assert (
        "0 added, 1 changed, 0 removed" in app._status.getvalue()[first_status_length:]
    )
    second = build_warnings(app)[len(first) :]
    second_total = _built_needs(app)["RD_FLT"]["total"]

    assert (first_total, second_total) == (3.0, 3.0)
    assert first == second == []


# -- T11: ubCode's fixture -------------------------------------------------------


def _locations(app) -> dict[str, int]:
    """Each need's line, by id, from the ``needs.json`` the last build wrote."""
    return {need_id: need["lineno"] for need_id, need in _built_needs(app).items()}


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_df_unresolved"}],
    indirect=True,
)
def test_ubcode_fixture(test_app):
    """ubCode's ``dynamic_functions_unresolved`` fixture: the phase-1 values and findings.

    The project is ubCode's build fixture
    ``rust/ubc_parser_ctrl/tests/build_fixtures/dynamic_functions_unresolved``, with
    one adaptation, for what sphinx-needs refuses: ``hours``' default moves from its
    ``schema`` (``schema = { type = "number", default = 0.0 }``) to the field
    (``[needs.fields.hours] default = 0.0``). Phase 0 reported twelve reads here as
    ``needs.derive_unresolved``; ordered, every value is the chained one, and what
    remains is what ubCode's phase 1 reports too: the cycle ``CYC_A`` / ``CYC_B``
    (both empty, one ``needs.derive_cycle`` each), and ``NEED_ATTR``, whose call
    selects its need by ``need.parent``, computed in the same step
    (``needs.derive_scope``, the field empty and the call not run). The two
    ``needs.dynamic_function`` failures of phase 0 (``GATE_1`` and ``MIRROR_VAR`` read
    an unresolved ``None``) are gone: they read computed values now.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    computed = {
        need_id: {field: needs[need_id][field] for field in fields}
        for need_id, fields in {
            "CHAIN_A": ["summary"],
            "CHAIN_B": ["summary"],
            "CHAIN_C": ["summary"],
            "SAME_NEED": ["status", "comment"],
            "SUM_ALL": ["total"],
            "SUM_ALL2": ["total"],
            "SUM_LINKS": ["total"],
            "GATE_1": ["summary"],
            "CYC_A": ["summary"],
            "CYC_B": ["summary"],
            "VAR_COND": ["f1", "band"],
            "MIRROR_VAR": ["summary"],
            "MIRROR_LIT": ["total"],
            "NEED_ATTR": ["parent", "summary"],
            "OWN_LINKS": ["links", "total"],
            "HRS_1": ["hours"],
            "LIT_3": ["hours"],
            "OWN_COPY": ["status"],
        }.items()
    }
    assert computed == {
        "CHAIN_A": {"summary": "done"},
        "CHAIN_B": {"summary": "done"},
        "CHAIN_C": {"summary": "done"},
        "SAME_NEED": {"status": "The title", "comment": "The title"},
        "SUM_ALL": {"total": 21.0},
        "SUM_ALL2": {"total": 21.0},
        "SUM_LINKS": {"total": 8.0},
        "GATE_1": {"summary": "ready"},
        "CYC_A": {"summary": ""},
        "CYC_B": {"summary": ""},
        "VAR_COND": {"f1": "T", "band": "matched"},
        "MIRROR_VAR": {"summary": "yes"},
        "MIRROR_LIT": {"total": 4.0},
        "NEED_ATTR": {"parent": "HRS_3", "summary": ""},
        "OWN_LINKS": {"links": ["HRS_3", "LIT_1"], "total": 7.0},
        "HRS_1": {"hours": 5.0},
        "LIT_3": {"hours": 1.0},
        "OWN_COPY": {"status": "done"},
    }
    line = _locations(app)
    cycle = (
        "dynamic function 'copy' for option 'summary' is on a cycle: "
        "'summary' on 2 needs (CYC_A, CYC_B); the field is left empty"
    )
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_options" is deprecated. '
        'Please use "needs_fields" instead. [needs.deprecated]',
        _warning(f"index.rst:{line['CYC_A']}", cycle, "derive_cycle"),
        _warning(f"index.rst:{line['CYC_B']}", cycle, "derive_cycle"),
        _warning(
            f"index.rst:{line['NEED_ATTR']}",
            "dynamic function 'copy' for option 'summary' names its target by "
            "'need.parent', which is computed in the same step: the call is not run "
            "and the field is left empty",
            "derive_scope",
        ),
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_df_own_field_copy"}],
    indirect=True,
)
def test_ubcode_own_field_copy_fixture(test_app):
    """ubCode's ``dynamic_functions_own_field_copy`` fixture: the values of its scratch build.

    The pages and ``ubproject.toml`` are the fixture's, verbatim. ``BACKLINK`` copies
    its own back links into an array field, and no need links to it: the empty list,
    ``[]``, as a back link list with no link is. (ubCode's phase 1 stores ``null`` for
    it until its own fix; every other value here is the one it stores.)
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert {
        need_id: {field: needs[need_id][field] for field in fields}
        for need_id, fields in {
            "OWN_BESIDE": ["summary"],
            "OWN_EXTENDED": ["summary"],
            "MIRROR_POS": ["summary"],
            "BACKLINK": ["incoming"],
            "OWN_MOVED": ["line"],
        }.items()
    } == {
        "OWN_BESIDE": {"summary": "open"},
        "OWN_EXTENDED": {"summary": "open"},
        "MIRROR_POS": {"summary": "open"},
        "BACKLINK": {"incoming": []},
        "OWN_MOVED": {"line": 4},
    }
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_options" is deprecated. '
        'Please use "needs_fields" instead. [needs.deprecated]',
    ]


# -- T12: who is handed the record ---------------------------------------------------
#
# The pass hands each call's record to the built-ins marked ``records_reads``, as their
# keyword-only ``reads``, and to nothing else: a user's function is called exactly as
# before, and a built-in called anywhere but by the pass itself (an ``ndf`` role, a
# ``:style_row:``, a direct call, a user's function) gets ``reads=None`` and notes nothing.
# A user's function runs after every built-in function of its stratum, so it reads
# the values the built-ins computed.

USER_FUNCTIONS_CONF = (
    CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled, which
# is not what these tests are about
suppress_warnings = ["config.cache"]

from sphinx_needs.functions.common import copy


def shout(app, need, needs, text):
    # the plain signature: a ``reads`` keyword would be a TypeError
    return text.upper()


def mirror(app, need, needs, need_id):
    # another need's field, read through a built-in
    return copy(app, need, needs, "summary", need_id)


needs_functions = [shout, mirror]
"""
)

PLAIN_USER_FUNCTION_INDEX = """\
User function
=============

.. req:: Plain
   :id: PLAIN
   :summary: [[shout("quiet")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), USER_FUNCTIONS_CONF),
                (Path("index.rst"), PLAIN_USER_FUNCTION_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_user_function_is_called_without_the_record(test_app):
    """A user's function, which is not marked, is called with no ``reads`` in the pass.

    ``shout`` takes no ``**kwargs``, so a ``reads`` keyword would end the call in a
    ``TypeError`` and a ``needs.dynamic_function`` warning.
    """
    app = test_app
    app.build()
    assert _built_needs(app)["PLAIN"]["summary"] == "QUIET"
    assert_no_warnings(app)


USER_FUNCTION_READS_INDEX = """\
User function
=============

.. req:: Mirror
   :id: MIRROR_USER
   :summary: [[mirror("CHAIN_B")]]

.. req:: Middle
   :id: CHAIN_B
   :summary: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), USER_FUNCTIONS_CONF),
                (Path("index.rst"), USER_FUNCTION_READS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_builtin_a_user_function_calls_is_not_reported(test_app):
    """A built-in called by a user's function in the pass is handed no record.

    ``mirror`` copies ``CHAIN_B``'s computed ``summary`` through ``copy``. It runs after
    the built-in functions, so it reads the computed value, although ``CHAIN_B`` comes
    later (the insertion-order pass gave it the unresolved ``""``); the user's function
    has no record to pass on, and nothing is reported.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["MIRROR_USER"]["summary"], needs["CHAIN_B"]["summary"]) == (
        "Middle",
        "Middle",
    )
    assert_no_warnings(app)


WRAPPED_BUILTIN_CONF = (
    CONF
    + """\
# Sphinx's own warning that a function in the configuration is not pickled, which
# is not what these tests are about
suppress_warnings = ["config.cache"]

import functools

from sphinx_needs.functions.common import copy


@functools.wraps(copy)
def narrowcopy(app, need, needs, option, need_id=None):
    # a narrower signature than the built-in's, without **kwargs
    return copy(app, need, needs, option, need_id, upper=True)


@functools.wraps(copy)
def forwardcopy(app, need, needs, *args, **kwargs):
    # forwards whatever it is given to the built-in
    return copy(app, need, needs, *args, **kwargs)


# ``functools.wraps`` copied the built-in's name too
narrowcopy.__name__ = "narrowcopy"
forwardcopy.__name__ = "forwardcopy"

needs_functions = [narrowcopy, forwardcopy]
"""
)

WRAPPED_BUILTIN_INDEX = """\
Wrapped built-in
================

.. req:: narrow
   :id: U_NARROW
   :summary: [[narrowcopy("title")]]

.. req:: Forward
   :id: U_FORWARD
   :summary: [[forwardcopy("summary", "CHAIN_B")]]

.. req:: Middle
   :id: CHAIN_B
   :summary: [[copy("title")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), WRAPPED_BUILTIN_CONF),
                (Path("index.rst"), WRAPPED_BUILTIN_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_user_wrapper_of_a_builtin_is_not_handed_the_record(test_app):
    """A user's function made with ``functools.wraps(copy)`` is a user's function.

    ``functools.wraps`` copies the built-in's attributes, its mark included, but the
    mark names the function it was set on, so the wrapper is not marked: ``narrowcopy``,
    which takes no ``**kwargs``, is called without ``reads`` and resolves, and
    ``forwardcopy``, which would forward a record to ``copy``, has none to forward. As a
    user's function it runs after the built-ins, so its read of ``CHAIN_B``'s computed
    ``summary`` sees ``"Middle"`` (the insertion-order pass gave it ``""``).
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["U_NARROW"]["summary"], needs["U_FORWARD"]["summary"]) == (
        "NARROW",
        "Middle",
    )
    assert_no_warnings(app)


AFTER_THE_PASS_INDEX = """\
After the pass
==============

.. req:: Hours
   :id: HRS_1
   :h0: 5
   :hours: [[copy("h0")]]

.. req:: done
   :id: WORK_1
   :status: [[copy("title")]]

.. req:: Renders
   :id: RENDERS
   :links: WORK_1

   Sum :ndf:`calc_sum("hours")`, copy :ndf:`copy("hours", "HRS_1")`,
   gate :ndf:`check_linked_values("ready", "status", "done")`.

.. needtable::
   :filter: id == "WORK_1"
   :style_row: [[copy("status")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), AFTER_THE_PASS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_builtin_called_after_the_pass_notes_nothing(test_app):
    """The built-ins called with no ``reads`` resolve and report nothing.

    The ``ndf`` roles and the ``:style_row:`` run after the pass, through
    ``execute_func``, which passes no ``reads``: each read of a computed value there
    renders the final value and is not reported. A direct ``execute_func`` call after
    the build does the same.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Sum 5.0, copy 5.0,\ngate ready." in html
    assert re.search(r'<tr class="[^"]*\bdone\b[^"]*" data-need-id="WORK_1"', html)

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert execute_func(app, needs["RENDERS"], needs, 'calc_sum("hours")', None) == 5.0
    assert_no_warnings(app)


RESERVED_INDEX = """\
Reserved
========

.. req:: Reserved keyword
   :id: RESERVED
   :summary: [[copy("title", reads=1)]]

   Rendered: :ndf:`copy("title", reads=1)`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), RESERVED_INDEX)],
        }
    ],
    indirect=True,
)
def test_reads_written_in_a_call_is_an_error(test_app):
    """``reads`` is reserved: written in a call, it fails that call, not the build.

    In the pass, the resolver's own ``reads`` meets the written one; in an ``ndf`` role,
    the written value is not a record. Either way the call ends in the usual
    ``needs.dynamic_function`` warning (Python's own words, so matched loosely) and the
    role renders ``??``.
    """
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 2, warnings
    assert re.fullmatch(
        r"<srcdir>/index\.rst:4: WARNING: Error while resolving dynamic values for "
        r"field 'summary', of need 'RESERVED': Error while executing function 'copy': "
        r".*got multiple values for keyword argument 'reads' \[needs\.dynamic_function\]",
        warnings[0],
    ), warnings[0]
    assert re.fullmatch(
        r"<srcdir>/index\.rst:8: WARNING: Error while executing function 'copy': "
        r".+ \[needs\.dynamic_function\]",
        warnings[1],
    ), warnings[1]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Rendered: ??." in html


def test_the_builtins_take_the_record_only_as_a_keyword_defaulting_to_none():
    """The record reaches a built-in only as the argument the pass gives it.

    ``reads`` is keyword-only and defaults to ``None``: a shared record as the default
    would be module-level state again, noted into by every call made outside the pass
    and never reported.
    """
    for function in (copy, calc_sum, check_linked_values):
        parameter = inspect.signature(function).parameters["reads"]
        assert parameter.kind is parameter.KEYWORD_ONLY, function.__name__
        assert parameter.default is None, function.__name__
