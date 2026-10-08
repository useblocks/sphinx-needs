# @Test suite for one-line comment parser functionality, TEST_OLP_1, test, [IMPL_OLP_1]
import pytest

from sphinx_codelinks.analyse.oneline_parser import (
    OnelineParserInvalidWarning,
    WarningSubTypeEnum,
    docstring_tag,
    oneline_parser,
)
from sphinx_codelinks.config import ESCAPE, UNIX_NEWLINE, OneLineCommentStyle

from .conftest import ONELINE_COMMENT_STYLE, ONELINE_COMMENT_STYLE_DEFAULT


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            f"@title 1, IMPL_1 {UNIX_NEWLINE}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
                "start_column": 1,
                "end_column": 17,
            },
        ),
        # Test case for leading space after start sequence (bug fix)
        (
            f"@ title 1, IMPL_1 {UNIX_NEWLINE}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
                "start_column": 1,
                "end_column": 18,
            },
        ),
        # Test case for multiple leading spaces after start sequence
        (
            f"@   title 1, IMPL_1 {UNIX_NEWLINE}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
                "start_column": 1,
                "end_column": 20,
            },
        ),
        # Test case for trailing space before end sequence
        (
            f"@title 1, IMPL_1  {UNIX_NEWLINE}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
                "start_column": 1,
                "end_column": 18,
            },
        ),
        # Test case for both leading and trailing spaces
        (
            f"@  title 1, IMPL_1   {UNIX_NEWLINE}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
                "start_column": 1,
                "end_column": 21,
            },
        ),
    ],
)
def test_oneline_parser_default_config_positive(
    oneline: str, result: dict[str, str | list[str]]
) -> None:
    oneline_need = oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT)
    assert oneline_need == result


# Test case for space as field separator (as mentioned by Kilian)
# Example: @Implementation <field1> <field2>
ONELINE_COMMENT_STYLE_SPACE_SEPARATOR = OneLineCommentStyle(
    start_sequence="@",
    end_sequence=UNIX_NEWLINE,
    field_split_char=" ",
    needs_fields=[
        {"name": "title"},
        {"name": "id"},
        {"name": "type", "default": "impl"},
    ],
)


@pytest.mark.parametrize(
    "oneline, result",
    [
        # Basic space-separated fields
        (
            f"@Implementation IMPL_1{UNIX_NEWLINE}",
            {
                "title": "Implementation",
                "id": "IMPL_1",
                "type": "impl",
                "start_column": 1,
                "end_column": 22,
            },
        ),
        # Space separator with explicit type
        (
            f"@MyFeature FEAT_001 feature{UNIX_NEWLINE}",
            {
                "title": "MyFeature",
                "id": "FEAT_001",
                "type": "feature",
                "start_column": 1,
                "end_column": 27,
            },
        ),
        # Leading space after @ (the bug Kilian reported)
        (
            f"@ Implementation IMPL_2{UNIX_NEWLINE}",
            {
                "title": "Implementation",
                "id": "IMPL_2",
                "type": "impl",
                "start_column": 1,
                "end_column": 23,
            },
        ),
        # Trailing space before newline
        (
            f"@Implementation IMPL_3 {UNIX_NEWLINE}",
            {
                "title": "Implementation",
                "id": "IMPL_3",
                "type": "impl",
                "start_column": 1,
                "end_column": 23,
            },
        ),
        # Multiple leading spaces after @
        (
            f"@  Title ID_456{UNIX_NEWLINE}",
            {
                "title": "Title",
                "id": "ID_456",
                "type": "impl",
                "start_column": 1,
                "end_column": 15,
            },
        ),
        # Title contain spaces
        (
            f"@  Title\ escape\ space ID_456{UNIX_NEWLINE}",
            {
                "title": "Title escape space",
                "id": "ID_456",
                "type": "impl",
                "start_column": 1,
                "end_column": 30,
            },
        ),
    ],
)
def test_oneline_parser_space_separator(
    oneline: str, result: dict[str, str | list[str]]
) -> None:
    """Test oneline parser with space as field separator."""
    oneline_need = oneline_parser(oneline, ONELINE_COMMENT_STYLE_SPACE_SEPARATOR)
    assert oneline_need == result


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            "[[IMPL_1, title 1]]",
            {
                "id": "IMPL_1",
                "title": "title 1",
                "type": "impl",
                "links": [],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 17,
            },
        ),
        (
            "[[IMPL_2, title 2, impl, [], closed]]",
            {
                "id": "IMPL_2",
                "title": "title 2",
                "type": "impl",
                "links": [],
                "status": "closed",
                "priority": "low",
                "start_column": 2,
                "end_column": 35,
            },
        ),
        (
            "[[IMPL_3, title\, 3, impl, [], closed]]",
            {
                "id": "IMPL_3",
                "title": "title, 3",
                "type": "impl",
                "links": [],
                "status": "closed",
                "priority": "low",
                "start_column": 2,
                "end_column": 37,
            },
        ),
        (
            "[[IMPL_5, title 5, impl, [SPEC_1, SPEC_2], open]]",
            {
                "id": "IMPL_5",
                "title": "title 5",
                "type": "impl",
                "links": ["SPEC_1", "SPEC_2"],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 47,
            },
        ),
        (
            "[[IMPL_7, Function has a, in the title]]",
            {
                "id": "IMPL_7",
                "title": "Function has a",
                "type": "in the title",
                "links": [],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 38,
            },
        ),
        (
            "[[IMPL_8, [Title starts with a bracket], impl]]",
            {
                "id": "IMPL_8",
                "title": "[Title starts with a bracket]",
                "type": "impl",
                "links": [],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 45,
            },
        ),
        (
            "[[IMPL_9, Function Baz, impl, [SPEC_1, SPEC_2[text], SPEC_3], open]]",
            {
                "id": "IMPL_9",
                "title": "Function Baz",
                "type": "impl",
                "links": ["SPEC_1", "SPEC_2[text"],
                "status": "SPEC_3]",
                "priority": "open",
                "start_column": 2,
                "end_column": 66,
            },
        ),
        (
            "[[IMPL_10, title 10, impl, [SPEC_1], open]]",
            {
                "id": "IMPL_10",
                "title": "title 10",
                "type": "impl",
                "links": ["SPEC_1"],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 41,
            },
        ),
        (
            "[[IMPL_11, title 11, impl, [SPEC\,_1], open]]",
            {
                "id": "IMPL_11",
                "title": "title 11",
                "type": "impl",
                "links": ["SPEC,_1"],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 43,
            },
        ),
        (
            "[[IMPL_12, title 12, impl, [\[SPEC\,_1\]], open]]",
            {
                "id": "IMPL_12",
                "title": "title 12",
                "type": "impl",
                "links": ["[SPEC,_1]"],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 47,
            },
        ),
        (
            "[[IMPL_13, title\\ 13, impl, [\[SPEC\,_1\]], open]]",
            {
                "id": "IMPL_13",
                "title": "title\ 13",
                "type": "impl",
                "links": ["[SPEC,_1]"],
                "status": "open",
                "priority": "low",
                "start_column": 2,
                "end_column": 48,
            },
        ),
    ],
)
def test_oneline_parser_custom_config_positive(
    oneline: str, result: dict[str, str | list[str]]
) -> None:
    oneline_need = oneline_parser(oneline, ONELINE_COMMENT_STYLE)
    assert oneline_need == result


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            f"[[IMPL_4, title{ESCAPE}{ESCAPE}, 4, impl, [], closed]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.missing_square_brackets,
                msg="Field 'links' with 'type': 'list[str]' must be given with '[]' brackets",
            ),
        ),
        (
            "[[IMPL_2, Function Bar, impl, [SPEC_1, SPEC_2, open]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.missing_square_brackets,
                msg="Field 'links' with 'type': 'list[str]' must be given with '[]' brackets",
            ),
        ),
        (
            "[[IMPL_13, title 13, impl, 13[\[SPEC\,_1\]], open]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.not_start_or_end_with_square_brackets,
                msg="Field 'links' with 'type': 'list[str]' must start with '[' and end with ']'",
            ),
        ),
        (
            "[[IMPL_14, title 13, impl, 13[\[SPEC\,_1\]], open, low, high]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.too_many_fields,
                msg="7 given fields, maximum is 6",
            ),
        ),
        (
            "[[IMPL_15]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.too_few_fields,
                msg="1 given fields, minimum is 2",
            ),
        ),
        (
            f"[[IMPL_16]]{UNIX_NEWLINE}, title 16]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field 'id' contains a newline character",
            ),
        ),
    ],
)
def test_oneline_parser_custom_config_negative(
    oneline: str, result: OnelineParserInvalidWarning
) -> None:
    res = oneline_parser(oneline, ONELINE_COMMENT_STYLE)
    assert res == result


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            f"@title 17]]{UNIX_NEWLINE}, IMPL_17 {UNIX_NEWLINE}",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field 'title' contains a newline character",
            ),
        ),
        (
            f"@title 17]], IMPL_17, impl, [SPEC_3, SPEC_4{UNIX_NEWLINE} ] {UNIX_NEWLINE}",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field 'links' contains a newline character",
            ),
        ),
    ],
)
def test_oneline_parser_default_config_negative(
    oneline: str, result: OnelineParserInvalidWarning
) -> None:
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT) == result


@pytest.mark.parametrize(
    "oneline_config, result",
    [
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {"name": "type", "default": "impl"},
                    {"name": "links", "type": "list[]", "default": []},  # wrong type
                ],
            ),
            [
                "Schema validation error in need_fields 'links': 'list[]' is not one of ['str', 'list[str]']"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {"name": "type", "default": 123},  # int is invalid
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'type': 123 is not of type 'string'"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title", "qwe": "qwe"},  # invalid qwe filed
                    {"name": "id"},
                    {"name": "type", "default": "impl"},
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'title': Additional properties are not allowed ('qwe' was unexpected)"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "title"},
                    {"name": "id"},
                    {
                        "name": "type",
                        "type: ": "list[str]",
                        "default": "impl",
                    },  # wring combination of type and default
                    {"name": "links", "type": "list[str]", "default": []},
                ],
            ),
            [
                "Schema validation error in need_fields 'type': Additional properties are not allowed ('type: ' was unexpected)"
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "id"}  # "title" and "type" are not given
                ],
            ),
            ["Missing required fields: ['title', 'type']"],
        ),
        (
            OneLineCommentStyle(
                start_sequence="[[",
                end_sequence="]]",
                field_split_char=",",
                needs_fields=[
                    {"name": "id"},
                    {"name": "id"},  # duplicate
                ],
            ),
            [
                "Missing required fields: ['title', 'type']",
                "Field 'id' is defined multiple times.",
            ],
        ),
        (
            OneLineCommentStyle(
                start_sequence=1234,  # wrong type
                end_sequence=5678,
                field_split_char=2222,
                needs_fields=[
                    {"name": "id"},
                ],
            ),
            [
                "Schema validation error in field 'field_split_char': 2222 is not of type 'string'",
                "Schema validation error in field 'end_sequence': 5678 is not of type 'string'",
                "Schema validation error in field 'start_sequence': 1234 is not of type 'string'",
                "Missing required fields: ['title', 'type']",
            ],
        ),
    ],
)
def test_oneline_schema_validator_negative(oneline_config, result):
    errors = oneline_config.check_fields_configuration()
    assert sorted(errors) == sorted(result)


@pytest.mark.parametrize(
    "oneline",
    [
        # A start sequence embedded in free-form prose (word chars before it)
        # must not be treated as a one-line marker (issue #88).
        f"// Some prose that mentions @@another-tag(item_1, item_2): more text{UNIX_NEWLINE}",
        f"// See @author, check the example{UNIX_NEWLINE}",
        f"// We parse things matching @pattern, then act{UNIX_NEWLINE}",
    ],
)
def test_oneline_parser_ignores_start_sequence_in_prose(oneline: str) -> None:
    """Issue #88: only anchor a marker at the start of the comment content."""
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT) is None


@pytest.mark.parametrize(
    "oneline, expected_id",
    [
        (f"// @My Title, IMPL_1{UNIX_NEWLINE}", "IMPL_1"),  # line-comment leader
        (f"    // @My Title, IMPL_2{UNIX_NEWLINE}", "IMPL_2"),  # indented
        (f"* @My Title, IMPL_3{UNIX_NEWLINE}", "IMPL_3"),  # block-comment continuation
        (f"/// @My Title, IMPL_4{UNIX_NEWLINE}", "IMPL_4"),  # doc comment
        (f"//! @My Title, IMPL_5{UNIX_NEWLINE}", "IMPL_5"),  # inner doc comment
    ],
)
def test_oneline_parser_marker_preceded_only_by_comment_decoration(
    oneline: str, expected_id: str
) -> None:
    """A marker preceded only by comment syntax/whitespace is still recognized."""
    res = oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT)
    assert isinstance(res, dict)
    assert res["id"] == expected_id


def test_oneline_parser_bounded_marker_allowed_after_prose() -> None:
    """Explicitly-bounded markers ([[ ... ]]) are self-delimiting, so they may
    be embedded after prose; only newline-terminated markers are anchored."""
    oneline = "// one-line comment style: [[IMPL_1, title 1]]"
    res = oneline_parser(oneline, ONELINE_COMMENT_STYLE)
    assert isinstance(res, dict)
    assert res["id"] == "IMPL_1"


#: one required field (``title``): a line without the separator is a whole marker
ONE_REQUIRED_FIELD = OneLineCommentStyle(
    needs_fields=[{"name": "title"}, {"name": "type", "default": "impl"}]
)


@pytest.mark.parametrize(
    "oneline",
    [
        f"// @param x the value{UNIX_NEWLINE}",
        f"/// @return nothing{UNIX_NEWLINE}",
        f" * @only{UNIX_NEWLINE}",
    ],
)
def test_one_character_start_without_separator_is_not_a_marker(oneline: str) -> None:
    """A one-character start sequence, no field separator in the content and more than
    one required field: documentation tags such as ``@param`` are not markers, and not
    warnings either."""
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT) is None


@pytest.mark.parametrize(
    "oneline, sub_type",
    [
        (
            f"// @see A, B, C, D, E{UNIX_NEWLINE}",
            WarningSubTypeEnum.too_many_fields,
        ),
        # the fourth field is ``links``, a ``list[str]``
        (
            f"// @brief a, b, c, d{UNIX_NEWLINE}",
            WarningSubTypeEnum.missing_square_brackets,
        ),
    ],
)
def test_one_character_start_with_separator_still_warns(
    oneline: str, sub_type: WarningSubTypeEnum
) -> None:
    res = oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT)
    assert isinstance(res, OnelineParserInvalidWarning)
    assert res.sub_type == sub_type


def test_one_character_start_with_two_fields_is_still_a_need() -> None:
    """A line with the separator, ``@brief Does a, b``, is the need it always was."""
    assert oneline_parser(
        f"// @brief Does a, b{UNIX_NEWLINE}", ONELINE_COMMENT_STYLE_DEFAULT
    ) == {
        "title": "brief Does a",
        "id": "b",
        "type": "impl",
        "links": [],
        "start_column": 4,
        "end_column": 19,
    }


def test_multi_character_start_without_separator_still_warns() -> None:
    """``[[`` is specific enough: a marker with too few fields is a warning."""
    assert oneline_parser(
        "// [[ only-title ]]", ONELINE_COMMENT_STYLE
    ) == OnelineParserInvalidWarning(
        sub_type=WarningSubTypeEnum.too_few_fields,
        msg="1 given fields, minimum is 2",
    )


def test_one_character_start_with_one_required_field_is_a_need() -> None:
    """With one required field, a line without the separator is a whole marker."""
    assert oneline_parser(f"// @x{UNIX_NEWLINE}", ONE_REQUIRED_FIELD) == {
        "title": "x",
        "type": "impl",
        "start_column": 4,
        "end_column": 5,
    }


@pytest.mark.parametrize(
    "oneline, style",
    [
        ("// [[ ]]", ONELINE_COMMENT_STYLE),
        (f"// @{UNIX_NEWLINE}", ONE_REQUIRED_FIELD),
        (f"// @{UNIX_NEWLINE}", ONELINE_COMMENT_STYLE_DEFAULT),
        (f"// @   {UNIX_NEWLINE}", ONELINE_COMMENT_STYLE_DEFAULT),
    ],
)
def test_empty_content_is_not_a_marker(
    oneline: str, style: OneLineCommentStyle
) -> None:
    """Nothing between the start and end sequences: not a marker, whatever the start
    sequence and however many fields are required."""
    assert oneline_parser(oneline, style) is None


def test_an_escaped_separator_counts_as_present() -> None:
    """``\\,`` is a separator in the content, so the line is a marker, and one field
    is too few."""
    res = oneline_parser(f"// @a\\,b{UNIX_NEWLINE}", ONELINE_COMMENT_STYLE_DEFAULT)
    assert isinstance(res, OnelineParserInvalidWarning)
    assert res.sub_type == WarningSubTypeEnum.too_few_fields


def test_a_non_ascii_start_sequence_of_one_character_is_one_character() -> None:
    """One character is one code point: ``§`` is a one-character start sequence."""
    style = OneLineCommentStyle(start_sequence="§")
    assert oneline_parser(f"// §only{UNIX_NEWLINE}", style) is None
    res = oneline_parser(f"// §a title, IMPL_SECT{UNIX_NEWLINE}", style)
    assert isinstance(res, dict)
    assert res["id"] == "IMPL_SECT"


@pytest.mark.parametrize(
    "line, expected",
    [
        pytest.param("@param a: the first, thing", "param", id="param_field"),
        pytest.param("@return: nothing", "return", id="return_field"),
        pytest.param("@raise ValueError: on bad input", "raise", id="raise_field"),
        pytest.param("@type x_1: int", "type", id="type_field"),
        pytest.param("@param a:", "param", id="field_empty_text"),
        pytest.param('"""@return: nothing', "return", id="opening_quotes"),
        pytest.param("@todo fix the parser, IMPL_DS, impl", None, id="todo_title"),
        pytest.param(
            '"""@todo fix the parser, IMPL_DS, impl"""',
            None,
            id="todo_title_opening_quotes",
        ),
        pytest.param("@param a the first, thing", None, id="doxygen_comma_form"),
        pytest.param("@return", None, id="bare_tag"),
        pytest.param("@param a b: text", None, id="two_words_before_colon"),
        pytest.param("@param a : text", None, id="space_before_colon"),
        pytest.param(
            "@Todo fix the parser, IMPL_TODO2, impl", None, id="case_sensitive"
        ),
        pytest.param("@params a: text", None, id="not_a_tag"),
        pytest.param("see @param a: text", None, id="text_before_start"),
        # the field word is any run of characters other than space, tab and ``:``,
        # after spaces or tabs only: ``:|[ \t]+[^ \t:]+:``, locale-free
        pytest.param("@param नाम: text", "param", id="non_ascii_word_devanagari"),
        pytest.param("@param ä: text", "param", id="non_ascii_word_latin"),
        pytest.param("@param *args: text", "param", id="star_args_word"),
        pytest.param("@type a.b: int", "type", id="dotted_word"),
        pytest.param("@param\ta: text", "param", id="tab_separator"),
        pytest.param("@param\x1ca: text", None, id="unit_separator_is_not_a_space"),
        pytest.param(
            "@param\u3000a: text", None, id="ideographic_space_is_not_a_space"
        ),
        pytest.param("@return : text", None, id="empty_word_before_colon"),
        pytest.param("@param : text", None, id="empty_word_after_param"),
        pytest.param("@param1: text", None, id="digit_glued_to_tag"),
        pytest.param("@return_x: text", None, id="underscore_glued_to_tag"),
    ],
)
def test_docstring_tag_field_shape(line: str, expected: str | None) -> None:
    """A docstring line is a ``docstring_tag`` only when a listed tag right after the
    start sequence has the Epydoc field shape: ``:`` directly, or spaces or tabs, one
    word without space, tab or ``:``, and ``:``. The same table as ubCode's."""
    assert docstring_tag(line, "@") == expected
