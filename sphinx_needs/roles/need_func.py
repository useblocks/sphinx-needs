"""
Provide the role ``need_func``, which executes a dynamic function.
"""

from typing import List

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.logging import get_logger

log = get_logger(__name__)


class NeedFunc(nodes.Inline, nodes.Element):  # type: ignore
    pass


def replace_need_func_nodes(
    app: Sphinx, doctree: nodes.document, _fromdocname: str, found_nodes: List[nodes.Element]
) -> None:
    """Replace all ``NeedFunc`` nodes with renderable nodes.

    **Important**: This function should not modify the needs data,
    since it will be skipped for needs data builders.
    """
    env = app.env
    # for node_need_func in doctree.findall(NeedFunc):
    for node_need_func in found_nodes:
        result = check_and_get_content(node_need_func.attributes["reftarget"], {"id": "need_func_dummy"}, env)
        new_node_func = nodes.Text(str(result))
        node_need_func.replace_self(new_node_func)
