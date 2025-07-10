# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from datetime import datetime
from pathlib import Path
import tomllib

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
]

# exclude_patterns = []
templates_path = ["_templates"]
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
html_favicon = "source/_static/favicon.ico"
html_static_path = ["source/_static"]

html_theme_options = {
    "sidebar_hide_name": True,
    "top_of_page_buttons": ["view", "edit"],
    "source_repository": "https://github.com/useblocks/sphinx-codelinks",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "light_logo": "sphinx-codelinks-logo_dark.svg",
    "dark_logo": "sphinx-codelinks-logo_light.svg",
}
html_css_files = ["furo.css"]

src_trace_config_from_toml = "./src_trace.toml"
