import json
import re
from io import StringIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import myst_parser
import pytest
from sphinx.application import Sphinx
from sphinx.util.parallel import parallel_available

NS = {"html": "http://www.w3.org/1999/xhtml"}


class HtmlNeed:
    """Helper class to parse HTML needs"""

    def __init__(self, need):
        self.need = need

    @property
    def id(self):
        found_id = self.need.find(".//html:a[@class='reference internal']", NS)
        if found_id is None:
            found_id = self.need.find(
                ".//html:a[@class='reference internal']", {"html": ""}
            )
        return found_id.text

    @property
    def title(self):
        found_title = self.need.find(".//html:span[@class='needs_title']", NS)
        if found_title is None:
            found_title = self.need.find(
                ".//html:span[@class='needs_title']", {"html": ""}
            )
        return (
            found_title[0].text if found_title else None
        )  # title[0] aims to the span_data element


def extract_needs_from_html(html):
    # Replace entities, which elementTree can not handle
    html = html.replace("&copy;", "")
    html = html.replace("&amp;", "")

    source = StringIO(html)
    parser = ElementTree.XMLParser(encoding="utf-8")

    # XML knows not nbsp definition, which comes from HTML.
    # So we need to add it
    parser.entity["nbsp"] = " "

    etree = ElementTree.ElementTree()
    document = etree.parse(source, parser=parser)
    tables = document.findall(".//html:table", NS)

    # Sphinx <3.0 start html-code with:
    #    <html xmlns="http://www.w3.org/1999/xhtml">
    # Sphinx >= 3.0 starts it with:
    #    <html>
    # So above search will not work for Sphinx >= 3.0 and we try a new one
    if len(tables) == 0:
        tables = document.findall(".//html:table", {"html": ""})

    return [HtmlNeed(table) for table in tables if "need" in table.get("class", "")]


def chart_images(html: str) -> dict[str, str]:
    """Map the alt text of every chart image of a page to its image file name.

    A chart's alt text is its title, so this is how a test picks one ``needpie``
    or ``needbar`` of a page out of the ``_images`` directory. A chart without a
    title has no alt text and keys on its image path instead, so a fixture whose
    charts must be addressed individually has to give each of them a title.
    """
    return dict(re.findall(r'<img alt="([^"]*)"[^>]*src="_images/([^"]*)"', html))


def pie_slice_counts(svg: str) -> list[int]:
    """The absolute value every slice of a pie chart reports, in content order.

    Matplotlib draws text as glyph paths, but writes the string itself as an XML
    comment beside them, which is the only readable trace a label leaves. A pie
    writes each slice's value as its own ``(N)`` comment, from the second line of
    the ``percent\n(absolute)`` label that ``label_calc`` builds.

    A slice below 5% -- a zero one included -- has that label hidden, and the
    directive then switches the legend on and appends ``percent (absolute)`` to
    every legend entry. Only that enriched legend is read instead, and only when
    it is there: a legend the author asked for with ``:legend:`` carries bare
    labels and no counts, so the slice labels are still the complete list.
    """
    legend_at = svg.find('<g id="legend_1">')
    if legend_at != -1:
        enriched = [
            int(match.group(1))
            for comment in re.findall(r"<!-- (.*?) -->", svg[legend_at:])
            if (match := re.search(r" \d+\.\d% \((\d+)\)$", comment))
        ]
        if enriched:
            return enriched

    return [
        int(match.group(1))
        for comment in re.findall(r"<!-- (.*?) -->", svg)
        if (match := re.fullmatch(r"\((\d+)\)", comment))
    ]


def bar_sum_labels(svg: str, title: str) -> list[str]:
    """Every value a ``:show_sum:`` bar chart writes into its bars, row by row.

    The labels leave the same XML comments as any other matplotlib text. They are
    drawn after both axes -- so after the tick labels, which are the only other
    numbers on the chart -- and before the title, which is the anchor this reads
    up to. The whole list is returned, so a caller that asserts it sees every row
    the chart drew rather than a chosen tail of them.
    """
    axis_at = svg.index('<g id="matplotlib.axis_2"')
    # the axis groups hold only line and text groups, so the next patch group is
    # past the tick labels: the axes spines, drawn just before the bar labels
    bars_at = svg.index('<g id="patch_', axis_at)
    title_at = svg.index(f"<!-- {title} -->", bars_at)
    return re.findall(r"<!-- (.*?) -->", svg[bars_at:title_at])


# Sphinx 7 reads in parallel only above five documents (Sphinx 9 at any count), so the
# ``-j 2`` variant adds four orphan pages: a project of two or more documents is read in
# parallel on every cell
PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


def serial_and_parallel(files: list[tuple[Path, str]]) -> list[Any]:
    """``test_app`` parameters building ``files`` serially, and with ``-j 2``."""
    return [
        pytest.param({"buildername": "html", "files": files}, id="serial"),
        pytest.param(
            {"buildername": "html", "files": [*files, *PADDING], "parallel": 2},
            id="j2",
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        ),
    ]


def needs_by_id(app: Sphinx) -> dict[str, dict[str, Any]]:
    """The needs of the build's ``needs.json``, by id."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf8"))
    return data["versions"][data["current_version"]]["needs"]


# The bodies and helpers of the content-markup tests (``add_need(content=MarkupContent(...))``
# and needimport's parse by ``doctype``): bodies the other parser renders visibly
# differently, so parsing one with the wrong parser shows in the HTML.

MYST_MAJOR = int(myst_parser.__version__.split(".")[0])
"""myst-parser 5 logs its own warnings at ``(env.docname, line)``; 4 at
``(document["source"], line)``, which Sphinx then reads as a docname."""


RST_BODY = [
    "Some *emphasis*, :ref:`host <hostlabel>`, :need:`REQ_HOST`.",
    "",
    ".. note:: An RST note.",
    "",
    ".. _inside_{cell}:",
    "",
    "A labelled paragraph.",
    "",
    ".. nosuchdirective::",
    "",
    ":nosuchrole:`x` and :ref:`nosuchlabel_{cell}`.",
]
"""A reStructuredText body; ``{cell}`` names the cell."""

MYST_BODY = [
    "Some *emphasis*, {ref}`host <hostlabel>`, {need}`REQ_HOST`, a [ref link][lnk].",
    "",
    "```{note}",
    "A MyST note.",
    "```",
    "",
    "(inside_{cell})=",
    "A labelled paragraph.",
    "",
    "```{nosuchdirective}",
    "```",
    "",
    "{nosuchrole}`x` and {ref}`nosuchlabel_{cell}`.",
    "",
    "```{note}",
    "```",
    "",
    "[lnk]: https://example.com",
]
"""A MyST body; the empty ``note`` is an error docutils itself reports."""

BODIES = {".rst": RST_BODY, ".md": MYST_BODY}


def at(body: list[str], start: str) -> int:
    """The 0-based offset of the first body line starting with ``start``."""
    return next(i for i, line in enumerate(body) if line.startswith(start))


def myst_logged(host: str, source: str, line: int) -> str:
    """Where a warning myst-parser logs itself points, for content from ``source``.

    Not the content's file: this version does not rewrite myst-parser's own locations.
    myst-parser 5 logs the page being read, with the content's line; myst-parser 4 logs
    ``document["source"]`` -- the content's file for the duration -- which Sphinx reads
    as a docname and gives the ``.rst`` suffix (the documented first-slice defect).
    """
    if MYST_MAJOR >= 5:
        return f"<srcdir>/{host}:{line}"
    return f"<srcdir>/{source}.rst:{line}"


def html(app: Sphinx, page: str) -> str:
    return Path(app.outdir, page).read_text(encoding="utf-8")


def need_content_html(app: Sphinx, page: str, need_id: str) -> str:
    """The HTML of the content cell of the need ``need_id``."""
    text = html(app, page)
    start = text.index('<td class="need content"', text.index(f'id="{need_id}"'))
    return text[start : text.index("</td>", start)]


def line_of(page: list[str], text: str) -> int:
    """The 1-based line of the first page line containing ``text``."""
    return next(i for i, line in enumerate(page, 1) if text in line)
