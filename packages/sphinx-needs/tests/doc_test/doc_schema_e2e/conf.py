project = "basic test"
# copyright = "2024, basic test"
# author = "basic test"

extensions = ["sphinx_needs"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

needs_from_toml = "ubproject.toml"

html_theme = "alabaster"
