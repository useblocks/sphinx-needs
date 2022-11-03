"""
Provide the role ``need_count``, which output is the amount of needs found by a given filter-string.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/37
"""

from typing import List

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import filter_needs, prepare_need_list
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import unwrap

log = get_logger(__name__)


class NeedCount(nodes.Inline, nodes.Element):  # type: ignore
    pass


def process_need_count(
    app: Sphinx, doctree: nodes.document, _fromdocname: str, found_nodes: List[nodes.Element]
) -> None:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)
    # for node_need_count in doctree.findall(NeedCount):
    for node_need_count in found_nodes:
        all_needs = list(getattr(env, "needs_all_needs", {}).values())
        filter = node_need_count["reftarget"]

        if filter:
            filters = filter.split(" ? ")
            if len(filters) == 1:
                need_list = prepare_need_list(all_needs)  # adds parts to need_list
                amount = str(len(filter_needs(app, need_list, filters[0])))
            elif len(filters) == 2:
                need_list = prepare_need_list(all_needs)  # adds parts to need_list
                amount_1 = len(filter_needs(app, need_list, filters[0]))
                amount_2 = len(filter_needs(app, need_list, filters[1]))
                amount = f"{amount_1 / amount_2 * 100:2.1f}"
            elif len(filters) > 2:
                raise NeedsInvalidFilter(
                    "Filter not valid. Got too many filter elements. Allowed are 1 or 2. "
                    'Use " ? " only once to separate filters.'
                )
        else:
            amount = str(len(all_needs))

        new_node_count = nodes.Text(amount)
        node_need_count.replace_self(new_node_count)
