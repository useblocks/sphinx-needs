import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx import version_info as sphinx_version
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.exceptions import NeedsConfigException

CURR_DIR = Path(__file__).parent


@pytest.mark.fixture_file(
    "schema/fixtures/config.yml",
)
def test_schema_config(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    # Check if test should be skipped based on min_python version
    if "mark" in content and "min_python" in content["mark"]:
        min_version = tuple(content["mark"]["min_python"])
        if sys.version_info < min_version:
            pytest.skip(
                f"Test requires Python {'.'.join(map(str, min_version))} or higher"
            )
    write_fixture_files(tmpdir, content)
    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=Path(tmpdir), freshenv=True)
        app.build()
    assert str(excinfo.value) == snapshot


@pytest.mark.fixture_file(
    "schema/fixtures/extra_links.yml",
    "schema/fixtures/fields.yml",
    "schema/fixtures/network.yml",
    "schema/fixtures/reporting.yml",
    "schema/fixtures/unevaluated.yml",
)
def test_schemas(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0
    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )
    assert warnings == snapshot

    schema_violations: dict[str, Any] = json.loads(
        Path(app.outdir, "schema_violations.json").read_text("utf8")
    )
    exclude_keys = {"validated_needs_per_second", "validation_summary"}
    for key in exclude_keys:
        schema_violations.pop(key, None)
    assert schema_violations == snapshot
    app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/schema_typing", "no_plantuml": True}],
    indirect=True,
)
def test_schema_typing(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warnings = (
        strip_colors(test_app._warning.getvalue())
        .replace(str(test_app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )
    print(warnings)
    assert not warnings

    needs = json.loads(Path(test_app.outdir, "needs.json").read_text("utf8"))
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_e2e", "no_plantuml": True}],
    indirect=True,
)
def test_schema_e2e(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warnings = strip_colors(test_app._warning.getvalue())
    assert warnings == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))

    html = Path(test_app.outdir, "index.html").read_text()
    assert html
    # check schema validation report JSON exist
    report_json = Path(test_app.outdir, "schema_violations.json")
    assert report_json.exists(), (
        f"Expected schema validation report JSON file not found: {report_json}"
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_schema_example",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_schema_example(test_app: SphinxTestApp, snapshot) -> None:
    """Check error-free build of the example from the docs."""
    test_app.build()
    warnings = strip_colors(test_app._warning.getvalue())
    assert not warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    "conf.py",
                    """

extensions = ["sphinx_needs"]
needs_schema_validation_enabled = False
needs_fields = {
    "extra": {"schema": {"type": "string", "enum": ["a", "b"]}}
        }
                """,
                ),
                (
                    "index.rst",
                    """
Test
====
.. req:: A requirement
  :extra: x
""",
                ),
            ],
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_validation_disabled(test_app):
    """Test that disabling schema validation suppresses schema violation warnings and output."""
    app = test_app
    app.build()
    assert app.statuscode == 0
    assert not app._warning.getvalue()
    assert not Path(app.outdir, "schema_violations.json").exists()


@pytest.mark.parametrize("schema_benchmark_app", [10, 100], indirect=True)
@pytest.mark.skipif(
    sphinx_version < (8,),
    reason="sphinx 7 does not emit warning code prefixes, so snapshots differ",
)
def test_schema_benchmark(schema_benchmark_app, snapshot):
    """Test the benchmark project works."""
    schema_benchmark_app.build()
    assert schema_benchmark_app.statuscode == 0
    warnings = strip_colors(schema_benchmark_app.warning.getvalue()).replace(
        str(schema_benchmark_app.srcdir) + os.path.sep, "<srcdir>/"
    )
    assert warnings == snapshot

@pytest.mark.fixture_file(
    "schema/fixtures/fields.yml",
)
def test_multiple_errors_per_need(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    """Test that all validation errors per need are collected and reported.

    This test verifies the fix for issue #1627 where only the first error
    was being returned instead of all errors for a given need.
    """
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0
    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )
    assert warnings == snapshot

    schema_violations: dict[str, Any] = json.loads(
        Path(app.outdir, "schema_violations.json").read_text("utf8")
    )
    exclude_keys = {"validated_needs_per_second", "validation_summary"}
    for key in exclude_keys:
        schema_violations.pop(key, None)
    assert schema_violations == snapshot

    # Verify that all errors for IMPL_1 are present
    violations = schema_violations.get("violations", [])
    impl_1_violations = [v for v in violations if v.get("need") == "IMPL_1"]
    # Should have multiple errors (one for priority being invalid type, one for severity being invalid enum value)
    assert len(impl_1_violations) == 2, (
        f"Expected exactly 2 errors for IMPL_1, but got {len(impl_1_violations)}: {impl_1_violations}"
    )
    app.cleanup()
