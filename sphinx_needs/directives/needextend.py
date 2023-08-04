"""


"""
import re
from typing import Any, Callable, Dict, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import filter_needs
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import add_doc, unwrap

logger = get_logger(__name__)


class Needextend(nodes.General, nodes.Element):
    pass


class NeedextendDirective(SphinxDirective):
    """
    Directive to modify existing needs
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    option_spec: Dict[str, Callable[[str], Any]] = {
        "strict": directives.unchanged_required,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needextend"):
            env.need_all_needextend = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        id = env.new_serialno("needextend")
        targetid = f"needextend-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        extend_filter = self.arguments[0] if self.arguments else None
        if not extend_filter:
            raise NeedsInvalidFilter(f"Filter of needextend must be set. See {env.docname}:{self.lineno}")

        strict_option = self.options.get("strict", str(self.env.app.config.needs_needextend_strict))
        strict = True
        if strict_option.upper() == "TRUE":
            strict = True
        elif strict_option.upper() == "FALSE":
            strict = False

        env.need_all_needextend[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": self.arguments[0] if self.arguments else None,
            "modifications": self.options,
            "strict": strict,
        }

        add_doc(env, env.docname)

        return [targetnode, Needextend("")]


def process_needextend(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    """
    Perform all modifications on needs
    """
    builder = unwrap(app.builder)
    env = unwrap(builder.env)
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

        for current_needextend in env.need_all_needextend.values():
            # Check if filter is just a need-id.
            # In this case create the needed filter string
            need_filter = current_needextend["filter"]
            if need_filter in env.needs_all_needs:
                need_filter = f'id == "{need_filter}"'
            # If it looks like a need id, but we haven't found one, raise an exception
            elif re.fullmatch(app.config.needs_id_regex, need_filter):
                error = f"Provided id {need_filter} for needextend does not exist."
                if current_needextend["strict"]:
                    raise NeedsInvalidFilter(error)
                else:
                    logger.info(error)
                    continue
            try:
                found_needs = filter_needs(app, env.needs_all_needs.values(), need_filter)
            except NeedsInvalidFilter as e:
                raise NeedsInvalidFilter(
                    f"Filter not valid for needextend on page {current_needextend['docname']}:\n{e}"
                )

            for found_need in found_needs:
                # Work in the stored needs, not on the search result
                need = env.needs_all_needs[found_need["id"]]
                need["is_modified"] = True
                need["modifications"] += 1

                for option, value in current_needextend["modifications"].items():
                    if option.startswith("+"):
                        option_name = option[1:]

                        # If we need to handle a list
                        if option_name in list_names:
                            for link in re.split(";|,", value):
                                # Remove whitespaces
                                link = link.strip()
                                if link not in need[option_name]:
                                    need[option_name].append(link)

                            # If we manipulate links, we need to set all the reference in the target need
                            # under e.g. links_back
                            if option_name in link_names:
                                for ref_need in re.split(";|,", value):
                                    # Remove whitespaces
                                    ref_need = ref_need.strip()
                                    if found_need["id"] not in env.needs_all_needs[ref_need][f"{option_name}_back"]:
                                        env.needs_all_needs[ref_need][f"{option_name}_back"] += [found_need["id"]]

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
                                    env.needs_all_needs[ref_need][f"{option_name}_back"].remove(found_need["id"])

                        else:
                            need[option_name] = ""
                    else:
                        if option in list_names:
                            old_content = need[option].copy()

                            need[option] = []
                            for link in re.split(";|,", value):
                                # Remove whitespaces
                                link = link.strip()
                                if link not in need[option]:
                                    need[option].append(link)

                            # If add new links also as "link_s_back" to the referenced need.
                            if option in link_names:
                                # Remove old links
                                for ref_need in old_content:  # There may be several links
                                    env.needs_all_needs[ref_need][f"{option}_back"].remove(found_need["id"])

                                # Add new links
                                for ref_need in need[option]:  # There may be several links
                                    if found_need["id"] not in env.needs_all_needs[ref_need][f"{option}_back"]:
                                        env.needs_all_needs[ref_need][f"{option}_back"] += [found_need["id"]]

                        else:
                            need[option] = value

    for node in doctree.findall(Needextend):
        # No printouts for needextend
        removed_needextend_node(node)


def removed_needextend_node(node) -> None:
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
