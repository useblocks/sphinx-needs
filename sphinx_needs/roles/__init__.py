from docutils.nodes import Node, system_message
from sphinx.roles import XRefRole

from sphinx_needs.utils import add_doc


class NeedsXRefRole(XRefRole):
    """
    Does the same as XRefRole, but we are able to log some information
    and store the files, in which the role is used.
    """

    def run(self) -> tuple[list[Node], list[system_message]]:
        # Stores the doc, in which the role got found
        add_doc(self.env, self.env.docname)
        return super().run()
