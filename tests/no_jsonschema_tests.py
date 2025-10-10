"""These tests should only be run in an environment without sphinx_needs installed."""

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needsfile"}],
    indirect=True,
)
def test_needsfile(test_app):
    """Test the build fails correctly, if matplotlib is not installed."""
    test_app.build()
