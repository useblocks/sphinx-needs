from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_role_need_template"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "ROLE NEED TEMPLATE" in html
    assert (
        "[NEED] [SP_TOO_001] [SP_TOO_001] [SP_TOO_001] [] "
        "[SPEC] [SP_TOO_001] Command line interface (implemented) Specification/spec - test;test2 - SP_TOO_002 -  - "
        "The Tool awesome shall have a command line interface." in html
    )
    assert (
        "[NEED] [IM_TOO_001] [IM_TOO_001] [IM_TOO_001] [] "
        "[IMPL] [IM_TOO_001] Command line implementation (implemented) Implementation/impl -  -  -  - "
        "Implements command line interface." in html
    )
    assert '<em class="xref need">IMPL</em>' in html
    assert (
        "[NEEDPART][SP_TOO_001.cli] [SP_TOO_001.cli] [SP_TOO_001] [cli] "
        "[SPEC] [SP_TOO_001.cli]  Command parser support (implemented) Specification/spec"
        in html
    )
    assert '<em class="xref need"> COMMAND PARSER SUPPORT</em>' in html
