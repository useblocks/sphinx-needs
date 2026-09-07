import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_in_heading"}],
    indirect=True,
)
def test_role_need_in_heading(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    # The heading should contain a reference to the need
    heading = re.search(r"<h2>(.*?)</h2>", html, re.DOTALL)
    assert heading is not None, "Expected an h2 heading in the output"
    heading_content = heading.group(1)

    # The heading should contain a link to the need with the resolved title
    assert "REQ_001" in heading_content
    assert "My Requirement" in heading_content
