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
    or ``needbar`` of a page out of the ``_images`` directory.
    """
    return dict(re.findall(r'<img alt="([^"]*)"[^>]*src="_images/([^"]*)"', html))


def pie_slice_counts(svg: str) -> list[int]:
    """The absolute value every slice of a pie chart reports, in content order.

    Matplotlib draws text as glyph paths, but writes the string itself as an XML
    comment beside them, which is the only readable trace a label leaves.

    A slice below 5% -- a zero one included -- has its own label hidden and is
    listed in the legend instead, which ``needpie`` then switches on. The legend
    holds every slice, so it is read whenever there is one.
    """
    legend = svg.find('<g id="legend_1">')
    region = svg if legend == -1 else svg[legend:]
    return [
        int(match.group(1))
        for comment in re.findall(r"<!-- (.*?) -->", region)
        if (match := re.search(r"\((\d+)\)$", comment))
    ]


def bar_sum_labels(svg: str, title: str, count: int) -> list[str]:
    """The values a ``:show_sum:`` bar chart writes into its bars, in cell order.

    The labels leave the same XML comments as any other matplotlib text. The bars
    are drawn after both axes and the title after the bars, so the sum labels are
    the ``count`` comments in front of the title, which is asserted as the anchor.
    """
    comments = re.findall(r"<!-- (.*?) -->", svg)
    assert comments[-1] == title, comments
    return comments[-(count + 1) : -1]
