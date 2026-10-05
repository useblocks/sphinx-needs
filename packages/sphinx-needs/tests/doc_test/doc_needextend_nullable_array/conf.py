extensions = ["sphinx_needs"]

needs_build_json = True
needs_id_regex = "^[A-Za-z0-9_]*"
needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
]
needs_fields = {
    "targets": {
        "schema": {"type": "array", "items": {"type": "string"}},
        "nullable": True,
    },
}
