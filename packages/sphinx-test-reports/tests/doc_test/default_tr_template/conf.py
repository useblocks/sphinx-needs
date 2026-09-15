# A `test-report` build that leaves `tr_report_template` at its default, so the
# template this package ships is the one that renders. Every other
# `test-report` fixture points the option at a template of its own, which left
# the shipped template -- and the `result` value its filters name -- uncovered.
extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

master_doc = "index"
html_theme = "basic"
