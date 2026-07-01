"""Tests for the ``variant`` role."""

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
            "srcdir": "doc_test/doc_variant_role",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_role_html(test_app):
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    # The invalid reference and the mapping reference should warn.
    assert warnings == [
        "srcdir/index.rst:12: WARNING: 'variant' role could not resolve "
        "'nonexistent': Unknown variant data key: 'var.nonexistent' [needs.variant]",
        "srcdir/index.rst:14: WARNING: 'variant' role could not resolve "
        "'build': variant data reference 'var.build' resolves to a mapping "
        "('var.build'); access a leaf value instead [needs.variant]",
    ]

    index_html = Path(app.outdir, "index.html").read_text()

    # Scalar string resolves to its value.
    assert "Scalar string: arm" in index_html
    # Nested int is stringified.
    assert "Nested int: 2" in index_html
    # Nested bool is stringified.
    assert "Nested bool: True" in index_html
    # List values are comma-joined.
    assert "List value: arm, x86" in index_html
    # A mapping reference produces empty text.
    assert (
        "Mapping reference: </p>" in index_html
        or "Mapping reference:</p>" in index_html
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_role_no_data",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_role_no_data_html(test_app):
    """The role warns (and emits empty text) when no variant data is available."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    assert warnings == [
        "srcdir/index.rst:4: WARNING: 'variant' role used but no variant data "
        "is available: 'platform' [needs.variant]",
    ]

    index_html = Path(app.outdir, "index.html").read_text()
    assert "Reference: </p>" in index_html or "Reference:</p>" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_variant_role_file",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_variant_role_file_html(test_app):
    """The role reads the resolved/merged variant data (file + inline override)."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == []

    index_html = Path(app.outdir, "index.html").read_text()
    # Value from the JSON file.
    assert "From file: us-east" in index_html
    # Inline value overrides the file value.
    assert "Overridden inline: staging" in index_html
