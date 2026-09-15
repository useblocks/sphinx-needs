import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

# -- General configuration ------------------------------------------------

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "test-report schema strictness"
copyright = "2024, team useblocks"
author = "team useblocks"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Load a strict sphinx-needs schema that forbids any field beyond the core
# id/title/type (see schemas.json). sphinx-test-reports registers a lot of
# extra fields (file, suite, passed, ...) via the sphinx-needs field API; this
# project deliberately leaves them unpopulated to make sure they are not
# wrongly reported as "additional" fields.
needs_schema_definitions_from_json = "schemas.json"

# -- Options for HTML output ----------------------------------------------

html_theme = "alabaster"
