"""
Provide the role ``need_func``, which executes a dynamic function.
"""

from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxRole

from sphinx_needs.data import NeedsInfoType
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import add_doc

log = get_logger(__name__)


class NeedFuncRole(SphinxRole):
    """Role for creating ``NeedFunc`` node."""

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        add_doc(self.env, self.env.docname)
        node = NeedFunc(
            self.rawtext, nodes.literal(self.rawtext, self.text), **self.options
        )
        self.set_source_info(node)
        return [node], []


class NeedFunc(nodes.Inline, nodes.Element):
    def get_text(self, env: BuildEnvironment, need: NeedsInfoType | None) -> nodes.Text:
        """Execute function and return result."""
        from sphinx_needs.functions.functions import check_and_get_content

        result = check_and_get_content(self.astext(), need, env, self)
        return nodes.Text(str(result))


def process_need_func(
    app: Sphinx,
    doctree: nodes.document,
    _fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    node_need_func: NeedFunc
    for node_need_func in found_nodes:  # type: ignore[assignment]
        new_node_func = node_need_func.get_text(app.env, None)
        node_need_func.replace_self(new_node_func)
