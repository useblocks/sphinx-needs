# @Test suite for CLI commands including analyse, discover, and write, TEST_CLI_1, test, [IMPL_CLI_ANALYZE, IMPL_CLI_DISCOVER, IMPL_CLI_WRITE]
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


def test_analyse_outputs_warnings(tmp_path: Path) -> None:
    """Test that the analyse CLI command outputs warnings to console."""
    # Create a config file that will produce warnings
    src_dir = TEST_DIR / "data" / "oneline_comment_default"
    config_dict = {
        "codelinks": {
            "outdir": str(tmp_path),
            "projects": {
                "test_project": {
                    "source_discover": {
                        "src_dir": str(src_dir),
                        "include": ["*.c"],
                        "comment_type": "cpp",
                    },
                    "analyse": {
                        "get_oneline_needs": True,
                        # Use default oneline_comment_style which will cause warnings
                        # for the test file with too many fields
                    },
                }
            },
        }
    }

    config_file = tmp_path / "test_config.toml"
    with config_file.open("w", encoding="utf-8") as f:
        toml.dump(config_dict, f)

    options: list[str] = ["analyse", str(config_file)]
    result = runner.invoke(app, options)

    assert result.exit_code == 0
    # Verify that warnings are output to console
    assert "Oneline parser warning" in result.output
    assert "too_many_fields" in result.output


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


def test_analyse_with_relative_git_root(tmp_path: Path) -> None:
    """Test that relative git_root is resolved relative to the config file location."""
    # Create a fake git repo structure
    fake_git_root = tmp_path / "fake_repo"
    fake_git_root.mkdir()
    (fake_git_root / ".git").mkdir()
    git_config = fake_git_root / ".git" / "config"
    git_config.write_text(
        '[remote "origin"]\n    url = https://github.com/test/repo.git\n'
    )
    git_head = fake_git_root / ".git" / "HEAD"
    git_head.write_text("ref: refs/heads/main\n")
    refs_dir = fake_git_root / ".git" / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("abc123def456\n")

    # Create source file
    src_dir = fake_git_root / "src"
    src_dir.mkdir()
    src_file = src_dir / "test.c"
    src_file.write_text("// @Test, TEST_1, test\nvoid test() {}\n")

    # Create config in a subdirectory using a RELATIVE git_root path
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "codelinks.toml"
    config_content = """
[codelinks.projects.test_project.source_discover]
src_dir = "../fake_repo/src"
gitignore = false

[codelinks.projects.test_project.analyse]
get_oneline_needs = true
git_root = "../fake_repo"
"""
    config_file.write_text(config_content)

    outdir = tmp_path / "output"
    outdir.mkdir()

    options = ["analyse", str(config_file), "--outdir", str(outdir)]
    result = runner.invoke(app, options)

    assert result.exit_code == 0, f"CLI failed: {result.stdout}"
    output_path = outdir / "marked_content.json"
    assert output_path.exists()

    with output_path.open("r") as f:
        marked_content = json.load(f)
    # Verify the content was analysed using the correct git_root
    assert len(marked_content["test_project"]) > 0


def test_analyse_with_absolute_git_root(tmp_path: Path) -> None:
    """Test that absolute git_root is used as-is."""
    # Create a fake git repo structure
    fake_git_root = tmp_path / "fake_repo"
    fake_git_root.mkdir()
    (fake_git_root / ".git").mkdir()
    git_config = fake_git_root / ".git" / "config"
    git_config.write_text(
        '[remote "origin"]\n    url = https://github.com/test/repo.git\n'
    )
    git_head = fake_git_root / ".git" / "HEAD"
    git_head.write_text("ref: refs/heads/main\n")
    refs_dir = fake_git_root / ".git" / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("abc123def456\n")

    # Create source file
    src_dir = fake_git_root / "src"
    src_dir.mkdir()
    src_file = src_dir / "test.c"
    src_file.write_text("// @Test, TEST_2, test\nvoid test() {}\n")

    # Create config in a different location using an ABSOLUTE git_root path
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "codelinks.toml"
    # Use absolute path for both src_dir and git_root
    config_content = f"""
[codelinks.projects.test_project.source_discover]
src_dir = "{src_dir.as_posix()}"
gitignore = false

[codelinks.projects.test_project.analyse]
get_oneline_needs = true
git_root = "{fake_git_root.as_posix()}"
"""
    config_file.write_text(config_content)

    outdir = tmp_path / "output"
    outdir.mkdir()

    options = ["analyse", str(config_file), "--outdir", str(outdir)]
    result = runner.invoke(app, options)

    assert result.exit_code == 0, f"CLI failed: {result.stdout}"
    output_path = outdir / "marked_content.json"
    assert output_path.exists()

    with output_path.open("r") as f:
        marked_content = json.load(f)
    # Verify the content was analysed using the correct git_root
    assert len(marked_content["test_project"]) > 0
