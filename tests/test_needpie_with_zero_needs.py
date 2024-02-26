import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/needpie_with_zero_needs"}],
    indirect=True,
)
def test_needpie_with_zero_needs(test_app):
    app = test_app
    app.build()
