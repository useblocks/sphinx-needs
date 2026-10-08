# Two nested suites of one name under one parent (#2050): the suite-id collision still raises
# (#2052 will turn it into a warning and update this project's test).
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested twins"
exclude_patterns = ["_build"]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
