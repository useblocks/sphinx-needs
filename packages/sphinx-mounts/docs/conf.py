"""Sphinx configuration for the sphinx-mounts docs."""

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

extensions = [
    "sphinx_design",
    "myst_parser",
    "sphinx.ext.intersphinx",
]

exclude_patterns: list[str] = []
templates_path = ["source/_static/_templates/furo"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

html_title = "sphinx-mounts"
html_theme = "furo"
html_static_path = ["source/_static"]
html_favicon = "source/_static/favicon.svg"
html_theme_options = {
    # The logo carries the project name, so hide the textual title.
    "sidebar_hide_name": True,
    "light_logo": "sphinx-mounts-logo_light.svg",
    "dark_logo": "sphinx-mounts-logo_dark.svg",
    "source_repository": "https://github.com/useblocks/sphinx-mounts",
    "source_branch": "main",
    "source_directory": "docs/source/",
}
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
html_context = {"repository": "useblocks/sphinx-mounts"}
html_css_files = ["furo.css"]

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
