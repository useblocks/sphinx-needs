from pathlib import Path

import pytest

from tests.util import extract_needs_from_html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/title_from_content"}],
    indirect=True,
)
def test_title_from_content_scenarios(test_app):
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
    assert needs[4].title == "Title is first sentence"

    assert needs[5].id is not None
    assert needs[5].title == "Title should be first sentence"

    # The handling of the ellipses' character varies between Sphinx versions
    # So we're ignoring it in our comparisons.
    assert needs[6].id is not None
    assert needs[6].title == "First sentence will be title, but elided since ..."

    assert needs[7].id == "R_12348"
    assert needs[7].title == "First sentence will be title, but elided since ..."

    assert needs[8].id == "R_12349"
    assert needs[8].title == "Title matches this"

    assert needs[9].id is not None
    assert needs[9].title == "Title should match this"

    assert needs[10].id == "R_12350"
    assert needs[10].title == "First sentence is really long so this should be..."

    assert needs[11].id is not None
    assert needs[11].title == "First sentence is really long so this should be..."
