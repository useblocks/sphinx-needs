# `:auto_cases:` without `:auto_suites:` is a configuration error.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report auto cases only"
exclude_patterns = ["_build"]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
