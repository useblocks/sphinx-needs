"""Docutils helpers shared by the needflow engines.

The graph both engines draw lives in :mod:`~sphinx_needs.directives.needflow._model`;
this module only holds the document content that neither of them writes in its own
diagram syntax.

The out-of-diagram legend is the clearest case of that.  Each engine draws one inside
the picture, in its own syntax and to its own scope rule, so the same option produces
two different legends; the one built here is a document table instead, which means one
implementation, one scope rule, and a legend that is selectable text rather than pixels.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Sequence

from docutils import nodes

from sphinx_needs.config import NeedType
from sphinx_needs.data import NeedsFlowType
from sphinx_needs.needs_schema import LinkSchema

from ._options import LegendPart


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


def _table(
    head: Sequence[str], rows: Sequence[Sequence[nodes.Node]], part: LegendPart
) -> nodes.table:
    """Build a simple docutils table.

    :param head: The column titles.
    :param rows: The cell contents of each body row, one entry per column.
    :param part: Which legend section this is, which names the table so that a reader's
        stylesheet -- and the conformance corpus -- can address one section rather than
        having to count tables.
    :return: The table.
    """
    table = nodes.table(classes=["needflow_legend_table", f"needflow_legend_{part}"])
    group = nodes.tgroup(cols=len(head))
    table += group
    for _ in head:
        group += nodes.colspec(colwidth=1)

    header = nodes.thead()
    group += header
    header_row = nodes.row()
    header += header_row
    for title in head:
        entry = nodes.entry()
        entry += nodes.paragraph("", "", nodes.Text(title))
        header_row += entry

    body = nodes.tbody()
    group += body
    for cells in rows:
        row = nodes.row()
        body += row
        for cell in cells:
            entry = nodes.entry()
            entry += nodes.paragraph("", "", cell)
            row += entry

    return table


def _color_swatch(color: str) -> nodes.Node:
    """Show a color as a small block of it, falling back to its value as text.

    HTML output gets the block; a builder that cannot show one is left with the color
    value written out, which is what the in-diagram legends have always displayed.

    :param color: The configured color of a need type.
    :return: The node to put in the cell.
    """
    escaped = html.escape(color, quote=True)
    return nodes.raw(
        "",
        f'<span class="needflow_legend_swatch" '
        f'style="background-color:{escaped}">&#160;&#160;&#160;</span> {escaped}',
        format="html",
    )


def create_legend_nodes(
    parts: Iterable[LegendPart],
    need_types: Sequence[NeedType],
    link_types: Sequence[LinkSchema],
) -> list[nodes.Element]:
    """Describe what a diagram drew, as document tables beside it.

    Only what was actually drawn is described: a legend that lists need types or link
    types the reader cannot find anywhere in the picture is worse than no legend, and
    it is the reason this is computed from the graph rather than from the configuration.

    :param parts: The legend sections to draw, in the order they were asked for.
    :param need_types: The configured need types that the diagram drew, in
        configuration order.
    :param link_types: The link fields that the diagram drew edges for, in schema order.
    :return: The nodes to place after the diagram, empty if there is nothing to say.
    """
    tables: list[nodes.Element] = []
    for part in parts:
        if part == "types" and need_types:
            tables.append(
                _table(
                    ("Color", "Type"),
                    [
                        (
                            # 'color' is optional, and a type without one keeps its
                            # row rather than being dropped from the legend
                            _color_swatch(color)
                            if (color := need_type.get("color"))
                            else nodes.Text(""),
                            nodes.Text(need_type["title"]),
                        )
                        for need_type in need_types
                    ],
                    "types",
                )
            )
        elif part == "links" and link_types:
            tables.append(
                _table(
                    ("Link", "Description"),
                    [
                        (
                            nodes.literal("", link_type.name),
                            nodes.Text(link_type.display.outgoing),
                        )
                        for link_type in link_types
                    ],
                    "links",
                )
            )

    if not tables:
        return []

    container = nodes.container(classes=["needflow_legend"])
    container += tables
    return [container]
