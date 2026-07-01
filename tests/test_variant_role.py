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

    # Only the invalid reference should warn.
    assert warnings == [
        "srcdir/index.rst:12: WARNING: 'variant' role could not resolve "
        "'nonexistent': Unknown variant data key: 'var.nonexistent' [needs.variant]",
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
