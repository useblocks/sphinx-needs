import json
from collections.abc import Generator
from pathlib import Path
from textwrap import dedent
from typing import Callable, Optional

import pytest
import sphinx
import tomli
import tomli_w
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.needs import NeedsConfigException
from tests.schema.param_data import SCHEMA_CONFIG_ERROR_PARAMS, SCHEMA_VALIDATION_PARAMS

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
directive = "spec"
title = "Specification"
prefix = "SPEC_"

[[needs.types]]
directive = "impl"
title = "Implementation"
prefix = "IMPL_"
"""
"""Need types config with linking impl->spec->feat."""

CONF_PY_BASE = """
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
"""


def gen_param_tuple_without_type(
    test_name: str,
    ubproject: str,
    rst_content: str,
    schemas_json: Optional[list[dict]] = None,
    warnings: Optional[list[str]] = None,
) -> tuple[str, str, str, list[str], Optional[str]]:
    """Prepare test case parametrisation tuple without warning type."""
    ubproject_base_obj = tomli.loads(UBPROJECT_BASE)
    ubproject_obj = tomli.loads(ubproject)
    # merge dictionaries on root needs level, so we can override
    # the base needs config
    if ubproject_obj:
        ubproject_base_obj["needs"].update(ubproject_obj["needs"])
    toml_content = tomli_w.dumps(ubproject_base_obj)
    schemas_json = schemas_json or []
    warnings = warnings or []
    return (
        test_name,
        toml_content,
        dedent(rst_content),
        json.dumps(schemas_json),
        warnings,
    )


def gen_param_tuple_with_type(
    test_name: str,
    ubproject: str,
    rst_content: str,
    schemas_json: Optional[list[dict]] = None,
    warnings: Optional[list[str]] = None,
    warning_type: Optional[str] = None,
) -> tuple[str, str, str, list[str], Optional[str]]:
    """Prepare test case parametrisation tuple with warning type."""
    return (
        *gen_param_tuple_without_type(
            test_name, ubproject, rst_content, schemas_json, warnings
        ),
        warning_type,
    )


@pytest.mark.parametrize(
    "name_ubproject_rst_schemas_warnings_type",
    [
        *[
            gen_param_tuple_with_type(name, *params)
            for name, params in SCHEMA_VALIDATION_PARAMS.items()
        ],
    ],
    ids=lambda params: params[0],
)
def test_schema_validations(
    tmpdir: Path,
    name_ubproject_rst_schemas_warnings_type: tuple[str, str, str],
    make_app: Generator[Callable[[], SphinxTestApp]],
):
    """Test matching option type."""
    conf_py_path = tmpdir / "conf.py"
    conf_py_path.write_text(CONF_PY_BASE, encoding="utf-8")

    (
        _,
        ubproject_content,
        rst_content,
        schemas_content,
        expected_warnings,
        warning_type,
    ) = name_ubproject_rst_schemas_warnings_type

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

    errors_count = len([item for item in warnings if "ERROR: " in item])
    assert errors_count == 0, f"Errors found: {errors_count} ({warnings})"

    warnings_count = len([item for item in warnings if item.startswith("WARNING:")])
    if expected_warnings:
        # 1 warning per test parameter set
        assert warnings_count == 1
    else:
        assert warnings_count == 0, f"Warnings found: {warnings}"

    if warning_type and sphinx.version_info[0] >= 8:
        # check if the warning type is correct
        assert any(f"[{warning_type}]" in warning for warning in warnings), (
            f"Expected warning type not found: {warning_type} ({warnings})"
        )


@pytest.mark.parametrize(
    "name_ubproject_rst_schemas_warnings",
    [
        *[
            gen_param_tuple_without_type(name, *params)
            for name, params in SCHEMA_CONFIG_ERROR_PARAMS.items()
        ],
    ],
    ids=lambda params: params[0],
)
def test_schema_config_errors(
    tmpdir: Path,
    name_ubproject_rst_schemas_warnings: tuple[str, str, str],
    make_app: Generator[Callable[[], SphinxTestApp]],
):
    """Test matching option type."""
    conf_py_path = tmpdir / "conf.py"
    conf_py_path.write_text(CONF_PY_BASE, encoding="utf-8")

    (
        _,
        ubproject_content,
        rst_content,
        schemas_content,
        expected_warnings,
    ) = name_ubproject_rst_schemas_warnings

    toml_path = tmpdir / "ubproject.toml"
    json_path = tmpdir / "schemas.json"
    rst_path = tmpdir / "index.rst"

    toml_path.write_text(ubproject_content, encoding="utf-8")
    json_path.write_text(schemas_content, encoding="utf-8")
    rst_path.write_text(rst_content, encoding="utf-8")

    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=Path(tmpdir), freshenv=True)
    assert expected_warnings, (
        "NeedsConfigException exception was raised, expected_warnings should not be empty"
    )
    for expected_warning in expected_warnings:
        assert expected_warning in str(excinfo.value), (
            f"Expected warning '{expected_warning}' not found in exception message: {excinfo.value}"
        )


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
