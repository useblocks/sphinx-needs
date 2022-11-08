from typing import List, Tuple

from docutils.nodes import Node, system_message
from sphinx.roles import XRefRole

from sphinx_needs.utils import add_doc


class NeedsXRefRole(XRefRole):
    """
    Does the same as XRefRole, but we are able to log some information
    and store the files, in which the role is used.
    """

    def run(self) -> Tuple[List[Node], List[system_message]]:
        # Stores the doc, in which the role got found
        add_doc(self.env, self.env.docname)
        return super().run()
