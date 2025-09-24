project = "Docs modeling example"

extensions = ["sphinx_needs"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

needs_from_toml = "ubproject.toml"

html_theme = "alabaster"
