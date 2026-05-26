"""Tests for the ``.. if::`` directive."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_if_directive"}],
    indirect=True,
)
def test_if_directive(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    # True condition includes content
    assert "INCLUDED_ARCH_ABC" in html
    # False condition excludes content
    assert "EXCLUDED_ARCH_XYZ" not in html

    # Boolean truthiness
    assert "INCLUDED_DEBUG_TRUE" in html
    assert "EXCLUDED_DEBUG_FALSE" not in html

    # Nested attribute access
    assert "INCLUDED_BUILD_OPT" in html
    assert "EXCLUDED_BUILD_OPT_HIGH" not in html

    # Membership test (in operator)
    assert "INCLUDED_FEATURE_F1" in html
    assert "EXCLUDED_FEATURE_MISSING" not in html

    # Nested if directives
    assert "OUTER_IF_CONTENT" in html
    assert "NESTED_IF_CONTENT" in html

    # Section headers inside if blocks
    assert "Conditional section" in html
    assert "INCLUDED_SECTION_CONTENT" in html
    assert "Skipped section" not in html
    assert "EXCLUDED_SECTION_CONTENT" not in html

    # Needs inside if blocks
    assert "REQ_CONDITIONAL" in html
    assert "A conditional requirement" in html
    assert "REQ_SKIPPED" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_if_no_variant"}],
    indirect=True,
)
def test_if_no_variant_data(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SHOULD_NOT_APPEAR" not in html
    # Check that a warning was emitted
    warnings = app._warning.getvalue()
    assert "needs_variant_data is not configured" in warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "extensions = ['sphinx_needs']\n"
                    "needs_variant_data = {'arch': 'abc'}\n"
                    "needs_types = []\n",
                ),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. if:: invalid syntax !!!\n\n"
                    "   SHOULD_NOT_APPEAR\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_invalid_expression_warns(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SHOULD_NOT_APPEAR" not in html
    warnings = app._warning.getvalue()
    assert "'if' directive expression failed" in warnings
