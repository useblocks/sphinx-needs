import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

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
) -> None:
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
    snapshot,
) -> None:
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0
    warnings = strip_colors(app._warning.getvalue())
    assert warnings == snapshot
    app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema_e2e", "no_plantuml": True}],
    indirect=True,
)
def test_schema_e2e(test_app: SphinxTestApp, snapshot) -> None:
    test_app.builder.build_all()
    warnings = strip_colors(test_app._warning.getvalue())
    assert warnings == snapshot

    html = Path(test_app.outdir, "index.html").read_text()
    assert html
    # check schema validation report JSON exist
    report_json = Path(test_app.outdir, "schema_violations.json")
    assert report_json.exists(), (
        f"Expected schema validation report JSON file not found: {report_json}"
    )
