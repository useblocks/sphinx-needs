extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
]

# needgantt requires both of its value options to be numeric fields
needs_fields = {
    "duration": {"schema": {"type": "integer"}, "nullable": True},
    "completion": {"schema": {"type": "integer"}, "nullable": True},
}
