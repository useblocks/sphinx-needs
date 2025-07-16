from collections.abc import Callable
from pathlib import Path
from textwrap import dedent

import pytest
import sphinx
import syrupy
from jinja2 import Template
from sphinx.testing.util import SphinxTestApp
from syrupy.extensions.amber import AmberSnapshotExtension
from syrupy.location import PyTestLocation

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
    get_warnings_list: Callable[[SphinxTestApp], list[str]],
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
