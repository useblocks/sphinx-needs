from pathlib import Path

import pytest

from tests.benchmarks._builds import time_html_builds


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_basic"}], indirect=True
)
def test_basic_time(test_app, make_app, benchmark):
    # a build of a few hundredths of a second: one round is all noise, the fastest of
    # twenty is not
    app = time_html_builds(benchmark, make_app, Path(test_app.srcdir), rounds=20)

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "needstable.js" in files
    assert build_dir / "needstable.css" in files
    # the whole vendored DataTables tree went with the enhancer that replaced it
    assert not [f for f in files if "datatables" in f.name.lower()]
