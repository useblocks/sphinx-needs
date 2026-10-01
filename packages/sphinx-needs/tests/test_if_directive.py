"""Tests for the ``.. if::`` directive."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needif import IfChainMarker
from sphinx_needs_testkit import assert_no_warnings, build_warnings


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


# ``elif`` and ``else``

_CHAIN_CONF = (
    "extensions = ['sphinx_needs']\n"
    "needs_variant_data = {'arch': 'abc', 'count': 5}\n"
    "needs_types = []\n"
)


def _chain_project(body: str, conf: str = _CHAIN_CONF) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Test\n====\n\n" + body),
        ],
    }


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_if_elif_else"}],
    indirect=True,
)
def test_if_elif_else_chains(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text()

    taken = [
        "TAKEN_IF",
        "TAKEN_FIRST_TRUE_ELIF",
        "TAKEN_ELSE_ALL_FALSE",
        "TAKEN_ELSE_WITHOUT_ELIF",
        "TAKEN_FIRST_CHAIN",
        "TAKEN_SECOND_CHAIN_ELSE",
        "TAKEN_ELSE_AFTER_COMMENT",
        "OUTER_TAKEN",
        "TAKEN_NESTED_ELSE",
        "Conditional heading",
        "TAKEN_SECTION_CONTENT",
        "TAKEN_IN_NEED",
    ]
    assert [word for word in taken if word not in html] == []
    assert "SKIPPED_" not in html

    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["REQ_ELIF_TAKEN", "REQ_HOST"]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_if_elif_else"}],
    indirect=True,
)
def test_if_chain_markers_are_stripped(test_app):
    """No marker reaches the pickled doctree, whichever branch left it."""
    app = test_app
    app.build()
    doctree = app.env.get_doctree("index")
    assert list(doctree.findall(IfChainMarker)) == []


@pytest.mark.parametrize(
    "test_app",
    [
        _chain_project(
            ".. if:: var.arch == 'abc'\n\n"
            "   TAKEN_IF\n\n"
            ".. elif:: var.unknown_key == 'x'\n\n"
            "   SKIPPED_ELIF\n\n"
            ".. elif:: invalid syntax !!!\n\n"
            "   SKIPPED_ELIF_2\n"
        )
    ],
    indirect=True,
)
def test_elif_short_circuits(test_app):
    """An ``elif`` after a taken branch is not evaluated, so it cannot warn."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text()
    assert "TAKEN_IF" in html
    assert "SKIPPED_" not in html


_WARNING_CASES = {
    "orphan elif": (
        ".. elif:: True\n\n   SKIPPED_ORPHAN\n",
        ["'elif' directive without a preceding 'if' or 'elif'"],
        [],
    ),
    "orphan else": (
        ".. else::\n\n   SKIPPED_ORPHAN\n",
        ["'else' directive without a preceding 'if' or 'elif'"],
        [],
    ),
    "orphan else with a condition": (
        ".. else:: True\n\n   SKIPPED_ORPHAN\n",
        ["'else' directive takes no condition, got 'True'"],
        [],
    ),
    "paragraph breaks the chain": (
        ".. if:: False\n\n   SKIPPED_IF\n\n"
        "A paragraph between the branches.\n\n"
        ".. else::\n\n   SKIPPED_ORPHAN\n",
        ["'else' directive without a preceding 'if' or 'elif'"],
        [],
    ),
    "orphan poisons its chain": (
        ".. elif:: False\n\n   SKIPPED_ORPHAN\n\n.. else::\n\n   SKIPPED_ELSE\n",
        ["'elif' directive without a preceding 'if' or 'elif'"],
        [],
    ),
    "elif after else": (
        ".. if:: False\n\n   SKIPPED_IF\n\n"
        ".. else::\n\n   TAKEN_ELSE\n\n"
        ".. elif:: True\n\n   SKIPPED_ELIF\n",
        ["'elif' directive after 'else'"],
        ["TAKEN_ELSE"],
    ),
    "else after else": (
        ".. if:: True\n\n   TAKEN_IF\n\n"
        ".. else::\n\n   SKIPPED_ELSE\n\n"
        ".. else::\n\n   SKIPPED_ELSE_2\n",
        ["'else' directive after 'else'"],
        ["TAKEN_IF"],
    ),
    "error in if poisons the chain": (
        ".. if:: var.unknown_key == 'x'\n\n   SKIPPED_IF\n\n"
        ".. elif:: True\n\n   SKIPPED_ELIF\n\n"
        ".. else::\n\n   SKIPPED_ELSE\n",
        ["'if' directive expression failed"],
        [],
    ),
    "error in elif poisons the chain": (
        ".. if:: False\n\n   SKIPPED_IF\n\n"
        ".. elif:: invalid syntax !!!\n\n   SKIPPED_ELIF\n\n"
        ".. elif:: True\n\n   SKIPPED_ELIF_2\n\n"
        ".. else::\n\n   SKIPPED_ELSE\n",
        ["'elif' directive expression failed"],
        [],
    ),
    "builtins blocked in elif": (
        ".. if:: False\n\n   SKIPPED_IF\n\n"
        ".. elif:: __import__('os').system('echo pwned')\n\n   SKIPPED_ELIF\n",
        ["'elif' directive expression failed"],
        [],
    ),
    "non-bool elif is coerced": (
        ".. if:: False\n\n   SKIPPED_IF\n\n"
        ".. elif:: var.count\n\n   TAKEN_ELIF\n\n"
        ".. else::\n\n   SKIPPED_ELSE\n",
        ["'elif' directive expression did not return a bool"],
        ["TAKEN_ELIF"],
    ),
}


@pytest.mark.parametrize(
    ("test_app", "expected_warnings", "taken"),
    [
        (_chain_project(body), warnings, taken)
        for body, warnings, taken in _WARNING_CASES.values()
    ],
    ids=list(_WARNING_CASES),
    indirect=["test_app"],
)
def test_if_chain_warnings(test_app, expected_warnings, taken):
    """Each mistake warns exactly once, and fails closed: its content is skipped."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(expected_warnings), warnings
    for warning, expected in zip(warnings, expected_warnings, strict=True):
        assert expected in warning
        assert "[needs.if]" in warning
    html = Path(app.outdir, "index.html").read_text()
    assert [word for word in taken if word not in html] == []
    assert "SKIPPED_" not in html


@pytest.mark.parametrize(
    "test_app",
    [
        _chain_project(
            ".. if:: var.arch == 'abc'\n\n   SKIPPED_IF\n\n"
            ".. else::\n\n   SKIPPED_ELSE\n",
            conf="extensions = ['sphinx_needs']\nneeds_types = []\n",
        )
    ],
    indirect=True,
)
def test_if_chain_without_variant_data(test_app):
    """With no variant data the chain fails closed: the ``else`` is not a fallback."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert "needs_variant_data is not configured" in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SKIPPED_" not in html


@pytest.mark.parametrize(
    "test_app",
    [_chain_project("Para.\n\n.. elif:: True\n\n   SKIPPED_ORPHAN\n")],
    indirect=True,
)
def test_orphan_warning_location(test_app):
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    # the `elif` is on line 6: the title takes lines 1-2, then a blank, `Para.`, a blank
    assert warning.startswith("<srcdir>/index.rst:6: WARNING:"), warning


@pytest.mark.parametrize(
    "test_app",
    [_chain_project(".. if:: False\n\n   SKIPPED_IF\n\n.. else:: True\n\n   X\n")],
    indirect=True,
)
def test_else_takes_no_argument(test_app):
    """A condition on ``else`` warns and fails closed, rather than becoming body text."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert "'else' directive takes no condition, got 'True'" in warning
    html = Path(app.outdir, "index.html").read_text()
    assert "SKIPPED_" not in html
    assert "<p>X</p>" not in html


@pytest.mark.skipif(
    importlib.util.find_spec("myst_parser") is None, reason="needs myst-parser"
)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    _CHAIN_CONF.replace(
                        "['sphinx_needs']", "['sphinx_needs', 'myst_parser']"
                    ),
                ),
                (
                    Path("index.md"),
                    "# Test\n\n"
                    "```{if} var.arch == 'xyz'\nSKIPPED_IF\n```\n\n"
                    "```{elif} var.arch == 'abc'\nTAKEN_ELIF\n```\n\n"
                    "```{else}\nSKIPPED_ELSE\n```\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_if_chain_in_myst(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text()
    assert "TAKEN_ELIF" in html
    assert "SKIPPED_" not in html


_EXTRACT_CONF = (
    "extensions = ['sphinx_needs']\n"
    "needs_variant_data = {'arch': 'abc'}\n"
    "needs_types = [{'directive': 'req', 'title': 'Requirement',"
    " 'prefix': 'R_', 'color': '#BFD8D2'}]\n"
)

_NEED_CONTENT_CHAINS = {
    "chain": (
        "   .. if:: False\n\n      SKIPPED_IF\n\n"
        "   .. elif:: True\n\n      TAKEN_BRANCH\n\n"
        "   .. else::\n\n      SKIPPED_ELSE\n"
    ),
    # a plain `if` leaves markers too; this is the case that built on master
    "plain if": (
        "   .. if:: False\n\n      SKIPPED_IF\n\n"
        "   .. if:: True\n\n      TAKEN_BRANCH\n"
    ),
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), _EXTRACT_CONF),
                (
                    Path("index.rst"),
                    "Test\n====\n\n"
                    ".. toctree::\n\n   other\n\n"
                    ".. req:: Host\n   :id: R_HOST\n\n" + body,
                ),
                (
                    Path("other.rst"),
                    "Other\n=====\n\n.. needextract::\n   :filter: id == 'R_HOST'\n",
                ),
            ],
        }
        for body in _NEED_CONTENT_CHAINS.values()
    ],
    ids=list(_NEED_CONTENT_CHAINS),
    indirect=True,
)
def test_if_chain_in_need_content_is_extractable(test_app):
    """No marker reaches the need-node cache, which ``needextract`` renders elsewhere.

    The cache is filled while the need directive runs, before any transform.
    """
    app = test_app
    app.build()
    assert_no_warnings(app)
    for page in ("index.html", "other.html"):
        html = Path(app.outdir, page).read_text()
        assert "TAKEN_BRANCH" in html, page
        assert "SKIPPED_" not in html, page
    need_node = SphinxNeedsData(app.env).get_need_node("R_HOST")
    assert need_node is not None
    assert list(need_node.findall(IfChainMarker)) == []
