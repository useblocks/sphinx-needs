from pathlib import Path

import pytest
from bs4 import BeautifulSoup


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_test_file"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_test_file"}],
    indirect=True,
)
def test_test_file_needs_extra_options_no_warning(test_app):
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

    # Check no warnings — Sphinx writes warnings to stderr, not stdout
    stderr = out.stderr.decode("utf-8")
    stdout = out.stdout.decode("utf-8")

    # stdout should not contain warnings (Sphinx doesn't write them there)
    assert "WARNING" not in stdout, f"Found warnings in stdout (unexpected): {stdout}"

    # stderr should not contain warnings or errors
    assert "WARNING" not in stderr, f"Found warnings in stderr: {stderr}"
    assert "ERROR" not in stderr, f"Found errors in stderr: {stderr}"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_test_file"}],
    indirect=True,
)
def test_test_file_renders_need_with_counts(test_app):
    """test-file directive must render a need node with correct count fields.

    Catches regressions where int values (suites, cases, passed, etc.) passed
    to add_need() are rejected by newer sphinx-needs versions.
    """
    app = test_app
    app.build()
    assert app.statuscode == 0

    html = Path(app.outdir, "index.html").read_text()
    assert "TESTFILE_1" in html

    # Verify HTML contains the need table and integer count fields were rendered
    # sphinx-needs renders needs as <table id="NEED_ID"> with field values in
    # <span class="needs_<field>"> elements.
    soup = BeautifulSoup(html, "html.parser")
    need_table = soup.find("table", id="TESTFILE_1")
    assert need_table is not None, "Need table with id='TESTFILE_1' not found in HTML"

    # Verify integer count fields are present and contain numeric values
    required_fields = ["suites", "cases", "passed", "skipped", "failed", "errors"]
    for field in required_fields:
        span = need_table.find(class_=f"needs_{field}")
        assert span is not None, f"Missing <span class='needs_{field}'> in need table"
        value = span.get_text(strip=True).replace(f"{field}:", "").strip()
        try:
            int(value)
        except ValueError:
            raise AssertionError(
                f"needs_{field} value should be numeric, got: {value!r}"
            ) from None
