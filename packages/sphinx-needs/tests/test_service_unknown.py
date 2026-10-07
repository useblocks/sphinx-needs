import pytest
from sphinx_needs_testkit import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_service_unknown"}],
    indirect=True,
)
def test_unregistered_service_warns(test_app):
    """A ``needservice`` naming an unregistered service warns instead of crashing."""
    app = test_app
    app.build()

    assert app.statuscode == 0
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Service foo could not be found. "
        "Available services are github-issues, github-prs, github-commits "
        "[needs.directive]"
    ]
