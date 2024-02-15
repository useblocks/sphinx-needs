"""These tests should only be run in an environment without matplotlib installed."""

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needbar"}],
    indirect=True,
)
def test_needbar(test_app):
    """Test the build fails correctly, if matplotlib is not installed."""
    test_app.build()
    expected = "WARNING: Matplotlib is not installed and required by needbar. Install with `sphinx-needs[plotting]` to use. [needs.mpl]"
    assert expected in test_app._warning.getvalue()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needpie"}],
    indirect=True,
)
def test_needpie(test_app):
    """Test the build fails correctly, if matplotlib is not installed."""
    test_app.build()
    expected = "WARNING: Matplotlib is not installed and required by needpie. Install with `sphinx-needs[plotting]` to use. [needs.mpl]"
    assert expected in test_app._warning.getvalue()
