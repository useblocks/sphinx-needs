# `sphinx.ext.autosectionlabel` over the sections `test-results` generates (#1959): they are
# sections like any other, so it labels them; the test toggles the document prefix.
extensions = ["sphinx_needs", "sphinx_test_reports", "sphinx.ext.autosectionlabel"]
autosectionlabel_prefix_document = True
master_doc = "index"
project = "test-report sections and autosectionlabel"
exclude_patterns = ["_build"]
html_theme = "alabaster"
