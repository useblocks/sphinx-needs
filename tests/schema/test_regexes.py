"""Unit tests for sphinx_needs.schema.config_utils module."""

import pytest

from sphinx_needs.schema.config_utils import UnsafePatternError, validate_regex_pattern


@pytest.mark.parametrize(
    "pattern",
    [
        # Basic literals
        "abc",
        "hello world",
        # Character classes
        "[abc]",
        "[a-z]",
        "[^abc]",
        # Basic quantifiers
        "a+",
        "a*",
        "a?",
        "a{2}",
        "a{2,}",
        "a{2,5}",
        # Anchors
        "^start",
        "end$",
        "^full match$",
        # Alternation
        "cat|dog",
        "red|green|blue",
        # Groups
        "(abc)",
        "(?:abc)",  # non-capturing
        "(a|b)c",
        # Any character
        "a.b",
        ".*",
    ],
)
def test_basic_patterns_allowed(pattern):
    """Test that basic regex patterns are allowed."""
    validate_regex_pattern(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        # Escaped special regex characters
        r"\(",
        r"\)",
        r"\[",
        r"\]",
        r"\{",
        r"\}",
        r"\|",
        r"\+",
        r"\*",
        r"\?",
        r"\^",
        r"\$",
        r"\\",
        # Escaped whitespace
        r"\n",
        r"\r",
        r"\t",
        r"\v",
        r"\f",
        # Escaped dot
        r"\.",
        r"file\.txt",
        r"\.\.",
    ],
)
def test_escaped_special_characters_allowed(pattern):
    """Test that escaped special characters are allowed."""
    validate_regex_pattern(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"^[a-zA-Z0-9_]+$",
        r"^(https?|ftp)://[^ /$.?#].[^ ]*$",
        r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}",
        r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$",
    ],
)
def test_complex_allowed_patterns(pattern):
    """Test complex but allowed patterns."""
    validate_regex_pattern(pattern)


@pytest.mark.parametrize(
    "pattern,expected_reason",
    [
        # Lookahead/lookbehind
        (r"(?=foo)", "lookahead/lookbehind"),
        (r"(?!foo)", "lookahead/lookbehind"),
        (r"(?<=foo)", "lookahead/lookbehind"),
        # Backreferences
        (r"(a)\1", "backreferences"),
        # Character class shortcuts
        (r"\d+", "character class shortcuts"),
        (r"\w+", "character class shortcuts"),
        (r"\b", "character class shortcuts"),
    ],
)
def test_unsafe_constructs_rejected(pattern, expected_reason):
    """Test that unsafe regex constructs are rejected."""
    with pytest.raises(UnsafePatternError) as exc:
        validate_regex_pattern(pattern)
    assert expected_reason in str(exc.value)


@pytest.mark.parametrize(
    "pattern",
    [
        r"(unclosed",
        r"[unclosed",
    ],
)
def test_invalid_regex_syntax(pattern):
    """Test that invalid regex syntax is rejected."""
    with pytest.raises(UnsafePatternError) as exc:
        validate_regex_pattern(pattern)
    assert "invalid regex syntax" in str(exc.value)
