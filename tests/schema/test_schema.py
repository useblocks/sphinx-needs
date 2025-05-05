from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent
from typing import Callable

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

CURR_DIR = Path(__file__).parent


def get_warnings_list(app: SphinxTestApp):
    return strip_colors(app._warning.getvalue()).splitlines()


UBPROJECT_BASE = """
[needs]
schemas_from_json = "schemas.json"

[[needs.extra_options]]
name = "asil"
description = "Automotive Safety Integrity Level"

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


@pytest.mark.parametrize(
    "ubproject_schemas_rst",
    [
        [
            UBPROJECT_BASE
            + dedent("""
                [[needs.extra_options]]
                name = "efforts"
                [needs.extra_options.schema]
                type = "integer" 
                """),
            dedent("""
                []
                """),
            dedent("""
                .. feat:: feat wrong id
                   :id: FEAT_01
                   :asil: QM
                """),
        ]
    ],
)
def test_schema_option_type(
    tmpdir: Path,
    ubproject_schemas_rst: tuple[str, str, str],
    make_app: Iterator[Callable[[], SphinxTestApp]],
):
    """Test matching option type."""
    conf_py_path = tmpdir / "conf.py"
    conf_py_path.write_text(CONF_PY_BASE, encoding="utf-8")

    ubproject_content, schemas_content, rst_content = ubproject_schemas_rst
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
    assert len(warnings) == 0


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
