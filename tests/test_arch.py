from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/arch_doc"}], indirect=True
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")

    assert "<object data=" in html  # PlantUML got generated
    assert "peter --&gt; max" in html  # First Spec diagram is loaded
    assert "Yehaa &lt;--&gt; Ups" in html  # Second Spec diagram is loaded
    assert "Yehaa --&gt; peter" in html  # Combined diagram is loaded
