import re
import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_github_issue_44"}],
    indirect=True,
)
def test_doc_github_44(test_app):
    """
    https://github.com/useblocks/sphinxcontrib-needs/issues/44
    """
    # Ugly workaround to get the sphinx build output.
    # I have no glue how to get it from an app.build(), because stdout redirecting does not work. Maybe because
    # nosetest is doing something similar for each test.
    # So we call the needed command directly, but still use the sphinx_testing app to create the outdir for us.
    app = test_app

    output = subprocess.run(
        ["sphinx-build", "-a", "-E", "-b", "html", app.srcdir, app.outdir],
        check=True,
        capture_output=True,
    )

    # app.build() Uncomment, if build should stop on breakpoints
    html = Path(app.outdir, "index.html").read_text()
    assert "<h1>Github Issue 44 test" in html
    assert "Test 1" in html
    assert "Test 2" in html
    assert "Test 3" in html

    stderr = strip_colors(output.stderr.decode("utf-8"))

    expected_warnings = [
        f"{Path(str(app.srcdir)) / 'index.rst'}:11: WARNING: Need 'test_3' has unknown outgoing link 'test_123_broken' in field 'links' [needs.link_outgoing]"
    ]

    assert stderr.splitlines() == expected_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_github_issue_61"}],
    indirect=True,
)
def test_doc_github_61(test_app):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/61
    """
    # PlantUML doesn't support entity names with dashes in them, and Needs uses
    # the IDs as entity names, and IDs could have dashes.  To avoid this limitation,
    # Entity names are transformed to replace the dashes with underscores in the entity
    # names.
    # Even if there's an error creating the diagram, there's no way to tell since the
    # error message is embedded in the image itself. The best we can do is make sure
    # the transformed entity names are in the alt text of the image.
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    alt_text = re.findall("<img.*?alt=(.*?)>", html, re.MULTILINE + re.DOTALL)
    assert len(alt_text) == 1
    assert "A-001" in alt_text[0]
    assert "A-002" in alt_text[0]
    assert "A_001" in alt_text[0]
    assert "A_002" in alt_text[0]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_github_issue_160"}],
    indirect=True,
)
def test_doc_github_160(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert '<a class="reference internal" href="#A-001" title="A-002">A-001</a>' in html
