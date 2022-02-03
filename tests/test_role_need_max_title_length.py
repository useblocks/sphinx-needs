import os
from pathlib import Path

import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_role_need_max_title_length_unlimited")])
def test_max_title_length_unlimited(create_app, buildername):

    os.environ["MAX_TITLE_LENGTH"] = "-1"

    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert (
        "[SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/doc_role_need_max_title_length")])
def test_max_title_length_10(create_app, buildername):

    os.environ["MAX_TITLE_LENGTH"] = "10"

    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert (
        "[SP_TOO_001] Command... (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )
