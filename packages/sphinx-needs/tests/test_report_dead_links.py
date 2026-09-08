import pytest

from sphinx_needs_testkit import assert_no_warnings, build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_true"}],
    indirect=True,
)
def test_needs_dead_links_warnings(test_app):
    app = test_app
    app.build()

    # check there are expected warnings
    emitted = build_warnings(app)
    expected_warnings = [
        "<srcdir>/index.rst:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
    ]

    assert emitted == expected_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_report_dead_links_true"}],
    indirect=True,
)
def test_needs_dead_links_warnings_needs_builder(test_app):
    app = test_app
    app.build()

    # check there are expected warnings
    emitted = build_warnings(app)
    expected_warnings = [
        "<srcdir>/index.rst:17: WARNING: Need 'REQ_004' has unknown outgoing link 'ANOTHER_DEAD_LINK' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'tests' [needs.link_outgoing]",
        "<srcdir>/index.rst:45: WARNING: Need 'TEST_004' has unknown outgoing link 'REQ_005.invalid' in field 'links' [needs.link_outgoing]",
    ]

    assert emitted == expected_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_report_dead_links_false"}],
    indirect=True,
)
def test_needs_dead_links_suppress_warnings(test_app):
    app = test_app
    app.build()

    # check there are no warnings
    assert_no_warnings(app)
