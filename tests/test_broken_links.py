import sys
from io import StringIO

from sphinx_testing import with_app

# Currently not working as I'm not able to get the complete console output of a sphinx build.


@with_app(buildername='html', srcdir='doc_test/broken_links')
def test_doc_build_html(app, status, warning):
    backup = sys.stdout
    sys.stderr = StringIO()

    app.build()
    sys.stderr.flush()
    out = sys.stderr.getvalue()
    try:
        # Need to put is inside a try except statement, as the tests thorws following error using tox:
        # AttributeError: 'Tee' object has no attribute 'close'
        sys.stdout.close()  # close the stream
        sys.stdout = backup  # restore original stdout
    except Exception:
        pass

    # assert "Needs: linked need" in out
