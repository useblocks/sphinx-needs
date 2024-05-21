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
