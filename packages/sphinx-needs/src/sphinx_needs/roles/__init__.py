from docutils.nodes import Element, Node, system_message
from sphinx.roles import XRefRole

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedLink
from sphinx_needs.roles.need_count import NeedCount
from sphinx_needs.roles.need_ref import NeedRef
from sphinx_needs.utils import add_doc


class NeedsXRefRole(XRefRole):
    """
    Does the same as XRefRole, but we are able to log some information
    and store the files, in which the role is used.

    A role naming a need (``:need:``, ``:need_incoming:``, ``:need_outgoing:``) records
    its id for the document, so an incremental build re-writes the document when that
    need changes; ``:need_count:`` takes a filter, so its document is a view, re-written
    whenever any need changes.
    """

    def run(self) -> tuple[list[Node], list[system_message]]:
        # Stores the doc, in which the role got found
        is_count = self.nodeclass is NeedCount
        add_doc(self.env, self.env.docname, "need_count" if is_count else None)
        nodes, messages = super().run()
        for node in nodes:
            if isinstance(node, NeedRef):
                node["need_link"] = NeedLink.parse_address(node["reftarget"])
        if not is_count:
            refs = SphinxNeedsData(self.env).get_or_create_role_refs()
            for node in nodes:
                if (
                    isinstance(node, Element)
                    and (target := node.get("reftarget")) is not None
                ):
                    refs.setdefault(self.env.docname, set()).add(
                        NeedLink.parse_address(target).id
                    )
        return nodes, messages
