# @Test suite for source file discovery with gitignore support, TEST_DISC_1, test, [IMPL_DISC_1]
import json
from pathlib import Path
import subprocess

import pytest

from sphinx_codelinks.source_discover.config import (
    COMMENT_FILETYPE,
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover

FIXTURES_PATH = Path(__file__).parent / "data" / "discover_fixtures.json"


@pytest.mark.parametrize(
    ("config", "msgs"),
    [
        (
            {
                "src_dir": 123,
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": "cpp",
            },
            ["Schema validation error in field 'src_dir': 123 is not of type 'string'"],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": "TrueAsString",
                "comment_type": "cpp",
            },
            [
                "Schema validation error in field 'gitignore': 'TrueAsString' is not of type 'boolean'"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": "java",
            },
            [
                "Schema validation error in field 'comment_type': 'java' is not one of ['cpp', 'cs', 'python', 'rust', 'yaml']"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": ["cpp", "hpp"],
            },
            [
                "Schema validation error in field 'comment_type': ['cpp', 'hpp'] is not of type 'string'"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "follow_links": "not_a_bool",
            },
            [
                "Schema validation error in field 'follow_links': 'not_a_bool' is not of type 'boolean'"
            ],
        ),
    ],
)
def test_schema_negative(config, msgs):
    source_discover_config = SourceDiscoverConfig(**config)
    errors = source_discover_config.check_schema()
    assert sorted(errors) == sorted(msgs)


@pytest.mark.parametrize(
    "config",
    [
        {},
        {
            "src_dir": "/path/to/root",
            "exclude": ["exclude1", "exclude2"],
            "include": ["include1", "include2"],
            "gitignore": True,
            "comment_type": "cpp",
        },
        {
            "src_dir": "/path/to/root",
            "exclude": ["exclude1", "exclude2"],
            "include": ["include1", "include2"],
            "gitignore": True,
            "comment_type": "python",
        },
        {
            "src_dir": "/path/to/root",
            "follow_links": True,
        },
    ],
)
def test_schema_positive(config):
    source_discover_config = SourceDiscoverConfig(**config)
    errors = source_discover_config.check_schema()
    assert len(errors) == 0


@pytest.mark.parametrize(
    ("config", "num_files", "suffix"),
    [
        (
            {
                "gitignore": False,
            },
            4,
            "",
        ),
        (
            {
                "gitignore": True,
            },
            3,
            "",
        ),
        (
            {
                "gitignore": True,
                "exclude": ["charge/*.cpp"],
                "include": ["**/*.cpp"],
            },
            # With ignore-python, include patterns whitelist files (overriding
            # gitignore) and exclude patterns are applied after, so both
            # charge/*.cpp files are excluded resulting in 2 instead of 4.
            2,
            "",
        ),
        (
            {
                "gitignore": True,
                "exclude": ["charge/*.cpp"],
            },
            2,
            "",
        ),
        (
            {"gitignore": False, "comment_type": "cpp"},
            4,
            "cpp",
        ),
    ],
)
def test_source_discover(
    config: SourceDiscoverConfigType,
    num_files: int,
    suffix: str,
    source_directory: Path,
) -> None:
    config["src_dir"] = source_directory
    src_discover_config = SourceDiscoverConfig(**config)
    source_discover = SourceDiscover(src_discover_config)
    assert len(source_discover.source_paths) == num_files
    if suffix:
        assert all(path.suffix == ".cpp" for path in source_discover.source_paths)


@pytest.fixture(scope="function")
def create_source_files(tmp_path: Path) -> Path:
    for file_types in COMMENT_FILETYPE.values():
        for ext in file_types:
            (tmp_path / f"file.{ext}").touch()
    return tmp_path


@pytest.mark.parametrize(
    ("comment_type", "nums_files"),
    [
        ("cpp", len(COMMENT_FILETYPE["cpp"])),
        ("python", len(COMMENT_FILETYPE["python"])),
    ],
)
def test_comment_filetype(
    comment_type: str, nums_files: int, create_source_files: Path
) -> None:
    src_dir = create_source_files

    config = SourceDiscoverConfig(
        src_dir=src_dir, comment_type=comment_type, gitignore=False
    )
    source_discover = SourceDiscover(config)
    assert len(source_discover.source_paths) == nums_files


def test_follow_links(tmp_path: Path) -> None:
    """Test that follow_links controls whether symbolic links are followed."""
    # Create a real directory with a source file
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "source.cpp").write_text("// test")

    # Create a project directory with a symlink to the real directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "direct.cpp").write_text("// direct")
    link = project_dir / "linked"
    link.symlink_to(real_dir)

    # Without follow_links, symlinked files should not be discovered
    config_no_follow = SourceDiscoverConfig(
        src_dir=project_dir, gitignore=False, follow_links=False
    )
    discover_no_follow = SourceDiscover(config_no_follow)
    discovered_names = {p.name for p in discover_no_follow.source_paths}
    assert "direct.cpp" in discovered_names
    assert "source.cpp" not in discovered_names

    # With follow_links, symlinked files should be discovered
    config_follow = SourceDiscoverConfig(
        src_dir=project_dir, gitignore=False, follow_links=True
    )
    discover_follow = SourceDiscover(config_follow)
    discovered_names = {p.name for p in discover_follow.source_paths}
    assert "direct.cpp" in discovered_names
    assert "source.cpp" in discovered_names


def _load_discover_fixtures() -> list[dict]:
    with FIXTURES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "case",
    _load_discover_fixtures(),
    ids=lambda c: c["name"],
)
def test_discover_fixture(case: dict, tmp_path: Path) -> None:
    """Run portable discovery test cases from the shared JSON fixture."""
    # Create files
    for rel_path, content in case["files"].items():
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # Optionally initialise a git repo (required for .gitignore support)
    if case.get("git_init", False):
        subprocess.run(
            ["git", "init"],  # noqa: S607
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

    cfg = case["config"]
    src_dir = tmp_path / cfg["src_dir"]

    config = SourceDiscoverConfig(
        src_dir=src_dir,
        include=cfg.get("include", []),
        exclude=cfg.get("exclude", []),
        gitignore=cfg.get("gitignore", True),
        comment_type=cfg.get("comment_type", "cpp"),
    )

    discover = SourceDiscover(config)

    # Convert discovered paths to paths relative to tmp_path for comparison
    discovered_relative = sorted(
        str(p.relative_to(tmp_path)) for p in discover.source_paths
    )

    # Normalise expected paths to use the OS path separator
    expected = sorted(str(Path(p)) for p in case["expected"])

    assert discovered_relative == expected, (
        f"Case '{case['name']}': expected {expected}, got {discovered_relative}"
    )
