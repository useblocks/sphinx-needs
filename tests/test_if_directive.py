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
                    ".. if:: var.unknown_key == 'x'\n\n"
                    "   SHOULD_NOT_APPEAR\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_unknown_variant_key_warns(test_app):
    """AttributeError from VariantDataProxy is caught and warned."""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SHOULD_NOT_APPEAR" not in html
    warnings = app._warning.getvalue()
    assert "'if' directive expression failed" in warnings
    assert "Unknown variant key" in warnings


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
                    ".. if:: __import__('os').system('echo pwned')\n\n"
                    "   SHOULD_NOT_APPEAR\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_builtin_access_blocked(test_app):
    """Builtins are not accessible in if expressions."""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SHOULD_NOT_APPEAR" not in html
    warnings = app._warning.getvalue()
    assert "'if' directive expression failed" in warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "extensions = ['sphinx_needs']\n"
                    "needs_variant_data = {'arch': 'xyz'}\n"
                    "needs_types = [{'directive': 'req', 'title': 'Requirement',"
                    " 'prefix': 'REQ_', 'color': '#BFD8D2'}]\n",
                ),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. req:: Existing need\n"
                    "   :id: REQ_EXISTS\n\n"
                    "   Always present.\n\n"
                    ".. if:: var.arch == 'abc'\n\n"
                    "   .. req:: Conditional\n"
                    "      :id: REQ_GHOST\n\n"
                    "      Ghost need.\n\n"
                    ".. needextend:: REQ_GHOST\n"
                    "   :status: open\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_needextend_to_suppressed_need(test_app):
    """needextend targeting a need inside a false if block warns about missing ID."""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "REQ_GHOST" not in html
    warnings = app._warning.getvalue()
    assert "REQ_GHOST" in warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "extensions = ['sphinx_needs']\n"
                    "needs_variant_data = {'arch': 'abc', 'count': 5}\n"
                    "needs_types = []\n",
                ),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. if:: var.arch\n\n"
                    "   INCLUDED_VIA_TRUTHY_STRING\n\n"
                    ".. if:: var.count\n\n"
                    "   INCLUDED_VIA_TRUTHY_INT\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_non_bool_warns(test_app):
    """Non-bool result still works (coerced) but emits a warning."""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    # Content is still included (coercion works)
    assert "INCLUDED_VIA_TRUTHY_STRING" in html
    assert "INCLUDED_VIA_TRUTHY_INT" in html
    # But warnings are emitted
    warnings = app._warning.getvalue()
    assert "did not return a bool" in warnings
