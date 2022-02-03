import pytest


@pytest.mark.parametrize("buildername, srcdir", [("needs", "doc_test/doc_needsfile")])
def test_doc_build_html(create_app, buildername):
    make_app = create_app[0]
    srcdir = create_app[1]
    app = make_app(buildername, srcdir=srcdir)

    app.build()
