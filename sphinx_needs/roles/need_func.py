"""
Provide the role ``need_func``, which executes a dynamic function.
"""

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import unwrap

log = get_logger(__name__)


class NeedFunc(nodes.Inline, nodes.Element):
    pass


def process_need_func(app: Sphinx, doctree: nodes.document, _fromdocname: str) -> None:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)
    for node_need_func in doctree.traverse(NeedFunc):
        result = check_and_get_content(node_need_func.attributes["reftarget"], {"id": "need_func_dummy"}, env)
        new_node_func = nodes.Text(str(result))
        node_need_func.replace_self(new_node_func)
