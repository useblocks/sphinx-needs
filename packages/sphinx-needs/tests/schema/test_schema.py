import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx import version_info as sphinx_version
from sphinx.testing.util import SphinxTestApp
from syrupy.filters import props

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit import assert_no_warnings, build_warnings

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
    "schema/fixtures/links.yml",
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
    warnings_text = "\n".join(build_warnings(app))
    assert warnings_text == snapshot

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
    [{"buildername": "html", "srcdir": "doc_test/schema_typing"}],
    indirect=True,
)
def test_schema_typing(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warning_records = build_warnings(test_app)
    print(warning_records)
    assert_no_warnings(test_app)

    needs = json.loads(Path(test_app.outdir, "needs.json").read_text("utf8"))
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_e2e"}],
    indirect=True,
)
def test_schema_e2e(test_app: SphinxTestApp, snapshot) -> None:
    test_app.build()
    warnings_text = "\n".join(build_warnings(test_app))
    assert warnings_text == snapshot

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
        }
    ],
    indirect=True,
)
def test_schema_example(test_app: SphinxTestApp, snapshot) -> None:
    """Check error-free build of the example from the docs."""
    test_app.build()
    assert_no_warnings(test_app)


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
    warnings_text = "\n".join(build_warnings(schema_benchmark_app))
    assert warnings_text == snapshot


_HEADER_CONF = """
extensions = ["sphinx_needs"]
needs_links = {
    "verifies": {"incoming": "is verified by", "outgoing": "verifies"},
    "implements": {"incoming": "is implemented by", "outgoing": "implements"},
}
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
    {"directive": "test", "title": "Test", "prefix": "T_"},
]
needs_schema_definitions = {"schemas": [{
    "id": "test-rule",
    "select": {"properties": {"type": {"const": "test"}}},
    "validate": {"network": {"verifies": {"items": %s}}},
}]}
"""
_HEADER_RST = """
Test
====

.. req:: A requirement
   :id: R_001

.. spec:: A spec
   :id: S_001
   :implements: %s

.. spec:: Another spec
   :id: S_002

.. test:: A test
   :id: T_001
   :verifies: S_001
"""


@pytest.mark.parametrize(
    "test_app, need_paths",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % '{"local": {"properties": {"type": {"const": "req"}}}}',
                    ),
                    ("index.rst", _HEADER_RST % "R_001"),
                ],
            },
            ["T_001 > verifies > S_001"],
            id="level-1-network-local-fail",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % (
                            '{"network": {"implements": {"items": {"local":'
                            ' {"properties": {"type": {"const": "req"}}}}}}}'
                        ),
                    ),
                    ("index.rst", _HEADER_RST % "S_002"),
                ],
            },
            ["T_001 > verifies > S_001 > implements > S_002"],
            id="level-2-network-local-fail",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        "conf.py",
                        _HEADER_CONF
                        % (
                            '{"network": {"implements": {"contains": {"local":'
                            ' {"properties": {"type": {"const": "req"}}}}}}}'
                        ),
                    ),
                    ("index.rst", _HEADER_RST % "S_002"),
                ],
            },
            ["T_001 > verifies > S_001 > implements"],
            id="level-1-network-contains-too-few",
        ),
    ],
    indirect=["test_app"],
)
def test_network_finding_header_names_selected_need(
    test_app: SphinxTestApp, need_paths: list[str]
) -> None:
    """A network finding's console header names the need the rule SELECTED (#2297).

    The rule selects ``T_001``; the failure is found on a need it links to,
    one or two hops away.
    The header used to name the need at the failing level (``S_001`` / ``S_002``),
    which reads as if the linked need broke the rule,
    while ``schema_violations.json`` files the finding under ``T_001``.
    The ``Need path`` line keeps the whole chain.
    """
    test_app.build()
    records = [r for r in build_warnings(test_app) if "Need path:" in r]
    assert len(records) == len(need_paths), records
    for record, need_path in zip(records, need_paths, strict=True):
        first_line = record.splitlines()[0]
        assert first_line == "ERROR: Need 'T_001' has schema violations:", record
        assert f"  Need path:      {need_path}" in record.splitlines(), record

    report = json.loads(
        Path(test_app.outdir, "schema_violations.json").read_text("utf8")
    )
    assert list(report["validation_warnings"]) == ["T_001"]
