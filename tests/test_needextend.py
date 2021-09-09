from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needextend")
def test_doc_needextend_html(app, status, warning):
    app.build()
    index_html = Path(app.outdir, "index.html").read_text()
    assert "extend_test_003" in index_html

    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#extend_'
        'test_004" title="extend_test_003">extend_test_004</a></span></span></div>' in index_html
    )

    assert (
        '<div class="line">links outgoing: <span class="links"><span><a class="reference internal" href="#extend_'
        'test_003" title="extend_test_006">extend_test_003</a>, <a class="reference internal" href="#extend_'
        'test_004" title="extend_test_006">extend_test_004</a></span></span></div>' in index_html
    )

    page_1__html = Path(app.outdir, "page_1.html").read_text()
    assert (
        '<span class="needs_data_container"><span class="needs_data">tag_1</span><span class="needs_spacer">, '
        '</span><span class="needs_data">new_tag</span><span class="needs_spacer">, '
        '</span><span class="needs_data">another_tag</span></span>' in page_1__html
    )

    # Check needs external filter
    # the external filter value is a string
    assert (
        '<div class="line"><span class="needs_variant"><span class="needs_label">variant: </span>'
        '<span class="needs_data">filtered_current_variant_works</span>' in index_html
    )

    # the external filter value is a function get executed and returns a string object
    assert (
        '<div class="line"><span class="needs_tags"><span class="needs_label">tags: </span>'
        '<span class="needs_data_container"><span class="needs_data">my_tag</span><span class="needs_spacer">, '
        '</span><span class="needs_data">filtered_my_tag_works</span>' in index_html
    )

    # negativ tests for external filter value not a string
    warnings = warning.getvalue()
    assert (
        "WARNING: External filter value: True from needs_filter_data {'current_variant': 'project_x', "
        "'sphinx_tag': 'my_tag', 'variant_wrong_value': True} is not a string." in warnings
    )
