"""A link's string form: every condition the writer spells reads back as itself, and
every link string the reader read cleanly before still reads the same.

``NeedLink.to_link_string`` writes the string format 1 of needs.json carries (and that
an author may write), ``NeedLink.from_string_with_warnings`` reads it. Two properties
are pinned here:

- the round trip: for every link, ``from_string_with_warnings(link.to_link_string())``
  is ``(link, [])`` -- explicit cases first, then a property test over conditions
  holding ``[`` and ``]`` anywhere;
- nothing moves for a string that read without a warning: a frozen copy of the reader as
  it was in 9.2.0 (``_reference_parse``) is the oracle, over every string of a small
  alphabet up to a length, and over longer random strings. A string the old reader warned
  about (unclosed brackets, text after the closing ones) may read differently now: that
  is where a condition the writer spells, but the old reader could not read, lives.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sphinx_needs.need_item import NeedLink

# The reader as it was in sphinx-needs 9.2.0 (`NeedLink.from_string_with_warnings` and
# `NeedLink.parse_address`), copied verbatim but for the names. It is the oracle of
# "every string that read cleanly reads the same": never edit it to follow the reader.


def _reference_parse_address(
    address: str, /, *, condition: str | None = None
) -> NeedLink:
    if "." in address:
        id_, part = address.split(".", maxsplit=1)
        return NeedLink(id=id_, part=part, condition=condition)
    return NeedLink(id=address, condition=condition)


def _reference_parse(
    link_str: str, *, parse_conditions: bool = True
) -> tuple[NeedLink, list[str]]:
    warnings: list[str] = []

    if not parse_conditions:
        return _reference_parse_address(link_str), warnings

    # Find the first '[' that could start a condition
    bracket_start = link_str.find("[")
    if bracket_start <= 0:
        # No condition or no address before '[' — plain ID or ID.part
        return _reference_parse_address(link_str), warnings

    address = link_str[:bracket_start]
    rest = link_str[bracket_start:]

    # Count opening bracket depth
    depth = 0
    while depth < len(rest) and rest[depth] == "[":
        depth += 1

    # Find the matching closing brackets
    closing = "]" * depth
    inner = rest[depth:]
    close_pos = inner.find(closing)
    if close_pos < 0:
        warnings.append(
            f"Unclosed condition brackets in link {link_str!r}: "
            f"expected {depth} closing ']' characters."
        )
        return _reference_parse_address(link_str), warnings

    trailing = inner[close_pos + depth :]
    if trailing:
        warnings.append(
            f"Unexpected text after closing condition bracket "
            f"in link {link_str!r}: {trailing!r}."
        )
        return _reference_parse_address(address), warnings

    condition = inner[:close_pos]
    link = _reference_parse_address(address, condition=condition if condition else None)
    return link, warnings


#: (condition, its spelling after the id ``B``): conditions that END in ``]``, which
#: the reader of 9.2.0 read with a warning and without the condition.
ENDS_IN_A_BRACKET = [
    ("x == a[0]", "[[x == a[0]]]"),
    ("status in ['open']", "[[status in ['open']]]"),
    ("a]", "[[a]]]"),
    ("]", "[[]]]"),
    ("]]", "[[[]]]]]"),
    ("a]]", "[[[a]]]]]"),
    ("a[b[0]]", "[[[a[b[0]]]]]"),
]

#: (condition, its spelling): conditions the writer and reader of 9.2.0 already agreed on,
#: kept here so that a change to either is seen beside the cases above
ALREADY_ROUND_TRIPPED = [
    ("x", "[x]"),
    ("x]]y", "[[[x]]y]]]"),
    ("]a", "[[]a]]"),
    ("a[", "[a[]"),
    ("x ] ", "[[x ] ]]"),
    ("tags[0] == 'x'", "[[tags[0] == 'x']]"),
]

#: (condition, its spelling): conditions that START with ``[`` (after any spaces), which
#: the reader of 9.2.0 read as another link or with a warning. One that also ends in
#: ``]`` is written with one space after the opening brackets, which the reader drops;
#: one that does not is written as any other, and read where the closing brackets that
#: end the link are fewer than the opening ones.
STARTS_WITH_A_BRACKET = [
    ("[x]", "[[ [x]]]"),
    ("[x] == a[0]", "[[ [x] == a[0]]]"),
    ("[]", "[[ []]]"),
    (" [x]", "[[  [x]]]"),
    ("  [x]", "[[   [x]]]"),
    ("[1] == y", "[[[1] == y]]"),
    ("[x", "[[x]"),
    ("[", "[[]"),
    ("[[", "[[[]"),
    ("[[x]] y", "[[[[[x]] y]]]"),
]

CASES = ENDS_IN_A_BRACKET + STARTS_WITH_A_BRACKET + ALREADY_ROUND_TRIPPED


@pytest.mark.parametrize("part", [None, "p1"], ids=["no-part", "part"])
@pytest.mark.parametrize(
    ("condition", "spelled"), CASES, ids=[repr(c) for c, _ in CASES]
)
def test_a_condition_is_spelled_and_read_back(
    condition: str, spelled: str, part: str | None
) -> None:
    """The writer's spelling of each condition, with and without a part, and the reader
    reading that spelling back as the same link, with no warning."""
    link = NeedLink(id="B", part=part, condition=condition)
    base = "B.p1" if part else "B"
    assert link.to_link_string() == base + spelled
    assert NeedLink.from_string_with_warnings(link.to_link_string()) == (link, [])


@pytest.mark.parametrize(
    ("written", "condition"),
    [
        # depth one, as an author writes it: the condition runs to the closing bracket
        # that ends the link, not to the first one
        ("REQ_1[status in ['open']]", "status in ['open']"),
        ("REQ_1.p1[x == a[0]]", "x == a[0]"),
        ("REQ_1[a]b]", "a]b"),
        # a condition that starts with `[` and ends with `]`: one space after the
        # opening brackets, at any depth
        ("REQ_1[ ['open'] == tags[:1]]", "['open'] == tags[:1]"),
        ("REQ_1[[ [x]]]", "[x]"),
        # one that starts with `[` and does not end with `]`
        ("REQ_1[[1] == y]", "[1] == y"),
    ],
)
def test_the_condition_ends_at_the_closing_brackets_that_end_the_link(
    written: str, condition: str
) -> None:
    """A link that ends with as many ``]`` as it opened with: the condition is all that
    lies between, read without a warning. ``REQ_1[a]b]`` warned before (text after the
    closing bracket) and read as ``REQ_1`` without a condition."""
    link, warnings = NeedLink.from_string_with_warnings(written)
    assert (link.condition, warnings) == (condition, [])


def test_an_empty_condition_is_no_condition() -> None:
    """``""`` is spelled ``B[]``, which reads as no condition: an empty condition and
    no condition are the same link (the one condition that does not round-trip, by
    design)."""
    assert NeedLink(id="B", condition="").to_link_string() == "B[]"
    assert NeedLink.from_string_with_warnings("B[]") == (NeedLink(id="B"), [])


@pytest.mark.parametrize(
    "written",
    [
        "NEED-1[cond]extra",  # text after the closing bracket, not ending with one
        "NEED-1[[a]]b]",  # ends with one `]`, opened with two
        "NEED-1[unclosed",
    ],
)
def test_a_malformed_link_still_warns(written: str) -> None:
    """A link whose closing brackets do not end it, or that has none, is still
    malformed: one warning, and no condition."""
    link, warnings = NeedLink.from_string_with_warnings(written)
    assert link.condition is None
    assert len(warnings) == 1


_CONDITIONS = st.text(alphabet="x[] a=0'", min_size=1, max_size=30)
_PARTS = st.sampled_from([None, "p1"])


@given(condition=_CONDITIONS, part=_PARTS)
def test_every_condition_round_trips(condition: str, part: str | None) -> None:
    """The property behind the cases above, over conditions holding ``[`` and ``]`` at
    any position, the end included."""
    link = NeedLink(id="B", part=part, condition=condition)
    assert NeedLink.from_string_with_warnings(link.to_link_string()) == (link, [])


def _all_strings(alphabet: str, max_length: int) -> itertools.chain[str]:
    return itertools.chain.from_iterable(
        ("".join(t) for t in itertools.product(alphabet, repeat=n))
        for n in range(max_length + 1)
    )


def _key(link: NeedLink) -> tuple[str, str | None, str | None]:
    return (link.id, link.part, link.condition)


def _assert_reads_as_before(written: str) -> None:
    before, before_warnings = _reference_parse(written)
    if before_warnings:
        return
    now, warnings = NeedLink.from_string_with_warnings(written)
    assert (_key(now), warnings) == (_key(before), []), written


def test_every_clean_string_reads_as_before_exhaustively() -> None:
    """Every string over ``B.[] x`` of length 7 or less (335,923 of them) that the
    9.2.0 reader read without a warning reads the same, without a warning."""
    for written in _all_strings("B.[] x", 7):
        _assert_reads_as_before(written)


@given(written=st.text(alphabet="B.[] x=a", max_size=40))
def test_every_clean_string_reads_as_before(written: str) -> None:
    """The same over longer strings, where deeper brackets and longer runs live."""
    _assert_reads_as_before(written)


def test_without_conditions_every_string_reads_as_before() -> None:
    """A link type that does not parse conditions reads every string as before: the
    brackets stay in the id or the part."""
    for written in _all_strings("B.[] x", 6):
        assert NeedLink.from_string_with_warnings(
            written, parse_conditions=False
        ) == _reference_parse(written, parse_conditions=False), written
