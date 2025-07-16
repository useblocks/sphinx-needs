project = "basic test"

extensions = ["sphinx_needs"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

needs_from_toml = "ubproject.toml"
needs_schemas_from_json = "schemas.json"

html_theme = "alabaster"
