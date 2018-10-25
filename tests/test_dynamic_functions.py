import re
from sphinx_testing import with_app
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


@with_app(buildername='html', srcdir='doc_test/doc_dynamic_functions')
def test_doc_dynamic_functions(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'This is id SP_TOO_001' in html

    assert sum(1 for _ in re.finditer('<span class="needs-tag test2">test2</span>', html)) == 2
    assert sum(1 for _ in re.finditer('<span class="needs-tag test">test</span>', html)) == 2
    assert sum(1 for _ in re.finditer('<span class="needs-tag my_tag">my_tag</span>', html)) == 1

    assert 'Test output of need TEST_3. args:' in html


@with_app(buildername='html', srcdir='doc_test/doc_df_calc_sum')
def test_doc_df_calc_sum(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert '43210' in html  # all hours
    assert '3210' in html  # hours of linked needs
    assert '210' in html  # hours of filtered needs


@with_app(buildername='html', srcdir='doc_test/doc_df_check_linked_values')
def test_doc_df_calc_sum(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'all_good' in html
    assert 'all_bad' not in html
    assert 'all_awesome' in html
