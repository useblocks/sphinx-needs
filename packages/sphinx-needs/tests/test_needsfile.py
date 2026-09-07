import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needsfile"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
