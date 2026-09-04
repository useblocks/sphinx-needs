import json
import re
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/add_sections_sigs",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_section_is_usable_in_filters(test_app: SphinxTestApp, snapshot):
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    assert needs_data["versions"][""]["needs"] == snapshot

    html = Path(app.outdir, "index.html").read_text()

    tables = re.findall("(<table .*?</table>)", html, re.DOTALL)
    assert len(tables) == 5

    # All requirements should be in first table
    assert "R_12345" in tables[3]
    assert "First Section" in tables[3]
    assert "R_12346" in tables[3]
    assert "Second Section" in tables[3]

    # Only requirements from the first section should be in table 2
    assert "R_12345" in tables[4]
    assert "First Section" in tables[4]
    assert "R_12346" not in tables[4]
    assert "Second Section" not in tables[4]
