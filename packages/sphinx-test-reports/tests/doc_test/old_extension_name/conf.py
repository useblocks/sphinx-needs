# The PRE-3.0 extension name, on purpose: tests/test_aliases.py builds this project to
# prove the alias still loads the extension, and warns. Every other project names
# `sphinx_test_reports`.
extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

master_doc = "index"
project = "old-extension-name"
exclude_patterns = ["_build"]
html_theme = "alabaster"
