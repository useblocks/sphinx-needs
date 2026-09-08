"""A second extension that patches the HTML translator's ``starttag`` on the INSTANCE.

That is the technique sphinx-needs itself uses to put the needtable's contract attributes
on the ``<table>``, the ``<tr>``s and the ``<th>``s -- so it is the technique the needtable
has to survive. This extension marks every start tag it writes with ``data-otherext``; a
needtable in the middle of the document must not switch it off for everything after it.
"""

from __future__ import annotations

from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx


# lower case, like docutils' own node classes (`paragraph`, `table`, `row`)
class marker(nodes.General, nodes.Element):  # noqa: N801
    """Where the patch is installed. It writes nothing of its own."""


class MarkerDirective(Directive):
    def run(self) -> list[nodes.Node]:
        return [marker()]


def _visit_marker(translator: Any, node: marker) -> None:
    original = translator.starttag

    def starttag(
        node_: nodes.Element,
        tagname: str,
        suffix: str = "\n",
        empty: bool = False,
        **attributes: Any,
    ) -> str:
        attributes["data-otherext"] = "yes"
        return original(node_, tagname, suffix, empty, **attributes)

    translator.starttag = starttag
    raise nodes.SkipNode


# a SECOND patch, installed further down the document, so that a needtable meets one
# extension already patching and hands the translator to another afterwards
# lower case, like docutils' own node classes
class marker2(nodes.General, nodes.Element):  # noqa: N801
    """Where the second patch is installed."""


class Marker2Directive(Directive):
    def run(self) -> list[nodes.Node]:
        return [marker2()]


def _visit_marker2(translator: Any, node: marker2) -> None:
    original = translator.starttag

    def starttag(
        node_: nodes.Element,
        tagname: str,
        suffix: str = "\n",
        empty: bool = False,
        **attributes: Any,
    ) -> str:
        attributes["data-otherext2"] = "yes"
        return original(node_, tagname, suffix, empty, **attributes)

    translator.starttag = starttag
    raise nodes.SkipNode


def setup(app: Sphinx) -> dict[str, Any]:
    app.add_node(marker, html=(_visit_marker, None))
    app.add_node(marker2, html=(_visit_marker2, None))
    app.add_directive("otherext-marker", MarkerDirective)
    app.add_directive("otherext-marker2", Marker2Directive)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
