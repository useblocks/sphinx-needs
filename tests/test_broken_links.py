import pytest


@pytest.mark.parametrize("create_app", [{"buildername": "html", "srcdir": "doc_test/broken_links"}], indirect=True)
def test_doc_build_html(create_app):
    app = create_app
    app.build()

    warning = app._warning
    # stdout warnings
    warnings = warning.getvalue()

    assert "Needs: linked need BROKEN_LINK not found" in warnings
