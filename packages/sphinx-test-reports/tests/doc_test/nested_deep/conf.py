# Nested suites three levels deep (#2050) over `nested_deep.xml`: the expansion's minting order
# and need set, and a hand-written `:suite:` that must find the depth-2 `inner` first.
import os

extensions = ["sphinx_needs", "sphinx_test_reports"]
master_doc = "index"
project = "test-report nested deep"
exclude_patterns = ["_build"]
needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    }
]
tr_rootdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "utils")
