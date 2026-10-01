project = "needs_choose_test"
version = "0.1.0"
extensions = ["sphinx_needs"]

suppress_warnings = ["epub.unknown_project_files"]
# the files `.. include::` reads are not documents of their own
exclude_patterns = ["_build", "*.txt"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
    },
]

needs_variant_data = {
    "arch": "abc",
    "debug": True,
    "count": 5,
}
