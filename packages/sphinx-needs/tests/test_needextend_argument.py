"""How ``needextend`` reads its argument: a need id or a filter.

On the stripped argument, in this order: ``<…>`` is an id; ``"…"`` is a filter; one
whitespace-separated word is a filter when it holds ``(``, ``=``, ``'`` or ``"``, and
an id otherwise; anything else is a filter. So ``c.this_doc()`` and ``status=="open"``,
written without a space, are filters, and an id holding one of the four characters is
written ``<id>``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

#: (argument as written, the stored ``filter``, the stored ``filter_is_id``)
ROWS: list[tuple[str, str, bool]] = [
    ("REQ_1", "REQ_1", True),
    ("nc::REQ_1", "nc::REQ_1", True),
    ("nc::m2::REQ_B", "nc::m2::REQ_B", True),
    ("REQ-1", "REQ-1", True),
    ("REQ.1", "REQ.1", True),
    ("<nc::REQ_1>", "nc::REQ_1", True),
    ('"is_external"', "is_external", False),
    ("is_external", "is_external", True),
    ("c.this_doc()", "c.this_doc()", False),
    ("c.is_a('req')", "c.is_a('req')", False),
    ('c.is_a("req")', 'c.is_a("req")', False),
    ("c.in_namespace('nc')", "c.in_namespace('nc')", False),
    ('status=="open"', 'status=="open"', False),
    ("id!='X'", "id!='X'", False),
    ('status == "open"', 'status == "open"', False),
    ("<a(b)>", "a(b)", True),
    # each of the four characters alone makes a word a filter
    ("f(x", "f(x", False),
    ("a=b", "a=b", False),
    ("a'b", "a'b", False),
    ('a"b', 'a"b', False),
    # and no other character does
    ("a)b", "a)b", True),
    ("a[0]", "a[0]", True),
    ("a!b", "a!b", True),
    ("a<b", "a<b", True),
    ("a:b", "a:b", True),
]

HEADER = """\
Index
=====

.. req:: One
   :id: REQ_ONE
"""


def _index(arguments: list[str]) -> tuple[str, dict[int, str]]:
    """A page with one ``needextend`` per argument, and the line of each."""
    lines = HEADER.splitlines()
    at: dict[int, str] = {}
    for argument in arguments:
        lines.append("")
        at[len(lines) + 1] = argument
        lines += [f".. needextend:: {argument}", "   :+tags: x"]
    return "\n".join(lines) + "\n", at


CLASSIFY_INDEX, CLASSIFY_AT = _index([row[0] for row in ROWS])


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), CLASSIFY_INDEX)],
        }
    ],
    indirect=True,
)
def test_argument_classification(test_app: Sphinx):
    """Each argument is stored as the filter or id it is read as."""
    app = test_app
    app.build()

    extends = SphinxNeedsData(app.env).get_or_create_extends()
    stored = {
        CLASSIFY_AT[extend["lineno"]]: (extend["filter"], extend["filter_is_id"])
        for extend in extends.values()
    }
    assert stored == {argument: (text, is_id) for argument, text, is_id in ROWS}
    for extend in extends.values():
        assert type(extend["filter_is_id"]) is bool


EMPTY_INDEX, EMPTY_AT = _index(['"', '""', "<>"])


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), EMPTY_INDEX)],
        }
    ],
    indirect=True,
)
def test_empty_corners_are_unchanged(test_app: Sphinx):
    """``"``, ``""`` and ``<>`` are each an empty argument, as before."""
    app = test_app
    app.build()

    assert SphinxNeedsData(app.env).get_or_create_extends() == {}
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:{line}: WARNING: Empty ID/filter argument in needextend "
        "directive. [needs.needextend]"
        for line in sorted(EMPTY_AT)
    ]


FILTERS_INDEX = """\
Index
=====

.. req:: Open
   :id: REQ_OPEN
   :status: open

.. req:: Closed
   :id: REQ_CLOSED
   :status: closed

.. needextend:: c.this_doc()
   :+tags: this_doc

.. needextend:: status=="open"
   :+tags: open
"""

OTHER_PAGE = """\
Other
=====

.. req:: Elsewhere
   :id: REQ_OTHER
   :status: open
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), FILTERS_INDEX + "\n.. toctree::\n\n   other\n"),
                (Path("other.rst"), OTHER_PAGE),
            ],
        }
    ],
    indirect=True,
)
def test_one_word_filters_modify_needs(test_app: Sphinx):
    app = test_app
    app.build()

    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_OPEN"]["tags"] == ["this_doc", "open"]
    assert needs["REQ_CLOSED"]["tags"] == ["this_doc"]
    assert needs["REQ_OTHER"]["tags"] == ["open"]


NAMESPACED_CONF = CONF + 'needs_id_regex = r"^[A-Za-z0-9_:]+$"\n'

NAMESPACED_INDEX = """\
Index
=====

.. req:: One
   :id: nc::REQ_1

.. needextend:: nc::REQ_1
   :+tags: by_id
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NAMESPACED_CONF),
                (Path("index.rst"), NAMESPACED_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_an_id_holding_colons_is_still_an_id(test_app: Sphinx):
    app = test_app
    app.build()

    assert build_warnings(app) == []
    assert needs_by_id(app)["nc::REQ_1"]["tags"] == ["by_id"]


MISSING_INDEX = """\
Index
=====

.. req:: One
   :id: REQ_1

.. needextend:: REQ_MISSING
   :+tags: x
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), MISSING_INDEX)],
        }
    ],
    indirect=True,
)
def test_a_missing_id_is_reported_as_before(test_app: Sphinx):
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:7: WARNING: Provided id 'REQ_MISSING' for needextend "
        "does not exist. [needs.needextend]"
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), MISSING_INDEX)],
            "confoverrides": {"needs_needextend_strict": True},
        }
    ],
    indirect=True,
)
def test_a_missing_id_under_strict_ends_the_build_as_before(test_app: Sphinx):
    with pytest.raises(
        NeedsInvalidFilter,
        match=re.escape("Provided id 'REQ_MISSING' for needextend does not exist."),
    ):
        test_app.build()


EXOTIC_INDEX = """\
Index
=====

.. req:: Exotic
   :id: REQ_001(A)

.. needextend:: REQ_001(A)
   :+tags: bare

.. needextend:: <REQ_001(A)>
   :+tags: bracketed
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), EXOTIC_INDEX)],
        }
    ],
    indirect=True,
)
def test_an_existing_id_holding_a_filter_character_is_written_bracketed(
    test_app: Sphinx,
):
    """``REQ_001(A)`` is accepted by the default id pattern (a prefix test).

    Written bare, the one word holds ``(``, so it is a filter, reported as the invalid
    filter it is, and the need is not extended; written ``<REQ_001(A)>`` it is the
    need's id. The rule is lexical: it does not ask which needs exist.
    """
    app = test_app
    app.build()

    assert needs_by_id(app)["REQ_001(A)"]["tags"] == ["bracketed"]
    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith("<srcdir>/index.rst:7: WARNING: "), warnings[0]
    assert "'REQ_001(A)'" in warnings[0]
    assert "Provided id" not in warnings[0]


PART_INDEX = """\
Index
=====

.. req:: Parts
   :id: REQ_1

   Text with :np:`(p1) the part`.

.. req:: A need whose id holds a dot
   :id: REQ_9.x

.. needextend:: {argument}
   :+tags: x
"""


def _part_app(argument: str, **overrides: object) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), CONF),
            (Path("index.rst"), PART_INDEX.format(argument=argument)),
        ],
        **overrides,
    }


def _names_a_part(argument: str) -> str:
    return (
        f"Provided id {argument!r} for needextend names a part of the need 'REQ_1': "
        "a part has no fields and cannot be extended; extend the need."
    )


@pytest.mark.parametrize(
    ("test_app", "argument"),
    [
        (_part_app("REQ_1.p1"), "REQ_1.p1"),
        (_part_app("<REQ_1.p1>"), "REQ_1.p1"),
    ],
    ids=["bare", "bracketed"],
    indirect=["test_app"],
)
def test_a_part_address_is_refused_naming_the_part(test_app: Sphinx, argument: str):
    """A part has no fields, so it cannot be extended: the address is refused with the
    warning an id naming no need gets, and its message says the address names a part
    of the need and to extend the need. Nothing is extended."""
    app = test_app
    app.build()

    assert build_warnings(app) == [
        f"<srcdir>/index.rst:12: WARNING: {_names_a_part(argument)} [needs.needextend]"
    ]
    assert needs_by_id(app)["REQ_1"]["tags"] == []


@pytest.mark.parametrize(
    "test_app",
    [_part_app("REQ_1.p1", confoverrides={"needs_needextend_strict": True})],
    ids=["strict"],
    indirect=True,
)
def test_a_part_address_under_strict_ends_the_build(test_app: Sphinx):
    """Strictness is as for an id naming no need: the build ends, with the message."""
    with pytest.raises(NeedsInvalidFilter, match=re.escape(_names_a_part("REQ_1.p1"))):
        test_app.build()


@pytest.mark.parametrize(
    ("test_app", "argument"),
    [
        (_part_app("REQ_1.p9"), "REQ_1.p9"),
        (_part_app("NOPE_1.p1"), "NOPE_1.p1"),
    ],
    ids=["part-missing", "part-of-a-missing-need"],
    indirect=["test_app"],
)
def test_an_address_naming_no_part_is_reported_as_before(
    test_app: Sphinx, argument: str
):
    app = test_app
    app.build()

    assert build_warnings(app) == [
        f"<srcdir>/index.rst:12: WARNING: Provided id {argument!r} for needextend "
        "does not exist. [needs.needextend]"
    ]


@pytest.mark.parametrize(
    "test_app", [_part_app("REQ_9.x")], ids=["no-need-REQ_9"], indirect=True
)
def test_a_need_id_holding_a_dot_is_extended_as_before(test_app: Sphinx):
    """``REQ_9.x`` is a need (there is no need ``REQ_9``): it is extended, as in 9.3.0,
    which takes no side on what such an id should mean."""
    app = test_app
    app.build()

    assert build_warnings(app) == []
    assert needs_by_id(app)["REQ_9.x"]["tags"] == ["x"]
