project = "schema-strictness-demo"
copyright = "2026, useblocks"
author = "useblocks"

extensions = ["sphinx_needs", "sphinx_codelinks"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# A strict sphinx-needs schema that forbids any field beyond the core
# id/title/type. sphinx-codelinks registers fields (project/file/directory and
# optionally the url fields) globally, attaching them to every need; those must
# not be reported as "additional" fields when left unpopulated.
needs_schema_definitions_from_json = "schemas.json"

html_theme = "alabaster"
