"""


"""
import re

from docutils import nodes
from docutils.parsers.rst import Directive

from sphinxcontrib.needs.api.exceptions import NeedsInvalidFilter
from sphinxcontrib.needs.filter_common import filter_needs


class Needextend(nodes.General, nodes.Element):
    pass


class NeedextendDirective(Directive):
    """
    Directive to modify existing needs
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    option_spec = {}

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needextend"):
            env.need_all_needextend = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        id = env.new_serialno("needextend")
        targetid = "needextend-{docname}-{id}".format(docname=env.docname, id=id)
        targetnode = nodes.target("", "", ids=[targetid])

        extend_filter = self.arguments[0] if self.arguments else None
        if not extend_filter:
            raise NeedsInvalidFilter(f"Filter of needextend must be set. See {env.docname}:{self.lineno}")

        env.need_all_needextend[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "env": env,
            "filter": self.arguments[0] if self.arguments else None,
            "modifications": self.options,
        }

        return [targetnode] + [Needextend("")]


def process_needextend(app, doctree, fromdocname):
    """
    Perform all modifications on needs
    """
    env = app.builder.env
    list_names = (
        ["tags", "links"]
        + [x["option"] for x in app.config.needs_extra_links]
        + [f"{x['option']}_back" for x in app.config.needs_extra_links]
    )  # back-links (incoming)

    for node in doctree.traverse(Needextend):
        id = node.attributes["ids"][0]
        current_needextend = env.need_all_needextend[id]
        found_needs = filter_needs(app.env.needs_all_needs.values(), current_needextend["filter"])

        for found_need in found_needs:
            # Work in the stored needs, not on the search result
            need = app.env.needs_all_needs[found_need["id"]]
            need["is_modified"] = True
            need["modifications"] += 1

            for option, value in current_needextend["modifications"].items():
                if option.startswith("+"):
                    option_name = option[1:]

                    # If we need to handle a list
                    if option_name in list_names:
                        need[option_name] += re.split(";|,", value)

                    # else it must be a normal string
                    else:
                        # If content is already stored, we need to add some whitespace
                        if need[option_name]:
                            need[option_name] += " "
                        need[option_name] += value
                elif option.startswith("-"):
                    option_name = option[1:]
                    if option_name in list_names:
                        need[option_name] = []
                    else:
                        need[option_name] = ""
                else:
                    if option in list_names:
                        need[option] = re.split(";|,", value)
                    else:
                        need[option] = value

        # Remove needextend from docutils node-tree, so that no output gets generated for it.
        # Ok, this is really dirty.
        # If we replace a node, docutils checks, if it will not lose any attributes.
        # But this is here the case, because we are using the attribute "ids" of a node.
        # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
        # before docutils claims about it.
        for att in ("ids", "names", "classes", "dupnames"):
            node[att] = []
        node.replace_self([])
