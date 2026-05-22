extensions = ["sphinx_needs"]

needs_id_regex = "^[A-Za-z0-9_-]{5,}"

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "color": "#FEDCD2",
        "style": "node",
    },
]

needs_build_json = True
needs_json_remove_defaults = True
