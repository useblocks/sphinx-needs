from pathlib import Path

import pytest

from sphinx_codelinks.source_discovery.config import SourceDiscoveryConfig
from sphinx_codelinks.source_discovery.source_discover import SourceDiscover


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
                "file_types": ["py", "hpp"],
            },
            [
                "Schema validation error in field 'file_types': 'py' is not one of ['c', 'h', 'cpp', 'hpp']"
            ],
        ),
    ],
)
def test_schema_negative(config, msgs):
    source_discovery_config = SourceDiscoveryConfig(**config)
    errors = source_discovery_config.check_schema()
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
    source_discovery_config = SourceDiscoveryConfig(**config)
    errors = source_discovery_config.check_schema()
    assert len(errors) == 0


def test_source_discover_all_files(source_directory: Path):
    source_discover = SourceDiscover(source_directory, gitignore=False)
    assert len(source_discover.source_paths) == 5


def test_source_discover_gitignore(source_directory: Path):
    source_discover = SourceDiscover(source_directory, gitignore=True)
    assert len(source_discover.source_paths) == 4


def test_source_discover_includes(source_directory: Path):
    source_discover = SourceDiscover(
        source_directory,
        gitignore=True,
        exclude=["charge/*.cpp"],
        include=["**/*.cpp"],
    )
    assert len(source_discover.source_paths) == 5


def test_source_discover_excludes(source_directory: Path):
    source_discover = SourceDiscover(
        source_directory, gitignore=True, exclude=["charge/*.cpp"]
    )
    assert len(source_discover.source_paths) == 3


def test_source_discover_type(source_directory: Path):
    source_discover = SourceDiscover(
        source_directory, gitignore=False, file_types=["cpp"]
    )
    assert len(source_discover.source_paths) == 4
    assert all(path.suffix == ".cpp" for path in source_discover.source_paths)
