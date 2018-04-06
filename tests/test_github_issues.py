from sphinx_testing import with_app
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3
from subprocess import check_output, STDOUT

# @with_app(buildername='html', srcdir='doc_test/doc_github_issue_21')
# def test_doc_github_21(app, status, warning):
#     """
#     https://github.com/useblocks/sphinxcontrib-needs/issues/21
#     """
#     #app.builder.build_all()
#     app.build()
#     html = (app.outdir / 'index.html').read_text()
#     assert '<h1>Some needs' in html
#     assert 'OWN_ID_123' in html


@with_app(buildername='html', srcdir='doc_test/doc_github_issue_44', warningiserror=False, verbosity=2)
def test_doc_github_44(app, status, warning):
    """
    https://github.com/useblocks/sphinxcontrib-needs/issues/44
    """
    # Ugly workaround to get the sphinx build output.
    # I have no glue how to get it from an app.build(), because stdout redirecting does not work. Maybe because
    # nosetest is doing something similar for each test.
    # So we call the needed command directly, but still use the sphinx_testing app to create the outdir for us.
    output = str(check_output(["sphinx-build", "-a", "-E", "-b", "html", app.srcdir, app.outdir],
                              stderr=STDOUT, universal_newlines=True))
    # app.build() Uncomment, if build should stop on breakpoints
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>Github Issue 44 test' in html
    assert 'Test 1' in html
    assert 'Test 2' in html
    assert 'Test 3' in html

    assert "Needs: linked need test_3 not found" not in output
    assert "Needs: linked need test_123_broken not found" in output


