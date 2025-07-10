from pathlib import Path

import pytest
import toml
from typer.testing import CliRunner

from sphinx_codelinks.cmd import app

from .conftest import (
    BASIC_VDOC_TOML,
    DEFAULT_VDOC_TOML,
    RECURSIVE_DIR_VDOC_TOML,
    SRC_TRACE_TOML,
    TEST_DIR,
)

ONELINE_COMMENT_TEMPLATE = {
    "start_sequence": "[[",
    "end_sequence": "]]",
    "field_split_char": ",",
    "needs_fields": [
        {"name": "id"},
        {"name": "title"},
        {"name": "type"},
    ],
}

VDOC_CONFIG_TEMPLATE = {
    "src_dir": str(TEST_DIR / "data" / "dcdc"),
    "exclude": ["**/charge/demo_1.cpp", "**/discharge/demo_3.cpp"],
    "include": ["**/charge/demo_2.cpp", "**/supercharge.cpp"],
    "gitignore": True,
    "file_types": ["cpp"],
    "oneline_comment_style": ONELINE_COMMENT_TEMPLATE,
}


runner = CliRunner()


@pytest.mark.parametrize(
    ("options", "stdout"),
    [
        (
            ["discover", str(TEST_DIR / "data" / "dcdc"), "--no-gitignore"],
            "5 files discovered",
        ),
        (
            ["discover", str(TEST_DIR / "data" / "dcdc"), "--gitignore"],
            "4 files discovered",
        ),
    ],
)
def test_discover(options, stdout):
    result = runner.invoke(app, options)
    assert result.exit_code == 0
    assert stdout in result.stdout


@pytest.mark.parametrize(
    ("options", "lines"),
    [
        (
            [
                "vdoc",
                "--config",
                SRC_TRACE_TOML,
                "--project",
                "dcdc",
            ],
            [
                "The virtual documents are generated:",
                Path("charge") / "demo_1.json",
                Path("charge") / "demo_2.json",
                Path("discharge") / "demo_3.json",
                Path("supercharge.json"),
                "The cached files are:",
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_2.cpp",
                TEST_DIR / "data" / "dcdc" / "discharge" / "demo_3.cpp",
                TEST_DIR / "data" / "dcdc" / "supercharge.cpp",
            ],
        ),
        (
            [
                "vdoc",
                "--config",
                BASIC_VDOC_TOML,
            ],
            [
                "The virtual documents are generated:",
                Path("basic_oneliners.json"),
                "The cached files are:",
                TEST_DIR / "data" / "oneline_comment_basic" / "basic_oneliners.c",
            ],
        ),
        (
            [
                "vdoc",
                "--config",
                DEFAULT_VDOC_TOML,
            ],
            [
                "The virtual documents are generated:",
                Path("default_oneliners.json"),
                "The cached files are:",
                TEST_DIR / "data" / "oneline_comment_default" / "default_oneliners.c",
            ],
        ),
        (
            ["vdoc", "--config", RECURSIVE_DIR_VDOC_TOML, "--project", "dummy_src"],
            [
                "The virtual documents are generated:",
                Path("dummy_1.json"),
                Path("dummy_lv2") / "dummy_2.json",
                Path("dummy_lv2") / "dummy_lv3" / "dummy_3.json",
                Path("dummy_lv2") / "dummy_lv3" / "dummy_lv4" / "dummy_4.json",
                "The cached files are:",
                TEST_DIR
                / "doc_test"
                / "recursive_dirs"
                / "dummy_src_lv1"
                / "dummy_1.cpp",
                TEST_DIR
                / "doc_test"
                / "recursive_dirs"
                / "dummy_src_lv1"
                / "dummy_lv2"
                / "dummy_2.cpp",
                TEST_DIR
                / "doc_test"
                / "recursive_dirs"
                / "dummy_src_lv1"
                / "dummy_lv2"
                / "dummy_lv3"
                / "dummy_3.cpp",
                TEST_DIR
                / "doc_test"
                / "recursive_dirs"
                / "dummy_src_lv1"
                / "dummy_lv2"
                / "dummy_lv3"
                / "dummy_lv4"
                / "dummy_4.cpp",
            ],
        ),
    ],
)
def test_vdoc(options, lines, tmp_path):
    options.append("--output-dir")
    options.append(tmp_path)
    for i in range(len(lines)):
        if lines[i] == "The virtual documents are generated:":
            continue
        if lines[i] == "The cached files are:":
            break
        lines[i] = tmp_path / lines[i]

    lines = [str(line) for line in lines]

    result = runner.invoke(
        app,
        options,
    )

    assert result.exit_code == 0
    assert result.stdout.splitlines() == lines


@pytest.mark.parametrize(
    ("config_dict", "output_lines"),
    [
        (
            {
                key: (123 if key == "exclude" else value)
                for key, value in VDOC_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: (123 if key == "include" else value)
                for key, value in VDOC_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: (123 if key in ("exclude", "include", "src_dir") else value)
                for key, value in VDOC_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "src_dir must be a string",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: (
                    {"not_expected": 123} if key == "oneline_comment_style" else value
                )
                for key, value in VDOC_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid oneline comment style configuration:",
                "OneLineCommentStyle.__init__() got an unexpected keyword argument",
                "'not_expected'",
            ],
        ),
        (
            {
                key: (
                    {"needs_fields": [{"name": "id"}, {"name": "id"}]}
                    if key == "oneline_comment_style"
                    else value
                )
                for key, value in VDOC_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid oneline comment style configuration:",
                "Missing required fields: ['title', 'type']",
                "Field 'id' is defined multiple times.",
            ],
        ),
    ],
)
def test_vdoc_config_negative(config_dict, output_lines, tmp_path: Path) -> None:
    # Force disable Rich styling
    config_file = tmp_path / "vdoc_config.toml"
    with config_file.open("w", encoding="utf-8") as f:
        toml.dump(config_dict, f)

    options = [
        "vdoc",
        "--config",
        str(config_file),
    ]
    result = runner.invoke(app, options)
    assert result.exit_code != 0
    for line in output_lines:
        assert line in result.stderr
