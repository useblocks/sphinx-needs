from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_basic"}], indirect=True
)
def test_basic_time(test_app, benchmark):
    app = test_app
    benchmark.pedantic(app.builder.build_all, rounds=1, iterations=1)

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "datatables_loader.js" in files
    assert build_dir / "DataTables-1.10.16" / "js" / "jquery.dataTables.min.js" in files
