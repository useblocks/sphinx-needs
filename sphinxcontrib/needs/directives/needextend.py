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
    if not hasattr(env, "need_all_needextend"):
        env.need_all_needextend = {}

    if not env.needs_workflow["needs_extended"]:
        env.needs_workflow["needs_extended"] = True

        list_names = (
            ["tags", "links"]
            + [x["option"] for x in app.config.needs_extra_links]
            + [f"{x['option']}_back" for x in app.config.needs_extra_links]
        )  # back-links (incoming)
        link_names = [x["option"] for x in app.config.needs_extra_links]

        for extend_name, current_needextend in env.need_all_needextend.items():

            # Check if filter is just a need-id.
            # In this case create the needed filter string
            need_filter = current_needextend["filter"]
            if need_filter in app.env.needs_all_needs:
                need_filter = f'id == "{need_filter}"'
            # If it looks like a need id, but we haven't found one, raise an exception
            elif re.fullmatch(app.config.needs_id_regex, need_filter):
                raise NeedsInvalidFilter(f"Provided id {need_filter} for needextend does not exist.")

            try:
                found_needs = filter_needs(app.env.needs_all_needs.values(), need_filter)
            except NeedsInvalidFilter as e:
                raise NeedsInvalidFilter(
                    f"Filter not valid for needextend on page {current_needextend['docname']}:\n{e}"
                )

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
                            for link in re.split(";|,", value):
                                if link not in need[option_name]:
                                    need[option_name].append(link)

                            # If we manipulate links, we need to set all the reference in the target need
                            # under e.g. links_back
                            if option_name in link_names:
                                for ref_need in re.split(";|,", value):
                                    if found_need["id"] not in app.env.needs_all_needs[ref_need][f"{option_name}_back"]:
                                        app.env.needs_all_needs[ref_need][f"{option_name}_back"] += [found_need["id"]]

                        # else it must be a normal string
                        else:
                            # If content is already stored, we need to add some whitespace
                            if need[option_name]:
                                need[option_name] += " "
                            need[option_name] += value
                    elif option.startswith("-"):
                        option_name = option[1:]
                        if option_name in list_names:
                            old_content = need[option_name]  # Save it, as it may be need to identify referenced needs
                            need[option_name] = []

                            # If we manipulate links, we need to delete the reference in the target need as well
                            if option_name in link_names:
                                for ref_need in old_content:  # There may be several links
                                    app.env.needs_all_needs[ref_need][f"{option_name}_back"].remove(found_need["id"])

                        else:
                            need[option_name] = ""
                    else:
                        if option in list_names:
                            old_content = need[option].copy()

                            need[option] = []
                            for link in re.split(";|,", value):
                                if link not in need[option]:
                                    need[option].append(link)

                            # If add new links also as "link_s_back" to the referenced need.
                            if option in link_names:
                                # Remove old links
                                for ref_need in old_content:  # There may be several links
                                    app.env.needs_all_needs[ref_need][f"{option}_back"].remove(found_need["id"])

                                # Add new links
                                for ref_need in need[option]:  # There may be several links
                                    if found_need["id"] not in app.env.needs_all_needs[ref_need][f"{option}_back"]:
                                        app.env.needs_all_needs[ref_need][f"{option}_back"] += [found_need["id"]]

                        else:
                            need[option] = value

    for node in doctree.traverse(Needextend):
        # No printouts for needextend
        removed_needextend_node(node)


def removed_needextend_node(node):
    """
    # Remove needextend from docutils node-tree, so that no output gets generated for it.
    # Ok, this is really dirty.
    # If we replace a node, docutils checks, if it will not lose any attributes.
    # But this is here the case, because we are using the attribute "ids" of a node.
    # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
    # before docutils claims about it.

    :param node:
    :return:
    """

    for att in ("ids", "names", "classes", "dupnames"):
        node[att] = []
    node.replace_self([])
