# A test-file whose authored `:links:` contains its own id as a SUBSTRING (#2114).
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
project = "parent links with a prefix id"
exclude_patterns = ["_build"]
