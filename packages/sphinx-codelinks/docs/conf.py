# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
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
    # writes `ai_docs_index.json`, the page index ubCode reads (packages/sphinx-ai-index)
    "sphinx_ai_index",
]

# the useblocks look for furo, shared with the repository's other docs sites
# (docs-theme/README.md at the repository root). A copy of these docs outside the
# repository has no such directory, so a build from one falls back to plain furo
_DOCS_THEME = Path(__file__).resolve().parents[3] / "docs-theme"
if _DOCS_THEME.is_dir():
    sys.path.insert(0, str(_DOCS_THEME))
    extensions.append("ub_docs_theme")

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

# the sidebar, the view/edit buttons, the repository they point into and the shared
# stylesheet come from `ub_docs_theme` above; what is here is this site's own
html_theme_options = {
    # the path to these sources inside the monorepo: furo's "view"/"edit" buttons build
    # `<repo>/blob|edit/<branch>/<directory><page>`
    "source_directory": "packages/sphinx-codelinks/docs/",
    "light_logo": "sphinx-codelinks-logo_light.svg",
    "dark_logo": "sphinx-codelinks-logo_dark.svg",
}
html_css_files = ["furo.css"]

# Sphinx-Needs configuration
needs_from_toml = "ubproject.toml"

# Sphinx-CodeLinks: the [codelinks] table of the same ubproject.toml is loaded
# by default (src_trace_config_from_toml defaults to "ubproject.toml")
