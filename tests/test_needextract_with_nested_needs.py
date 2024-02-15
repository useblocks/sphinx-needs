from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/needextract_with_nested_needs"}],
    indirect=True,
)
def test_needextract_with_nested_needs(test_app):
    app = test_app
    app.build()
    needextract_html = Path(app.outdir, "needextract.html").read_text()

    # ensure that the needs exist and that their hrefs point to the correct location
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1" title="SPEC_1">SPEC_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1_1" title="SPEC_1_1">SPEC_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_1" title="SPEC_1_1_1">SPEC_1_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_2" title="SPEC_1_1_2">SPEC_1_1_2</a>'
        in needextract_html
    )
