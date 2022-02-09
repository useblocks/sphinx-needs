import pytest


@pytest.mark.parametrize("create_app", [{"buildername": "needs", "srcdir": "doc_test/doc_needsfile"}], indirect=True)
def test_doc_build_html(create_app):
    app = create_app
    app.build()
