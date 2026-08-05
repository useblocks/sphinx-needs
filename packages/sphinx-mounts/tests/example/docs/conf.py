"""Minimal host project for the sphinx-mounts example.

All mount declarations live in ``ubproject.toml`` next to this file;
``conf.py`` registers ``sphinx_mounts`` plus the parsers/renderers the
mounted bundles use: ``myst_parser`` for the Markdown bundle,
graphviz / plantuml / mermaid for the api-foo "directives showcase"
page, and ``sphinx_needs`` for the Sphinx-Needs showcase bundle.
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
    "sphinx_needs",
]
exclude_patterns: list[str] = ["_build"]
master_doc = "index"

# Sphinx-Needs reads its own options from the ``[needs]`` table of the very
# same ``ubproject.toml`` that declares the mounts — so this one line is all
# the host ``conf.py`` needs to say about it. Two sibling tools, one
# declarative file, neither having to parse the other's section. The path is
# resolved relative to confdir, i.e. this directory.
needs_from_toml = "ubproject.toml"

# Mermaid renders client-side ("raw"), so the build needs no ``mmdc``
# binary. Graphviz and PlantUML do shell out at build time — to ``dot``
# and ``plantuml`` (Java) respectively — so building this example
# requires those on PATH (see this directory's README).
mermaid_output_format = "raw"

# SVG rather than the PlantUML default of PNG. Sphinx-Needs always stamps a
# ``scale`` attribute onto the diagram nodes it generates (100, i.e. no
# scaling), and sphinxcontrib-plantuml's PNG path warns about any scaling
# attribute unless Pillow is installed — which would fail this ``-nW`` build
# over a no-op. The SVG path applies no such scaling, so this keeps the
# example's dependency set to the binaries it already documents.
plantuml_output_format = "svg_img"

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
