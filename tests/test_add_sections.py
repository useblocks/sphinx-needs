import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/add_sections"}], indirect=True)
def test_section_is_usable_in_filters(test_app):
    app = test_app
    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()

    tables = re.findall("(<table .*?</table>)", html, re.DOTALL)
    assert len(tables) == 4

    # All requirements should be in first table
    assert "R_12345" in tables[2]
    assert "First Section" in tables[2]
    assert "R_12346" in tables[2]
    assert "Second Section" in tables[2]

    # Only requirements from the first section should be in table 2
    assert "R_12345" in tables[3]
    assert "First Section" in tables[3]
    assert "R_12346" not in tables[3]
    assert "Second Section" not in tables[3]
