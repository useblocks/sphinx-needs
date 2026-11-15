"""``ub_needs_exchange.need_id``: what the need-id corpus cannot state.

Every rule of the grammar is pinned by ``tests/fixtures/need_id_conformance.toml``, which
``test_need_id_conformance.py`` runs. What a case cannot state is tested here: the
messages of a refusal, the types the functions take and give, and that splitting never
raises whatever the text.
"""

from __future__ import annotations

import pytest

from ub_needs_exchange import (
    SEPARATOR,
    format_namespace,
    id_problem,
    join_id,
    parse_namespace,
    split_id,
)


def test_the_separator():
    assert SEPARATOR == "::"


@pytest.mark.parametrize(
    "text",
    [
        "\x00::\x00",
        "\ud800::X",  # a lone surrogate: a Python str can hold one
        ":" * 1001,
        "a::" * 1000 + "X",
        "a" + ":" * 999 + "b",
        "\U0001f600::\U0001f600",
    ],
)
def test_splitting_never_raises(text):
    namespace, local = split_id(text)
    assert isinstance(namespace, tuple)
    assert join_id(namespace, local) == text
    id_problem(text)


def test_a_deep_namespace_splits_in_one_pass():
    """Many segments split without a limit (and without a backtracking regex)."""
    text = "a::" * 5000 + "X"
    assert split_id(text) == (("a",) * 5000, "X")


def test_join_takes_any_iterable_of_segments():
    assert join_id(iter(["nc", "m2"]), "X") == "nc::m2::X"
    assert join_id((s for s in ()), "a::b") == "a::b"
    assert format_namespace(iter(["nc", "m2"])) == "nc::m2"


def test_format_namespace_does_not_check():
    assert format_namespace(["a.b", ""]) == "a.b::"
    assert format_namespace(()) == ""


def test_a_refused_segment_is_named_with_the_rule():
    with pytest.raises(ValueError, match=r"'nc\.x' is not a namespace segment") as info:
        join_id(["nc", "nc.x"], "X")
    assert "ASCII letters, ASCII digits, '_' or '-'" in str(info.value)


def test_a_refused_local_id_is_named_with_the_rule():
    with pytest.raises(ValueError, match="must not be empty"):
        join_id(["nc"], "")
    with pytest.raises(ValueError, match=r"the local id 'a::b' holds '::'"):
        join_id(["nc"], "a::b")
    with pytest.raises(ValueError, match=r"the local id ':b' starts with ':'"):
        join_id(["nc"], ":b")


def test_a_refused_namespace_is_named_with_its_piece_and_the_rule():
    with pytest.raises(
        ValueError, match=r"'nc::m 2' is not a namespace: its piece 'm 2' is not"
    ) as info:
        parse_namespace("nc::m 2")
    assert "ASCII letters, ASCII digits, '_' or '-'" in str(info.value)
    with pytest.raises(ValueError, match=r"its piece '' is not"):
        parse_namespace("nc::")
