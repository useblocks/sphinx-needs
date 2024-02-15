from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_syntax_doc"}],
    indirect=True,
)
def test_doc_broken_syntax(test_app):
    app = test_app

    app.build()
    html = Path(app.outdir, "index.html").read_text()

    warning = app._warning
    warnings = warning.getvalue()

    assert 'invalid option value: (option: "links"; value: None)' in warnings
    assert 'invalid option value: (option: "tags"; value: None)' in warnings

    assert "SP_TOO_001" not in html
    assert "SP_TOO_002" not in html
    assert "SP_TOO_003" not in html
