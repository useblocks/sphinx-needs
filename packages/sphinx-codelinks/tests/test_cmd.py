import json
from pathlib import Path

import pytest
import toml
from typer.testing import CliRunner

from sphinx_codelinks.cmd import app
from sphinx_codelinks.source_discover.config import CommentType

from .conftest import DATA_DIR, TEST_DIR

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
SRC_DISCOVER_TEMPLATE = {
    "src_dir": str(TEST_DIR / "data" / "dcdc"),
    "exclude": ["**/charge/demo_1.cpp", "**/discharge/demo_3.cpp"],
    "include": ["**/charge/demo_2.cpp", "**/supercharge.cpp"],
    "gitignore": True,
    "comment_type": CommentType.cpp.value,
}
ANALYSE_SECTION_CONFIG_TEMPLATE = {
    "get_oneline_needs": True,
    "oneline_comment_style": ONELINE_COMMENT_TEMPLATE,
}
ANALYSE_CONFIG_TEMPLATE = {
    "source_discover": SRC_DISCOVER_TEMPLATE,
    "analyse": ANALYSE_SECTION_CONFIG_TEMPLATE,
}


runner = CliRunner()


@pytest.mark.parametrize(
    ("config_path"), [(DATA_DIR / "analyse" / "minimum_config.toml")]
)
def test_analyse(config_path: Path, tmp_path: Path) -> None:
    options: list[str] = ["analyse", str(config_path), "--outdir", str(tmp_path)]
    result = runner.invoke(app, options)

    output_path = tmp_path / "marked_content.json"

    assert output_path.exists()
    assert result.exit_code == 0

    with output_path.open("r") as f:
        marked_content = json.load(f)
    assert marked_content


@pytest.mark.parametrize(
    ("options", "stdout"),
    [
        (
            ["discover", str(TEST_DIR / "data" / "dcdc"), "--no-gitignore"],
            "4 files discovered",
        ),
        (
            ["discover", str(TEST_DIR / "data" / "dcdc"), "--gitignore"],
            "3 files discovered",
        ),
    ],
)
def test_discover(options, stdout):
    result = runner.invoke(app, options)
    assert result.exit_code == 0
    assert stdout in result.stdout


@pytest.mark.parametrize(
    ("config_dict", "output_lines"),
    [
        (
            {
                key: {
                    src_key: (123 if src_key == "exclude" else src_value)
                    for src_key, src_value in value.items()
                    if isinstance(value, dict)
                }
                if isinstance(value, dict) and key == "source_discover"
                else value
                for key, value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: {
                    src_key: (123 if src_key == "include" else src_value)
                    for src_key, src_value in value.items()
                }
                if isinstance(value, dict) and key == "source_discover"
                else value
                for key, value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: {
                    src_key: (
                        123
                        if src_key in ("exclude", "include", "src_dir")
                        else src_value
                    )
                    for src_key, src_value in value.items()
                }
                if isinstance(value, dict) and key == "source_discover"
                else value
                for key, value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'src_dir': 123 is not of type 'string'",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            {
                key: {
                    oneline_key: (
                        {"not_expected": 123}
                        if oneline_key == "oneline_comment_style"
                        else oneline_value
                    )
                    for oneline_key, oneline_value in value.items()
                }
                if isinstance(value, dict) and key == "analyse"
                else value
                for key, value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid oneline comment style configuration:",
                "OneLineCommentStyle.__init__() got an unexpected keyword argument",
                "'not_expected'",
            ],
        ),
        (
            {
                key: {
                    oneline_key: (
                        {"needs_fields": [{"name": "id"}, {"name": "id"}]}
                        if oneline_key == "oneline_comment_style"
                        else oneline_value
                    )
                    for oneline_key, oneline_value in value.items()
                }
                if isinstance(value, dict) and key == "analyse"
                else value
                for key, value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: OneLineCommentStyle configuration errors:",
                "Missing required fields: ['title', 'type']",
                "Field 'id' is defined multiple times.",
            ],
        ),
    ],
)
def test_analyse_config_negative(config_dict, output_lines, tmp_path: Path) -> None:
    # Force disable Rich styling
    config_file = tmp_path / "analyse_config.toml"
    with config_file.open("w", encoding="utf-8") as f:
        toml.dump(config_dict, f)

    options = [
        "analyse",
        str(config_file),
    ]
    result = runner.invoke(app, options)
    assert result.exit_code != 0
    for line in output_lines:
        assert line in result.stdout
