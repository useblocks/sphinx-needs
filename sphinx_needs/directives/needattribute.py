import math
import os
from typing import Sequence

import matplotlib
import numpy
from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.directives.need import (Need, )

from sphinx_needs.filter_common import FilterBase, filter_needs, prepare_need_list
from sphinx_needs.utils import unwrap

if not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")
import hashlib

from docutils.parsers.rst import directives

from sphinx_needs.logging import get_logger

logger = get_logger(__name__)


class Needattribute(nodes.General, nodes.Element):
    id = ""
    title = ""
    targetid = ""
    error_id = ""
    content = ""
    uml = False
    pass


class NeedattributeDirective(FilterBase):
    """
    Directive to plot diagrams with the help of matplotlib

    .. versionadded: 0.7.5
    """

    has_content = True

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    option_spec = {
        "uml": directives.flag,
    }

    # Algorithm:
    # 1. define constants
    def run(self) -> Sequence[nodes.Node]:
        # 1. define constants
        env = self.state.document.settings.env

        id = env.new_serialno("needattribute")
        targetid = f"needattribute-{env.docname}-{id}"
        error_id = f"Needattribute - file '{env.docname}' - line '{self.lineno}'"

        content = self.content
        if not content:
            raise Exception(f"{error_id} content cannot be empty.")

        #content = "\n".join(content) 

        title = self.arguments[0].strip() if self.arguments else None

        needattribute = Needattribute("")

        uml = "uml" in self.options

        #todo: add exception if title is not a option in extra options. 

        # 2. Stores infos for needbar
        needattribute.id = id
        needattribute.title = title
        needattribute.targetid = targetid
        needattribute.error_id = error_id
        needattribute.content = content
        needattribute.uml = uml

        return [needattribute]


# Algorithm:
def process_needattribute(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    # NEEDFLOW
    for node in doctree.traverse(Needattribute):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ("ids", "names", "classes", "dupnames"):
                node[att] = []
            node.replace_self([])
            continue

        current_node = getattr(node, "parent", None)

        while current_node:
            if isinstance(current_node, Need):
                refid = current_node["refid"]
                env.needs_all_needs[refid][node.title] = node.content

                need_attribute_metadata = {}
                need_attribute_metadata["uml"] = node.uml
                need_attribute_metadata["multiline"] = True 

                if not "attribute_metadata" in env.needs_all_needs[refid]:
                    env.needs_all_needs[refid]["attribute_metadata"] = {}
                env.needs_all_needs[refid]["attribute_metadata"][node.title] = need_attribute_metadata

                break

            current_node = getattr(current_node, "parent", None)

        node.replace_self([])
