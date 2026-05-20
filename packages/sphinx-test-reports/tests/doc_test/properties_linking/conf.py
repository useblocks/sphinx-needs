import os
import sys

import sphinx_needs
from packaging.version import Version

sys.path.insert(0, os.path.abspath("../../sphinxcontrib"))

extensions = ["sphinx_needs", "sphinxcontrib.test_reports"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "REQ_",
        "color": "#BFD8D2",
        "style": "node",
    },
]

source_suffix = ".rst"
master_doc = "index"

project = "properties-linking-test"
copyright = "2026, test"
author = "test"
version = "1.0"
release = "1.0"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"

# Register "verifies" as both a sphinx-needs field and a tr_extra_option
if Version(sphinx_needs.__version__) >= Version("8.0.0"):
    needs_fields = {
        "verifies": {"nullable": True},
        "priority": {"nullable": True},
        "category": {"nullable": True},
    }
else:
    needs_extra_options = ["verifies", "priority", "category"]

tr_extra_options = ["verifies", "priority", "category"]

# Map the "verifies" property to sphinx-needs links
tr_property_link_types = {
    "verifies": "links",
}
