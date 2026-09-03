import re
from io import StringIO
from xml.etree import ElementTree

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
