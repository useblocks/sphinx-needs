from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/role_need_doc"}],
    indirect=True,
)
def test_role_need(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    # Normal need ref
    assert (
        '<a class="reference internal" href="#REQ_1" title="REQ_1">'
        '<em class="xref need">Test requirement 1 (REQ_1)</em></a>' in html
    )

    # Imported need ref
    assert (
        '<a class="reference internal" href="#IMP_TEST_01" title="IMP_TEST_01">'
        '<em class="xref need">TEST_01 DESCRIPTION (IMP_TEST_01)</em></a>' in html
    )

    # External need ref
    assert (
        '<a class="external_link reference external" '
        'href="http://my_company.com/docs/v1/index.html#TEST_01">EXT_TEST_01</a>'
        in html
    )
