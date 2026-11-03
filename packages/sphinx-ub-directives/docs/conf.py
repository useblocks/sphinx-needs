"""Sphinx configuration for the sphinx-ub-directives docs."""

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

extensions = [
    "sphinx_design",
    "myst_parser",
    "sphinx.ext.intersphinx",
    # writes `ai_docs_index.json`, the page index ubCode reads (packages/sphinx-ai-index)
    "sphinx_ai_index",
]

# The useblocks look for furo, shared with the repository's other docs sites
# (docs-theme/README.md at the repository root). A copy of these docs outside the
# repository has no such directory, so a build from one falls back to plain furo.
_DOCS_THEME = Path(__file__).resolve().parents[3] / "docs-theme"
if _DOCS_THEME.is_dir():
    sys.path.insert(0, str(_DOCS_THEME))
    extensions.append("ub_docs_theme")

exclude_patterns: list[str] = ["_build"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

html_title = "sphinx-ub-directives"
html_theme = "furo"
html_theme_options = {
    "source_directory": "packages/sphinx-ub-directives/docs/",
}
