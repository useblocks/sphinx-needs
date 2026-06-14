"""Minimal host project for the sphinx-mounts example.

All mount declarations live in ``ubproject.toml`` next to this file;
``conf.py`` registers ``sphinx_mounts`` plus the parsers/renderers the
mounted bundles use: ``myst_parser`` for the Markdown bundle, and
graphviz / plantuml / mermaid for the api-foo "directives showcase"
page.
"""

from pathlib import Path

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

# Ship a pre-built HTML coverage report alongside the docs **without
# copying it into the source tree**. ``html_extra_path`` makes Sphinx copy
# an external directory verbatim into the build *output*, so the rendered
# site stays self-contained (you can publish ``_build/html`` anywhere and
# the report travels with it) while the report itself is read in place
# from the Bazel output tree.
#
# ``html_extra_path`` copies the *contents* of each listed path into the
# output root, so we point it at the parent of the ``coverage/`` directory
# to land the report at ``<site>/coverage/``. The api-foo bundle's
# ``coverage`` page then links to / embeds ``coverage/index.html``.
#
# The entry is added only when the report has actually been built (i.e.
# ``bazel build //:all_bundles`` has run), mirroring the example's "the
# host still builds when an external artefact is absent" stance — a
# missing ``html_extra_path`` entry would otherwise fail the ``-nW`` build.
_coverage_extra = (
    Path(__file__).resolve().parent / ".." / "bazel-bin" / "coverage_report" / "extra"
).resolve()
html_extra_path = [str(_coverage_extra)] if _coverage_extra.is_dir() else []
