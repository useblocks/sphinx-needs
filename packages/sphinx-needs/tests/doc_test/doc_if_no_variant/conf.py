project = "needs_if_no_variant"
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

# No needs_variant_data configured
