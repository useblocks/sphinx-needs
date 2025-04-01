from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_test_ctest_file"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_test_ctest_file"}],
    indirect=True,
)
def test_test_ctest_file(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir],
        capture_output=True,
        check=False,
    )

    assert out.returncode == 0

    # Check no warnings
    assert "WARNING" not in out.stdout.decode("utf-8")

    html = Path(app.outdir, "index.html").read_text()
    # print(html)
    assert html
    assert "TEST_CTEST_1" in html  # suite id
    assert "more_info" in html  # extra added option displayed
    assert "CTESTFILE_1" in html  # case id
    assert "This is a test" in html  # content correct
