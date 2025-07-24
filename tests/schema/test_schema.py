import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp

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
):
    # Check if test should be skipped based on min_python version
    if "mark" in content and "min_python" in content["mark"]:
        min_version = tuple(content["mark"]["min_python"])
        if sys.version_info < min_version:
            pytest.skip(
                f"Test requires Python {'.'.join(map(str, min_version))} or higher"
            )
    write_fixture_files(tmpdir, content)
    assert "exception" in content
    with pytest.raises(NeedsConfigException) as excinfo:
        make_app(srcdir=Path(tmpdir), freshenv=True)
    for snippet in content["exception"]:
        assert snippet in str(excinfo.value), (
            f"Expected exception message '{content['exception']}' not found in: {excinfo.value}"
        )


@pytest.mark.fixture_file(
    "schema/fixtures/extra_links.yml",
    "schema/fixtures/extra_options.yml",
    "schema/fixtures/network.yml",
    "schema/fixtures/unevaluated.yml",
)
def test_schemas(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    check_ontology_warnings: Callable[
        [SphinxTestApp, list[list[str | dict[Literal["sphinx8"], list[str]]]]], None
    ],
):
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0
    check_ontology_warnings(app, content["warnings"])
    app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_e2e", "no_plantuml": True}],
    indirect=True,
)
def test_schema_e2e(
    test_app: SphinxTestApp, get_warnings_list: Callable[[SphinxTestApp], list[str]]
) -> None:
    test_app.builder.build_all()
    warnings = get_warnings_list(test_app)

    expected_warnings = [
        (
            "'FEAt' does not match '^[A-Z0-9_]+$'",
            "[sn_schema.local_fail]",
        ),
        (
            "Unevaluated properties are not allowed ('asil', 'priority' were unexpected)",
            "[sn_schema.local_fail]",
        ),
        (
            "'approved' is a required property",
            "[sn_schema.local_fail]",
        ),
        (
            "'SPEC' does not match '^SPEC_[a-zA-Z0-9_-]*$'",
            "[sn_schema.local_fail]",
        ),
        (
            "Unevaluated properties are not allowed ('approved', 'asil', 'links', 'priority' were unexpected)",
            "[sn_schema.local_fail]",
        ),
        (
            "Too few valid links of type 'links' (0 < 1) / nok: FEAT",
            "[sn_schema.network_contains_too_few]",
        ),
        (
            "Unevaluated properties are not allowed ('approved', 'asil', 'links', 'priority' were unexpected)",
            "[sn_schema.local_fail]",
        ),
        (
            "Unevaluated properties are not allowed ('approved', 'asil', 'links', 'priority' were unexpected)",
            "[sn_schema.local_fail]",
        ),
    ]
    for expected in expected_warnings:
        assert any(expected[0] in warning for warning in warnings), (
            f"Expected warning not found: {expected[0]}"
        )
        if sphinx.version_info[0] >= 8:
            assert any(expected[1] in warning for warning in warnings), (
                f"Expected subtype not found: {expected[1]}"
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
