# @Test suite for source code analysis and marker extraction, TEST_ANA_1, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MRST_1]
import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import SourceAnalyseConfig
from tests.conftest import (
    ONELINE_COMMENT_STYLE,
    ONELINE_COMMENT_STYLE_DEFAULT,
    TEST_DIR,
)

TEST_DATA_DIR = Path(__file__).parent.parent / "tests" / "data"


@pytest.mark.parametrize(
    ("src_dir", "src_paths"),
    [
        (
            TEST_DATA_DIR,
            [
                TEST_DATA_DIR / "oneline_comment_default" / "default_oneliners.c",
                TEST_DATA_DIR / "need_id_refs" / "dummy_1.cpp",
                TEST_DATA_DIR / "marked_rst" / "dummy_1.cpp",
            ],
        )
    ],
)
def test_analyse(src_dir, src_paths, tmp_path, snapshot_marks):
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=True,
        get_oneline_needs=True,
        get_rst=True,
    )

    analyse = SourceAnalyse(src_analyse_config)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    analyse.dump_marked_content(tmp_path)

    dumped_content = tmp_path / "marked_content.json"
    with dumped_content.open("r") as f:
        marked_content = json.load(f)
    # normalize filepath
    for obj in marked_content:
        obj["filepath"] = (
            Path(obj["filepath"]).relative_to(src_analyse_config.src_dir)
        ).as_posix()
    assert marked_content == snapshot_marks


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
                "num_src_files": 4,
                "num_uncached_files": 4,
                "num_cached_files": 0,
                "num_comments": 29,
                "num_oneline_warnings": 0,
            },
        ),
        (
            TEST_DIR / "data" / "oneline_comment_basic",
            [
                TEST_DIR / "data" / "oneline_comment_basic" / "basic_oneliners.c",
            ],
            ONELINE_COMMENT_STYLE,
            {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 14,
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
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 5,
                "num_oneline_warnings": 1,
                "warnings_path_exists": True,
            },
        ),
        (
            TEST_DIR / "data" / "rust",
            [
                TEST_DIR / "data" / "rust" / "demo.rs",
            ],
            ONELINE_COMMENT_STYLE_DEFAULT,
            {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 6,
                "num_oneline_warnings": 0,
            },
        ),
    ],
)
def test_analyse_oneline_needs(
    tmp_path, src_dir, src_paths, oneline_comment_style, result
):
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        oneline_comment_style=oneline_comment_style,
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    assert len(src_analyse.src_files) == result["num_src_files"]
    assert len(src_analyse.oneline_warnings) == result["num_oneline_warnings"]

    cnt_comments = 0
    for src_file in src_analyse.src_files:
        cnt_comments += len(src_file.src_comments)
    assert cnt_comments == result["num_comments"]
