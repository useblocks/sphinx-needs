from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_warnings")  # , warningiserror=True)
def test_needs_warnings(app, status, warning):
    app.build()

    # stdout warnings
    warnings = warning.getvalue()

    # check multiple warning registration
    assert 'invalid_status for "warnings" is already registered.' in warnings

    # check warnings contents
    assert "WARNING: invalid_status: failed" in warnings
    assert "failed needs: 2 (SP_TOO_001, US_63252)" in warnings
    assert "used filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3']" in warnings

    # check needs warning from custom defined filter code
    assert "failed needs: 1 (TC_001)" in warnings
    assert "used filter: my_custom_warning_check" in warnings

    # negative test to check needs warning if need passed the warnings-check
    assert "TC_NEG_001" not in warnings

    # Check for warning registered via config api
    assert "WARNING: api_warning_filter: failed" in warnings
    assert "WARNING: api_warning_func: failed" in warnings
