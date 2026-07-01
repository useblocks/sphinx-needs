extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    },
]

# File provides: {"env": "production", "region": "us-east"}
needs_variant_data_file = "variant_data.json"

# Inline overrides env from "production" to "staging"
needs_variant_data = {"env": "staging"}
