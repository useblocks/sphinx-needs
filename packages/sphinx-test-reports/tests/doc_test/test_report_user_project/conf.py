# A USER project rendering `test-report` with the template this package ships:
# `tr_report_template` is left at its default, and the project lives outside the
# package, as every user's does.
extensions = ["sphinx_needs", "sphinx_test_reports"]

master_doc = "index"
project = "test-report in a user project"
exclude_patterns = ["_build"]
html_theme = "basic"
