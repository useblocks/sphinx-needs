from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_syntax_doc")])
def test_doc_broken_syntax(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()

    warning = app._warning
    warnings = warning.getvalue()

    assert 'invalid option value: (option: "links"; value: None)' in warnings
    assert 'invalid option value: (option: "tags"; value: None)' in warnings

    assert "SP_TOO_001" not in html
    assert "SP_TOO_002" not in html
    assert "SP_TOO_003" not in html
