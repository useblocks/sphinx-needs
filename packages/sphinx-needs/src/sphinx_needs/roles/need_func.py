"""
Provide the ``ndf`` role, which executes a dynamic function and renders its return value.
"""

from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxRole

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedItem
from sphinx_needs.utils import add_doc


class NeedFuncRole(SphinxRole):
    """Role for creating ``NeedFunc`` node."""

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        add_doc(self.env, self.env.docname)
        node = NeedFunc(
            self.rawtext,
            nodes.literal(self.rawtext, self.text),
            **self.options,
        )
        self.set_source_info(node)
        return [node], []


class NeedFunc(nodes.Inline, nodes.Element):
    def get_text(self, env: BuildEnvironment, need: NeedItem | None) -> nodes.Text:
        """Execute function and return result."""
        from sphinx_needs.functions.functions import execute_func

        func_return = execute_func(
            env.app,
            need,
            SphinxNeedsData(env).get_needs_view(),
            self.astext(),
            self,
        )
        if isinstance(func_return, list):
            func_return = ", ".join(str(el) for el in func_return)

        return nodes.Text("" if func_return is None else str(func_return))


def process_need_func(
    app: Sphinx,
    doctree: nodes.document,
    _fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    node_need_func: NeedFunc
    for node_need_func in found_nodes:  # ty: ignore[invalid-assignment]
        new_node_func = node_need_func.get_text(app.env, None)
        node_need_func.replace_self(new_node_func)
