# -*- coding: utf-8 -*-

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/unicode_support')  # , warningiserror=True)
def test_unicode_html(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert u'Загрузка' in html
    assert u'Aufräumlösung' in html
