# The documented `tr_link` usage (docs/functions.rst), on a test-case AND on a test-file.
extensions = ["sphinx_needs", "sphinx_test_reports"]

needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
]

master_doc = "index"
project = "tr_link documented usage"
exclude_patterns = ["_build"]
