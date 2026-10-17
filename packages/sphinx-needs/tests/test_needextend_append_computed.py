"""``needextend``'s ``:+option:`` where one side of the append is computed.

A need's value that holds a ``[[…]]`` and an extend's value that holds one are joined
into one computed value, item by item: on a link type, on a string field, and on an
array field of each item type. The two values are of the field's one kind, which
``_function_array`` checks, as the checker cannot see it (:issue:`1835`).
"""

from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx

from sphinx_needs.directives.needextend import _function_array
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.need_item import NeedLink
from sphinx_needs.needs_schema import FieldFunctionArray
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^[A-Z0-9_]+$"
needs_fields = {
    "note": {"schema": {"type": "string"}},
    "n": {"schema": {"type": "integer"}},
    "x": {"schema": {"type": "number"}},
    "b": {"schema": {"type": "boolean"}},
    "refs": {"schema": {"type": "array", "items": {"type": "string"}}},
    "counts": {"schema": {"type": "array", "items": {"type": "integer"}}},
    "weights": {"schema": {"type": "array", "items": {"type": "number"}}},
    "flags": {"schema": {"type": "array", "items": {"type": "boolean"}}},
}
"""

NEEDS = """\
Index
=====

.. req:: Source
   :id: SRC
   :n: 7
   :x: 2.5
   :b: false

.. req:: Target two
   :id: T2

.. req:: Target three
   :id: T3

.. req:: A link literal onto a computed link
   :id: L1
   :links: [[copy("id", "T2")]]

.. needextend:: L1
   :+links: T3

.. req:: A computed link onto a computed link
   :id: L2
   :links: [[copy("id", "T2")]]

.. needextend:: L2
   :+links: [[copy("id", "T3")]], T2

.. req:: Literals onto computed values
   :id: F1
   :note: pre [[copy("id")]]
   :refs: a, [[copy("id")]]
   :counts: 1, [[copy("n", "SRC")]]
   :weights: 0.5, [[copy("x", "SRC")]]
   :flags: true, [[copy("b", "SRC")]]

.. needextend:: F1
   :+note: post
   :+refs: b, c
   :+counts: 3, 4
   :+weights: 1.5
   :+flags: false, true

.. req:: Computed values onto computed values
   :id: F2
   :refs: [[copy("id")]]
   :counts: [[copy("n", "SRC")]]
   :weights: [[copy("x", "SRC")]], 3
   :flags: [[copy("b", "SRC")]]

.. needextend:: F2
   :+refs: z, [[copy("type")]]
   :+counts: 9, [[copy("n", "SRC")]]
   :+weights: [[copy("x", "SRC")]]
   :+flags: true, [[copy("b", "SRC")]]

.. req:: Computed values onto literals
   :id: F3
   :note: lit
   :refs: a
   :counts: 1, 2
   :weights: 0.25
   :flags: false

.. needextend:: F3
   :+note: [[copy("id")]] and more
   :+refs: [[copy("id")]], q
   :+counts: [[copy("n", "SRC")]], 5
   :+weights: 4, [[copy("x", "SRC")]]
   :+flags: true, [[copy("b", "SRC")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), NEEDS)],
        }
    ],
    indirect=True,
)
def test_append_joins_computed_values_of_each_kind(test_app: Sphinx):
    """Each append keeps the items of both sides, in order, computed or written."""
    test_app.build()
    assert build_warnings(test_app) == []
    needs: dict[str, dict[str, Any]] = needs_by_id(test_app)

    assert needs["L1"]["links"] == ["T2", "T3"]
    assert needs["L2"]["links"] == ["T2", "T3"]

    f1 = needs["F1"]
    # a string field's computed items are joined with spaces; the words are the point
    assert f1["note"].split() == ["pre", "F1", "post"]
    assert f1["refs"] == ["a", "F1", "b", "c"]
    assert f1["counts"] == [1, 7, 3, 4]
    assert f1["weights"] == [0.5, 2.5, 1.5]
    assert f1["flags"] == [True, False, False, True]

    f2 = needs["F2"]
    assert f2["refs"] == ["F2", "z", "req"]
    assert f2["counts"] == [7, 9, 7]
    assert f2["weights"] == [2.5, 3.0, 2.5]
    assert f2["flags"] == [False, True, False]

    f3 = needs["F3"]
    assert f3["note"].split() == ["lit", "F3", "and", "more"]
    assert f3["refs"] == ["a", "F3", "q"]
    assert f3["counts"] == [1, 2, 7, 5]
    assert f3["weights"] == [0.25, 4.0, 2.5]
    assert f3["flags"] == [False, True, False]


_COPY_ID = DynamicFunctionParsed.from_string('copy("id")', allow_need=True)


@pytest.mark.parametrize(
    "items",
    [
        ("a", _COPY_ID, "b"),
        (1, _COPY_ID, 2),
        (0.5, 1, _COPY_ID),
        (True, _COPY_ID),
        (_COPY_ID,),
        (),
    ],
)
def test_function_array_keeps_items_of_one_kind(items: tuple[Any, ...]):
    """The items of one kind are the computed value as they are, in order."""
    assert _function_array(items) == FieldFunctionArray(items)


@pytest.mark.parametrize(
    "items",
    [
        ("a", 1),
        (_COPY_ID, True, "a"),
        (NeedLink(id="T2"), _COPY_ID),
        (None,),
    ],
)
def test_function_array_refuses_items_of_two_kinds(items: tuple[Any, ...]):
    """Items no field's values hold together are refused, rather than joined."""
    with pytest.raises(RuntimeError, match="are not the values of one field"):
        _function_array(items)
