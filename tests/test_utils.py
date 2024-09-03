"""Test utility functions."""

import pytest

from sphinx_needs.api.need import _split_list_with_dyn_funcs


@pytest.mark.parametrize(
    "input, expected",
    [
        (None, []),
        ([], []),
        (["a"], ["a"]),
        ("a", ["a"]),
        ("a,b", ["a", "b"]),
        ("a, b", ["a", "b"]),
        ("a,b,", ["a", "b"]),
        ("a|b", ["a", "b"]),
        ("a| b", ["a", "b"]),
        ("a|b,", ["a", "b"]),
        ("a;b", ["a", "b"]),
        ("a; b", ["a", "b"]),
        ("a;b,", ["a", "b"]),
        ("a,b|c;d,", ["a", "b", "c", "d"]),
        ("[[x,y]],b", ["[[x,y]]", "b"]),
        ("a,[[x,y]],b", ["a", "[[x,y]]", "b"]),
        ("a,[[x,y", ["a", "[[x,y]]"]),
        ("a,[[x,y]", ["a", "[[x,y]]"]),
    ],
)
def test_split_list_with_dyn_funcs(input, expected):
    assert _split_list_with_dyn_funcs(input, None) == expected
