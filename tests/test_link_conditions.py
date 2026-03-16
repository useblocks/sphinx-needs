import os
import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_link_conditions"}],
    indirect=True,
)
def test_link_condition_passed(test_app):
    """Test that links with conditions that pass do not emit warnings."""
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    stderr = strip_colors(
        output.stderr.decode("utf-8").replace(str(app.srcdir) + os.sep, "srcdir/")
    )

    # SPEC_001 links to REQ_001[status=="open"] which should pass — no warning for it
    assert "SPEC_001" not in stderr
    # SPEC_004 links to REQ_001 with no condition — no warning for it
    assert "SPEC_004" not in stderr


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_link_conditions"}],
    indirect=True,
)
def test_link_condition_failed(test_app):
    """Test that links with failing conditions emit link_condition_failed warnings."""
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    stderr = strip_colors(
        output.stderr.decode("utf-8").replace(str(app.srcdir) + os.sep, "srcdir/")
    )

    # SPEC_002 links to REQ_002[status=="open"] but REQ_002 has status "closed"
    assert "SPEC_002" in stderr
    assert "link_condition_failed" in stderr
    assert "not satisfied" in stderr


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_link_conditions"}],
    indirect=True,
)
def test_link_condition_invalid_syntax(test_app):
    """Test that links with invalid condition syntax emit link_condition_invalid warnings."""
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    stderr = strip_colors(
        output.stderr.decode("utf-8").replace(str(app.srcdir) + os.sep, "srcdir/")
    )

    # SPEC_003 links to REQ_001[status===] which has invalid syntax
    assert "SPEC_003" in stderr
    assert "link_condition_invalid" in stderr
    assert "invalid condition syntax" in stderr


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_link_conditions"}],
    indirect=True,
)
def test_link_condition_mixed(test_app):
    """Test that with multiple links, only failing conditions emit warnings."""
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    stderr = strip_colors(
        output.stderr.decode("utf-8").replace(str(app.srcdir) + os.sep, "srcdir/")
    )

    # SPEC_005 links to REQ_001[status=="open"] (passes) and REQ_003[status=="open"] (fails)
    # We should see a warning for REQ_003 condition failure
    assert "SPEC_005" in stderr
    assert "REQ_003" in stderr
    assert "not satisfied" in stderr
