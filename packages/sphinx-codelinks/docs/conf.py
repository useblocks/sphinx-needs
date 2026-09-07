# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import tomllib
from datetime import datetime
from pathlib import Path

_project_data = tomllib.loads(
    (Path(__file__).parent.parent / "pyproject.toml").read_text("utf8")
)["project"]

project = _project_data["name"]
author = _project_data["authors"][0]["name"]
copyright = f"{datetime.now().year}, {author}"
version = release = _project_data["version"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx_design",
    "sphinx_needs",
    "sphinx_codelinks",
    "sphinx.ext.intersphinx",
    "sphinx_code_tabs",
    "sphinxcontrib.typer",
    "sphinxcontrib.video",
]

# The source directory IS this directory, so the build output and the shared ubCode project
# file live inside it and have to be kept out of the document set. (`conf.py` itself is
# excluded by Sphinx.)
exclude_patterns = ["_build", "ubproject.toml", "Thumbs.db", ".DS_Store"]
show_warning_types = True

todo_include_todos = True

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {
    "needs": ("https://sphinx-needs.readthedocs.io/en/latest/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_title = "CodeLinks"
html_theme = "furo"
# original source is in ubdocs repo at docs/developer_handbook/design/files/ubcode_favicon/favicon.ico
html_favicon = "_static/favicon.ico"
html_static_path = ["_static"]

html_theme_options = {
    "sidebar_hide_name": True,
    "top_of_page_buttons": ["view", "edit"],
    # the monorepo this package lives in, and the path to these sources inside it:
    # furo's "view"/"edit" buttons build `<repo>/blob|edit/<branch>/<directory><page>`
    "source_repository": "https://github.com/useblocks/sphinx-needs",
    "source_branch": "master",
    "source_directory": "packages/sphinx-codelinks/docs/",
    "light_logo": "sphinx-codelinks-logo_light.svg",
    "dark_logo": "sphinx-codelinks-logo_dark.svg",
}
templates_path = ["_static/_templates/furo"]
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
        "side-github.html",
        "sidebar/variant-selector.html",
    ]
}
html_context = {"repository": "useblocks/sphinx-needs"}
html_css_files = ["furo.css"]

# Sphinx-Needs configuration
needs_from_toml = "ubproject.toml"

# Sphinx-CodeLinks: the [codelinks] table of the same ubproject.toml is loaded
# by default (src_trace_config_from_toml defaults to "ubproject.toml")
