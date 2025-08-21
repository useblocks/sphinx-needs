import pytest

from sphinx_codelinks.config import OneLineCommentStyle, SourceAnalyseConfig

from .conftest import TEST_DIR


@pytest.mark.parametrize(
    ("analyse_config", "result"),
    [
        (
            SourceAnalyseConfig(
                src_files=[
                    TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                ],
                src_dir=TEST_DIR / "data" / "dcdc",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
            ],
        ),
        (
            SourceAnalyseConfig(
                src_files=None,
                src_dir=TEST_DIR / "data" / "dcdc",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
                "Schema validation error in field 'src_files': None is not of type 'array'",
            ],
        ),
    ],
)
def test_config_schema_validator_negative(analyse_config, result):
    errors = analyse_config.check_schema()
    assert sorted(errors) == sorted(result)


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
    "oneline_config",
    [
        OneLineCommentStyle(
            start_sequence="[[",
            end_sequence="]]",
            field_split_char=",",
            needs_fields=[
                {"name": "title"},
                {"name": "id"},
                {"name": "type", "default": "impl"},
                {"name": "links", "type": "list[str]", "default": []},
            ],
        ),
        OneLineCommentStyle(
            start_sequence="[[",
            end_sequence="]]",
            field_split_char=",",
            needs_fields=[
                {"name": "title"},  # minimum need_fields config
                {"name": "type"},
            ],
        ),
        OneLineCommentStyle(
            needs_fields=[  # minimum config
                {"name": "title"},
                {"name": "type"},
            ],
        ),
    ],
)
def test_oneline_schema_validator_positive(oneline_config):
    assert len(oneline_config.check_fields_configuration()) == 0
