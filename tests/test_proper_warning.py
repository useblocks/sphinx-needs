import pytest
from pathlib import Path
import subprocess

# local execution: pytest test_proper_warning.py

@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_warning"}],
    indirect=True,
)
def test_proper_warning(test_app):

    app = test_app
    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )

    # Build shall be sucessful
    assert out.returncode == 0

    # In html file we expect to get three needs
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")

    assert 'href="#SP_TOO_000" title="SP_TOO_000">SP_TOO_000' in html
    assert 'href="#SP_TOO_001" title="SP_TOO_001">SP_TOO_001' in html
    assert 'href="#SP_TOO_002" title="SP_TOO_002">SP_TOO_002' in html


    # stdout warnings
    warnings = out.stderr.decode("utf-8")

    # Check Sphinx-needs raised errors amount is equal to 3
    assert warnings.count("ERROR: ") == 3

    # Check warnings contents
    assert "index.rst:16: ERROR: Malformed table." in warnings
    assert "index.rst:30: ERROR: Malformed table." in warnings
    assert "index.rst:46: ERROR: Malformed table." in warnings
