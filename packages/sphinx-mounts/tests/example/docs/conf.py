"""Minimal host project for the sphinx-mounts example.

All mount declarations live in ``ubproject.toml`` next to this file;
``conf.py`` registers ``sphinx_mounts`` plus the parsers/renderers the
mounted bundles use: ``myst_parser`` for the Markdown bundle, and
graphviz / plantuml / mermaid for the api-foo "directives showcase"
page.
"""

project = "sphinx-mounts example"
author = "useblocks"
extensions = [
    "sphinx_mounts",
    "myst_parser",
    "sphinx.ext.graphviz",
    "sphinxcontrib.plantuml",
    "sphinxcontrib.mermaid",
]
exclude_patterns: list[str] = ["_build"]
master_doc = "index"

# Mermaid renders client-side ("raw"), so the build needs no ``mmdc``
# binary. Graphviz and PlantUML do shell out at build time — to ``dot``
# and ``plantuml`` (Java) respectively — so building this example
# requires those on PATH (see this directory's README).
mermaid_output_format = "raw"
