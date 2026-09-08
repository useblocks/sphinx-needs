import subprocess
from pathlib import Path

import pytest

from sphinx_needs_testkit import build_warnings, sphinx_build_command


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
        sphinx_build_command("-M", "html", src_dir, out_dir), capture_output=True
    )

    # check there are expected warnings
    emitted = build_warnings(output.stderr.decode("utf-8"), srcdir=app.srcdir)
    expected_warnings = [
        "<srcdir>/index.rst:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
    ]

    assert emitted == expected_warnings


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
        sphinx_build_command("-M", "needs", src_dir, out_dir), capture_output=True
    )

    # check there are expected warnings
    emitted = build_warnings(output.stderr.decode("utf-8"), srcdir=app.srcdir)
    expected_warnings = [
        "<srcdir>/index.rst:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
    ]

    assert emitted == expected_warnings


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
        sphinx_build_command("-M", "html", src_dir, out_dir), capture_output=True
    )

    # check there are no warnings
    assert not output.stderr
