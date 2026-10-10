import json
import os
import re
import time
from pathlib import Path

import pytest
from sphinx import version_info
from syrupy.filters import props

from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    NeedAttribute,
)
from sphinx_needs_testkit import assert_no_warnings, build_warnings


@pytest.mark.parametrize(
    "func_str,expected_name,expected_args,expected_kwargs",
    [
        ("my_function()", "my_function", (), ()),
        ("my_function(1, 2, 3.0)", "my_function", (1, 2, 3.0), ()),
        ('my_function("a", "b", "c")', "my_function", ("a", "b", "c"), ()),
        ("my_function(True, False)", "my_function", (True, False), ()),
        ("my_function(need.a)", "my_function", (NeedAttribute("a"),), ()),
        (
            'my_function(1, "a", True)',
            "my_function",
            (1, "a", True),
            (),
        ),
        (
            'my_function(1, "a", True, kwarg1=2, kwarg2=3.0, kwarg3="b", kwarg4=False, kwarg5=need.b)',
            "my_function",
            (1, "a", True),
            (
                ("kwarg1", 2),
                ("kwarg2", 3.0),
                ("kwarg3", "b"),
                ("kwarg4", False),
                ("kwarg5", NeedAttribute("b")),
            ),
        ),
        (
            'my_function(kwarg1=[1, 2, 3], kwarg2=[1.0, 2.0, 3.0], kwarg3=["a", "b", "c"], kwarg4=[True, False])',
            "my_function",
            (),
            (
                ("kwarg1", [1, 2, 3]),
                ("kwarg2", [1.0, 2.0, 3.0]),
                ("kwarg3", ["a", "b", "c"]),
                ("kwarg4", [True, False]),
            ),
        ),
    ],
)
def test_dynamic_function_from_string(
    func_str, expected_name, expected_args, expected_kwargs
):
    dynamic_func = DynamicFunctionParsed.from_string(func_str, allow_need=True)

    assert dynamic_func.name == expected_name
    assert dynamic_func.args == expected_args
    assert dynamic_func.kwargs == expected_kwargs


@pytest.mark.parametrize(
    "func_str,error_message",
    [
        ("", "Error parsing dynamic function: Not a function call"),
        ("x.", "Error parsing dynamic function: Not a function call"),
        ("xx", "Error parsing dynamic function: Not a function call"),
        (
            "dunc(None)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc([None])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(1, x.y)",
            "Error parsing dynamic function 'dunc': Unsupported arg 1 value type",
        ),
        (
            "dunc(func())",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(x=x)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(1, y=x.y)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'y' value type",
        ),
        (
            "dunc(z=func())",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'z' value type",
        ),
        (
            "dunc(x=None)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(x=[None])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 0 value type",
        ),
        (
            "dunc([need.x])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x=[1, need.x])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 1 value type",
        ),
    ],
)
def test_dynamic_function_from_string_fail(func_str, error_message):
    with pytest.raises(FunctionParsingException, match=error_message):
        DynamicFunctionParsed.from_string(func_str, allow_need=True)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_dynamic_functions",
        }
    ],
    indirect=True,
)
def test_doc_dynamic_functions(test_app, snapshot):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:26: WARNING: Need could not be created: 'tags' value is invalid: only one string, dynamic function or variant function allowed per array item. [needs.create_need]",
        # since 9.0.0 a ``need.<field>`` argument is accepted in a field value: TEST_7 is
        # created and resolves, TEST_8 is created and its call fails on the unknown field
        "<srcdir>/index.rst:53: WARNING: Error while resolving dynamic values for field 'test_func', of need 'TEST_8': Error while applying need to function 'test': Error parsing dynamic function 'test': need has no attribute 'unknown' [needs.dynamic_function]",
        "<srcdir>/index.rst:45: WARNING: Error while executing function 'copy': Need not found [needs.dynamic_function]",
    ]

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    # since 9.0.0 ``[[...]]`` in a need's CONTENT is plain text, and only the ``ndf`` role runs
    # a dynamic function there.  Sphinx's smartquotes transform has already curled the quotes by
    # the time the text is rendered -- which is what the removed scan used to undo before it ran
    # the call, and one of the reasons the syntax was surprising.
    assert "This is id [[copy(\u201cid\u201d)]]" in html
    assert "This is the best id SP_TOO_001" in html
    assert "nested id [[copy(\u2018id\u2019)]]" in html
    assert "nested id best TEST_6" in html
    # a link's URI is left alone too
    assert "href=\"http://www.[[copy('id')]]\"" in html
    # an ``ndf`` reached through a substitution used as an INTERNAL hyperlink reference
    # (``|intsub|_``): the reference node carries a refid and NO refuri, and the walk this
    # PR replaced returned early on exactly that, never visiting the reference's children.
    # It rendered ``??``; here it resolves.  The other half of this assertion is the
    # expected-warnings list above, which is exact and holds a single "Need not found" --
    # the one from the need-less ``:ndf:`` at index.rst:45, not a second, spurious one.
    assert (
        'via an internal link: <a class="reference internal" '
        'href="#dynamic-functions">SP_TOO_001</a>' in html
    )

    json_data = Path(app.outdir, "needs.json").read_text(encoding="utf-8")
    needs = json.loads(json_data)
    built = needs["versions"][needs["current_version"]]["needs"]
    assert built["TEST_7"]["test_func"] == (
        "Test output of dynamic function; need: TEST_7; args: ('TEST_7',); "
        "kwargs: {'status': 'draft'}"
    )
    assert built["TEST_8"].get("test_func") is None  # unset fields are not written
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_calc_sum",
        }
    ],
    indirect=True,
)
def test_doc_df_calc_sum(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "43210" in html  # all hours
    assert "3210" in html  # hours of linked needs
    assert "210" in html  # hours of filtered needs


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_check_linked_values",
        }
    ],
    indirect=True,
)
def test_doc_df_linked_values(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "all_good" in html
    assert "all_bad" not in html
    assert "all_awesome" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_links_from_content",
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_content(test_app, snapshot):
    app = test_app
    app.build()
    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown1' [needs.dynamic_function]",
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown2' [needs.dynamic_function]",
        "<srcdir>/index.rst:57: WARNING: Error while executing function 'links_from_content': No need found for links_from_content [needs.dynamic_function]",
        "WARNING: links_from_content: no stored node for need 'unknown3' [needs.dynamic_function]",
    ]

    json_data = Path(app.outdir, "needs.json").read_text(encoding="utf-8")
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_user_functions",
        }
    ],
    indirect=True,
)
def test_doc_df_user_functions(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    # print(warnings)
    expected = [
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field 'status', of need 'TEST_2': dynamic function value <class 'object'> is not of type 'string' [needs.dynamic_function]",
        "<srcdir>/index.rst:16: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "<srcdir>/index.rst:18: WARNING: Error parsing dynamic function: Not a function call [needs.dynamic_function]",
        "<srcdir>/index.rst:20: WARNING: Unknown function 'unknown' [needs.dynamic_function]",
    ]
    if version_info >= (7, 3):
        warn = "WARNING: cannot cache unpickable configuration value: 'needs_functions' (because it contains a function, class, or module object)"
        if version_info >= (8, 0):
            warn += " [config.cache]"
        if version_info >= (8, 2):
            warn = warn.replace("unpickable", "unpickleable")
        expected.insert(0, warn)
    assert warning_records == expected

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Awesome" in html
    # the same call written as ``[[...]]`` in the content is plain text since 9.0.0
    assert "[[my_own_function()]] is not a dynamic function here" in html


# -- the ``need_func`` role, removed in 9.0.0 --------------------------------
#
# It was deprecated in 4.0.0 together with ``[[...]]`` in a need's content, and
# ``ndf`` replaces both.  Nothing registers it any more, so a document that still
# writes it gets docutils' own diagnostic for a role that does not exist.

NEED_FUNC_CONF = """\
extensions = ["sphinx_needs"]
"""

NEED_FUNC_INDEX = """\
Removed role
============

.. req:: One
   :id: R_ONE

   This is id :need_func:`[[copy("id")]]`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NEED_FUNC_CONF),
                (Path("index.rst"), NEED_FUNC_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_need_func_role_removed(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert len(warning_records) == 1, warning_records
    assert 'Unknown interpreted text role "need_func"' in warning_records[0]


# -- need-id order: ``calc_sum`` and ``copy(filter=...)`` ---------------------
#
# Float addition is not associative, so the order a whole-project ``calc_sum``
# reads the needs in decides the last digits of its total, and ``copy`` with a
# ``filter`` copies from one match out of several. Both read the needs in ascending
# need-id order, comparing ids as plain strings (code-point order, which is the
# UTF-8 byte order ubCode sorts by), so neither answer depends on the order the needs
# reached the environment: document names, which documents the last build re-read,
# or which ``-j`` worker finished first. ``0.1 + 0.2 + 0.3`` is ``0.6000000000000001``
# added in that order and ``0.6`` added as ``0.3 + 0.2 + 0.1``: the trailing digit is
# the summation order made visible, and the same bits as ubCode's total.

ORDER_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "hours": {"schema": {"type": "number"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
    "pick": {"nullable": True},
}
"""

#: The summands, one page each and named against their ids, so a scratch build reads
#: (and inserts) them in the REVERSE of need-id order: ``SUM_C``, ``SUM_B``, ``SUM_A``
ORDER_PAGES = [
    (
        Path("a.rst"),
        "A\n=\n\n.. req:: Third summand\n   :id: SUM_C\n   :hours: 0.3\n",
    ),
    (
        Path("b.rst"),
        "B\n=\n\n.. req:: Second summand\n   :id: SUM_B\n   :hours: 0.2\n",
    ),
    (
        Path("c.rst"),
        "C\n=\n\n.. req:: First summand\n   :id: SUM_A\n   :hours: 0.1\n",
    ),
]

ORDER_INDEX = """\
Index
=====

.. toctree::

   a
   b
   c

.. req:: Total
   :id: TOTAL
   :total: [[calc_sum("hours")]]
   :pick: [[copy("id", filter="hours is not None and hours > 0")]]
"""

ORDER_FILES = [
    (Path("conf.py"), ORDER_CONF),
    (Path("index.rst"), ORDER_INDEX),
    *ORDER_PAGES,
]

#: ubCode's ``dynamic_functions_sum_order`` build fixture, its page verbatim
UBCODE_SUM_ORDER_INDEX = """\
Summation order of a sum over every need
========================================

Added in need-id order (``SUM_A``, ``SUM_B``, ``SUM_C``), ``0.1 + 0.2 + 0.3`` is ``0.6000000000000001``
while two of the other five orders give ``0.6``,
so the trailing digit of ``TOTAL`` is the pinned summation order made visible, not a rounding accident to tidy away.
The needs are written in the reverse of that order, which alone would give ``0.6``,
so neither document order nor insertion order can produce the snapshot.

.. req:: Total
  :id: TOTAL
  :total: [[calc_sum("hours")]]

.. req:: Third summand
  :id: SUM_C
  :hours: 0.3

.. req:: Second summand
  :id: SUM_B
  :hours: 0.2

.. req:: First summand
  :id: SUM_A
  :hours: 0.1
"""


def _built_needs(app) -> dict[str, dict]:
    """The needs of the ``needs.json`` the last build wrote, by id."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "needs", "files": ORDER_FILES},
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), ORDER_CONF),
                (Path("index.rst"), UBCODE_SUM_ORDER_INDEX),
            ],
        },
    ],
    indirect=True,
    ids=["one-page-per-summand", "ubcode-fixture-page"],
)
def test_calc_sum_adds_in_need_id_order(test_app):
    """A whole-project ``calc_sum`` adds in ascending need-id order.

    The needs are written (and so inserted) in the reverse of need-id order, which
    would give ``0.6``; only need-id order gives ``0.6000000000000001``, the total
    ubCode's ``dynamic_functions_sum_order`` fixture pins, so both tools agree on
    the total bit for bit, whatever order the documents are read in.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    assert _built_needs(app)["TOTAL"]["total"] == 0.6000000000000001


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "files": ORDER_FILES}],
    indirect=True,
)
def test_copy_filter_copies_from_the_lowest_id(test_app):
    """``copy`` with a ``filter`` matching several needs copies from the lowest id.

    ``SUM_C`` is written, and so inserted, first; the copy source must not depend
    on that order (or on which documents the last build re-read, or on ``-j``),
    so it is the match with the lowest id, ``SUM_A``.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    assert _built_needs(app)["TOTAL"]["pick"] == "SUM_A"


NATURAL_ORDER_INDEX = """\
Need-id order is string order
=============================

.. req:: Two
   :id: NEED_2
   :hours: 0.2

.. req:: Nine
   :id: NEED_9
   :hours: 0.3

.. req:: Ten
   :id: NEED_10
   :hours: 0.1

.. req:: Total
   :id: TOTAL
   :total: [[calc_sum("hours")]]
   :pick: [[copy("id", filter='id in ["NEED_9", "NEED_10"]')]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), ORDER_CONF),
                (Path("index.rst"), NATURAL_ORDER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_need_id_order_compares_ids_as_strings(test_app):
    """Need-id order compares ids as plain strings, not in natural order.

    String (code-point) order is ``NEED_10 < NEED_2 < NEED_9``, the byte order ubCode
    sorts ids by, and adds ``0.1 + 0.2 + 0.3 = 0.6000000000000001``. The natural order
    sphinx-needs sorts links by (``NEED_2 < NEED_9 < NEED_10``), which is also the
    order these needs are written in, would add ``0.2 + 0.3 + 0.1 = 0.6`` and copy
    from ``NEED_9``, so this is the test that fails if the order becomes the natural one.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    total = _built_needs(app)["TOTAL"]
    assert total["total"] == 0.6000000000000001
    assert total["pick"] == "NEED_10"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "files": ORDER_FILES}],
    indirect=True,
)
def test_need_id_order_does_not_depend_on_the_build_history(test_app):
    """An incremental build gives the same ``calc_sum`` and ``copy(filter=)`` values.

    Re-reading a document purges its needs and inserts them again at the end of the
    environment's needs, so before need-id order the second build added in another
    order (``0.6`` became ``0.6000000000000001``) and copied from another need
    (``SUM_C`` became ``SUM_B``), from the same sources.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    first = _built_needs(app)["TOTAL"]
    first_status_length = len(app._status.getvalue())

    # newer than the time the first build read it, whatever the file system's clock
    # resolution, so the second build re-reads ``a.rst`` (``SUM_C``) and nothing else
    later = time.time_ns() + 60_000_000_000
    os.utime(Path(app.srcdir, "a.rst"), ns=(later, later))
    app.build()
    assert_no_warnings(app)
    assert (
        "0 added, 1 changed, 0 removed" in app._status.getvalue()[first_status_length:]
    )
    second = _built_needs(app)["TOTAL"]

    assert (second["total"], second["pick"]) == (first["total"], first["pick"])


NDF_ORDER_INDEX = """\
Index
=====

.. toctree::

   a
   b
   c

.. req:: Total
   :id: TOTAL

   Total: :ndf:`calc_sum("hours")`

   Pick: :ndf:`copy("id", filter="hours is not None and hours > 0")`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), ORDER_CONF),
                (Path("index.rst"), NDF_ORDER_INDEX),
                *ORDER_PAGES,
            ],
        }
    ],
    indirect=True,
)
def test_need_id_order_in_the_ndf_role(test_app):
    """The ``ndf`` role sums, and copies, in need-id order too.

    The role (like a need's ``:style:`` and a needtable's ``:style_row:``) runs after
    the needs are resolved and passes the functions a ``NeedsView``, a different
    mapping from the plain ``dict`` the resolution pass passes, so the order is
    pinned for it separately: the summands are written in the reverse of need-id
    order, which would render ``0.6`` and copy from ``SUM_C``.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    rendered = dict(re.findall(r"(Total|Pick): ([^<]*)<", html))
    assert rendered == {"Total": "0.6000000000000001", "Pick": "SUM_A"}


LINKS_ONLY_INDEX = """\
Links only
==========

.. req:: Third summand
   :id: SUM_C
   :hours: 0.3

.. req:: Second summand
   :id: SUM_B
   :hours: 0.2

.. req:: First summand
   :id: SUM_A
   :hours: 0.1

.. req:: Links in reverse id order
   :id: LINKSUM_REV
   :links: SUM_C, SUM_B, SUM_A
   :total: [[calc_sum("hours", links_only=True)]]

.. req:: Links in id order
   :id: LINKSUM_FWD
   :links: SUM_A, SUM_B, SUM_C
   :total: [[calc_sum("hours", links_only=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), ORDER_CONF),
                (Path("index.rst"), LINKS_ONLY_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_calc_sum_links_only_adds_in_the_written_link_order(test_app):
    """``calc_sum`` with ``links_only`` adds in the order the links are written.

    That order is already deterministic (it is the source's), and it is the order
    ubCode adds a ``links_only`` sum in, so it is kept rather than moved to need-id
    order: the same three links written in two orders give two different totals,
    on purpose.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = _built_needs(app)
    assert needs["LINKSUM_REV"]["total"] == 0.6
    assert needs["LINKSUM_FWD"]["total"] == 0.6000000000000001


NEEDLESS_SUM_INDEX = """\
Sum outside a need
==================

Total: :ndf:`calc_sum("hours")`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), ORDER_CONF),
                (Path("index.rst"), NEEDLESS_SUM_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_calc_sum_outside_a_need_names_itself(test_app):
    """``calc_sum`` called outside a need reports its own name.

    The message used to name ``check_linked_values``, copied from that function.
    """
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert (
        "Error while executing function 'calc_sum': No need given for calc_sum"
        in warnings[0]
    )


# -- a link to a need part reads the part's need (#2173) -----------------------
#
# A link may name a need PART (``REQ_1.a``): it is accepted, rendered as a part link
# and counted on ``REQ_1``'s back links. ``check_linked_values`` and a ``links_only``
# ``calc_sum`` read the fields of each need the links name, and they looked a part
# link up by its whole text, which no need has: both calls failed. They now read the
# part's need, as ubCode does on the same sources.

PART_LINKS_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {
    "hours": {"schema": {"type": "number"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
    "verdict": {"nullable": True},
}
"""

PART_LINKS_INDEX = """\
Part links
==========

.. req:: Req one
   :id: REQ_1
   :status: open
   :hours: 3

   :np:`(a) part a` and :np:`(b) part b`

.. req:: Req two
   :id: REQ_2
   :status: open
   :hours: 5

.. spec:: Closed spec
   :id: SPEC_C
   :status: closed
   :hours: 100

.. spec:: A part link and a need link
   :id: SPEC_1
   :links: REQ_1.a, REQ_2
   :verdict: [[check_linked_values('all-open', 'status', 'open')]]
   :total: [[calc_sum('hours', links_only=True)]]

.. spec:: Two parts of one need
   :id: SPEC_2
   :links: REQ_1.a, REQ_1.b
   :verdict: [[check_linked_values('all-open', 'status', 'open')]]
   :total: [[calc_sum('hours', links_only=True)]]

.. spec:: A filter tests the part's need
   :id: SPEC_3
   :links: REQ_1.b, SPEC_C
   :verdict: [[check_linked_values('all-open', 'status', 'open', 'type == "req"')]]
   :total: [[calc_sum('hours', 'type == "req"', links_only=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), PART_LINKS_CONF),
                (Path("index.rst"), PART_LINKS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_part_links_read_the_parts_need(test_app):
    """``check_linked_values`` and a ``links_only`` ``calc_sum`` read a part link's need.

    ``SPEC_1`` is the issue's own shape (#2173): ``'all-open'`` and ``3 + 5``. Two
    parts of one need name that need twice, so its value is added twice, as a need
    linked twice is (``SPEC_2``). A filter is tested on the part's need (``SPEC_3``:
    the part's need is a ``req``, the closed ``spec`` is filtered out).
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = _built_needs(app)
    assert needs["SPEC_1"]["verdict"] == "all-open"
    assert needs["SPEC_1"]["total"] == 8.0
    assert needs["SPEC_2"]["verdict"] == "all-open"
    assert needs["SPEC_2"]["total"] == 6.0
    assert needs["SPEC_3"]["verdict"] == "all-open"
    assert needs["SPEC_3"]["total"] == 3.0


PART_LINKS_ORDER_INDEX = """\
Part links, computed
====================

.. req:: Source of the hours
   :id: SRC_1
   :status: open
   :hours: 4

.. req:: The part's need computes the values the reader reads
   :id: Z_REQ
   :status: [[copy("status", "SRC_1")]]
   :hours: [[copy("hours", "SRC_1")]]

   :np:`(p) a part`

.. spec:: Reads through a part link, and sorts before the need it reads
   :id: A_SPEC
   :links: Z_REQ.p
   :verdict: [[check_linked_values('all-open', 'status', 'open')]]
   :total: [[calc_sum('hours', links_only=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), PART_LINKS_CONF),
                (Path("index.rst"), PART_LINKS_ORDER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_part_links_are_read_after_the_parts_need_is_computed(test_app):
    """The order of the pass reads a part link's need too.

    ``A_SPEC`` sorts before ``Z_REQ``, so only a read of ``Z_REQ``'s computed
    ``status`` and ``hours`` puts its calls after them: read through the part
    link's whole text, which names no need, they ran first and read the empty values,
    and the pass reported a read it did not account for.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    needs = _built_needs(app)
    assert needs["A_SPEC"]["verdict"] == "all-open"
    assert needs["A_SPEC"]["total"] == 4.0


DEAD_LINK_INDEX = """\
Dead link
=========

.. req:: Req two
   :id: REQ_2
   :status: open
   :hours: 5

.. spec:: A dead link
   :id: SPEC_D
   :links: REQ_2, NOPE_1
   :verdict: [[check_linked_values('all-open', 'status', 'open')]]
   :total: [[calc_sum('hours', links_only=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), PART_LINKS_CONF),
                (Path("index.rst"), DEAD_LINK_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_dead_link_still_fails_the_call(test_app):
    """A link naming no need still fails ``check_linked_values`` and a ``links_only`` sum.

    Only a part link is resolved to its need; a dead link fails the call, as before
    (and as ubCode, which mirrors it), and is reported as a dead link as well.
    """
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert warnings == [
        "<srcdir>/index.rst:9: WARNING: Error while resolving dynamic values for field "
        "'total', of need 'SPEC_D': Error while executing function 'calc_sum': "
        "'NOPE_1' [needs.dynamic_function]",
        "<srcdir>/index.rst:9: WARNING: Error while resolving dynamic values for field "
        "'verdict', of need 'SPEC_D': Error while executing function "
        "'check_linked_values': 'NOPE_1' [needs.dynamic_function]",
        "<srcdir>/index.rst:9: WARNING: Need 'SPEC_D' has unknown outgoing link "
        "'NOPE_1' in field 'links' [needs.link_outgoing]",
    ]
    needs = _built_needs(app)
    assert needs["SPEC_D"]["verdict"] is None
    assert needs["SPEC_D"]["total"] is None
