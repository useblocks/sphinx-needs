import json
from collections.abc import Generator
from pathlib import Path
from textwrap import dedent
from typing import Callable

import pytest
import sphinx
import tomli_w
import tomllib
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

CURR_DIR = Path(__file__).parent


def get_warnings_list(app: SphinxTestApp):
    return strip_colors(app._warning.getvalue()).splitlines()


UBPROJECT_BASE = """
[needs]
schemas_from_json = "schemas.json"

[[needs.types]]
directive = "feat"
title = "Feat"
prefix = "Feat_"

[[needs.types]]
directive = "req"
title = "Requirement"
prefix = "REQ_"

[[needs.types]]
directive = "spec"
title = "Specification"
prefix = "SPEC_"
"""

schemas_json = """
[
  {
    "severity": "warning",
    "message": "id must be uppercase",
    "local_schema": {
      "properties": {
        "id": { "pattern": "^[A-Z0-9_]+$" }
      }
    }
  }
]
"""

CONF_PY_BASE = """
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
"""


def gen_param_tuple(
    ubproject: str,
    schemas_json: list[dict],
    rst_content: str,
    warnings: list[str],
) -> tuple[str, str, str]:
    """Generate dedented strings for ubproject, schemas, and rst content."""
    ubproject_base_obj = tomllib.loads(UBPROJECT_BASE)
    ubproject_obj = tomllib.loads(ubproject)
    # merge dictionaries on root needs level, so we can override
    # the base needs config
    ubproject_base_obj["needs"].update(ubproject_obj["needs"])
    toml_content = tomli_w.dumps(ubproject_base_obj)
    return (
        toml_content,
        json.dumps(schemas_json),
        dedent(rst_content),
        warnings,
    )


@pytest.mark.parametrize(
    "ubproject_schemas_rst",
    [
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            [],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "string"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            [],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "integer"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            ["cannot coerce 'QM' to integer", "[sn_schema.option_type_error]"],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "boolean"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            ["cannot coerce 'QM' to boolean", "[sn_schema.option_type_error]"],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "number"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            ["cannot coerce 'QM' to number", "[sn_schema.option_type_error]"],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "string"
            enum = ["QM", "A", "B", "C", "D"]
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: QM
            """,
            [],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "asil"
            [needs.extra_options.schema]
            type = "string"
            enum = ["QM", "A", "B", "C", "D"]
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :asil: E
            """,
            [
                "properties > asil > enum",
                "'E' is not one of ['QM', 'A', 'B', 'C', 'D']",
                "[sn_schema.validation_fail]",
            ],
        ),
        gen_param_tuple(
            """
            [[needs.extra_options]]
            name = "start_date"
            [needs.extra_options.schema]
            type = "string"
            format = "date"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :start_date: 2023-01-01
            """,
            [],
        ),
        gen_param_tuple(
            """
            [needs]
            schemas_debug_active = true
            schemas_debug_ignore = []
            [[needs.extra_options]]
            name = "start_date"
            [needs.extra_options.schema]
            type = "string"
            format = "date"
            """,
            [],
            """
            .. feat:: feat wrong id
               :id: FEAT_01
               :start_date: not-a-date
            """,
            [
                "properties > start_date > format",
                "'not-a-date' is not a 'date'",
                "[sn_schema.validation_fail]",
            ],
        ),
    ],
)
def test_schema_validations(
    tmpdir: Path,
    ubproject_schemas_rst: tuple[str, str, str],
    make_app: Generator[Callable[[], SphinxTestApp]],
):
    """Test matching option type."""
    conf_py_path = tmpdir / "conf.py"
    conf_py_path.write_text(CONF_PY_BASE, encoding="utf-8")

    ubproject_content, schemas_content, rst_content, expected_warnings = (
        ubproject_schemas_rst
    )
    toml_path = tmpdir / "ubproject.toml"
    json_path = tmpdir / "schemas.json"
    rst_path = tmpdir / "index.rst"

    toml_path.write_text(ubproject_content, encoding="utf-8")
    json_path.write_text(schemas_content, encoding="utf-8")
    rst_path.write_text(rst_content, encoding="utf-8")

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)

    app.build()
    assert app.statuscode == 0
    warnings = get_warnings_list(app)
    for expected_warning in expected_warnings:
        assert any(expected_warning in warning for warning in warnings), (
            f"Expected warning not found: '{expected_warning}' ({warnings})"
        )

    warnings_count = len([item for item in warnings if item.startswith("WARNING:")])
    if expected_warnings:
        # 1 warning per test parameter set
        assert warnings_count == 1
    else:
        assert warnings_count == 0, f"Warnings found: {warnings}"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema", "no_plantuml": True}],
    indirect=True,
)
def test_schema_basic(test_app: SphinxTestApp) -> None:
    test_app.builder.build_all()

    warnings_raw = strip_colors(test_app.warning.getvalue())
    warnings = [part for part in warnings_raw.split("WARNING: ") if part]

    expected_warnings = [
        (
            "'FEAt' does not match '^[A-Z0-9_]+$'",
            "[sn_schema.validation_fail]",
        ),
        (
            "1 invalid links of type 'links' / nok: FEAT",
            "[sn_schema.unevaluated_additional_links]",
        ),
        (
            "Too few valid links of type 'links' (0 < 1) / nok: REQ_SAFE_UNSAFE_FEAT",
            "[sn_schema.too_few_links]",
        ),
        (
            "1 invalid links of type 'links' / nok: REQ_SAFE_UNSAFE_FEAT",
            "[sn_schema.unevaluated_additional_links]",
        ),
    ]
    for expected in expected_warnings:
        if sphinx.version_info[0] <= 8:
            expected_msg = expected[0]
        else:
            expected_msg = f"{expected[0]} {expected[1]}"
        assert any(expected_msg in warning for warning in warnings), (
            f"Expected warning not found: {expected}"
        )
    assert len(warnings) == len(expected_warnings)
    unexpected_warnings = [
        '"approved" is a required property [sn_schema.validation_fail]',  # severity info too low
    ]
    for unexpected in unexpected_warnings:
        assert all(unexpected not in warning for warning in warnings), (
            f"Unexpected warning found: {unexpected}"
        )

    html = Path(test_app.outdir, "index.html").read_text()
    assert html
