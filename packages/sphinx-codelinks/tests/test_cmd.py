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
ANALYSE_CONFIG_TEMPLATE = {
    "get_oneline_needs": True,
    "oneline_comment_style": ONELINE_COMMENT_TEMPLATE,
}
CODELINKS_CONFIG_TEMPLATE = {
    "outdir": "set/it/to/somewhere",
    "projects": {
        "project_1": {
            "source_discover": SRC_DISCOVER_TEMPLATE,
            "analyse": ANALYSE_CONFIG_TEMPLATE,
        }
    },
}


runner = CliRunner()


@pytest.mark.parametrize(
    ("config_path"),
    [
        (DATA_DIR / "configs" / "minimum_config.toml"),
        (DATA_DIR / "configs" / "full_config.toml"),
    ],
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
    ("src_discover_dict", "analyse_dict", "output_lines"),
    [
        (
            {
                src_key: (123 if src_key == "exclude" else src_value)
                for src_key, src_value in SRC_DISCOVER_TEMPLATE.items()
            },
            ANALYSE_CONFIG_TEMPLATE,
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
            ],
        ),
        (
            {
                src_key: (123 if src_key == "include" else src_value)
                for src_key, src_value in SRC_DISCOVER_TEMPLATE.items()
            },
            ANALYSE_CONFIG_TEMPLATE,
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            {
                src_key: (
                    123 if src_key in ("exclude", "include", "src_dir") else src_value
                )
                for src_key, src_value in SRC_DISCOVER_TEMPLATE.items()
            },
            ANALYSE_CONFIG_TEMPLATE,
            [
                "Invalid value: Invalid source discovery configuration:",
                "Schema validation error in field 'src_dir': 123 is not of type 'string'",
                "Schema validation error in field 'exclude': 123 is not of type 'array'",
                "Schema validation error in field 'include': 123 is not of type 'array'",
            ],
        ),
        (
            SRC_DISCOVER_TEMPLATE,
            {
                analyse_key: (
                    {"not_expected": 123}
                    if analyse_key == "oneline_comment_style"
                    else analyse_value
                )
                for analyse_key, analyse_value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: Invalid oneline comment style configuration:",
                "OneLineCommentStyle.__init__() got an unexpected keyword argument",
                "'not_expected'",
            ],
        ),
        (
            SRC_DISCOVER_TEMPLATE,
            {
                analyse_key: (
                    {"needs_fields": [{"name": "id"}, {"name": "id"}]}
                    if analyse_key == "oneline_comment_style"
                    else analyse_value
                )
                for analyse_key, analyse_value in ANALYSE_CONFIG_TEMPLATE.items()
            },
            [
                "Invalid value: OneLineCommentStyle configuration errors:",
                "Missing required fields: ['title', 'type']",
                "Field 'id' is defined multiple times.",
            ],
        ),
    ],
)
def test_analyse_config_negative(
    src_discover_dict, analyse_dict, output_lines, tmp_path: Path
) -> None:
    config_file = tmp_path / "codelinks_config.toml"
    codelink_dict = {"codelinks": CODELINKS_CONFIG_TEMPLATE}
    codelink_dict["codelinks"]["projects"]["project_1"]["source_discover"] = (
        src_discover_dict
    )
    codelink_dict["codelinks"]["projects"]["project_1"]["analyse"] = analyse_dict
    with config_file.open("w", encoding="utf-8") as f:
        toml.dump(codelink_dict, f)

    options = [
        "analyse",
        str(config_file),
    ]
    result = runner.invoke(app, options)
    assert result.exit_code != 0
    for line in output_lines:
        assert line in result.stdout


@pytest.mark.parametrize(
    ("projects", "output_lines"),
    [
        (
            ["project_1", "project_2"],
            [
                "The following projects are not found:",
                "project_2",
            ],
        ),
    ],
)
def test_analyse_project_negative(projects, output_lines, tmp_path: Path) -> None:
    config_file = tmp_path / "codelinks_config.toml"
    codelink_dict = {"codelinks": CODELINKS_CONFIG_TEMPLATE}
    with config_file.open("w", encoding="utf-8") as f:
        toml.dump(codelink_dict, f)
    projects_config = []
    for project in projects:
        projects_config.append("--project")
        projects_config.append(project)

    options = [
        "analyse",
        str(config_file),
    ]
    options.extend(projects_config)
    result = runner.invoke(app, options)
    assert result.exit_code != 0
    for line in output_lines:
        assert line in result.stdout


def test_write_rst_invalid_json(tmp_path: Path) -> None:
    json_obj = {
        "whatever": "json",
        "not": "expected",
    }
    json_text = json.dumps(json_obj)
    json_text = json_text.replace(",", "")
    jsonpath = tmp_path / "invalid_json.json"
    with jsonpath.open("w") as f:
        f.write(json_text)

    options = [
        "write",
        "rst",
        str(jsonpath),
        "--outpath",
        str(tmp_path / "out.rst"),
    ]
    result = runner.invoke(app, options)

    assert result.exit_code != 0
    assert "Expecting" in result.stdout


@pytest.mark.parametrize(
    ("json_objs", "output_lines"),
    [
        (
            [
                {
                    "filepath": 123,
                    "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/951e40e7845f06d5cfc4ca20ebb984308fdaf985/tests/data/marked_rst/dummy_1.cpp#L4",
                    "source_map": {
                        "start": {"row": 3, "column": 8},
                        "end": {"row": 3, "column": 61},
                    },
                    "tagged_scope": "void dummy_func1(){\n     //...\n }",
                    "rst": ".. impl:: implement dummy function 1\n   :id: IMPL_71\n",
                    "type": "need-id-refs",
                }
            ],
            [
                "Invalid value: Errors occurred",
                "Schema validation error in field 'filepath': 123 is not of type 'string'",
                "Marker is required for marked content of type 'need_id_refs'",
                "Need id refs are required for marked content of type 'need_id_refs'",
            ],
        ),
    ],
)
def test_write_rst_negative(json_objs: list[dict], output_lines, tmp_path) -> None:
    to_dump = {"project_1": json_objs}
    jsonpath = Path("invalid_objs.json")
    with jsonpath.open("w") as f:
        json.dump(to_dump, f)
    outpath = tmp_path / "needextend.rst"
    options = [
        "write",
        "rst",
        str(jsonpath),
        "--outpath",
        str(outpath),
    ]
    result = runner.invoke(app, options)

    assert result.exit_code != 0
    for line in output_lines:
        assert line in result.stdout
