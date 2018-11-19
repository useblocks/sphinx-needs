"""
Provide the role ``need_count``, which output is the amount of needs found by a given filter-string.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/37
"""

from docutils import nodes
import sphinx
from pkg_resources import parse_version

from sphinxcontrib.needs.filter_common import filter_needs, prepare_need_list

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
log = logging.getLogger(__name__)


class NeedCount(nodes.Inline, nodes.Element):
    pass


def process_need_count(app, doctree, fromdocname):
    for node_need_count in doctree.traverse(NeedCount):
        env = app.builder.env
        all_needs = env.needs_all_needs.values()
        filter = node_need_count['reftarget']

        if not filter:
            amount = len(all_needs)
        else:
            need_list = prepare_need_list(all_needs)  # adds parts to need_list
            amount = len(filter_needs(need_list, filter))

        new_node_count = nodes.Text(amount, amount)
        node_need_count.replace_self(new_node_count)
