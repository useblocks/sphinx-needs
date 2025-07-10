import os

import pytest

from sphinx_codelinks.virtual_docs.config import (
    ESCAPE,
    OneLineCommentStyle,
    VirtualDocsConfig,
)
from sphinx_codelinks.virtual_docs.utils import (
    OnelineParserInvalidWarning,
    WarningSubTypeEnum,
    oneline_parser,
)
from sphinx_codelinks.virtual_docs.virtual_docs import VirtualDocs

from .conftest import TEST_DIR

ONELINE_COMMENT_STYLE = OneLineCommentStyle(
    start_sequence="[[",
    end_sequence="]]",
    field_split_char=",",
    needs_fields=[
        {"name": "id"},
        {"name": "title"},
        {"name": "type", "default": "impl"},
        {"name": "links", "type": "list[str]", "default": []},
        {"name": "status", "default": "open"},
        {"name": "priority", "default": "low"},
    ],
)

ONELINE_COMMENT_STYLE_DEFAULT = OneLineCommentStyle()


@pytest.mark.parametrize(
    ("vdocs_config", "result"),
    [
        (
            VirtualDocsConfig(
                src_files=[
                    TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                ],
                src_dir=TEST_DIR / "data" / "dcdc",
                output_dir=TEST_DIR / "output",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
            ],
        ),
        (
            VirtualDocsConfig(
                src_files=None,
                src_dir=TEST_DIR / "data" / "dcdc",
                output_dir=TEST_DIR / "output",
                comment_type=123,
            ),
            [
                "Schema validation error in field 'comment_type': 123 is not of type 'string'",
                "Schema validation error in field 'src_files': None is not of type 'array'",
            ],
        ),
    ],
)
def test_config_schema_validator_negative(vdocs_config, result):
    errors = vdocs_config.check_schema()
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
            },
        ),
    ],
)
def test_oneline_parser_custom_config_positive(oneline: str, result):
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE) == result


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            f"@title 1, IMPL_1 {os.linesep}",
            {
                "title": "title 1",
                "id": "IMPL_1",
                "type": "impl",
                "links": [],
            },
        ),
    ],
)
def test_oneline_parser_default_config_positive(oneline: str, result):
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT) == result


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
            f"[[IMPL_16]]{os.linesep}, title 16]]",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field id has newline character. It is not allowed",
            ),
        ),
    ],
)
def test_oneline_parser_custom_config_negative(
    oneline: str, result: OnelineParserInvalidWarning
):
    res = oneline_parser(oneline, ONELINE_COMMENT_STYLE)
    assert res == result


@pytest.mark.parametrize(
    "oneline, result",
    [
        (
            f"@title 17]]{os.linesep}, IMPL_17 {os.linesep}",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field title has newline character. It is not allowed",
            ),
        ),
        (
            f"@title 17]], IMPL_17, impl, [SPEC_3, SPEC_4{os.linesep} ] {os.linesep}",
            OnelineParserInvalidWarning(
                sub_type=WarningSubTypeEnum.newline_in_field,
                msg="Field links has newline character. It is not allowed",
            ),
        ),
    ],
)
def test_oneline_parser_default_config_negative(oneline: str, result):
    assert oneline_parser(oneline, ONELINE_COMMENT_STYLE_DEFAULT) == result


@pytest.mark.parametrize(
    "src_dir, src_paths , oneline_comment_style, result",
    [
        (
            TEST_DIR / "data" / "dcdc",
            [
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_2.cpp",
                TEST_DIR / "data" / "dcdc" / "discharge" / "demo_3.cpp",
                TEST_DIR / "data" / "dcdc" / "supercharge.cpp",
            ],
            ONELINE_COMMENT_STYLE,
            {
                "num_virtual_docs": 4,
                "num_src_files": 4,
                "num_uncached_files": 4,
                "num_cached_files": 0,
                "num_valid_comments": 10,
                "num_oneline_warnings": 2,
            },
        ),
        (
            TEST_DIR / "data" / "oneline_comment_basic",
            [
                TEST_DIR / "data" / "oneline_comment_basic" / "basic_oneliners.c",
            ],
            ONELINE_COMMENT_STYLE,
            {
                "num_virtual_docs": 1,
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_valid_comments": 8,
                "num_oneline_warnings": 0,
                "warnings_path_exists": True,
            },
        ),
        (
            TEST_DIR / "data" / "oneline_comment_default",
            [
                TEST_DIR / "data" / "oneline_comment_default" / "default_oneliners.c",
            ],
            ONELINE_COMMENT_STYLE_DEFAULT,
            {
                "num_virtual_docs": 1,
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_valid_comments": 4,
                "num_oneline_warnings": 1,
                "warnings_path_exists": True,
            },
        ),
    ],
)
def test_virtual_docs(tmp_path, src_dir, src_paths, oneline_comment_style, result):
    virtual_docs = VirtualDocs(src_paths, src_dir, tmp_path, oneline_comment_style)
    virtual_docs.collect()

    assert len(virtual_docs.virtual_docs) == result["num_virtual_docs"]
    assert len(virtual_docs.src_files) == result["num_src_files"]
    assert len(virtual_docs.cache.uncached_files) == result["num_uncached_files"]
    assert len(virtual_docs.cache.cached_files) == result["num_cached_files"]
    assert len(virtual_docs.oneline_warnings) == result["num_oneline_warnings"]
    assert virtual_docs.warnings_path.exists()

    loaded_warnings = VirtualDocs.load_warnings(tmp_path)

    cnt_comments = 0
    for virtual_doc in virtual_docs.virtual_docs:
        cnt_comments += len(virtual_doc.comments)
    assert cnt_comments == result["num_valid_comments"]

    # generate virtual documents
    virtual_docs.dump_virtual_docs()
    for src_file in src_paths:
        assert (tmp_path / src_file.with_suffix(".json").relative_to(src_dir)).exists()

    # cache
    virtual_docs.cache.update_cache()
    assert len(virtual_docs.cache.cached_files) == result["num_uncached_files"]
    assert len(virtual_docs.cache.uncached_files) == result["num_cached_files"]
    cache_file = tmp_path / "ubt_cache.json"
    assert cache_file.exists()

    # save the current virtual documents
    saved_virtual_docs = virtual_docs.virtual_docs

    # use cache
    del virtual_docs
    virtual_docs = VirtualDocs(src_paths, src_dir, tmp_path, oneline_comment_style)
    virtual_docs.collect()
    assert len(virtual_docs.cache.cached_files) == result["num_uncached_files"]
    assert len(virtual_docs.cache.uncached_files) == result["num_cached_files"]
    cache_file = tmp_path / "ubt_cache.json"
    assert cache_file.exists()
    assert VirtualDocs.load_warnings(tmp_path) == loaded_warnings
    assert virtual_docs.virtual_docs == saved_virtual_docs
