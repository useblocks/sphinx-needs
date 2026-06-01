"""Tests for needs_variant_data configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    print(warnings)
    # The needs_warnings check for wrong_platform should fire for REQ_002
    assert warnings == [
        "WARNING: wrong_platform: failed",
        "\t\tfailed needs: 1 (REQ_002)",
        "\t\tused filter: platform is not None and var.platform != platform [needs.warnings]",
    ]

    index_html = Path(app.outdir, "index.html").read_text()

    # needtable: var.platform == platform matches REQ_001 (platform=arm)
    assert "REQ_001" in index_html
    assert '<td class="needs_title"><p>ARM Requirement</p></td>' in index_html

    # needlist: "arm" in var.archs is always True, so all needs shown
    assert "REQ_002" in index_html
    assert "REQ_003" in index_html

    # needcount: var.build.debug == True is always True, so count = 3
    assert "Debug mode needs: 3" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_file",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_file_html(test_app):
    """Test loading variant data from a JSON file with inline override."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    index_html = Path(app.outdir, "index.html").read_text()

    # Inline needs_variant_data overrides env from "production" to "staging"
    # so var.env == "staging" matches all needs
    assert "REQ_STAGING" in index_html
    assert "REQ_PROD" in index_html

    # var.region == "us-east" still works (from file, not overridden)
    assert "US East Needs" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_fields",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_fields_html(test_app):
    """Test resolving ``<{...}>`` variant data references in need fields."""
    import json

    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    needs = json.loads(Path(app.outdir, "needs.json").read_text())
    versions = needs["versions"]
    data = versions[next(iter(versions))]["needs"]

    # scalar string resolves to the variant data value
    assert data["REQ_001"]["mystring"] == "arm"
    # embedded string substitutes the resolved value
    # (string parts are joined with a space, as for variant functions)
    assert data["REQ_002"]["mystring"] == "platform is  arm !"
    # integer field resolves to the variant data integer
    assert data["REQ_003"]["myint"] == 2
    # array field substitutes the resolved value as an item
    assert data["REQ_004"]["myarray"] == ["a", "arm", "c"]
