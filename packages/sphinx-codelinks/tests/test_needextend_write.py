# @Test suite for needextend RST generation from extracted markers, TEST_WRITE_1, test, [IMPL_CLI_WRITE]
import pytest

from sphinx_codelinks.needextend_write import convert_marked_content


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
