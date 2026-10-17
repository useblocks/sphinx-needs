"""``needtable``'s ``:sort:``, and ``:sort_by:``, on a field some needs leave unset (#2253).

An unset field holds ``None``. The sort compared raw values, so ``None`` beside an
integer (or a string) raised ``TypeError`` and stopped the build. A field declared on one
need type alone makes this the normal case: it holds ``None`` on every other type's needs.
A need whose value is unset now comes before every need with a value, whatever the field's
type, as an empty string always has, and an unknown sort key is a warning rather than a
``KeyError``. ``:sort_by:``, which every filter directive takes, mapped ``None`` to ``""``
and crashed the same way beside a number; it shares the key, comparing text as it is.
"""

import math
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.filter_common import sort_key
from sphinx_needs_testkit import build_warnings

FIELD_CONF = """\
extensions = ["sphinx_needs"]
needs_fields = {"priority": {"schema": {"type": "integer"}, "nullable": True}}
"""

PER_TYPE_CONF = """\
extensions = ["sphinx_needs"]
needs_types = [
    {{"directive": "req", "title": "Requirement", "prefix": "R_",
     "fields": {{"priority": {{"schema": {{"type": "{type}"}}}}}}}},
    {{"directive": "spec", "title": "Specification", "prefix": "S_"}},
]
"""

INDEX = """\
Index
=====

.. toctree::

   table

{needs}
"""


def project(
    conf: str,
    needs: str,
    sort: str = "priority",
    directive: str = "needtable::\n   :columns: id\n   :sort:",
) -> list[dict[str, object]]:
    """``test_app`` parameters: the needs on one page, the table alone on another."""
    table = f"Table\n=====\n\n.. {directive} {sort}\n"
    return [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), conf),
                (Path("index.rst"), INDEX.format(needs=needs)),
                (Path("table.rst"), table),
            ],
        }
    ]


def row_order(app: Sphinx) -> list[str]:
    """The need ids of the table's rows, in order."""
    html = Path(app.outdir, "table.html").read_text()
    return list(dict.fromkeys(re.findall(r"\b(?:REQ|SPEC)_\d+\b", html)))


@pytest.mark.parametrize(
    "test_app",
    project(
        FIELD_CONF,
        """
.. req:: Three
   :id: REQ_001
   :priority: 3

.. req:: Unset
   :id: REQ_002

.. req:: One
   :id: REQ_003
   :priority: 1
""",
    ),
    indirect=True,
)
def test_sort_by_integer_field_with_unset_value(test_app: Sphinx):
    """The case of the issue: ``None`` beside an ``int``; the unset need comes first."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert row_order(test_app) == ["REQ_002", "REQ_003", "REQ_001"]


@pytest.mark.parametrize(
    "test_app",
    project(
        PER_TYPE_CONF.format(type="integer"),
        """
.. spec:: Other type
   :id: SPEC_001

.. req:: Two
   :id: REQ_001
   :priority: 2

.. req:: One
   :id: REQ_002
   :priority: 1
""",
    ),
    indirect=True,
)
def test_sort_by_integer_field_declared_on_one_type(test_app: Sphinx):
    """The field is declared on ``req`` alone, so the ``spec`` holds ``None``."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert row_order(test_app) == ["SPEC_001", "REQ_002", "REQ_001"]


@pytest.mark.parametrize(
    "test_app",
    project(
        PER_TYPE_CONF.format(type="string"),
        """
.. spec:: Other type
   :id: SPEC_001

.. req:: Lower b
   :id: REQ_001
   :priority: b

.. req:: Upper A
   :id: REQ_002
   :priority: A
""",
    ),
    indirect=True,
)
def test_sort_by_string_field_declared_on_one_type(test_app: Sphinx):
    """``None`` beside a ``str`` crashed too; strings still sort case-insensitively."""
    test_app.build()
    assert build_warnings(test_app) == []
    assert row_order(test_app) == ["SPEC_001", "REQ_002", "REQ_001"]


@pytest.mark.parametrize(
    "test_app",
    project(
        FIELD_CONF,
        """
.. req:: B
   :id: REQ_002

.. req:: A
   :id: REQ_001
""",
        sort="unknown_key",
    ),
    indirect=True,
)
def test_sort_by_unknown_key_warns(test_app: Sphinx):
    """An unknown key was an uncaught ``KeyError``; now a warning, the rows unsorted."""
    test_app.build()
    assert build_warnings(test_app) == [
        "<srcdir>/table.rst:4: WARNING: needtable sort key 'unknown_key' is not a field "
        "of the needs; the rows are left in the filter's order [needs.filter]",
    ]
    # the document's order, not the default sort by id
    assert row_order(test_app) == ["REQ_002", "REQ_001"]


def test_sort_key_orders_mixed_types_without_error():
    """Values a field's declaration does not restrict to one type never compare.

    ``None`` first, then booleans, numbers, and text (case-insensitive), where a list is
    its items joined with ``", "`` and anything else its text.
    """
    values = ["b", ["x", "y"], 2.5, "A", None, {"k": 1}, True, 1, False, "x"]
    assert sorted(values, key=lambda value: sort_key(value, ignore_case=True)) == [
        None,
        False,
        True,
        1,
        2.5,
        "A",
        "b",
        "x",
        ["x", "y"],
        {"k": 1},
    ]


def test_sort_key_is_stable_for_equal_keys():
    """Equal keys keep their order: ``"a"`` and ``"A"``, ``["a"]`` and ``"a"``."""
    values = ["a", ["a"], "A"]
    assert sorted(values, key=lambda value: sort_key(value, ignore_case=True)) == [
        "a",
        ["a"],
        "A",
    ]


@pytest.mark.parametrize(
    "test_app",
    project(
        PER_TYPE_CONF.format(type="integer"),
        """
.. req:: Two
   :id: REQ_001
   :priority: 2

.. spec:: Other type
   :id: SPEC_001

.. req:: Zero
   :id: REQ_002
   :priority: 0
""",
        directive="needlist::\n   :sort_by:",
    ),
    indirect=True,
)
def test_sort_by_option_on_integer_field_declared_on_one_type(test_app: Sphinx):
    """``:sort_by:`` compared ``""`` (for ``None``, and for ``0``) with an ``int``.

    A ``needlist`` shows ``:sort_by:``'s order (a needtable sorts again by ``:sort:``).
    """
    test_app.build()
    assert build_warnings(test_app) == []
    assert row_order(test_app) == ["SPEC_001", "REQ_002", "REQ_001"]


def test_sort_by_key_keeps_case():
    """``:sort_by:`` compares text as it is, ``:sort:`` lower-cased."""
    values = ["b", "a", "B"]
    assert sorted(values, key=lambda value: sort_key(value, ignore_case=False)) == [
        "B",
        "a",
        "b",
    ]
    assert sorted(values, key=lambda value: sort_key(value, ignore_case=True)) == [
        "a",
        "b",
        "B",
    ]


@pytest.mark.parametrize(
    "test_app",
    project(
        'extensions = ["sphinx_needs"]\n',
        """
.. req:: One value
   :id: REQ_001
   :tags: b

.. req:: Two values
   :id: REQ_002
   :tags: A, z

.. req:: Lower a
   :id: REQ_003
   :tags: a
""",
        sort="tags",
    ),
    indirect=True,
)
def test_sort_by_list_field_compares_joined_text(test_app: Sphinx):
    """A list sorts as its values joined with ``", "``, without regard to case.

    Compared value by value, with regard to case, as before, ``["A", "z"]`` came first.
    """
    test_app.build()
    assert build_warnings(test_app) == []
    assert row_order(test_app) == ["REQ_003", "REQ_002", "REQ_001"]


def test_sort_key_places_nan_after_the_other_numbers():
    """A NaN compares neither below nor above anything; it gets a place of its own."""
    values = [2.0, float("nan"), None, 1, float("nan"), 0.5]
    ordered = sorted(values, key=lambda value: sort_key(value, ignore_case=True))
    assert ordered[:4] == [None, 0.5, 1, 2.0]
    assert all(math.isnan(value) for value in ordered[4:])


TIES_PAGES = {
    "conf.py": FIELD_CONF,
    "index.rst": "Index\n=====\n\n.. toctree::\n\n   a\n   b\n   list\n   table\n",
    "a.rst": "A\n=\n\n.. req:: Second id\n   :id: REQ_002\n   :priority: 1\n",
    "b.rst": "B\n=\n\n.. req:: First id\n   :id: REQ_001\n   :priority: 1\n",
    "table.rst": "Table\n=====\n\n.. needtable::\n   :columns: id\n   :sort: priority\n",
    "list.rst": "List\n====\n\n.. needlist::\n   :sort_by: priority\n",
}


def _orders(app: SphinxTestApp) -> tuple[list[str], list[str]]:
    """The ids in the order the table and the list show them."""
    orders = []
    for page in ("table", "list"):
        html = Path(app.outdir, f"{page}.html").read_text()
        orders.append(list(dict.fromkeys(re.findall(r"\bREQ_\d+\b", html))))
    return orders[0], orders[1]


def test_equal_values_are_ordered_by_id_on_fresh_and_incremental_builds(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """Equal values used to keep the needs' own order: the order the documents were read in.

    ``a.rst`` holds ``REQ_002`` and is read before ``b.rst``, which holds ``REQ_001``; an
    incremental build that re-reads ``a.rst`` moves ``REQ_002`` to the end. With ties
    broken by id, ``:sort:`` and ``:sort_by:`` give the same order on both builds.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in TIES_PAGES.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    for edit in (None, "a.rst"):
        if edit is not None:
            path = srcdir / edit
            path.write_text(path.read_text() + "\nMore text.\n", encoding="utf-8")
        app = make_app("html", srcdir=srcdir, freshenv=edit is None)
        try:
            app.build()
            assert build_warnings(app) == []
            assert _orders(app) == (["REQ_001", "REQ_002"], ["REQ_001", "REQ_002"])
        finally:
            app.cleanup()
