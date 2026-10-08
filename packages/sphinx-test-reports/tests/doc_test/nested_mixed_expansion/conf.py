# The `:auto_suites:` / `:auto_cases:` expansion of `nested_mixed.xml` (#2050): a suite with BOTH direct cases
# and a nested suite, then a second top-level suite named like the nested one.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested expansion"
exclude_patterns = ["_build"]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
