import os
import sys

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

source_suffix = ".rst"
master_doc = "index"

project = "source-location-renamed-test"
copyright = "2026, test"
author = "test"
version = "1.0"
release = "1.0"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"

# Free up "file"/"line" for the *source* location by renaming the field that
# carries the XML report path (the S-CORE metamodel spells the source location
# verbatim as file/line).
tr_file_option = "report_file"
tr_source_file_option = "file"
tr_source_line_option = "line"
