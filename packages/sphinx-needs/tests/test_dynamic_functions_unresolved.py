"""``needs.derive_unresolved``: a read of a value computed in the same pass.

All dynamic functions and variants are resolved in one pass, need by need, in the
order the needs reached the build environment, writing each result into the need
as it goes. A ``[[…]]`` or ``<<…>>`` that reads a field which itself carries a
``[[…]]``, ``<<…>>`` or ``<{…}>`` (on another need, or on its own need) therefore
reads either the computed value or the unresolved one, depending on that order,
which changes with document names, with the documents the last build re-read and
with ``-j``. Each such read is reported once per reading call, at the reading need.

The rule is the read field's presence in the read need's dynamic fields (after
``needextend``), never whether the pass has reached that need yet: the second
would make the warning itself depend on the build history. So a read is reported
even where today's value happens to be the computed one, and the tests below pin
that with a layout in each direction. It is the rule ubCode reports the same reads
by (as an Info-graded ``needs.derive_unresolved``), and the last test runs ubCode's
own fixture for it.
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

#: the tail every message ends with: true whether or not the read value was computed yet
TAIL = (
    "a dynamic function or variant computed in the same pass: "
    "the value read depends on the order the needs are resolved in"
)


def _warning(location: str, head: str, *, carries: str = "carries") -> str:
    """One ``needs.derive_unresolved`` warning, as ``build_warnings`` normalises it."""
    return f"<srcdir>/{location}: WARNING: {head}, which {carries} {TAIL} [needs.derive_unresolved]"


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

SUPPRESSED = {"suppress_warnings": ["needs.derive_unresolved"]}


# -- the message --------------------------------------------------------------
#
# ubCode's head (``{what} for option '{option}' read {read}``), then a tail that is
# true under the presence rule: ubCode's own tail says the read saw the value before
# it was resolved, which here holds only when the pass had not reached the target yet.


@pytest.mark.parametrize(
    ("what", "option", "reads", "expected"),
    [
        pytest.param(
            "dynamic function 'copy'",
            "summary",
            [("summary", ["CHAIN_B"])],
            "dynamic function 'copy' for option 'summary' read 'summary' on need 'CHAIN_B', "
            f"which carries {TAIL}",
            id="one-id",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["HRS_1", "HRS_2"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 2 needs (HRS_1, HRS_2), "
            f"which carry {TAIL}",
            id="two-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["HRS_1", "HRS_2", "LIT_3"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 3 needs (HRS_1, HRS_2, LIT_3), "
            f"which carry {TAIL}",
            id="three-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", ["A_1", "A_2", "A_3", "A_4"])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 4 needs (A_1, A_2, A_3 and 1 more), "
            f"which carry {TAIL}",
            id="four-ids",
        ),
        pytest.param(
            "dynamic function 'calc_sum'",
            "total",
            [("hours", [f"A_{i}" for i in range(1, 11)])],
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 10 needs (A_1, A_2, A_3 and 7 more), "
            f"which carry {TAIL}",
            id="ten-ids",
        ),
        pytest.param(
            "dynamic function 'check_linked_values'",
            "summary",
            [("links", ["GATE"]), ("status", ["WORK_1"])],
            "dynamic function 'check_linked_values' for option 'summary' "
            "read 'links' on need 'GATE' and 'status' on need 'WORK_1', "
            f"which carry {TAIL}",
            id="two-names",
        ),
        pytest.param(
            "variant condition",
            "band",
            [("f1", ["V"]), ("f2", ["V"]), ("f3", ["V", "W"])],
            "variant condition for option 'band' "
            "read 'f1' on need 'V', 'f2' on need 'V' and 'f3' on 2 needs (V, W), "
            f"which carry {TAIL}",
            id="three-names-variant",
        ),
        pytest.param(
            "variant condition",
            "band",
            [("f1", ["VAR_COND"])],
            "variant condition for option 'band' read 'f1' on need 'VAR_COND', "
            f"which carries {TAIL}",
            id="variant-one-id",
        ),
    ],
)
def test_message_shape(what, option, reads, expected):
    """The message names each name once, with its one need or a count and the first three.

    Several names are joined as ubCode joins them (``a, b and c``). ``carries`` is
    singular only for one name read on one need. Imported here rather than at the
    top so that, before the formatter exists, only these tests fail on the import
    and the build tests below fail on their own assertions.
    """
    from sphinx_needs.functions.functions import (
        _derive_unresolved_message,
    )

    assert _derive_unresolved_message(what, option, reads) == expected


def test_message_needs_a_read():
    """A record with no read is never formatted: there is nothing to say."""
    from sphinx_needs.functions.functions import (
        _derive_unresolved_message,
    )

    with pytest.raises(ValueError, match="no read"):
        _derive_unresolved_message("variant condition", "band", [])


# -- T1: a chain across needs, in both layouts --------------------------------
#
# ``CHAIN_A`` copies ``CHAIN_B``'s ``summary``, which ``CHAIN_B`` copies from its
# title. ``CHAIN_A`` is on ``index.rst``; ``CHAIN_B`` is on ``z.rst`` (read after
# ``index``, so ``CHAIN_A`` reads the unresolved ``""``) or on ``a.rst`` (read
# before, so it reads the computed ``"Middle"``). Both layouts report the one read,
# at the same location and in the same words: which value the read saw is an
# accident of document names, and it flips on an incremental build (T10).

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

CHAIN_WARNINGS = [
    "<srcdir>/index.rst:8: WARNING: dynamic function 'copy' for option 'summary' "
    "read 'summary' on need 'CHAIN_B', which carries a dynamic function or variant "
    "computed in the same pass: the value read depends on the order the needs are "
    "resolved in [needs.derive_unresolved]"
]


@pytest.mark.parametrize(
    ("test_app", "chained"),
    [
        pytest.param(
            {"buildername": "needs", "files": CHAIN_FORWARD}, "", id="target-later"
        ),
        pytest.param(
            {"buildername": "needs", "files": CHAIN_REVERSE},
            "Middle",
            id="target-earlier",
        ),
        pytest.param(
            {"buildername": "needs", "files": CHAIN_FORWARD, "parallel": 2},
            None,
            id="target-later-parallel",
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        ),
    ],
    indirect=["test_app"],
)
def test_chain_across_needs(test_app, chained):
    """A ``copy`` of another need's computed field is reported, whichever value it saw.

    One warning, at the reader ``CHAIN_A``; none at ``CHAIN_B``, whose read of its
    own ``title`` reads an authored value. The value check proves the two layouts
    really differ: the target authored later leaves ``CHAIN_A`` the unresolved
    ``""``, the target authored earlier gives it the computed ``"Middle"``, and the
    warning is the same for both. Under ``-j`` the order the needs reach the
    environment depends on which worker finishes first (so no value is asserted),
    and the warning is still the same.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert needs["CHAIN_B"]["summary"] == "Middle"
    if chained is not None:
        assert needs["CHAIN_A"]["summary"] == chained
    assert build_warnings(app) == CHAIN_WARNINGS


# -- T2: a chain inside one need ----------------------------------------------
#
# ``status`` is a core field, so it is resolved before the extra field ``comment``
# it copies, and reads its unresolved ``None`` (joined into the string ``"None"``).

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
    """A ``copy`` of the need's own computed field is reported, naming the need itself."""
    app = test_app
    app.build()
    need = _built_needs(app)["SAME_NEED"]
    assert need["comment"] == "The title"
    assert need["status"] != "The title"
    assert build_warnings(app) == [
        _warning(
            "index.rst:4",
            "dynamic function 'copy' for option 'status' read 'comment' on need 'SAME_NEED'",
        )
    ]


# -- T2b: ``copy`` with a ``filter`` reads the match it copies from ----------
#
# A filter matching several needs copies from the lowest id. The read reported is
# that match's, not the first match in the order the needs were read: ``RD_ONE``'s
# lowest-id match ``SRC_A1`` is authored (the computed ``SRC_B1`` comes first but is
# not read), ``RD_TWO``'s is the computed ``SRC_A2`` (the authored ``SRC_B2`` comes
# first but is not read).

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
    """``copy(filter=)`` is reported for the lowest-id match it copies, and only for it."""
    app = test_app
    app.build()
    assert _built_needs(app)["RD_ONE"]["summary"] == "authored"
    assert build_warnings(app) == [
        _warning(
            "index.rst:18",
            "dynamic function 'copy' for option 'summary' read 'summary' on need 'SRC_A2'",
        )
    ]


# -- T3: a whole-project ``calc_sum`` -----------------------------------------
#
# The summands are written in the reverse of need-id order, and the message names
# them in need-id order, the order the sum reads them in.

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
    ("test_app", "read"),
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [(Path("conf.py"), CONF), (Path("index.rst"), SUM_TWO_INDEX)],
            },
            "'hours' on 2 needs (HRS_1, HRS_2)",
            id="two-computed-summands",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [(Path("conf.py"), CONF), (Path("index.rst"), SUM_FIVE_INDEX)],
            },
            "'hours' on 5 needs (HRS_1, HRS_2, HRS_3 and 2 more)",
            id="five-computed-summands",
        ),
    ],
    indirect=["test_app"],
)
def test_calc_sum_over_every_need(test_app, read):
    """One warning per summing call, naming each computed summand once, in need-id order.

    The authored ``LIT_3`` is not named; four or more computed summands name the
    first three and count the rest.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _warning(
            "index.rst:4",
            f"dynamic function 'calc_sum' for option 'total' read {read}",
            carries="carry",
        )
    ]


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

    Link fields are resolved after the extra fields, so the sum reads the
    unresolved empty list and totals ``0.0``; the ``links`` call itself copies an
    authored value and is not reported.
    """
    app = test_app
    app.build()
    need = _built_needs(app)["OWN_LINKS"]
    assert (need["total"], need["links"]) == (0.0, ["HRS_3"])
    assert build_warnings(app) == [
        _warning(
            "index.rst:12",
            "dynamic function 'calc_sum' for option 'total' read 'links' on need 'OWN_LINKS'",
        )
    ]


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
    """A ``links_only`` sum names its computed summands in the order of the links."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _warning(
            "index.rst:4",
            "dynamic function 'calc_sum' for option 'total' read 'hours' on 2 needs (HRS_2, HRS_1)",
            carries="carry",
        )
    ]


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
    """``check_linked_values`` is reported for the computed values it actually reads.

    ``GATE_ALL`` reads ``WORK_1``'s computed ``status`` (here already computed, as
    ``WORK_1`` is written first, so the gate opens; reported all the same).
    ``GATE_HIT`` stops at its first hit, the authored ``WORK_2``, and never reads
    ``WORK_1``: nothing to report.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["GATE_ALL"]["summary"], needs["GATE_HIT"]["summary"]) == (
        "ready",
        "ready",
    )
    assert build_warnings(app) == [
        _warning(
            "index.rst:12",
            "dynamic function 'check_linked_values' for option 'summary' read 'status' on need 'WORK_1'",
        )
    ]


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

    Link fields are resolved after the extra fields, so the check walks the unresolved
    empty list (and passes vacuously); the ``links`` call itself copies an authored
    value and is not reported.
    """
    app = test_app
    app.build()
    need = _built_needs(app)["GATE_OWN"]
    assert (need["summary"], need["links"]) == ("ready", ["WORK_9"])
    assert build_warnings(app) == [
        _warning(
            "index.rst:11",
            "dynamic function 'check_linked_values' for option 'summary' read 'links' on need 'GATE_OWN'",
        )
    ]


# -- T6: variant conditions ---------------------------------------------------
#
# Within a need, extra fields are resolved in the order they are declared, so
# declaring ``f1`` before ``band`` makes the condition read the computed ``"T"``
# (``matched``), declaring it after makes it read the unresolved ``None``
# (``unmatched``). The condition names ``f1`` twice; it is named once.

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
    ("test_app", "band"),
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (Path("conf.py"), _variant_conf(f1_first=True)),
                    (Path("index.rst"), VARIANT_INDEX),
                ],
            },
            "matched",
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
            "unmatched",
            id="band-declared-first",
        ),
    ],
    indirect=["test_app"],
)
def test_variant_condition(test_app, band):
    """A variant condition naming a computed field of its own need is reported.

    The same warning for both declaration orders, although one condition saw the
    computed value and the other the unresolved one.
    """
    app = test_app
    app.build()
    assert _built_needs(app)["VAR_COND"]["band"] == band
    assert build_warnings(app) == [
        _warning(
            "index.rst:4",
            "variant condition for option 'band' read 'f1' on need 'VAR_COND'",
        )
    ]


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
def test_variant_condition_reads_only_the_expressions_it_evaluates(test_app):
    """The names read are those of the expressions evaluated, up to the first true one.

    ``VAR_STOP``'s first condition, on the authored ``f1``, holds, so its second,
    on the computed ``f2``, is never evaluated: nothing to report. ``VAR_ON``'s
    first condition does not hold, so the second is evaluated and reads ``f2``.
    ``VAR_NAMED`` names a ``needs_variants`` entry, whose expression reads ``f2``.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert [needs[i]["band"] for i in ("VAR_STOP", "VAR_ON", "VAR_NAMED")] == [
        "first",
        "second",
        "named",
    ]
    assert build_warnings(app) == [
        _warning(
            "index.rst:10",
            "variant condition for option 'band' read 'f2' on need 'VAR_ON'",
        ),
        _warning(
            "index.rst:16",
            "variant condition for option 'band' read 'f2' on need 'VAR_NAMED'",
        ),
    ]


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
    """A field a ``needextend`` sets to a ``[[…]]`` is computed in the pass, so it is named.

    The sum reads ``LIT_3``'s value from before the extend (``1``), so the total is
    ``3.0`` although ``LIT_3`` resolves to the same ``1.0``: what matters is the call
    the need carries after the extends, not what the field held when it was written.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["SUM_ALL"]["total"], needs["LIT_3"]["hours"]) == (3.0, 1.0)
    assert build_warnings(app) == [
        _warning(
            "index.rst:4",
            "dynamic function 'calc_sum' for option 'total' read 'hours' on need 'LIT_3'",
        )
    ]


# -- T8: a call that fails because of what it read ----------------------------
#
# ``MIRROR`` is written before ``WORK_1``, so it copies ``WORK_1``'s unresolved
# ``status``, ``None``, which the non-nullable string ``summary`` refuses. The
# existing ``needs.dynamic_function`` warning says the call failed; the new one,
# emitted first, says why. Each is suppressed on its own.

FAILING_READ_INDEX = """\
Failing read
============

.. req:: Mirror
   :id: MIRROR
   :summary: [[copy("status", "WORK_1")]]

.. req:: done
   :id: WORK_1
   :status: [[copy("title")]]
"""

FAILING_READ_FILES = [(Path("conf.py"), CONF), (Path("index.rst"), FAILING_READ_INDEX)]

TYPE_CHECK_WARNING = (
    "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
    "'summary', of need 'MIRROR': dynamic function value <class 'NoneType'> is not of "
    "type 'string' [needs.dynamic_function]"
)


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            {"buildername": "needs", "files": FAILING_READ_FILES},
            [
                _warning(
                    "index.rst:4",
                    "dynamic function 'copy' for option 'summary' read 'status' on need 'WORK_1'",
                ),
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
            id="derive-unresolved-suppressed",
        ),
    ],
    indirect=["test_app"],
)
def test_a_failing_call_still_says_what_it_read(test_app, expected):
    """A call that fails is still reported for its read, and the two subtypes are separate."""
    app = test_app
    app.build()
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


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "files": CHAIN_FORWARD, "confoverrides": SUPPRESSED}],
    indirect=True,
)
def test_suppressed(test_app):
    """``suppress_warnings = ["needs.derive_unresolved"]`` silences the warning."""
    app = test_app
    app.build()
    assert_no_warnings(app)


def test_listed_with_the_build_warnings():
    """The subtype is in the list the documentation renders for ``suppress_warnings``."""
    assert "derive_unresolved" in get_args(WarningSubTypes)
    assert WarningSubTypeDescription["derive_unresolved"] == (
        "A dynamic function or variant condition read a value that another dynamic "
        "function or variant computes in the same pass"
    )


# -- T10: the warning does not depend on the build history ---------------------


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "files": CHAIN_FORWARD}], indirect=True
)
def test_the_warning_does_not_depend_on_the_build_history(test_app):
    """An incremental build re-reading the reader gives the same warning.

    Re-reading ``index.rst`` purges ``CHAIN_A`` and inserts it again after
    ``CHAIN_B``, so the second build resolves ``CHAIN_B`` first and ``CHAIN_A``
    reads the computed value: the value flips with the build history, the warning
    does not, so a ``-W`` build cannot turn red or green by which file was edited.
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

    assert (first_value, second_value) == ("", "Middle")
    assert first == second == CHAIN_WARNINGS


# -- T10b: a filter that reads a computed field --------------------------------
#
# A filter is evaluated on values the pass may or may not have computed yet, so a
# filter on a computed field decides, by the order, which needs it keeps. Its own reads
# are not reported, so the summand or target behind it is noted BEFORE the filter: the
# warning then cannot come and go with the build history although the kept set does.
# ``TGT_F``'s ``summary`` is ``"done"`` once computed, and empty before.

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

FILTERED_WARNINGS = [
    _warning(
        "a.rst:4",
        "dynamic function 'calc_sum' for option 'total' read 'hours' on need 'TGT_F'",
    ),
    _warning(
        "a.rst:8",
        "dynamic function 'check_linked_values' for option 'summary' read 'hours' on need 'TGT_F'",
    ),
]


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
    """A filtered ``calc_sum`` warns the same on every build, as does this layout's
    filtered ``check_linked_values``.

    A ``check_linked_values`` whose check stops at an authored target the filter kept,
    before it reaches a computed one, can still differ between builds; the docs say so.

    The first build reads ``a.rst`` before ``b.rst``, so the filter sees ``TGT_F``'s
    unresolved ``summary`` and drops it (the sum is ``0.0``); re-reading ``a.rst`` moves
    its needs after ``TGT_F``, the filter keeps it, and the sum is ``3.0``. Noted only
    after the filter, the read of ``TGT_F``'s computed ``hours`` would be reported in the
    second build only.
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

    assert (first_total, second_total) == (0.0, 3.0)
    assert first == second == FILTERED_WARNINGS


# -- T11: ubCode's fixture -------------------------------------------------------

DERIVE_UNRESOLVED = re.compile(
    r"<srcdir>/(?P<docname>[^:]+)\.rst:(?P<lineno>\d+): WARNING: "
    r"(?:dynamic function '\w+'|variant condition) for option '(?P<option>\w+)' "
    r"read (?P<read>.+), which carr(?:y|ies) .* \[needs\.derive_unresolved\]"
)
READ = re.compile(
    r"'(?P<name>\w+)' on (?:need '(?P<one>\w+)'|\d+ needs \((?P<some>[^)]*)\))"
)


def _findings(app) -> tuple[list[tuple[str, str, tuple]], list[str]]:
    """The ``needs.derive_unresolved`` findings as (reader id, option, reads), and the rest.

    A reader is identified by its location, a read by the name and the needs named.
    """
    by_location = {
        (need["docname"], need["lineno"]): need_id
        for need_id, need in _built_needs(app).items()
    }
    findings, others = [], []
    for warning in build_warnings(app):
        if (match := DERIVE_UNRESOLVED.fullmatch(warning)) is None:
            others.append(warning)
            continue
        reads = tuple(
            (read["name"], read["one"] or read["some"])
            for read in READ.finditer(match["read"])
        )
        reader = by_location[(match["docname"], int(match["lineno"]))]
        findings.append((reader, match["option"], reads))
    return sorted(findings), others


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_df_unresolved"}],
    indirect=True,
)
def test_ubcode_fixture(test_app):
    """ubCode's ``dynamic_functions_unresolved`` fixture: the same findings.

    The project is ubCode's build fixture
    ``rust/ubc_parser_ctrl/tests/build_fixtures/dynamic_functions_unresolved``,
    with two adaptations, both for what sphinx-needs refuses: ``hours``' default
    moves from its ``schema`` (``schema = { type = "number", default = 0.0 }``) to
    the field (``[needs.fields.hours] default = 0.0``), and ``NEED_ATTR`` is dropped,
    since a ``need.<field>`` argument is not accepted in a field value here (the need
    would not be created). ubCode's ``__expected__`` findings, minus ``NEED_ATTR``'s,
    map one to one:

    ======================  ==========  ===========================================
    reader                  option      read
    ======================  ==========  ===========================================
    ``CHAIN_A``             summary     ``summary`` on ``CHAIN_B``
    ``CHAIN_B``             summary     ``summary`` on ``CHAIN_C``
    ``CYC_A``               summary     ``summary`` on ``CYC_B``
    ``CYC_B``               summary     ``summary`` on ``CYC_A``
    ``GATE_1``              summary     ``status`` on ``WORK_1``
    ``MIRROR_VAR``          summary     ``band`` on ``VAR_B``
    ``OWN_LINKS``           total       ``links`` on ``OWN_LINKS``
    ``SAME_NEED``           status      ``comment`` on ``SAME_NEED``
    ``SUM_ALL``             total       ``hours`` on ``HRS_1, HRS_2, LIT_3``
    ``SUM_ALL2``            total       ``hours`` on ``HRS_1, HRS_2, LIT_3``
    ``SUM_LINKS``           total       ``hours`` on ``HRS_1``
    ``VAR_COND``            band        ``f1`` on ``VAR_COND``
    ======================  ==========  ===========================================

    ubCode reports these as Info; sphinx-needs as a warning. Here ``CHAIN_B``,
    ``CYC_B`` and ``VAR_COND`` happen to read the computed value (their targets are
    resolved first) and are reported all the same, as ubCode reports them. The
    other warnings are the project's own: the legacy ``extra_options`` it uses, and
    the two calls that fail because the value they read was unresolved ``None``.
    """
    app = test_app
    app.build()
    findings, others = _findings(app)
    assert findings == [
        ("CHAIN_A", "summary", (("summary", "CHAIN_B"),)),
        ("CHAIN_B", "summary", (("summary", "CHAIN_C"),)),
        ("CYC_A", "summary", (("summary", "CYC_B"),)),
        ("CYC_B", "summary", (("summary", "CYC_A"),)),
        ("GATE_1", "summary", (("status", "WORK_1"),)),
        ("MIRROR_VAR", "summary", (("band", "VAR_B"),)),
        ("OWN_LINKS", "total", (("links", "OWN_LINKS"),)),
        ("SAME_NEED", "status", (("comment", "SAME_NEED"),)),
        ("SUM_ALL", "total", (("hours", "HRS_1, HRS_2, LIT_3"),)),
        ("SUM_ALL2", "total", (("hours", "HRS_1, HRS_2, LIT_3"),)),
        ("SUM_LINKS", "total", (("hours", "HRS_1"),)),
        ("VAR_COND", "band", (("f1", "VAR_COND"),)),
    ]
    assert others == [
        'WARNING: Config option "needs_extra_options" is deprecated. '
        'Please use "needs_fields" instead. [needs.deprecated]',
        "<srcdir>/index.rst:82: WARNING: Error while resolving dynamic values for "
        "field 'summary', of need 'GATE_1': dynamic function value <class 'NoneType'> "
        "is not of type 'string' [needs.dynamic_function]",
        "<srcdir>/index.rst:100: WARNING: Error while resolving dynamic values for "
        "field 'summary', of need 'MIRROR_VAR': dynamic function value <class "
        "'NoneType'> is not of type 'string' [needs.dynamic_function]",
    ]


# -- T12: who is handed the record ---------------------------------------------------
#
# The pass hands each call's record to the built-ins marked ``records_reads``, as their
# keyword-only ``reads``, and to nothing else: a user's function is called exactly as
# before, and a built-in called anywhere but by the pass itself (an ``ndf`` role, a
# ``:style_row:``, a direct call, a user's function) gets ``reads=None`` and notes nothing.

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

    ``mirror`` copies ``CHAIN_B``'s computed ``summary`` through ``copy``, and reads it
    unresolved (``CHAIN_B`` comes later); the user's function has no record to pass on,
    so the read is not reported, as the documentation says.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["MIRROR_USER"]["summary"], needs["CHAIN_B"]["summary"]) == (
        "",
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
    ``forwardcopy``, which would forward a record to ``copy``, has none to forward, so
    its read of ``CHAIN_B``'s computed ``summary`` is not reported.
    """
    app = test_app
    app.build()
    needs = _built_needs(app)
    assert (needs["U_NARROW"]["summary"], needs["U_FORWARD"]["summary"]) == (
        "NARROW",
        "",
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
