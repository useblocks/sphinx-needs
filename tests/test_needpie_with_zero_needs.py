from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/needpie_with_zero_needs"}],
    indirect=True,
)
def test_needpie_with_zero_needs(test_app):
    """A pie whose every slice is 0 shows the "no needs" text and writes no image."""
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    assert "No needs passed the filters" in html
    assert "<img" not in html

    # the figure is never written, rather than written and then left unreferenced
    assert list(Path(app.outdir, "_images").glob("*")) == []
