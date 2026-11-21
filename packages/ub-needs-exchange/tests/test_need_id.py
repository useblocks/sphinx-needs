"""``ub_needs_exchange.need_id``: what the need-id corpus cannot state.

Every rule of the grammar is pinned by ``tests/fixtures/need_id_conformance.toml``, which
``test_need_id_conformance.py`` runs. What a case cannot state is tested here: the
messages of a refusal, the types the functions take and give, that splitting never
raises whatever the text, and the two laws of ``namespace_prefix`` over every short text of
a small alphabet.
"""

from __future__ import annotations

import itertools

import pytest

from ub_needs_exchange import (
    SEPARATOR,
    format_namespace,
    id_problem,
    join_id,
    namespace_prefix,
    need_id,
    parse_namespace,
    split_id,
)


def test_the_separator():
    assert SEPARATOR == "::"


def test_the_public_names():
    """The module's API, which the corpus's other implementations mirror."""
    assert set(need_id.__all__) == {
        "SEPARATOR",
        "EMPTY_LOCAL",
        "EMPTY_SEGMENT",
        "SEGMENT_CHARACTER",
        "is_segment",
        "split_id",
        "id_problem",
        "join_id",
        "namespace_prefix",
        "parse_namespace",
        "format_namespace",
    }


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


def test_a_deep_namespace_splits():
    """Many segments split without a limit."""
    text = "a::" * 5000 + "X"
    assert split_id(text) == (("a",) * 5000, "X")


@pytest.mark.parametrize(
    "make",
    [
        lambda: ["nc", "m2"],
        lambda: ("nc", "m2"),
        lambda: (segment for segment in ["nc", "m2"]),
        lambda: iter(["nc", "m2"]),
    ],
    ids=["list", "tuple", "generator", "iterator"],
)
def test_a_sequence_of_segments_is_a_namespace(make):
    """Any iterable of segments is a namespace: a list, a tuple, a generator."""
    assert format_namespace(make()) == "nc::m2"
    assert join_id(make(), "X") == "nc::m2::X"


def test_an_empty_generator_is_the_empty_namespace():
    assert join_id((segment for segment in ()), "a::b") == "a::b"
    assert format_namespace(segment for segment in ()) == ""


def test_a_bare_string_is_not_a_namespace():
    """A ``str`` is an iterable of strings, but iterating it gives its characters
    (``"nc"`` would be ``n::c``): both functions refuse it with a ``TypeError``, whose
    advice ``test_a_bare_string_is_refused_with_advice_that_holds`` pins."""
    with pytest.raises(TypeError, match=r"not the string 'nc'"):
        format_namespace("nc")
    with pytest.raises(TypeError, match=r"not the string 'nc'"):
        join_id("nc", "X")
    with pytest.raises(TypeError, match=r"not the string ''"):
        join_id("", "X")
    with pytest.raises(TypeError, match=r"not the string ''"):
        format_namespace("")


@pytest.mark.parametrize(
    ("text", "offers_a_list"),
    [("nc", True), ("nc::m2", False), ("", False), ("a.b", False)],
)
def test_a_bare_string_is_refused_with_advice_that_holds(text, offers_a_list):
    """``[text]`` is offered only where *text* is one segment; ``parse_namespace(text)``
    always."""
    with pytest.raises(TypeError) as info:
        join_id(text, "X")
    message = str(info.value)
    assert f"parse_namespace({text!r})" in message
    assert (f"[{text!r}]" in message) == offers_a_list


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


# --- namespace_prefix ----------------------------------------------------------------

#: The alphabet of the laws below: a letter, the colon the separator is made of, and three
#: characters that are not segment characters. Every text over it up to ``LAW_LENGTH``
#: characters, the empty one included, is checked -- 488 281 texts, about a second.
LAW_ALPHABET = "a: _."
LAW_LENGTH = 8


def _law_texts():
    for length in range(LAW_LENGTH + 1):
        for chars in itertools.product(LAW_ALPHABET, repeat=length):
            yield "".join(chars)


@pytest.mark.parametrize("namespace", [("SUP",), ("SUP", "m2")], ids=["one", "two"])
def test_the_prefix_laws_over_every_short_text(namespace):
    """For every text ``x`` of the alphabet, with ``(xns, xlocal) = split_id(x)``: where
    ``join_id(namespace + xns, xlocal)`` is accepted it equals the prefix followed by
    ``x`` (L1); where it is refused, the prefix followed by ``x`` is a plain id, with a
    problem (L2). It is refused exactly when ``x`` is empty, starts with ``:``, or holds
    ``::`` and does not split cleanly. Both counts are positive controls."""
    prefix = namespace_prefix(namespace)
    accepted = refused = 0
    for text in _law_texts():
        text_namespace, local = split_id(text)
        cannot_be_joined = (
            not text
            or text.startswith(SEPARATOR[0])
            or (SEPARATOR in text and id_problem(text) is not None)
        )
        try:
            joined = join_id(namespace + text_namespace, local)
        except ValueError:
            if not cannot_be_joined:
                pytest.fail(f"{text!r} is refused under {namespace!r}, unexpectedly")
            prefixed = prefix + text
            if split_id(prefixed) != ((), prefixed) or id_problem(prefixed) is None:
                pytest.fail(f"L2 fails on {text!r} under {namespace!r}")
            refused += 1
        else:
            if cannot_be_joined:
                pytest.fail(f"{text!r} is joined under {namespace!r}, unexpectedly")
            if joined != prefix + text:
                pytest.fail(f"L1 fails on {text!r} under {namespace!r}")
            accepted += 1
    assert (accepted, refused) == (327640, 160641)


def test_the_prefix_of_the_empty_namespace_is_empty():
    assert namespace_prefix(()) == ""
    assert namespace_prefix([]) == ""
    assert namespace_prefix(segment for segment in ()) == ""


@pytest.mark.parametrize(
    "make",
    [
        lambda: ["nc", "m2"],
        lambda: ("nc", "m2"),
        lambda: (segment for segment in ["nc", "m2"]),
        lambda: iter(["nc", "m2"]),
    ],
    ids=["list", "tuple", "generator", "iterator"],
)
def test_the_prefix_takes_any_sequence_of_segments(make):
    """A generator is read once: its segments are checked and joined, not lost."""
    prefix = namespace_prefix(make())
    assert prefix == "nc::m2::"
    assert type(prefix) is str


def test_the_prefix_ends_in_the_separator_and_joins_like_join_id():
    """The prefix is the namespace's text and the separator, and put before a local id
    it is exactly what ``join_id`` makes."""
    assert namespace_prefix(["SUP"]) == format_namespace(["SUP"]) + SEPARATOR
    assert namespace_prefix(["SUP"]) + "REQ_1" == join_id(["SUP"], "REQ_1")


@pytest.mark.parametrize("text", ["SUP", "", "nc::m2"])
def test_the_prefix_refuses_a_bare_string(text):
    """A ``str`` is refused with the module's ``TypeError``, its advice included: ``"SUP"``
    is not the namespace ``S::U::P``."""
    with pytest.raises(TypeError, match=rf"not the string {text!r}") as info:
        namespace_prefix(text)
    assert f"parse_namespace({text!r})" in str(info.value)


@pytest.mark.parametrize(
    "namespace", [["nc", "nc.x"], [""], ["a::b"], ["nc\n"]], ids=repr
)
def test_a_refused_prefix_is_named_in_join_ids_words(namespace):
    """The message names the segment and the rule, in exactly the words ``join_id``
    uses for the same namespace."""
    with pytest.raises(ValueError) as info:
        namespace_prefix(namespace)
    with pytest.raises(ValueError) as joined:
        join_id(namespace, "X")
    assert str(info.value) == str(joined.value)
    assert f"{namespace[-1]!r} is not a namespace segment" in str(info.value)
    assert "ASCII letters, ASCII digits, '_' or '-'" in str(info.value)
