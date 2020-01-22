import re

from sphinx_testing import with_app

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

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
#     html = (app.outdir, 'index.html').read_text()
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
    html = Path(app.outdir, 'index.html').read_text()
    assert '<h1>Github Issue 44 test' in html
    assert 'Test 1' in html
    assert 'Test 2' in html
    assert 'Test 3' in html

    assert "Needs: linked need test_3 not found" not in output
    assert "Needs: outgoing linked need test_123_broken not found" in output


@with_app(buildername='html', srcdir='doc_test/doc_github_issue_61')
def test_doc_github_61(app, status, warning):
    """
    Test for https://github.com/useblocks/sphinxcontrib-needs/issues/61
    """
    # PlantUML doesn't support entity names with dashes in them, and Needs uses
    # the IDs as entity names, and IDs could have dashes.  To avoid this limitation,
    # Entity names are transformed to replace the dashes with underscores in the entity
    # names.
    # Even if there's an error creating the diagram, there's no way to tell since the
    # error message is embedded in the image itself. The best we can do is make sure
    # the transformed entity names are in the alt text of the image.
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    alt_text = re.findall('<img.*?alt=(.*?)>', html, re.MULTILINE + re.DOTALL)
    assert len(alt_text) == 5
    assert "A-001" in alt_text[4]
    assert "A-002" in alt_text[4]
    assert "A_001" in alt_text[4]
    assert "A_002" in alt_text[4]
