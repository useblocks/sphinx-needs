import os
import re
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needbar"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    assert '<img alt="Bar Title"' in html


def _x_tick_labels(svg: str) -> list[str]:
    """Return the x axis tick label texts of a matplotlib SVG.

    Matplotlib draws text as glyph paths, but writes the string itself as an XML
    comment beside them, which is the only readable trace a tick label leaves.
    """
    start = svg.index('<g id="xtick_1">')
    end = svg.index('<g id="matplotlib.axis_2">')
    return re.findall(r"<!-- (.*?) -->", svg[start:end])


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needbar_from_data",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needbar_label_defaults(test_app):
    """Labels not taken from the content are numbered per data cell.

    ``:ylabels: FROM_DATA`` takes the first column of the content, so the default
    xlabels must count the remaining columns. They were derived before that column
    was removed, so a bar with only ``:ylabels: FROM_DATA`` always ended the build
    with "length of xlabels: N+1 is not equal with sum of columns: N".
    """
    app = test_app
    app.build()

    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )
    assert warnings.splitlines() == []

    html = Path(app.outdir, "index.html").read_text()
    images = dict(re.findall(r'<img alt="([^"]*)"[^>]*src="_images/([^"]*)"', html))
    assert set(images) == {"ylabels only", "xlabels only", "both", "no labels"}

    def x_labels(alt: str) -> list[str]:
        return _x_tick_labels(Path(app.outdir, "_images", images[alt]).read_text())

    # derived: one label per data column, numbered from 1
    assert x_labels("ylabels only") == ["1", "2"]
    assert x_labels("no labels") == ["1", "2"]
    # unchanged: taken from the first content row
    assert x_labels("xlabels only") == ["A", "B"]
    assert x_labels("both") == ["A", "B"]
