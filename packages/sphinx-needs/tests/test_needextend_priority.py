"""``needextend``'s ``:extend_priority:``, and filters whose matches depend on order (#1658).

``needextend`` directives are applied in ``(extend_priority, docname, lineno)`` order,
lower priority first (Sphinx's event-priority convention, default 500), so a project
that never sets the option keeps the ``(docname, lineno)`` order it always had.

Which needs a filter matches is unchanged in this release: each filter is still
evaluated against the needs as the extends applied before it left them. Every filter is
also evaluated against the needs as written, before any extend is applied, and where the
two differ the extend is reported as ``needs.needextend_match_order``: the next release
evaluates filters against the needs as written, so those are the extends whose reach
will change.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx
from sphinx.util.parallel import parallel_available
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives import needextend as needextend_module
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

INDEX_AB = """\
Index
=====

.. toctree::

   a
   b

.. req:: One
   :id: REQ_1
   :status: open
"""

# Sphinx 7 reads in parallel only above five documents (Sphinx 9 at any count), so the
# ``-j 2`` variants add four orphan pages: seven documents read in parallel on every cell
PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


def serial_and_parallel(files: list[tuple[Path, str]]) -> list[Any]:
    """``test_app`` parameters building ``files`` serially, and with ``-j 2``."""
    return [
        pytest.param({"buildername": "html", "files": files}, id="serial"),
        pytest.param(
            {"buildername": "html", "files": [*files, *PADDING], "parallel": 2},
            id="j2",
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        ),
    ]


def needs_by_id(app: Sphinx) -> dict[str, dict[str, Any]]:
    """The needs of the build's ``needs.json``, by id."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf8"))
    return data["versions"][data["current_version"]]["needs"]


def stored_priorities(app: Sphinx) -> dict[tuple[str, int], int]:
    """The ``extend_priority`` recorded for each needextend, by ``(docname, lineno)``."""
    extends = SphinxNeedsData(app.env).get_or_create_extends()
    return {
        (extend["docname"], extend["lineno"]): extend["extend_priority"]
        for extend in extends.values()
    }


# -- T1: a project that never sets the option ---------------------------------

T1_INDEX = """\
Index
=====

.. toctree::

   a
   b

.. req:: One
   :id: REQ_1
   :status: open
   :tags: authored

.. req:: Two
   :id: REQ_2
   :status: open

.. needextend:: REQ_2
   :status: from_index
   :+tags: index

.. needextend:: type == "req"
   :+tags: every_req
"""

T1_A = """\
A
=

.. needextend:: REQ_1
   :status: from_a
   :+tags: a_first

.. needextend:: <REQ_1>
   :+tags: a_second
"""

T1_B = """\
B
=

.. needextend:: REQ_1
   :status: from_b
   :+tags: b
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), T1_INDEX),
                (Path("a.rst"), T1_A),
                (Path("b.rst"), T1_B),
            ],
        }
    ],
    indirect=True,
)
def test_without_the_option_needs_json_is_unchanged(test_app: Sphinx, snapshot):
    """T1: a project that never sets ``:extend_priority:`` builds as it did before.

    Every extend sits at the default priority, so the order is ``(docname, lineno)``
    exactly as before the option existed. The snapshot was recorded before the option
    was implemented; the filter extend matches the same needs as written and live, so
    nothing is reported either.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_1"]["status"] == "from_b"
    assert needs["REQ_1"]["tags"] == [
        "authored",
        "a_first",
        "a_second",
        "b",
        "every_req",
    ]
    assert needs["REQ_2"]["status"] == "from_index"
    assert needs["REQ_2"]["tags"] == ["index", "every_req"]
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf8"))
    assert data == snapshot(exclude=props("created", "project", "creator"))


# -- T2: priority overrides file order (T9: also with -j 2) --------------------

T2_A = """\
A
=

.. needextend:: REQ_1
   :extend_priority: 600
   :status: late
"""

T2_B = """\
B
=

.. needextend:: REQ_1
   :extend_priority: 400
   :status: early
"""


@pytest.mark.parametrize(
    "test_app",
    serial_and_parallel(
        [
            (Path("conf.py"), CONF),
            (Path("index.rst"), INDEX_AB),
            (Path("a.rst"), T2_A),
            (Path("b.rst"), T2_B),
        ]
    ),
    indirect=True,
)
def test_higher_priority_is_applied_last(test_app: Sphinx):
    """T2 (and T9 under ``-j 2``): the extend with the higher priority wins a conflict.

    ``b.rst`` sorts after ``a.rst``, so by file order its ``early`` would be applied
    last; its priority 400 puts it before ``a.rst``'s 600, whose ``late`` wins.
    Merging parallel readers in completion order must not change that.
    """
    app = test_app
    app.build()

    need = needs_by_id(app)["REQ_1"]
    assert need["status"] == "late"
    assert need["modifications"] == 2
    assert build_warnings(app) == []


# -- T3: appends follow the priority --------------------------------------------

T3_INDEX = (
    INDEX_AB
    + """
.. needextend:: REQ_1
   :+tags: p500
"""
)

T3_A = """\
A
=

.. needextend:: REQ_1
   :extend_priority: 600
   :+tags: p600

.. needextend:: REQ_1
   :extend_priority: 0
   :+tags: p0
"""

T3_B = """\
B
=

.. needextend:: REQ_1
   :extend_priority: 400
   :+tags: p400
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), T3_INDEX),
                (Path("a.rst"), T3_A),
                (Path("b.rst"), T3_B),
            ],
        }
    ],
    indirect=True,
)
def test_appends_follow_ascending_priority(test_app: Sphinx):
    """T3: ``+tags`` from several extends are appended in ascending priority order.

    File order would give ``p600, p0, p400, p500`` (``a``, ``b``, ``index``); the
    priorities 0, 400, 500 (the default, in ``index.rst``) and 600 give their own
    order. 0, the lowest value allowed, is a priority like any other and runs first,
    not a missing one that falls back to the default.
    """
    app = test_app
    app.build()

    assert needs_by_id(app)["REQ_1"]["tags"] == ["p0", "p400", "p500", "p600"]
    assert build_warnings(app) == []


# -- T4: equal priorities keep (docname, lineno) order, and the default is 500 ---

T4_A = """\
A
=

.. needextend:: REQ_1
   :extend_priority: 500
   :status: from_a
   :+tags: a
"""

T4_B = """\
B
=

.. needextend:: REQ_1
   :status: from_b
   :+tags: b1

.. needextend:: REQ_1
   :extend_priority: 500
   :+tags: b2
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX_AB),
                (Path("a.rst"), T4_A),
                (Path("b.rst"), T4_B),
            ],
        }
    ],
    indirect=True,
)
def test_equal_priorities_keep_document_order(test_app: Sphinx):
    """T4: an explicit 500 and no option are the same priority.

    Extends of equal priority keep the ``(docname, lineno)`` order they always had, so
    a project that sets ``500`` on some extends and nothing on others gets today's
    result. Each recorded extend carries 500, the default for one without the option.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    need = needs_by_id(app)["REQ_1"]
    assert need["status"] == "from_b"
    assert need["tags"] == ["a", "b1", "b2"]
    assert stored_priorities(app) == {("a", 4): 500, ("b", 4): 500, ("b", 8): 500}


# -- T5: an invalid priority skips the extend -----------------------------------

T5_INDEX = """\
Index
=====

.. req:: One
   :id: REQ_1
   :status: open

.. needextend:: REQ_1
   :extend_priority: {value}
   :status: changed
"""

T5_CASES = [
    ("abc", "invalid literal for int() with base 10: 'abc'"),
    ("-1", "negative value; must be positive or zero"),
    ("1.5", "invalid literal for int() with base 10: '1.5'"),
    ("", "invalid literal for int() with base 10: ''"),
]


@pytest.mark.parametrize(
    ("test_app", "message"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), T5_INDEX.format(value=value)),
                ],
            },
            message,
            id=value or "empty",
        )
        for value, message in T5_CASES
    ],
    indirect=["test_app"],
)
def test_invalid_priority_is_reported_and_not_applied(test_app: Sphinx, message: str):
    """T5: a priority that is not an integer >= 0 is reported, and the extend skipped.

    This is what the directive does for a bad ``:strict:`` value: one warning under
    ``needs.needextend`` at the directive, and nothing recorded, so the extend is not
    applied at all rather than applied with the default priority.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Invalid value for 'extend_priority' option: "
        f"{message} [needs.needextend]"
    ]
    need = needs_by_id(app)["REQ_1"]
    assert need["status"] == "open"
    assert need["is_modified"] is False
    assert need["modifications"] == 0
    assert SphinxNeedsData(app.env).get_or_create_extends() == {}


T5_FIELD_CONF = CONF + 'needs_fields = {"extend_priority": {"nullable": True}}\n'

T5_FIELD_INDEX = """\
Index
=====

.. req:: One
   :id: REQ_1
   :extend_priority: authored

.. needextend:: REQ_1
   :extend_priority: 7
   :+extend_priority: appended
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), T5_FIELD_CONF),
                (Path("index.rst"), T5_FIELD_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_priority_option_shadows_a_field_of_that_name(test_app: Sphinx):
    """A field named ``extend_priority`` cannot be replaced by a ``needextend``.

    Like ``:strict:``, ``:extend_priority:`` is the directive's own option, taken
    before the options that modify fields, so it always sets the priority; the
    documented collision. ``:+extend_priority:`` is a different option, and still
    appends to the field.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    assert needs_by_id(app)["REQ_1"]["extend_priority"] == "authored appended"
    assert stored_priorities(app) == {("index", 8): 7}


# -- T6: a filter that matches only because of an earlier extend (T9: -j 2) -----
#
# The recon project ``q5_extend_chain``, as it is: the id-targeted extend in ``b.rst``
# closes TGT_1, so the filter after it in ``b.rst`` matches TGT_1, while the identical
# filter in ``a.rst``, applied first, matches nothing.

Q5_CONF = """\
extensions = ["sphinx_needs"]
needs_types = [{"directive": "req", "title": "Req", "prefix": "R_", "color": "#BFD8D2", "style": "node"}]
needs_build_json = True
"""

Q5_INDEX = """\
Index
=====

.. toctree::

   a
   b

.. req:: Target
   :id: TGT_1
   :status: open
"""

Q5_A = """\
A
=

.. needextend:: status == "closed"
   :+tags: saw_closed
"""

Q5_B = """\
B
=

.. needextend:: TGT_1
   :status: closed

.. needextend:: status == "closed"
   :+tags: saw_closed_later
"""

Q5_WARNING = (
    "<srcdir>/b.rst:7: WARNING: the needs matched by this needextend depend on "
    "modifications applied by earlier needextend directives: it matches 1 need (TGT_1) "
    "now and 0 against the needs as written; from the next release filters are "
    "evaluated against the needs as written, before any needextend is applied "
    "[needs.needextend_match_order]"
)


@pytest.mark.parametrize(
    "test_app",
    serial_and_parallel(
        [
            (Path("conf.py"), Q5_CONF),
            (Path("index.rst"), Q5_INDEX),
            (Path("a.rst"), Q5_A),
            (Path("b.rst"), Q5_B),
        ]
    ),
    indirect=True,
)
def test_filter_depending_on_an_earlier_extend_is_reported(test_app: Sphinx):
    """T6 (and T9 under ``-j 2``): one warning, at the filter that depends on order.

    The ``b.rst`` filter matches TGT_1 now, and nothing against the needs as written:
    it is reported once, at its own line. The id-targeted extend is never reported,
    nor the ``a.rst`` filter, which matches nothing either way. What is applied is
    unchanged in this release: the ``b.rst`` filter still tags TGT_1.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [Q5_WARNING]
    need = needs_by_id(app)["TGT_1"]
    assert need["status"] == "closed"
    assert need["tags"] == ["saw_closed_later"]
    assert need["is_modified"] is True
    assert need["modifications"] == 2


# -- T7: no warning where the two agree; suppressible on its own -----------------

T7_INDEX = """\
Index
=====

.. toctree::

   a
   b

.. req:: One
   :id: REQ_1
   :status: open

.. req:: Two
   :id: REQ_2
   :status: open
"""

T7_A = """\
A
=

.. needextend:: REQ_1
   :status: closed

.. needextend:: REQ_1
   :status: reopened
"""

T7_B = """\
B
=

.. needextend:: title == "One"
   :+tags: titled_one

.. needextend:: REQ_1
   :status: closed_again
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), T7_INDEX),
                (Path("a.rst"), T7_A),
                (Path("b.rst"), T7_B),
            ],
        }
    ],
    indirect=True,
)
def test_no_warning_where_the_matches_agree(test_app: Sphinx):
    """T7: a filter on a field no extend changes, and id-targeted extends, never warn.

    The earlier extends change REQ_1's status, but the filter reads its title, which
    no extend can change, so it matches REQ_1 either way. The id-targeted extends
    each modify REQ_1 after earlier ones did; their target is fixed, so they are never
    compared.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_1"]["status"] == "closed_again"
    assert needs["REQ_1"]["tags"] == ["titled_one"]
    assert needs["REQ_1"]["modifications"] == 4
    assert needs["REQ_2"]["modifications"] == 0


T7_SUPPRESSED_INDEX = (
    Q5_INDEX
    + """
.. needextend:: NOPE_1
   :status: closed
"""
)

T7_UNKNOWN_ID = (
    "<srcdir>/index.rst:13: WARNING: Provided id 'NOPE_1' for needextend does not "
    "exist. [needs.needextend]"
)


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), Q5_CONF + suppress),
                    (Path("index.rst"), T7_SUPPRESSED_INDEX),
                    (Path("a.rst"), Q5_A),
                    (Path("b.rst"), Q5_B),
                ],
            },
            expected,
            id=name,
        )
        for name, suppress, expected in [
            ("reported", "", [Q5_WARNING, T7_UNKNOWN_ID]),
            (
                "suppressed",
                'suppress_warnings = ["needs.needextend_match_order"]\n',
                [T7_UNKNOWN_ID],
            ),
        ]
    ],
    indirect=["test_app"],
)
def test_match_order_warning_is_suppressed_alone(test_app: Sphinx, expected: list[str]):
    """T7: ``suppress_warnings`` silences ``needs.needextend_match_order`` and no more.

    The other ``needextend`` warning of the same build, an unknown id, is still
    reported; without the suppression both are.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == expected


# -- T8: the needs as written, even after a lower-priority extend ---------------

T8_INDEX = """\
Index
=====

.. toctree::

   a
   z

.. req:: Six
   :id: REQ_6
   :status: closed

.. req:: Five
   :id: REQ_5
   :status: open

.. req:: Four
   :id: REQ_4
   :status: open

.. req:: Three
   :id: REQ_3
   :status: open

.. req:: Two
   :id: REQ_2
   :status: open

.. req:: One
   :id: REQ_1
   :status: open
"""

T8_A = """\
A
=

.. needextend:: status == "closed"
   :+tags: closed_now

.. needextend:: status == "open"
   :+tags: open_now
"""

T8_Z = """\
Z
=

.. needextend:: status == "open"
   :extend_priority: 100
   :status: closed
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), T8_INDEX),
                (Path("a.rst"), T8_A),
                (Path("z.rst"), T8_Z),
            ],
        }
    ],
    indirect=True,
)
def test_needs_as_written_ignore_an_earlier_priority(test_app: Sphinx):
    """T8: what a filter matches as written ignores every extend, whatever its priority.

    The priority-100 extend in ``z.rst`` is applied first, although ``z`` sorts last,
    and closes REQ_1 to REQ_5. It is itself the first extend applied, so it matches
    the same needs either way. Both ``a.rst`` filters then name ``status``, which it
    changed: each is reported with the needs it matches now and as written, in need-id
    order (the needs are written in the reverse order), three named and the rest
    counted. The tags show the filters still match the live needs.
    """
    app = test_app
    app.build()

    head = (
        "WARNING: the needs matched by this needextend depend on modifications applied "
        "by earlier needextend directives: it matches "
    )
    tail = (
        " against the needs as written; from the next release filters are evaluated "
        "against the needs as written, before any needextend is applied "
        "[needs.needextend_match_order]"
    )
    assert build_warnings(app) == [
        f"<srcdir>/a.rst:4: {head}6 needs (REQ_1, REQ_2, REQ_3 and 3 more) now "
        f"and 1 (REQ_6){tail}",
        f"<srcdir>/a.rst:7: {head}0 needs now "
        f"and 5 (REQ_1, REQ_2, REQ_3 and 2 more){tail}",
    ]
    needs = needs_by_id(app)
    assert {need["status"] for need in needs.values()} == {"closed"}
    assert {need_id: need["tags"] for need_id, need in needs.items()} == {
        f"REQ_{n}": ["closed_now"] for n in range(1, 7)
    }


# -- the as-written pass: once per filter and document, and none when suppressed ----

MEMO_B = (
    Q5_B
    + """
.. needextend:: status == "closed"
   :+tags: saw_closed_again
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), Q5_CONF),
                (Path("index.rst"), Q5_INDEX),
                (Path("a.rst"), Q5_A),
                (Path("b.rst"), MEMO_B),
            ],
        }
    ],
    indirect=True,
)
def test_identical_filters_are_evaluated_once_per_document(
    test_app: Sphinx, monkeypatch: pytest.MonkeyPatch
):
    """One filter string from one document is evaluated once against the needs as written.

    Every as-written evaluation reads the same needs, so the two identical filters of
    ``b.rst`` share one evaluation and are both reported, each at its own line. The same
    string in ``a.rst`` is evaluated on its own: a filter can depend on its document
    (``c.this_doc()``), so the document is part of what is shared.
    """
    calls: list[tuple[str, str]] = []
    evaluate = needextend_module._ids_matched_as_written

    def counted(*args: Any) -> frozenset[str] | None:
        calls.append((args[2]["filter"], args[2]["docname"]))
        return evaluate(*args)

    monkeypatch.setattr(needextend_module, "_ids_matched_as_written", counted)
    app = test_app
    app.build()

    assert build_warnings(app) == [
        Q5_WARNING,
        Q5_WARNING.replace("b.rst:7:", "b.rst:10:"),
    ]
    assert calls == [('status == "closed"', "a"), ('status == "closed"', "b")]
    need = needs_by_id(app)["TGT_1"]
    assert need["tags"] == ["saw_closed_later", "saw_closed_again"]
