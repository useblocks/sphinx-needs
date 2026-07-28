# @Test suite for source code analysis and marker extraction, TEST_ANA_1, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MLN_1]
import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse.analyse import SourceAnalyse, _count
from sphinx_codelinks.config import SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType
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
                TEST_DATA_DIR / "multiline_needs" / "dummy_1.cpp",
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
        get_multiline_needs=True,
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
        if "source" in obj:
            # a multi-line need's path is relative to the git root when the checkout is
            # a repository, else to src_dir: pin it against src_dir, as filepath is
            assert obj["source"].pop("root") in ("git", "src_dir")
            assert obj["source"]["path"].endswith(obj["filepath"])
            obj["source"]["path"] = obj["filepath"]
    assert marked_content == snapshot_marks


@pytest.mark.parametrize(
    "case",
    [
        {
            "src_dir": TEST_DIR / "data" / "dcdc",
            "src_paths": [
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_2.cpp",
                TEST_DIR / "data" / "dcdc" / "discharge" / "demo_3.cpp",
                TEST_DIR / "data" / "dcdc" / "supercharge.cpp",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE,
            "result": {
                "num_src_files": 4,
                "num_uncached_files": 4,
                "num_cached_files": 0,
                "num_comments": 29,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 12,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "oneline_comment_basic",
            "src_paths": [
                TEST_DIR / "data" / "oneline_comment_basic" / "basic_oneliners.c",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 14,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 8,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "oneline_comment_default",
            "src_paths": [
                TEST_DIR / "data" / "oneline_comment_default" / "default_oneliners.c",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 5,
                "num_oneline_warnings": 1,
                "num_oneline_needs": 4,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "rust",
            "src_paths": [
                TEST_DIR / "data" / "rust" / "demo.rs",
            ],
            "comment_type": CommentType.rust,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 6,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 4,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "typescript",
            "src_paths": [
                TEST_DIR / "data" / "typescript" / "demo.ts",
            ],
            "comment_type": CommentType.ts,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 4,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 1,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "typescript",
            "src_paths": [
                TEST_DIR / "data" / "typescript" / "demo.tsx",
            ],
            "comment_type": CommentType.ts,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 1,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 1,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "jsonc",
            "src_paths": [
                TEST_DIR / "data" / "jsonc" / "demo.jsonc",
            ],
            "comment_type": CommentType.jsonc,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 4,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 3,
            },
        },
    ],
)
def test_analyse_oneline_needs(tmp_path, case):
    src_analyse_config = SourceAnalyseConfig(
        src_files=case["src_paths"],
        src_dir=case["src_dir"],
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        oneline_comment_style=case["oneline_comment_style"],
        comment_type=case["comment_type"],
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    result = case["result"]
    assert len(src_analyse.src_files) == result["num_src_files"]
    assert len(src_analyse.warnings) == result["num_oneline_warnings"]
    assert len(src_analyse.oneline_needs) == result["num_oneline_needs"]

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
        get_multiline_needs=False,
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
        get_multiline_needs=False,
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
        get_multiline_needs=False,
        oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    # Verify that warnings were collected
    assert len(src_analyse.warnings) == 1
    warning = src_analyse.warnings[0]
    assert "too_many_fields" in warning.sub_type
    assert warning.lineno == 17
    # the old name reads the same list, for one release
    assert src_analyse.oneline_warnings is src_analyse.warnings


def test_a_hash_comment_is_never_a_docstring_tag(tmp_path: Path) -> None:
    """The ``docstring_tag`` rule reads Python docstrings only: a field-shaped tag line
    in a ``#`` comment goes to the one-line parser, as in any other language."""
    src = tmp_path / "x.py"
    src.write_text(
        "# @param a: the first, thing\ndef f(a):\n    pass\n", encoding="utf-8"
    )
    src_analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.python,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
        )
    )
    src_analyse.run()

    assert src_analyse.warnings == []
    assert [need.need["id"] for need in src_analyse.oneline_needs] == ["thing"]


def test_count_pluralizes_nouns() -> None:
    assert _count(0, "file") == "0 files"
    assert _count(1, "file") == "1 file"
    assert _count(2, "marker") == "2 markers"
    assert _count(1, "multi-line need") == "1 multi-line need"
