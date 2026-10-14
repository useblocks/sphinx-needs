"""Sphinx configuration for the sphinx-mounts docs."""

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

exclude_patterns: list[str] = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

html_title = "sphinx-mounts"
html_theme = "furo"
html_static_path = ["_static"]
html_favicon = "_static/favicon.svg"
# The sidebar, the view/edit buttons, the repository they point into and the stylesheet
# come from `ub_docs_theme` above (which also hides the textual title: the logo carries
# the project name). What is here is this site's own.
html_theme_options = {
    "light_logo": "sphinx-mounts-logo_light.svg",
    "dark_logo": "sphinx-mounts-logo_dark.svg",
    "source_directory": "packages/sphinx-mounts/docs/",
}

# Named hyperlink targets for sibling useblocks projects. Defined once
# here (appended to every RST source via ``rst_epilog``) so the URLs are
# not duplicated across the docs. Use them in RST as ``\`Sphinx-Needs\`_``,
# ``\`ubCode\`_``, etc.
rst_epilog = """
.. _Sphinx-Needs: https://sphinx-needs.readthedocs.io/
.. _sphinx-codelinks: https://github.com/useblocks/sphinx-codelinks
.. _ubCode: https://ubcode.useblocks.com/
.. _bazel-drives-sphinx: https://github.com/useblocks/bazel-drives-sphinx
.. _needs-config-writer: https://needs-config-writer.useblocks.com/
.. _sphinx-collections: https://sphinx-collections.readthedocs.io/
.. _useblocks: https://useblocks.com/
"""
