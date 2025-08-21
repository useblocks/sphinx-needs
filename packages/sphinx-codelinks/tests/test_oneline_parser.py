import pytest

from sphinx_codelinks.analyse.oneline_parser import (
    OnelineParserInvalidWarning,
    WarningSubTypeEnum,
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
    ],
)
def test_oneline_parser_default_config_positive(
    oneline: str, result: dict[str, str | list[str]]
) -> None:
    oneline_need = oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT)
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
                msg="Field links with 'type': 'list[str]' must be given with '[]' brackets",
            ),
        ),
        (
            "[[IMPL_2, Function Bar, impl, [SPEC_1, SPEC_2, open]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.missing_square_brackets,
                msg="Field links with 'type': 'list[str]' must be given with '[]' brackets",
            ),
        ),
        (
            "[[IMPL_13, title 13, impl, 13[\[SPEC\,_1\]], open]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.not_start_or_end_with_square_brackets,
                msg="Field links with 'type': 'list[str]' must start with '[' and end with ']'",
            ),
        ),
        (
            "[[IMPL_14, title 13, impl, 13[\[SPEC\,_1\]], open, low, high]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.too_many_fields,
                msg="7 given fields. They shall be less than 6",
            ),
        ),
        (
            "[[IMPL_15]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.too_few_fields,
                msg="1 given fields. They shall be more than 2",
            ),
        ),
        (
            f"[[IMPL_16]]{UNIX_NEWLINE}, title 16]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field id has newline character. It is not allowed",
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
                msg="Field title has newline character. It is not allowed",
            ),
        ),
        (
            f"@title 17]], IMPL_17, impl, [SPEC_3, SPEC_4{UNIX_NEWLINE} ] {UNIX_NEWLINE}",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field links has newline character. It is not allowed",
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
