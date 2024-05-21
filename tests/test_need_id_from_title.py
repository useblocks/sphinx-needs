from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_need_id_from_title"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html

    # check need_id_length
    need_id_length = app.config.needs_id_length
    assert need_id_length == 20

    # check generated id from title for need directive story
    assert "US_A_STORY_TITLE_2FD447" in html
    assert "US_CONTENT_ID_TEST_A313" in html

    # check need directive story prefix
    needs_types = app.config.needs_types
    need_directive_story_prefix = ""
    for need_type in needs_types:
        if need_type["directive"] == "story":
            need_directive_story_prefix = need_type["prefix"]

    assert len("US_A_STORY_TITLE_2FD447") == need_id_length + len(
        need_directive_story_prefix
    )
    assert len("US_CONTENT_ID_TEST_A313") == need_id_length + len(
        need_directive_story_prefix
    )
