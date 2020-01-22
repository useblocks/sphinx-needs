# -*- coding: utf-8 -*-
import sys
from sphinx_testing import with_app
from xml.etree import ElementTree
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

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


@with_app(buildername='html', srcdir='doc_test/title_optional')
def test_title_optional_scenarios(app, status, warning):
    app.build()

    html = Path(app.outdir, 'index.html').read_text()
    needs = extract_needs_from_html(html)

    assert needs[0].id == 'R_12345'
    assert needs[0].title == 'Scenario 1 Title'

    assert needs[1].id is not None
    assert needs[1].title == 'Scenario 2 Title'

    assert needs[2].id == 'R_12346'
    assert needs[2].title == 'Scenario 3 Title'

    assert needs[3].id is not None
    assert needs[3].title == 'Scenario 4 Title'

    assert needs[4].id == 'R_12347'
    assert needs[4].title is None

    assert needs[5].id is not None
    assert needs[5].title is None

    assert needs[6].id == 'R_12348'
    assert needs[6].title == 'Title matches this'

    assert needs[7].id is not None
    assert needs[7].title == 'Title should match this'

    assert needs[8].id == 'R_12349'
    assert needs[8].title == 'First sentence is really long so this should be...'

    assert needs[9].id is not None
    assert needs[9].title == 'First sentence is really long so this should be...'
