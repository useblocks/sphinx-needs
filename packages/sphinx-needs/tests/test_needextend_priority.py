"""``needextend``'s ``:extend_priority:``, and filters that see the needs as written (#1658).

``needextend`` directives are applied in ``(extend_priority, docname, lineno)`` order,
lower priority first (Sphinx's event-priority convention, default 500), so a project
that never sets the option keeps the ``(docname, lineno)`` order it always had.

Which needs a filter matches does not depend on that order: every filter is evaluated
against the needs as written, before any extend is applied, so no extend changes what
another one's filter matches, and the priority orders the modifications only.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives import needextend as needextend_module
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id, serial_and_parallel

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
    was implemented; the filter extend matches the same needs as written as after the
    extends before it, so evaluating it against the needs as written changes nothing.
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


# -- T6: a filter matches the needs as written, not what an earlier extend left (T9: -j 2)
#
# The recon project ``q5_extend_chain``, plus one filter: the id-targeted extend in
# ``b.rst`` closes TGT_1 before the two ``b.rst`` filters are applied, and neither sees
# it: ``status == "closed"`` matches nothing as written, ``status == "open"`` matches
# TGT_1, which is written open.

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

T6_B = (
    Q5_B
    + """
.. needextend:: status == "open"
   :+tags: open_as_written
"""
)


@pytest.mark.parametrize(
    "test_app",
    serial_and_parallel(
        [
            (Path("conf.py"), Q5_CONF),
            (Path("index.rst"), Q5_INDEX),
            (Path("a.rst"), Q5_A),
            (Path("b.rst"), T6_B),
        ]
    ),
    indirect=True,
)
def test_filter_matches_the_needs_as_written(test_app: Sphinx):
    """T6 (and T9 under ``-j 2``): an earlier extend never changes what a filter matches.

    The ``b.rst`` filter on ``closed`` comes after the extend that closes TGT_1, and
    does not match it, as TGT_1 is written open; the one on ``open`` does. Nothing is
    reported. Merging parallel readers in completion order must not change that.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    need = needs_by_id(app)["TGT_1"]
    assert need["status"] == "closed"
    assert need["tags"] == ["open_as_written"]
    assert need["is_modified"] is True
    assert need["modifications"] == 2


# -- T7: what a filter on an unmodified field matches is unchanged -----------------

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
def test_filter_on_an_unmodified_field_matches_as_before(test_app: Sphinx):
    """T7: a filter on a field no extend changes, and id-targeted extends, apply as before.

    The earlier extends change REQ_1's status, but the filter reads its title, which
    no extend can change, so it matches REQ_1 as written and after them alike. The
    id-targeted extends each modify REQ_1 after the earlier ones, in order.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_1"]["status"] == "closed_again"
    assert needs["REQ_1"]["tags"] == ["titled_one"]
    assert needs["REQ_1"]["modifications"] == 4
    assert needs["REQ_2"]["modifications"] == 0


T7_RETIRED_INDEX = (
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
    "test_app",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), Q5_CONF + suppress),
                    (Path("index.rst"), T7_RETIRED_INDEX),
                    (Path("a.rst"), Q5_A),
                    (Path("b.rst"), Q5_B),
                ],
            },
            id=name,
        )
        for name, suppress in [
            ("absent", ""),
            ("listed", 'suppress_warnings = ["needs.needextend_match_order"]\n'),
        ]
    ],
    indirect=True,
)
def test_retired_match_order_type_is_a_no_op_in_suppress_warnings(test_app: Sphinx):
    """T7: ``needs.needextend_match_order`` is gone, and listing it changes nothing.

    The project of T6, whose ``b.rst`` filter the previous behaviour reported, builds
    with the one ``needextend`` warning it really has, an unknown id, whether or not
    ``suppress_warnings`` still names the retired type: Sphinx ignores a type that is
    never emitted.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [T7_UNKNOWN_ID]
    need = needs_by_id(app)["TGT_1"]
    assert need["status"] == "closed"
    assert need["tags"] == []


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
   :+tags: closed_as_written

.. needextend:: status == "open"
   :+tags: open_as_written
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
def test_filters_ignore_an_earlier_priority(test_app: Sphinx):
    """T8: what a filter matches ignores every extend, whatever its priority.

    The priority-100 extend in ``z.rst`` is applied first, although ``z`` sorts last,
    and closes REQ_1 to REQ_5. Both ``a.rst`` filters then name ``status``, which it
    changed, and still match the needs as written: the one written closed, and the
    five written open.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert {need["status"] for need in needs.values()} == {"closed"}
    assert {need_id: need["tags"] for need_id, need in needs.items()} == {
        "REQ_6": ["closed_as_written"],
        **{f"REQ_{n}": ["open_as_written"] for n in range(1, 6)},
    }


# -- the as-written evaluation: once per filter and document --------------------

MEMO_A = """\
A
=

.. needextend:: status == "open"
   :+tags: a_open
"""

MEMO_B = """\
B
=

.. needextend:: TGT_1
   :status: closed

.. needextend:: status == "open"
   :+tags: b_open

.. needextend:: status == "open"
   :+tags: b_open_again
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), Q5_CONF),
                (Path("index.rst"), Q5_INDEX),
                (Path("a.rst"), MEMO_A),
                (Path("b.rst"), MEMO_B),
            ],
        }
    ],
    indirect=True,
)
def test_identical_filters_are_evaluated_once_per_document(
    test_app: Sphinx, monkeypatch: pytest.MonkeyPatch
):
    """One filter string from one document is evaluated once, against the needs as written.

    Every evaluation reads the same needs, so the two identical filters of ``b.rst``
    share one, and both apply what it matched, although TGT_1 was closed before them.
    The same string in ``a.rst`` is evaluated on its own: a filter can depend on its
    document (``c.this_doc()``), so the document is part of what is shared.
    """
    calls: list[tuple[str, str]] = []
    evaluate = needextend_module._ids_matched_as_written

    def counted(*args: Any) -> Any:
        calls.append((args[2]["filter"], args[2]["docname"]))
        return evaluate(*args)

    monkeypatch.setattr(needextend_module, "_ids_matched_as_written", counted)
    app = test_app
    app.build()

    assert build_warnings(app) == []
    assert calls == [('status == "open"', "a"), ('status == "open"', "b")]
    need = needs_by_id(app)["TGT_1"]
    assert need["status"] == "closed"
    assert need["tags"] == ["a_open", "b_open", "b_open_again"]


THIS_DOC_INDEX = """\
Index
=====

.. toctree::

   a
   b
"""

THIS_DOC_A = """\
A
=

.. req:: A one
   :id: AAA_1
   :status: open

.. needextend:: c.this_doc() and status == "open"
   :+tags: a_this

.. needextend:: c.this_doc() and status == "open"
   :+tags: a_this_again
"""

THIS_DOC_B = """\
B
=

.. req:: B one
   :id: BBB_1
   :status: open

.. needextend:: c.this_doc() and status == "open"
   :+tags: b_this
"""


@pytest.mark.parametrize(
    "test_app",
    serial_and_parallel(
        [
            (Path("conf.py"), CONF),
            (Path("index.rst"), THIS_DOC_INDEX),
            (Path("a.rst"), THIS_DOC_A),
            (Path("b.rst"), THIS_DOC_B),
        ]
    ),
    indirect=True,
)
def test_a_filter_reading_its_document_is_shared_within_that_document_only(
    test_app: Sphinx,
):
    """The same filter string in two documents is two evaluations, with two results.

    ``c.this_doc()`` reads the document of the ``needextend``, so the one string
    matches AAA_1 in ``a.rst`` and BBB_1 in ``b.rst``: each tag lands on its own
    document's need only. The two extends of ``a.rst`` share one evaluation and both
    apply it. Sharing an evaluation across documents would tag AAA_1 with ``b_this``
    and leave BBB_1 untagged.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["AAA_1"]["tags"] == ["a_this", "a_this_again"]
    assert needs["BBB_1"]["tags"] == ["b_this"]


# -- a filter that fails against the needs as written --------------------------

T10_INDEX = """\
Index
=====

.. req:: Target
   :id: TGT_1
   :status: open

.. needextend:: TGT_1
   :status: closed

.. needextend:: {filter}
   :+tags: matched

.. needextend:: {filter}
   :+tags: matched_again

.. needextend:: <TGT_1>
   :+tags: by_id
"""


def _invalid_filter_at(line: int) -> tuple[str, str]:
    """The start and end of the ``Invalid filter`` warning of the extend at ``line``.

    The middle is Python's own ``SyntaxError`` text, which varies between versions.
    """
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Invalid filter 'status ==': ",
        " [needs.needextend]",
    )


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), T10_INDEX.format(filter=filter_string)),
                ],
            },
            expected,
            id=name,
        )
        for name, filter_string, expected in [
            ("raises", "status ==", [_invalid_filter_at(11), _invalid_filter_at(14)]),
            (
                "reports",
                'unknown_field == "x"',
                [
                    (
                        "<srcdir>/index.rst:11: WARNING: Filter 'unknown_field == \"x\"' "
                        "not valid. Error: name 'unknown_field' is not defined.",
                        " [needs.filter]",
                    )
                ],
            ),
        ]
    ],
    indirect=["test_app"],
)
def test_filter_that_fails_as_written_applies_to_nothing(
    test_app: Sphinx, expected: list[tuple[str, str]]
):
    """A filter that cannot be evaluated against the needs as written modifies nothing.

    One that raises, here a syntax error, is the ``Invalid filter`` warning of
    ``needs.needextend``, once for each extend that carries it, at its own line,
    although the two share one evaluation. One whose evaluation reports its own
    error, here an unknown name, does so under ``needs.filter`` from that one
    evaluation, at the first of them. Either way the extend applies to nothing, and
    the extends around it are applied.
    """
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == len(expected)
    for warning, (start, end) in zip(warnings, expected, strict=True):
        assert warning.startswith(start), warning
        assert warning.endswith(end), warning
    need = needs_by_id(app)["TGT_1"]
    assert need["status"] == "closed"
    assert need["tags"] == ["by_id"]
    assert need["modifications"] == 2


# -- an unknown id under strict still ends the build ------------------------------

STRICT_INDEX = """\
Index
=====

.. req:: One
   :id: REQ_1
   :status: open

.. needextend:: REQ_1
   :status: closed

.. needextend:: NOPE_1
   :strict: true
   :status: closed
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), STRICT_INDEX)],
        }
    ],
    indirect=True,
)
def test_strict_unknown_id_ends_the_build(test_app: Sphinx):
    """A ``:strict:`` extend whose id names no need raises, as it always has.

    The targets of every extend are now resolved before any is applied, the ids with
    the filters, so this is where the error comes from; it is the same error.
    """
    with pytest.raises(
        NeedsInvalidFilter,
        match=re.escape("Provided id 'NOPE_1' for needextend does not exist."),
    ):
        test_app.build()
