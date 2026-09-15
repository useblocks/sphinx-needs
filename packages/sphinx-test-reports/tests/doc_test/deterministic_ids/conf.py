import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "deterministic-ids-test"
copyright = "2026, test"
author = "test"
version = "1.0"
release = "1.0"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"

# Opt in to source-derived, SCORE-compatible test-case IDs.
tr_deterministic_case_ids = True

# The scheme produces lowercase IDs, which the sphinx-needs default
# ("^[A-Z0-9_]{5,}") rejects. This is the value S-CORE itself uses.
needs_id_regex = "^[A-Za-z0-9_-]{6,}"
