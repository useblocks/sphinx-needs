# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "Test Env"
copyright = "2022, open-needs community"
author = "open-needs community"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx_needs"]

needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "S_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "I_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "T_", "color": "#DCB239", "style": "node"},
    # Kept for backwards compatibility
    {"directive": "need", "title": "Need", "prefix": "N_", "color": "#9856a5", "style": "node"},
]

needs_build_json = True

# custom IDE directive snippets per need_type
needs_ide_directive_snippets = {
    "req": """\
.. req:: REQ Example
   :id: ID
   :status:
   :custom_option_1:

   random content.
""",
    "test": """\
.. test:: Test Title
   :id: TEST_
   :status: open
   :custom_option: something

   test directive content.
""",
}

# Or maybe define like this
# needs_ide_directive_snippets = [
#     {
#         "need_type": "req",
#         "title": "My Custom req title",
#         "options": {
#             "id": "REQ_",
#             "status": "open",
#         },
#         "content": "My req snippets content."
#     },
# ]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "alabaster"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ["_static"]
