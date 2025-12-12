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


def test_explicit_git_root_configuration(tmp_path):
    """Test that explicit git_root configuration is used instead of auto-detection."""
    # Create a fake git repo structure in tmp_path
    fake_git_root = tmp_path / "fake_repo"
    fake_git_root.mkdir()
    (fake_git_root / ".git").mkdir()

    # Create a minimal .git/config with remote URL
    git_config = fake_git_root / ".git" / "config"
    git_config.write_text(
        '[remote "origin"]\n    url = https://github.com/test/repo.git\n'
    )

    # Create HEAD file pointing to a branch ref
    git_head = fake_git_root / ".git" / "HEAD"
    git_head.write_text("ref: refs/heads/main\n")

    # Create the refs/heads/main file with the commit hash
    refs_dir = fake_git_root / ".git" / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("abc123def456\n")

    # Create source file in a deeply nested location
    src_dir = tmp_path / "deeply" / "nested" / "src"
    src_dir.mkdir(parents=True)
    src_file = src_dir / "test.c"
    src_file.write_text("// @Test, TEST_1\nvoid test() {}\n")

    # Configure with explicit git_root
    src_analyse_config = SourceAnalyseConfig(
        src_files=[src_file],
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        git_root=fake_git_root,
    )

    src_analyse = SourceAnalyse(src_analyse_config)

    # Verify the explicit git_root was used
    assert src_analyse.git_root == fake_git_root.resolve()
    assert src_analyse.git_remote_url == "https://github.com/test/repo.git"
    assert src_analyse.git_commit_rev == "abc123def456"


def test_git_root_auto_detection_when_not_configured(tmp_path):
    """Test that git_root is auto-detected when not explicitly configured."""
    src_dir = TEST_DIR / "data" / "dcdc"
    src_paths = [src_dir / "charge" / "demo_1.cpp"]

    # Don't set git_root - it should auto-detect
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        # git_root is not set, so auto-detection should be used
    )

    src_analyse = SourceAnalyse(src_analyse_config)

    # The test is running inside a git repo, so git_root should be detected
    # We just verify it's not None (since this test runs in the sphinx-codelinks repo)
    assert src_analyse.git_root is not None
    assert (src_analyse.git_root / ".git").exists()


def test_oneline_parser_warnings_are_collected(tmp_path):
    """Test that oneline parser warnings are collected for later output."""
    src_dir = TEST_DIR / "data" / "oneline_comment_default"
    src_paths = [src_dir / "default_oneliners.c"]
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    # Verify that warnings were collected
    assert len(src_analyse.oneline_warnings) == 1
    warning = src_analyse.oneline_warnings[0]
    assert "too_many_fields" in warning.sub_type
    assert warning.lineno == 17
