from pathlib import Path

import pytest

from sphinx_codelinks.source_discover.config import (
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover


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
                "Schema validation error in field 'comment_type': 'java' is not one of ['cpp', 'python']"
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
            4,
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
