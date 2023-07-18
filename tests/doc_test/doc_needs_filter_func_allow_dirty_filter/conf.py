# Configuration file for Sphinx-Needs Documentation.

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# -- General configuration ------------------------------------------------

project = "Useblocks Sphinx-Needs Test"
copyright = "2023, Useblocks GmbH"
author = "Teams Useblocks"
version = "1.0"

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_id_regex = "^[A-Za-z0-9_]*"

needs_types = [
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "usecase", "title": "Use Case", "prefix": "USE_", "color": "#DF744A", "style": "node"},
]

needs_extra_options = ["ti", "tcl"]

needs_extra_links = [
    {
        "option": "features",
        "incoming": "featured by",
        "outgoing": "features",
        "copy": False,
        "style": "#Gold",
        "style_part": "#Gold",
    },
]

needs_allow_unsafe_filters = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# Doc info
source_suffix = ".rst"
master_doc = "index"
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "alabaster"
