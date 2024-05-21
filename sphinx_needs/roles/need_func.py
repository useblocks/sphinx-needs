"""
Provide the role ``need_func``, which executes a dynamic function.
"""

from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.logging import get_logger

log = get_logger(__name__)


class NeedFunc(nodes.Inline, nodes.Element):
    pass


def process_need_func(
    app: Sphinx,
    doctree: nodes.document,
    _fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    env = app.env
    # for node_need_func in doctree.findall(NeedFunc):
    for node_need_func in found_nodes:
        result = check_and_get_content(
            node_need_func.attributes["reftarget"],
            {"id": "need_func_dummy"},  # type: ignore
            env,
        )
        new_node_func = nodes.Text(str(result))
        node_need_func.replace_self(new_node_func)
