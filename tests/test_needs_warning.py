from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needs_warnings"}], indirect=True)
def test_needs_warnings(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()

    # check multiple warning registration
    assert "'invalid_status' in 'needs_warnings' is already registered." in warnings

    # check warnings contents
    assert "WARNING: invalid_status: failed" in warnings
    assert "failed needs: 2 (SP_TOO_001, US_63252)" in warnings
    assert "used filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3']" in warnings

    # check needs warning from custom defined filter code
    assert "failed needs: 1 (TC_001)" in warnings
    assert "used filter: my_custom_warning_check" in warnings

    # negative test to check needs warning if need passed the warnings-check
    assert "TC_NEG_001" not in warnings

    # Check for warning registered via config api
    assert "WARNING: api_warning_filter: failed" in warnings
    assert "WARNING: api_warning_func: failed" in warnings

    # Check warnings not including external needs
    assert "EXT_TEST_01" not in warnings


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needs_warnings_return_status_code"}], indirect=True
)
def test_needs_warnings_return_status_code(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    # Check return code when "-W --keep-going" not used
    out_normal = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out_normal.returncode == 0

    # Check return code when only "-W" is used
    out_w = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir, "-W"], capture_output=True)
    assert out_w.returncode >= 1

    # Check return code when only "--keep-going" is used
    out_keep_going = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "--keep-going"], capture_output=True
    )
    assert out_keep_going.returncode == 0

    # Check return code when "-W --keep-going" is used
    out_w_keep_going = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "-W", "--keep-going"], capture_output=True
    )
    assert out_w_keep_going.returncode == 1

    # Check no Sphinx raised warnings
    assert "WARNING" not in out_w_keep_going.stdout.decode("utf-8")

    warnings = out_w_keep_going.stderr.decode("utf-8")

    # Check Sphinx-needs raised warnings amount
    assert warnings.count("WARNING: ") == 2

    # Check warnings contents
    assert "WARNING: invalid_status: failed" in warnings
    assert "failed needs: 2 (SP_TOO_001, US_63252)" in warnings
    assert "used filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3']" in warnings

    # Check needs warning from custom defined filter code
    assert "WARNING: type_match: failed" in warnings
    assert "failed needs: 1 (TC_001)" in warnings
    assert "used filter: my_custom_warning_check" in warnings
