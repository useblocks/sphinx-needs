import sys
from collections.abc import Callable
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal

import pytest
import sphinx
import syrupy
from jinja2 import Template
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from syrupy.extensions.amber import AmberSnapshotExtension
from syrupy.location import PyTestLocation

from sphinx_needs.exceptions import NeedsConfigException

CURR_DIR = Path(__file__).parent


def get_warnings_list(app: SphinxTestApp) -> list[str]:
    warnings_raw = strip_colors(app.warning.getvalue())
    warnings_split = [part for part in warnings_raw.split("WARNING: ") if part]
    return warnings_split


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
def test_schema_e2e(test_app: SphinxTestApp) -> None:
    test_app.builder.build_all()

    warnings_raw = strip_colors(test_app.warning.getvalue())
    warnings = [part for part in warnings_raw.split("WARNING: ") if part]

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


# split snapshot dir as warning (sub-)types are emitted only for Sphinx >= 8
SNAPSHOT_DIR = (
    "__snapshots__sphinx_lt_8"
    if sphinx.version_info[0] < 8
    else "__snapshots__sphinx_ge_8"
)
"""Snapshot directory name."""


class DifferentDirectoryExtension(AmberSnapshotExtension):
    """Overwrite the directory name for the snapshot files."""

    @classmethod
    def dirname(cls, *, test_location: "PyTestLocation") -> str:
        return str(Path(test_location.filepath).parent.joinpath(SNAPSHOT_DIR))


@pytest.fixture
def snapshot(snapshot: syrupy.SnapshotAssertion):
    return snapshot.use_extension(DifferentDirectoryExtension)


@pytest.mark.parametrize(
    "need_cnt",
    [
        10,
        100,
        1_000,
        # 5_000,
        # 10_000,
    ],
)
@pytest.mark.benchmark
def test_schema_benchmark(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    need_cnt: int,
    snapshot: syrupy.SnapshotAssertion,
):
    """
    Benchmark on many needs with thousands of warnings.

    This also tests the dedicated schema builder.
    """
    assert need_cnt % 10 == 0, "need_cnt must be a multiple of 10"
    page_cnt = int(need_cnt / 10)

    this_file_dir = Path(__file__).parent

    src_dir = this_file_dir / ".." / "doc_test" / "doc_schema_benchmark"
    page_template_path = src_dir / "page.rst.j2"
    with page_template_path.open() as fp:
        template_content = fp.read()

    template = Template(template_content)
    pages_dir = Path(tmpdir) / "pages"
    pages_dir.mkdir(exist_ok=True)
    toctree_content = dedent(
        """
        .. toctree::
           :maxdepth: 2

        """
    )

    width = len(str(page_cnt))
    for i in range(1, page_cnt + 1):
        i_fmt = f"{i:0{width}d}"
        page_rst_content = template.render(page_nr=i_fmt)

        page_name = f"page_{i_fmt}"
        page_file = f"{page_name}.rst"
        page_rst_path = pages_dir / page_file
        page_rst_path.write_text(page_rst_content, encoding="utf-8")
        toctree_content += f"   pages/{page_name}\n"

    index_file = tmpdir / "index.rst"
    index_file.write_text(toctree_content, encoding="utf-8")

    copy_files = [
        src_dir / "conf.py",
        src_dir / "schemas.json",
        src_dir / "ubproject.toml",
    ]
    for copy_file in copy_files:
        dst_file = tmpdir / copy_file.name
        dst_file.write_text(copy_file.read_text(), encoding="utf-8")

    app: SphinxTestApp = make_app(
        # the schema builder does only validate, no output
        buildername="schema",
        srcdir=Path(tmpdir),
        freshenv=True,
    )
    app.build()

    assert app.statuscode == 0

    warnings = get_warnings_list(app)
    expected_warnings_per_page = 7
    assert len(warnings) == expected_warnings_per_page * page_cnt

    if need_cnt < 500:
        # keep snapshot small;
        assert warnings == snapshot

    app.cleanup()
