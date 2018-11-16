import re

from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


@with_app(buildername='html', srcdir='doc_test/multiple_link_backs')
def test_multiple_link_backs(app, status, warning):
    app.builder.build_all()
    html = Path(app.outdir, 'index.html').read_text()

    links_to = re.findall("#R_12346", html)
    assert len(links_to) == 3
