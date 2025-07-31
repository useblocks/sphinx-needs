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
                "file_types": ["cpp", "hpp"],
            },
            ["Schema validation error in field 'src_dir': 123 is not of type 'string'"],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": "TrueAsString",
                "file_types": ["cpp", "hpp"],
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
                "file_types": "py",
            },
            [
                "Schema validation error in field 'file_types': 'py' is not of type 'array'"
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
            "file_types": ["cpp", "hpp"],
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
            {"gitignore": False, "file_types": ["cpp"]},
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
