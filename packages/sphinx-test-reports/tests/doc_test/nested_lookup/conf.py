# The `:suite:` lookup of a hand-written `test-suite` / `test-case` over nested suites (#2050):
# the first top-level suite of the name, else the first of that name at any depth in pre-order.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested lookup"
exclude_patterns = ["_build"]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
