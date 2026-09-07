project = "needs_if_test"
version = "0.1.0"
extensions = ["sphinx_needs"]

suppress_warnings = ["epub.unknown_project_files"]

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
    "build": {"opt": 2, "features": ["f1", "f2"]},
}
