from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_warnings")  # , warningiserror=True)
def test_needs_warnings(app, status, warning):
    app.build()

    # stdout warnings
    warnings = warning.getvalue()

    # check warnings contents
    assert "WARNING: invalid_status: failed" in warnings
    assert "failed needs: 2 (SP_TOO_001, US_63252)" in warnings
    assert "used filter: status not in ['open', 'closed', 'done']" in warnings
