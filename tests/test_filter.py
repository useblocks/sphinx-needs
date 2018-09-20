try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/filter_doc')  # , warningiserror=True)
def test_filter_build_html(app, status, warning):
    app.build()
    html = Path(app.outdir, 'index.html').read_text()
    assert 'story_a_1' in html
    assert 'story_b_1' not in html
    assert 'story_a_b_1' in html

    assert 'req_a_1' not in html
    assert 'req_b_1' not in html
    assert 'req_c_1' in html

    html_2 = Path(app.outdir, 'filter_tags_or.html').read_text()
    assert 'req_a' in html_2
    assert 'req_b' in html_2
    assert 'req_c' in html_2

    html_3 = Path(app.outdir, 'filter_all.html').read_text()
    assert 'req_a_not' not in html_3
    assert 'req_b_found' in html_3
    assert 'req_c_not' not in html_3
    assert 'req_d_found' in html_3
    assert 'story_1_not' not in html_3
    assert 'story_2_found' in html_3
    assert 'my_test' in html_3

    html_4 = Path(app.outdir, 'filter_search.html').read_text()
    assert 'search_a' in html_4
    assert 'search_b' not in html_4
    assert 'search_c' not in html_4
    assert 'search_d' not in html_4
    assert 'search_2_1' in html_4
    assert 'search_2_2' in html_4
    assert 'test_email' in html_4
