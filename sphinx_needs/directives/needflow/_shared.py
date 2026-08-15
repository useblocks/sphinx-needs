"""Docutils helpers shared by the needflow engines.

The graph both engines draw lives in :mod:`~sphinx_needs.directives.needflow._model`;
this module only holds the document content that neither of them writes in its own
diagram syntax.
"""

from __future__ import annotations

from docutils import nodes

from sphinx_needs.data import NeedsFlowType


def create_filter_paragraph(data: NeedsFlowType) -> nodes.paragraph:
    """Describe the filters a needflow was created with, as a paragraph.

    :param data: The needflow's options.
    :return: The paragraph to add to the document.
    """
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += (
        " status({})".format(" OR ".join(data["status"]))
        if len(data["status"]) > 0
        else ""
    )
    if len(data["status"]) > 0 and len(data["tags"]) > 0:
        filter_text += " AND "
    filter_text += (
        " tags({})".format(" OR ".join(data["tags"])) if len(data["tags"]) > 0 else ""
    )
    if (len(data["status"]) > 0 or len(data["tags"]) > 0) and len(data["types"]) > 0:
        filter_text += " AND "
    filter_text += (
        " types({})".format(" OR ".join(data["types"]))
        if len(data["types"]) > 0
        else ""
    )

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node

    return para
