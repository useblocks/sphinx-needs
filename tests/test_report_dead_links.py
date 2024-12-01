import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_true"}],
    indirect=True,
)
def test_needs_dead_links_warnings(test_app):
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    # check there are expected warnings
    stderr = strip_colors(output.stderr.decode("utf-8"))
    expected_warnings = [
        f"{Path(str(app.srcdir)) / 'index.rst'}:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        f"{Path(str(app.srcdir)) / 'index.rst'}:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
        f"{Path(str(app.srcdir)) / 'index.rst'}:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
    ]

    assert stderr.splitlines() == expected_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_report_dead_links_true"}],
    indirect=True,
)
def test_needs_dead_links_warnings_needs_builder(test_app):
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "needs", src_dir, out_dir], capture_output=True
    )

    # check there are expected warnings
    stderr = strip_colors(output.stderr.decode("utf-8"))
    expected_warnings = [
        f"{Path(str(app.srcdir)) / 'index.rst'}:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        f"{Path(str(app.srcdir)) / 'index.rst'}:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
        f"{Path(str(app.srcdir)) / 'index.rst'}:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
    ]

    assert stderr.splitlines() == expected_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_false"}],
    indirect=True,
)
def test_needs_dead_links_suppress_warnings(test_app):
    app = test_app

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )

    # check there are no warnings
    assert not output.stderr
