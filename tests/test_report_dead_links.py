from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_true"}], indirect=True
)
def test_needs_report_dead_links_true(test_app):
    import subprocess

    app = test_app

    # Check config value of needs_report_dead_links
    assert app.config.needs_report_dead_links

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)

    # Check log info msg of dead links
    assert (
        "Needs: outgoing linked need DEAD_LINK_ALLOWED not found (document: index, source need REQ_001 on line 7 )"
        in output.stdout.decode("utf-8")
    )
    # Check log warning msg of dead links
    assert (
        "WARNING: Needs: outgoing linked need ANOTHER_DEAD_LINK not found (document: index, "
        "source need REQ_004 on line 17 )" in output.stderr.decode("utf-8")
    )
    assert (
        "WARNING: Needs: outgoing linked need REQ_005 not found (document: index, source need TEST_004 on line 45 )"
        in output.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_false"}], indirect=True
)
def test_needs_report_dead_links_false(test_app):
    import subprocess

    app = test_app

    # Check config value of needs_report_dead_links
    assert not app.config.needs_report_dead_links

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)

    # Check log info msg of dead links deactivated
    assert (
        "Needs: outgoing linked need DEAD_LINK_ALLOWED not found (document: index, source need REQ_001 on line 7 )"
        not in output.stdout.decode("utf-8")
    )
    # Check log warning msg of dead links deactivated
    assert (
        "WARNING: Needs: outgoing linked need ANOTHER_DEAD_LINK not found (document: index, "
        "source need REQ_004 on line 17 )" not in output.stderr.decode("utf-8")
    )
    assert (
        "WARNING: Needs: outgoing linked need REQ_005 not found (document: index, source need TEST_004 on line 45 )"
        not in output.stderr.decode("utf-8")
    )
    assert not output.stderr
