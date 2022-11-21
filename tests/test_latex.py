from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "latex", "srcdir": "doc_test/doc_basic_latex", "warning": True, "parallel": 2}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    tex = Path(app.outdir, "basictest.tex").read_text(encoding="utf8")

    assert "Test story" in tex  # PlantUML got generated
