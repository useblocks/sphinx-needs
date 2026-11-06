"""Unit tests of the helpers in ``sphinx_needs.utils``."""

from collections.abc import Collection

import pytest

from sphinx_needs.utils import counted_ids, external_part_url


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


@pytest.mark.parametrize(
    ("external_url", "need_id", "expected"),
    [
        pytest.param(
            "https://up.example.org/docs/index.html#UP_001",
            "UP_001",
            "https://up.example.org/docs/index.html#UP_001.p1",
            id="default-url",
        ),
        pytest.param(
            "https://up.example.org/docs/index.html#UP_001",
            "EXT_UP_001",
            "https://up.example.org/docs/index.html#UP_001.p1",
            id="default-url-id-prefix",
        ),
        pytest.param(
            "../up/sub/page.html#UP_001",
            "UP_001",
            "../up/sub/page.html#UP_001.p1",
            id="relative-base-url",
        ),
        pytest.param(
            "https://up.example.org/docs/issue/UP_001",
            "UP_001",
            "https://up.example.org/docs/issue/UP_001",
            id="no-fragment",
        ),
        pytest.param(
            "https://up.example.org/docs/page.html#",
            "UP_001",
            "https://up.example.org/docs/page.html#",
            id="empty-fragment",
        ),
        pytest.param(
            "https://up.example.org/docs/page.html#req-UP_001",
            "UP_001",
            "https://up.example.org/docs/page.html#req-UP_001",
            id="fragment-not-a-suffix-of-the-id",
        ),
        pytest.param(
            "https://up.example.org/docs/index.html#UP_001",
            "UP_0011",
            "https://up.example.org/docs/index.html#UP_001",
            id="fragment-a-prefix-of-the-id",
        ),
    ],
)
def test_external_part_url(external_url: str, need_id: str, expected: str):
    """The URL of a part of an external need, from the need's URL (#2487).

    A sphinx-needs page anchors a part at ``<id>.<part>``. The default URL of an external
    need ends in ``#<id>``, the id as its source wrote it, which an ``id_prefix`` only
    prepends to: then the part's fragment is ``<id>.<part>``. Any other URL is kept as
    it is, since nothing says where on that page the part is.
    """
    assert external_part_url(external_url, need_id, "p1") == expected
