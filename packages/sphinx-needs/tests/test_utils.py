"""Unit tests of the helpers in ``sphinx_needs.utils``."""

from collections.abc import Collection

import pytest

from sphinx_needs.utils import counted_ids


@pytest.mark.parametrize(
    ("ids", "noun", "expected"),
    [
        pytest.param([], "", "0", id="none"),
        pytest.param([], " needs", "0 needs", id="none-with-noun"),
        pytest.param(["REQ_1"], " need", "1 need (REQ_1)", id="one"),
        pytest.param(["C", "A", "B"], "", "3 (A, B, C)", id="three-named"),
        pytest.param(["D", "C", "B", "A"], "", "4 (A, B, C and 1 more)", id="four"),
        pytest.param(["REQ_9", "REQ_10"], "", "2 (REQ_10, REQ_9)", id="string-order"),
        pytest.param(
            frozenset(f"REQ_{n}" for n in range(1, 7)),
            " needs",
            "6 needs (REQ_1, REQ_2, REQ_3 and 3 more)",
            id="set",
        ),
    ],
)
def test_counted_ids(ids: Collection[str], noun: str, expected: str):
    """The count, then the first three ids in need-id order and how many more there are.

    The shape a message about a set of needs uses, so that it stays short however many
    needs there are and reads the same whatever order the set was built in: ids are
    sorted as strings, and no ids is the count alone.
    """
    assert counted_ids(ids, noun) == expected
