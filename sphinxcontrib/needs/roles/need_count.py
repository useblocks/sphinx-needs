"""
Provide the role ``need_count``, which output is the amount of needs found by a given filter-string.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/37
"""

from docutils import nodes
import re
import sphinx
from pkg_resources import parse_version
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
        amount = 0

        if not filter:
            amount = len(all_needs)
        for need in all_needs:
            filter_context = need.copy()
            filter_context["search"] = re.search
            try:
                if eval(filter, None, filter_context):
                    amount += 1
            except Exception as e:
                print("Filter {0} not valid: Error: {1}".format(filter, e))

            new_node_count = nodes.Text(amount, amount)
        node_need_count.replace_self(new_node_count)
