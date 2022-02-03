import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/multiple_link_backs")])
def test_multiple_link_backs(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()

    links_to = re.findall("#R_12346", html)
    assert len(links_to) == 3
