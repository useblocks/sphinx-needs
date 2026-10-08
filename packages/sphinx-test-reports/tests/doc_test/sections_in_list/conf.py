# `test-results` and `test-env` written inside a bullet item (#1959): a project of its own,
# because before the fix this page failed the whole build.
extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report sections in a list"
exclude_patterns = ["_build"]
html_theme = "alabaster"
