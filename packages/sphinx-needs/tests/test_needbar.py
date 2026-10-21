import re
from pathlib import Path

import pytest

from sphinx_needs_testkit import assert_no_warnings, build_warnings
from tests.util import bar_sum_labels, chart_images


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

    assert_no_warnings(app)

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


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needbar_from_data",
        }
    ],
    indirect=True,
)
def test_chart_element_ids_are_unique_per_chart(test_app):
    """Charts of one document must not share matplotlib's internal element ids.

    The ids are salted with each chart's own file name, so that they stay stable
    between builds without becoming equal across charts. A single constant salt
    would satisfy reproducibility just as well, and the four bars of this document
    would then all refer to the same clip path -- harmless while each SVG is a
    separate file, but not once a consumer inlines them into one page.

    This fixture is used because its four bars are close enough in shape that a
    shared salt really does collapse their ids onto one value.
    """
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    images = dict(re.findall(r'<img alt="([^"]*)"[^>]*src="_images/([^"]*)"', html))
    assert len(images) == 4

    id_sets = {
        alt: set(
            re.findall(
                r"url\(#([^)]+)\)", Path(app.outdir, "_images", name).read_text()
            )
        )
        for alt, name in images.items()
    }
    assert all(id_sets.values()), "no chart referenced an element id"

    seen: set[str] = set()
    for ids in id_sets.values():
        assert not (seen & ids), (
            f"element id shared between charts: {sorted(seen & ids)}"
        )
        seen |= ids


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), 'extensions = ["sphinx_needs"]\n'),
                (
                    Path("index.rst"),
                    "Bar\n===\n\n"
                    ".. req:: One\n   :id: REQ_1\n   :tags: a\n\n"
                    ".. req:: Two\n   :id: REQ_2\n   :tags: b\n\n"
                    ".. req:: Three\n   :id: REQ_3\n\n"
                    ".. needbar:: cells\n   :show_sum:\n\n   10,10.5,-5,tags,True\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_cell_is_a_static_value_or_counts_the_needs_it_is_true_for(test_app):
    """A non-negative integer is a static value; anything else is a filter, which counts
    the needs it is true for (``tags``: the two with tags, ``True``: all three), and a
    filter that is any other constant (``10.5``, ``-5``) says nothing about a need: it is
    warned about and counts zero."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:15: WARNING: Filter {cell!r} not valid. Error: it is a "
        "constant, which says nothing about a need, so it selects none. [needs.filter]"
        for cell in ("10.5", "-5")
    ]
    images = chart_images(Path(app.outdir, "index.html").read_text())
    svg = Path(app.outdir, "_images", images["cells"]).read_text()
    assert bar_sum_labels(svg, "cells") == ["10", "0", "0", "2", "3"]
