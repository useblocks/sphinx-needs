import sys
from xml.etree import ElementTree

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

NS = {'html': 'http://www.w3.org/1999/xhtml'}


class HtmlNeed(object):
    """Helper class to parse HTML needs"""

    def __init__(self, need):
        self.need = need

    @property
    def id(self):
        # return self.need.find(".//html:span[@class='needs-id']", NS)._children[0].text
        return self.need.find(".//html:a[@class='reference internal']", NS).text

    @property
    def title(self):
        title = self.need.find(".//html:span[@class='needs_title']", NS)
        return title[0].text if title is not None else None  # title[0] aims to the span_data element


def extract_needs_from_html(html):
    # Replace entities, which elementTree can not handle
    html = html.replace('&copy;', '')
    html = html.replace('&amp;', '')

    if sys.version_info >= (3, 0):
        source = StringIO(html)
        parser = ElementTree.XMLParser(encoding="utf-8")
    else:  # Python 2.x
        source = StringIO(html.encode("utf-8"))
        parser = ElementTree.XMLParser(encoding="utf-8")

    # XML knows not nbsp definition, which comes from HTML.
    # So we need to add it
    parser.entity["nbsp"] = ' '

    etree = ElementTree.ElementTree()
    document = etree.parse(source, parser=parser)
    tables = document.findall(".//html:table", NS)
    return [HtmlNeed(table) for table in tables if 'need' in table.get('class', '')]
