"""
Tests a more complex documentation project with different Sphinx-Needs features on different builders and in parallel
mode.
"""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": "doc_test/doc_complex"}],
    indirect=True,
)
def test_doc_complex_latex(test_app):
    app = test_app
    app.build()
    tex = Path(app.outdir, "basictest.tex").read_text(encoding="utf8")

    assert "Test story" in tex  # PlantUML got generated


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "singlehtml", "srcdir": "doc_test/doc_complex"}],
    indirect=True,
)
def test_doc_complex_singlehtml(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")

    assert "Test story" in html  # PlantUML got generated
