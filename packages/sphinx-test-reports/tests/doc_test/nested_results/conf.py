# `test-results` over nested suites (#2050), and the file need's counters as a control.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested results"
exclude_patterns = ["_build"]
html_theme = "alabaster"
needs_build_json = True
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
