project = "schema incremental"

extensions = ["sphinx_needs"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

needs_types = [
    {"directive": "spec", "title": "Specification", "prefix": "SPEC_"},
]

needs_schema_definitions_from_json = "schemas.json"

html_theme = "alabaster"
