"""Sphinx extension: AI documentation index builder.

Generates ``ai_docs_index.json`` in the HTML output directory during every
HTML build. The file contains a structured listing of all documentation pages
with their titles, top-level section headings, and optional page summaries.

The optional ``.. page-summary::`` directive can be placed in any RST page to
attach a short prose description that is included in the index. Pages without
the directive still receive a full index entry (with an empty summary field).

Generated file format::

    {
      "version": "1.0",
      "pages": [
        {
          "rst_source_path": "_sources/basics/installation.rst.txt",
          "html_path": "basics/installation.html",
          "title": "Installation",
          "sections": ["System Requirements", "Installing via pip"],
          "summary": "Covers installation of ubCode on all platforms."
        }
      ]
    }
"""

import json
from pathlib import Path
from typing import Any
import weakref

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

# ---------------------------------------------------------------------------
# Per-build accumulator keyed on the Sphinx app instance.
# Using WeakKeyDictionary ensures data from one build does not leak into
# another build running in the same Python process (e.g. sphinx-autobuild,
# test suites), and the entry is garbage-collected when the app is destroyed.
# ---------------------------------------------------------------------------

_build_data: weakref.WeakKeyDictionary[Sphinx, dict[str, Any]] = (
    weakref.WeakKeyDictionary()
)


# ---------------------------------------------------------------------------
# Custom node
# ---------------------------------------------------------------------------


class PageSummaryNode(nodes.General, nodes.Element):
    """Docutils node carrying the content of a ``.. page-summary::`` directive."""


# ---------------------------------------------------------------------------
# Directive
# ---------------------------------------------------------------------------


class PageSummaryDirective(Directive):
    """RST directive for providing an AI-oriented page description.

    Usage::

        .. page-summary::

            This page covers the installation of ubCode on all major platforms,
            including system requirements and VS Code extension setup.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[nodes.Node]:
        node = PageSummaryNode()
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


# ---------------------------------------------------------------------------
# HTML visitors — suppress rendering of page-summary nodes
# ---------------------------------------------------------------------------


def visit_page_summary_node_html(_self: Any, _node: PageSummaryNode) -> None:
    raise nodes.SkipNode


def depart_page_summary_node_html(_self: Any, _node: PageSummaryNode) -> None:
    pass


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------


def _top_level_sections(doctree: nodes.document) -> list[str]:
    """Return titles of direct subsections within the page's root section.

    :param doctree: The fully-resolved doctree for a page.
    :returns: List of section title strings, in document order.
    """
    root_section = next(
        (child for child in doctree.children if isinstance(child, nodes.section)),
        None,
    )
    if root_section is None:
        return []
    return [
        child[0].astext()
        for child in root_section.children
        if isinstance(child, nodes.section) and child.children
    ]


def _page_summary(doctree: nodes.document) -> str:
    """Return the text of the first ``.. page-summary::`` in the doctree.

    :param doctree: The fully-resolved doctree for a page.
    :returns: Summary text, or empty string if the directive is absent.
    """
    found = list(doctree.findall(PageSummaryNode))
    if not found:
        return ""
    return found[0].astext().strip()


# ---------------------------------------------------------------------------
# Sphinx event handlers
# ---------------------------------------------------------------------------


def on_builder_inited(app: Sphinx) -> None:
    """Initialise the per-build accumulator when an HTML build starts.

    :param app: The Sphinx application object.
    """
    if app.builder.name == "html":
        _build_data[app] = {}


def on_doctree_resolved(
    app: Sphinx,
    doctree: nodes.document,
    docname: str,
) -> None:
    """Collect AI index data for a single page.

    Called by Sphinx for each document during the write phase of an HTML build.

    :param app: The Sphinx application object.
    :param doctree: The fully-resolved document tree.
    :param docname: The document name (e.g. ``basics/installation``).
    """
    if app.builder.name != "html":
        return

    page_data = _build_data.get(app)
    if page_data is None:
        return

    title_node = app.env.titles.get(docname)
    title = title_node.astext() if title_node else ""

    # env.doc2path returns the source-relative path including the real extension,
    # e.g. "basics/installation.rst" or "references/ubproject_schema.md".
    source_rel = app.env.doc2path(docname, base=False)
    rst_source_path = f"_sources/{source_rel}.txt"

    page_data[docname] = {
        "rst_source_path": rst_source_path,
        "html_path": f"{docname}.html",
        "title": title,
        "sections": _top_level_sections(doctree),
        "summary": _page_summary(doctree),
    }


def on_build_finished(app: Sphinx, exception: Exception | None) -> None:
    """Write ``ai_docs_index.json`` to the HTML output directory.

    Skipped when the build errored or this is not an HTML builder.

    :param app: The Sphinx application object.
    :param exception: The exception that caused the build to fail, or None.
    """
    if exception is not None:
        return

    page_data = _build_data.get(app)
    if not page_data:
        return

    pages = list(page_data.values())
    output: dict[str, Any] = {"version": "1.0", "pages": pages}
    out_path = Path(app.outdir) / "ai_docs_index.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Extension entry point
# ---------------------------------------------------------------------------


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx.

    :param app: The Sphinx application object.
    :returns: Extension metadata dict.
    """
    # Register a skip visitor for every standard Sphinx builder so that
    # PageSummaryNode is silently ignored in all non-HTML outputs.
    _skip = (visit_page_summary_node_html, depart_page_summary_node_html)
    app.add_node(
        PageSummaryNode,
        html=_skip,
        latex=_skip,
        text=_skip,
        man=_skip,
        texinfo=_skip,
        xml=_skip,
        pseudoxml=_skip,
    )
    app.add_directive("page-summary", PageSummaryDirective)
    app.connect("builder-inited", on_builder_inited)
    app.connect("doctree-resolved", on_doctree_resolved)
    app.connect("build-finished", on_build_finished)
    return {
        "version": "0.1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": False,
    }
