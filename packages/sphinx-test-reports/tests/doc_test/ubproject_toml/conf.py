import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "ubproject-toml-test"
copyright = "2026, test"
author = "test"
version = "1.0"
release = "1.0"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"

# Deliberately clashes with the ubproject.toml value: the declarative file is
# the source of truth, so file_option must end up as "report_file", not
# "confpy_report_file". See tests/test_project_config.py.
tr_file_option = "confpy_report_file"
