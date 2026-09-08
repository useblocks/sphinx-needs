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
    assert build_dir / "needstable.js" in files
    assert build_dir / "needstable.css" in files
    # the whole vendored DataTables tree went with the enhancer that replaced it
    assert not [f for f in files if "datatables" in f.name.lower()]
