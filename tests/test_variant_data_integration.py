"""Tests for needs_variant_data configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.extensions.json import JSONSnapshotExtension


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


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


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
def test_variant_data_fields_html(test_app, snapshot_json):
    """Test resolving ``<{...}>`` variant data references in need fields."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_data_field_errors",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_data_field_errors_html(test_app, snapshot_json):
    """Test warnings for problematic ``<{...}>`` variant data references.

    Covers invalid ``var.*`` paths, missing variant keys (top-level and
    nested), and resolved values whose type does not match the field schema.
    """
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    assert warnings == [
        "srcdir/index.rst:4: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_SYNTAX': variant data reference 'platform' is invalid: expected a dotted 'var.*' path [needs.dynamic_function]",
        "srcdir/index.rst:8: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING': Unknown variant data key: 'var.nonexistent' [needs.dynamic_function]",
        "srcdir/index.rst:12: WARNING: Error while resolving dynamic values for field 'mystring', of need 'REQ_MISSING_NESTED': Unknown variant data key: 'var.build.missing' [needs.dynamic_function]",
        "srcdir/index.rst:16: WARNING: Error while resolving dynamic values for field 'myint', of need 'REQ_BADTYPE_STR': variant data value <class 'str'> is not of type 'integer' [needs.dynamic_function]",
        "srcdir/index.rst:20: WARNING: Error while resolving dynamic values for field 'myarray', of need 'REQ_BADTYPE_ARRAY': variant data value <class 'int'> is not of type 'array' or item type 'string' [needs.dynamic_function]",
    ]

    data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert data["versions"][""]["needs"] == snapshot_json
