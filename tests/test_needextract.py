from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needextract"}], indirect=True)
def test_needextract_filter_options(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 0


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needextract"}], indirect=True)
def test_needextract_basic_run(test_app):
    app = test_app
    app.build()
    pass
