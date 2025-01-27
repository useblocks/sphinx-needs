"""Test utility functions."""

import pytest

from sphinx_needs.api.need import _split_list_with_dyn_funcs


@pytest.mark.parametrize(
    "input, expected",
    [
        (None, []),
        ([], []),
        (["a"], [("a", False)]),
        ("a", [("a", False)]),
        ("a,", [("a", False)]),
        ("[[a]]", [("[[a]]", True)]),
        ("a,b", [("a", False), ("b", False)]),
        ("a, b", [("a", False), ("b", False)]),
        ("a,b,", [("a", False), ("b", False)]),
        ("a|b", [("a", False), ("b", False)]),
        ("a| b", [("a", False), ("b", False)]),
        ("a|b,", [("a", False), ("b", False)]),
        ("a;b", [("a", False), ("b", False)]),
        ("a; b", [("a", False), ("b", False)]),
        ("a;b,", [("a", False), ("b", False)]),
        ("a,b|c;d,", [("a", False), ("b", False), ("c", False), ("d", False)]),
        ("[[x,y]],b", [("[[x,y]]", True), ("b", False)]),
        ("a,[[x,y]],b", [("a", False), ("[[x,y]]", True), ("b", False)]),
        ("a,[[x,y", [("a", False), ("[[x,y]]", True)]),
        ("a,[[x,y]", [("a", False), ("[[x,y]]", True)]),
        # previously in from _split_value in needextend.py
        ("[[a]]b", [("[[a]]b", True)]),
        ("[[a;]],", [("[[a;]]", True)]),
        ("a,b;c", [("a", False), ("b", False), ("c", False)]),
        ("[[a]],[[b]];[[c]]", [("[[a]]", True), ("[[b]]", True), ("[[c]]", True)]),
        (" a ,, b; c ", [("a", False), ("b", False), ("c", False)]),
        (
            " [[a]] ,, [[b]] ; [[c]] ",
            [("[[a]]", True), ("[[b]]", True), ("[[c]]", True)],
        ),
        ("a,[[b]];c", [("a", False), ("[[b]]", True), ("c", False)]),
        (" a ,, [[b;]] ; c ", [("a", False), ("[[b;]]", True), ("c", False)]),
    ],
)
def test_split_list_with_dyn_funcs(input, expected):
    assert list(_split_list_with_dyn_funcs(input, None)) == expected
