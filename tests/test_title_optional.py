from pathlib import Path

import pytest

from tests.util import extract_needs_from_html

NS = {"html": "http://www.w3.org/1999/xhtml"}


class HtmlNeed:
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
        return (
            title[0].text if title is not None else None
        )  # title[0] aims to the span_data element


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/title_optional"}],
    indirect=True,
)
def test_title_optional_scenarios(test_app):
    app = test_app
    app.build()

    html = Path(app.outdir, "index.html").read_text()
    needs = extract_needs_from_html(html)

    assert needs[0].id == "R_12345"
    assert needs[0].title == "Scenario 1 Title"

    assert needs[1].id is not None
    assert needs[1].title == "Scenario 2 Title"

    assert needs[2].id == "R_12346"
    assert needs[2].title == "Scenario 3 Title"

    assert needs[3].id is not None
    assert needs[3].title == "Scenario 4 Title"

    assert needs[4].id == "R_12347"
    assert needs[4].title is None

    assert needs[5].id is not None
    assert needs[5].title is None

    assert needs[6].id == "R_12348"
    assert needs[6].title == "Title matches this"

    assert needs[7].id is not None
    assert needs[7].title == "Title should match this"

    assert needs[8].id == "R_12349"
    assert needs[8].title == "First sentence is really long so this should be..."

    assert needs[9].id is not None
    assert needs[9].title == "First sentence is really long so this should be..."
