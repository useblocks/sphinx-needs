import pytest


@pytest.mark.jstest
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/variant_doc",
            "tags": ["tag_a"],
            "spec_pattern": "js_test/js-test-sn-collapse-button.cy.js",
        }
    ],
    indirect=True,
)
def test_collapse_button_in_docs(test_app):
    """Check if the Sphinx-Needs collapse button works in the provided documentation source."""
    app = test_app
    app.build()

    # Call `app.test_js()` to run the JS test for a particular specPattern
    js_test_result = app.test_js()

    # Check the return code and stdout
    assert js_test_result["returncode"] == 0
    assert "All specs passed!" in js_test_result["stdout"].decode("utf-8")
