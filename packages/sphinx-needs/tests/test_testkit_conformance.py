"""Tests for the conformance runners' value comparison (``sphinx_needs_testkit.conformance``).

A corpus pins values as ``needs.json`` writes them, and :func:`same` is what holds a
build's value to a pin in every case-per-project runner here (the derived-field and the
field-declaration corpora). A comparison that is looser than the pin lets a case pass
for the wrong value: ``-0.0 == 0.0`` in Python, so a pin of ``-0.0`` (the corpus case
``fingerprint-defaults-compared-as-text`` holds one) could not tell a build that kept the
sign from one that dropped it. ubCode's runner compares floats bit for bit, so the two
runners must agree on what "the same float" means.

They live in THIS suite for the reason ``test_testkit_warnings.py`` gives.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from sphinx_needs_testkit.conformance import check_values, same


@pytest.mark.parametrize(
    "actual,expected",
    [
        (0.0, -0.0),
        (-0.0, 0.0),
        ([0.0], [-0.0]),
        (1.0, 1.0000000000000002),
        (math.nan, 0.0),
        (math.inf, -math.inf),
    ],
    ids=[
        "zero-for-negative-zero",
        "negative-zero-for-zero",
        "in-a-list",
        "one-ulp-apart",
        "nan-for-zero",
        "infinities",
    ],
)
def test_floats_that_differ_in_their_bits_are_not_the_same(
    actual: Any, expected: Any
) -> None:
    assert not same(actual, expected)


@pytest.mark.parametrize(
    "actual,expected",
    [
        (-0.0, -0.0),
        (0.0, 0.0),
        (1.5, 1.5),
        (math.inf, math.inf),
        (math.nan, math.nan),
        (math.nan, -math.nan),
        ([math.nan, -0.0], [math.nan, -0.0]),
    ],
    ids=[
        "negative-zero",
        "zero",
        "plain",
        "infinity",
        "nan",
        "nan-of-either-sign",
        "in-a-list",
    ],
)
def test_floats_with_the_same_bits_and_every_nan_are_the_same(
    actual: Any, expected: Any
) -> None:
    """Every NaN is one value, as ``needs.json`` has no way to tell two NaNs apart."""
    assert same(actual, expected)


@pytest.mark.parametrize(
    "actual,expected,result",
    [
        (7, 7.0, False),
        (7.0, 7, False),
        (True, 1, False),
        (0, False, False),
        (7, 7, True),
        ("0.0", "-0.0", False),
        (None, None, True),
    ],
)
def test_everything_else_is_compared_as_before(
    actual: Any, expected: Any, result: bool
) -> None:
    """The type stays part of a number's identity, and a non-float compares with ``==``."""
    assert same(actual, expected) is result


def test_a_negative_zero_pin_fails_against_a_zero_value() -> None:
    """The issue's case, through the runner's own entry point: a ``-0.0`` pin read
    against a build that stored ``0.0`` is a problem, not a pass."""
    problems = check_values(
        {"REQ_1": {"zero": 0.0}}, {"needs": {"REQ_1": {"zero": -0.0}}}
    )
    assert problems == ["REQ_1.zero: 0.0, expected -0.0"]
