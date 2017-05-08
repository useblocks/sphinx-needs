from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/filter_doc')
def test_filter_build_html(app, status, warning):
    #app.builder.build_all()
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert 'story_a' in html
    assert 'story_b' not in html
    assert 'story_a_b' in html

    assert 'req_a' not in html
    assert 'req_b' not in html
    assert 'req_c' in html

    html_2 = (app.outdir / 'filter_tags_or.html').read_text()
    assert 'req_a' in html_2
    assert 'req_b' in html_2
    assert 'req_c' in html_2

    html_3 = (app.outdir / 'filter_all.html').read_text()
    assert 'req_a_not' not in html_3
    assert 'req_b_found' in html_3
    assert 'req_c_not' not in html_3
    assert 'req_d_found' in html_3
    assert 'story_1_not' not in html_3
    assert 'story_2_found' in html_3
