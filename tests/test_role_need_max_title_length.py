import os
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "create_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_max_title_length_unlimited"}],
    indirect=True,
)
def test_max_title_length_unlimited(create_app):

    os.environ["MAX_TITLE_LENGTH"] = "-1"

    app = create_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert (
        "[SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )


@pytest.mark.parametrize(
    "create_app", [{"buildername": "html", "srcdir": "doc_test/doc_role_need_max_title_length"}], indirect=True
)
def test_max_title_length_10(create_app):

    os.environ["MAX_TITLE_LENGTH"] = "10"

    app = create_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert (
        "[SP_TOO_001] Command... (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )
