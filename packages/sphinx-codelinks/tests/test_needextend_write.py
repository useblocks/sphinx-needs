# @Test suite for needextend RST generation from extracted markers, TEST_WRITE_1, test, [IMPL_CLI_WRITE]
import pytest

from sphinx_codelinks.analyse.models import MarkedContentType
from sphinx_codelinks.needextend_write import (
    MarkedContentSchema,
    convert_marked_content,
)


@pytest.mark.parametrize(
    ("markers", "texts"),
    [
        (
            [
                {
                    "filepath": "/home/jui-wen/git_repo/ub/sphinx-codelinks/tests/data/need_id_refs/dummy_1.cpp",
                    "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3",
                    "source_map": {
                        "start": {"row": 2, "column": 13},
                        "end": {"row": 2, "column": 51},
                    },
                    "tagged_scope": "void dummy_func1(){\n     //...\n }",
                    "need_ids": ["NEED_001", "NEED_002", "NEED_003", "NEED_004"],
                    "marker": "@need-ids:",
                    "type": "need-id-refs",
                },
            ],
            [
                ".. needextend:: NEED_001\n   :remote-url: https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3\n\n",
                ".. needextend:: NEED_002\n   :remote-url: https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3\n\n",
                ".. needextend:: NEED_003\n   :remote-url: https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3\n\n",
                ".. needextend:: NEED_004\n   :remote-url: https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3\n\n",
            ],
        ),
        (
            [
                {
                    "filepath": "/home/jui-wen/git_repo/ub/sphinx-codelinks/tests/data/need_id_refs/dummy_1.cpp",
                    "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3",
                    "source_map": {
                        "start": {"row": 2, "column": 13},
                        "end": {"row": 2, "column": 51},
                    },
                    "tagged_scope": "void dummy_func1(){\n     //...\n }",
                    "need_ids": ["NEED_001"],
                    "marker": "@need-ids:",
                    "type": "need-id-refs",
                },
                {
                    "filepath": "/home/jui-wen/git_repo/ub/sphinx-codelinks/tests/data/need_id_refs/dummy_1.cpp",
                    "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L10",
                    "source_map": {
                        "start": {"row": 2, "column": 13},
                        "end": {"row": 2, "column": 51},
                    },
                    "tagged_scope": "void dummy_func1(){\n     //...\n }",
                    "need_ids": ["NEED_001"],
                    "marker": "@need-ids:",
                    "type": "need-id-refs",
                },
            ],
            [
                ".. needextend:: NEED_001\n   :remote-url: https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L3,https://github.com/useblocks/sphinx-codelinks/blob/main/tests/data/need_id_refs/dummy_1.cpp#L10\n\n"
            ],
        ),
    ],
)
def test_convert_marked_content(markers, texts):
    # Normalize line endings
    texts = [line.replace("\r\n", "\n").replace("\r", "\n") for line in texts]
    needextend_texts, errors = convert_marked_content(markers)

    assert not errors

    assert needextend_texts == texts


def test_convert_marked_content_ignores_multiline_needs() -> None:
    """``write rst`` converts the references only: a multi-line need record is valid
    input and yields nothing."""
    markers = [
        {
            "filepath": "src/demo.cpp",
            "remote_url": None,
            "source_map": {
                "start": {"row": 0, "column": 3},
                "end": {"row": 5, "column": 11},
            },
            "tagged_scope": None,
            "type": "multiline-need",
            "need": {"type": "impl", "title": "Demo", "content": "", "doctype": ".rst"},
            "markup": "rst",
            "source": {"project": "p", "path": "src/demo.cpp", "root": "git"},
        },
        {
            "filepath": "src/demo.cpp",
            "remote_url": "https://example.com/src/demo.cpp#L8",
            "source_map": {
                "start": {"row": 7, "column": 13},
                "end": {"row": 7, "column": 21},
            },
            "tagged_scope": None,
            "need_ids": ["NEED_001"],
            "marker": "@need-ids:",
            "type": "need-id-refs",
        },
    ]

    needextend_texts, errors = convert_marked_content(markers)

    assert not errors
    assert needextend_texts == [
        ".. needextend:: NEED_001\n   :remote-url: https://example.com/src/demo.cpp#L8\n\n"
    ]


def test_a_multiline_need_record_needs_its_need() -> None:
    schema = MarkedContentSchema(
        filepath="src/demo.cpp",
        remote_url=None,
        source_map={"start": {"row": 0, "column": 0}, "end": {"row": 1, "column": 0}},
        tagged_scope=None,
        type=MarkedContentType.multiline_need,
    )

    assert schema.check_conditional_required_fields() == [
        "Need definition is required for marked content of type 'multiline-need'"
    ]
