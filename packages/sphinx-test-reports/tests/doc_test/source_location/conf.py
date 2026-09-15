import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "source-location-test"
copyright = "2026, test"
author = "test"
version = "1.0"
release = "1.0"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"
