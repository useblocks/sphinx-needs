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

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------


def _get_index_data(env: BuildEnvironment) -> dict[str, Any]:
    """Retrieve or initialize the index string structure from the build environment."""
    if not hasattr(env, "ai_docs_index_data"):
        env.ai_docs_index_data = {}  # ty: ignore[invalid-assignment]
    return env.ai_docs_index_data  # ty: ignore[unresolved-attribute]


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


def on_env_purge_doc(_app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Remove a document from the accumulated data when it is purged."""
    data = _get_index_data(env)
    data.pop(docname, None)


def on_env_merge_info(
    _app: Sphinx,
    env: BuildEnvironment,
    docnames: list[str],
    other: BuildEnvironment,
) -> None:
    """Merge environment data from parallel workers into the main environment."""
    data = _get_index_data(env)
    other_data = _get_index_data(other)
    for docname in docnames:
        if docname in other_data:
            data[docname] = other_data[docname]


def on_doctree_read(app: Sphinx, doctree: nodes.document) -> None:
    """Collect AI index data for a single page during the read phase.

    :param app: The Sphinx application object.
    :param doctree: The parsed document tree.
    """
    docname = app.env.docname
    data = _get_index_data(app.env)

    data[docname] = {
        "sections": _top_level_sections(doctree),
        "summary": _page_summary(doctree),
    }


def on_build_finished(app: Sphinx, exception: Exception | None) -> None:
    """Write ``ai_docs_index.json`` to the HTML output directory.

    Skipped when the build errored or this is not an HTML builder.

    :param app: The Sphinx application object.
    :param exception: The exception that caused the build to fail, or None.
    """
    if exception is not None or getattr(app.builder, "format", "") != "html":
        return

    data = _get_index_data(app.env)
    if not data:
        return

    pages = []
    html_copy_source = getattr(app.config, "html_copy_source", True)
    sourcelink_suffix = getattr(app.config, "html_sourcelink_suffix", ".txt")
    sourcename = getattr(app.builder, "sourcename", "_sources")

    for docname, doc_info in data.items():
        title_node = app.env.titles.get(docname)
        title = title_node.astext() if title_node else ""

        if html_copy_source:
            source_rel = os.fspath(app.env.doc2path(docname, base=False))
            if not source_rel.endswith(sourcelink_suffix):
                rst_source_path = f"{sourcename}/{source_rel}{sourcelink_suffix}"
            else:
                rst_source_path = f"{sourcename}/{source_rel}"
        else:
            rst_source_path = ""

        html_path = getattr(app.builder, "get_target_uri", lambda doc: f"{doc}.html")(
            docname
        )

        pages.append(
            {
                "rst_source_path": rst_source_path,
                "html_path": html_path,
                "title": title,
                "sections": doc_info["sections"],
                "summary": doc_info["summary"],
            }
        )

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
    app.connect("env-purge-doc", on_env_purge_doc)
    app.connect("env-merge-info", on_env_merge_info)
    app.connect("doctree-read", on_doctree_read)
    app.connect("build-finished", on_build_finished)
    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
