import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

# -- General configuration ------------------------------------------------

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "test-report schema strictness (status)"
copyright = "2024, team useblocks"
author = "team useblocks"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Load a strict sphinx-needs schema. Unlike the sibling ``schema_strictness``
# fixture, this one *evaluates* a field in the local schema: ``status`` is
# constrained to a fixed value (see schemas.json). The sphinx-test-reports
# fields are still left unpopulated to confirm they remain ignored.
needs_schema_definitions_from_json = "schemas.json"

# -- Options for HTML output ----------------------------------------------

html_theme = "alabaster"
