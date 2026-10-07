# A user project with its own `tr_report_template`, whose generated test-file sits at
# ONE space of indentation, and a `tr_rootdir` that is not the conf.py directory (the
# absolute form, built from this file's location).
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]

tr_report_template = "one_space_template.txt"
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")

master_doc = "index"
project = "test-report with a custom template and rootdir"
exclude_patterns = ["_build"]
html_theme = "basic"
