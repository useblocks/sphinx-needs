import pytest

from sphinx_needs_testkit import build_warnings

#: the projects' ``tests`` link type copies into ``links``, which is deprecated
DEPRECATED_COPY = (
    "WARNING: needs_links['tests'] sets 'copy = true', which is deprecated and will be "
    "removed in sphinx-needs 10.0; declare a link type deriving the union instead, e.g. "
    'derive = {kind = "union", fields = ["links", "tests"]}, and read it where the '
    "copies in links were read [needs.deprecated]"
)


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
        DEPRECATED_COPY,
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
        DEPRECATED_COPY,
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

    # check there are no warnings but the deprecated copy
    assert build_warnings(app) == [DEPRECATED_COPY]
