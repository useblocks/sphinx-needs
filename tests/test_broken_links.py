import pytest


@pytest.mark.parametrize("buildername, srcdir", [("html", "doc_test/broken_links")])
def test_doc_build_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()

    warning = app._warning
    # stdout warnings
    warnings = warning.getvalue()

    assert "Needs: linked need BROKEN_LINK not found" in warnings
