import re
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "create_app", [{"buildername": "html", "srcdir": "doc_test/multiple_link_backs"}], indirect=True
)
def test_multiple_link_backs(create_app):
    app = create_app

    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()

    links_to = re.findall("#R_12346", html)
    assert len(links_to) == 3
