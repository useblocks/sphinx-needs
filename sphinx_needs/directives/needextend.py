"""


"""
import re
from typing import Any, Callable, Dict, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsExtendType, NeedsInfoType, SphinxNeedsData
from sphinx_needs.filter_common import filter_needs
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import add_doc

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
        env = self.env

        id = env.new_serialno("needextend")
        targetid = f"needextend-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        extend_filter = self.arguments[0] if self.arguments else None
        if not extend_filter:
            raise NeedsInvalidFilter(f"Filter of needextend must be set. See {env.docname}:{self.lineno}")

        strict_option = self.options.get("strict", str(NeedsSphinxConfig(self.env.app.config).needextend_strict))
        strict = True
        if strict_option.upper() == "TRUE":
            strict = True
        elif strict_option.upper() == "FALSE":
            strict = False

        data = SphinxNeedsData(env).get_or_create_extends()
        data[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "filter": self.arguments[0] if self.arguments else None,
            "modifications": self.options,
            "strict": strict,
        }

        add_doc(env, env.docname)

        return [targetnode, Needextend("")]


def extend_needs_data(
    all_needs: Dict[str, NeedsInfoType], extends: Dict[str, NeedsExtendType], needs_config: NeedsSphinxConfig
) -> None:
    """Use data gathered from needextend directives to modify fields of existing needs."""

    list_values = (
        ["tags", "links"]
        + [x["option"] for x in needs_config.extra_links]
        + [f"{x['option']}_back" for x in needs_config.extra_links]
    )  # back-links (incoming)
    link_names = [x["option"] for x in needs_config.extra_links]

    for current_needextend in extends.values():
        need_filter = current_needextend["filter"]
        if need_filter in all_needs:
            # a single known ID
            found_needs = [all_needs[need_filter]]
        elif need_filter is not None and re.fullmatch(needs_config.id_regex, need_filter):
            # an unknown ID
            error = f"Provided id {need_filter} for needextend does not exist."
            if current_needextend["strict"]:
                raise NeedsInvalidFilter(error)
            else:
                logger.info(error)
                continue
        else:
            # a filter string
            try:
                found_needs = filter_needs(all_needs.values(), needs_config, need_filter)
            except NeedsInvalidFilter as e:
                raise NeedsInvalidFilter(
                    f"Filter not valid for needextend on page {current_needextend['docname']}:\n{e}"
                )

        for found_need in found_needs:
            # Work in the stored needs, not on the search result
            need = all_needs[found_need["id"]]
            need["is_modified"] = True
            need["modifications"] += 1

            for option, value in current_needextend["modifications"].items():
                if option.startswith("+"):
                    option_name = option[1:]
                    if option_name in link_names:
                        # If we add links, then add all corresponding back links
                        for ref_need in [i.strip() for i in re.split(";|,", value)]:
                            if ref_need not in all_needs:
                                logger.warning(
                                    f"Provided link id {ref_need} for needextend does not exist. [needs]",
                                    type="needs",
                                    location=(current_needextend["docname"], current_needextend["lineno"]),
                                )
                                continue
                            if ref_need not in need[option_name]:
                                need[option_name].append(ref_need)
                            if found_need["id"] not in all_needs[ref_need][f"{option_name}_back"]:
                                all_needs[ref_need][f"{option_name}_back"] += [found_need["id"]]
                    elif option_name in list_values:
                        for item in [i.strip() for i in re.split(";|,", value)]:
                            if item not in need[option_name]:
                                need[option_name].append(item)
                    else:
                        if need[option_name]:
                            # If content is already stored, we need to add some whitespace
                            need[option_name] += " "
                        need[option_name] += value

                elif option.startswith("-"):
                    option_name = option[1:]
                    if option_name in link_names:
                        # If we remove links, then remove all corresponding back links
                        for ref_need in (i for i in need[option_name] if i in all_needs):
                            all_needs[ref_need][f"{option_name}_back"].remove(found_need["id"])
                        need[option_name] = []
                    if option_name in list_values:
                        need[option_name] = []
                    else:
                        need[option_name] = ""
                else:
                    if option in link_names:
                        # If we change links, then modify all corresponding back links
                        for ref_need in (i for i in need[option] if i in all_needs):
                            all_needs[ref_need][f"{option}_back"].remove(found_need["id"])
                        need[option] = []
                        for ref_need in [i.strip() for i in re.split(";|,", value)]:
                            if ref_need not in all_needs:
                                logger.warning(
                                    f"Provided link id {ref_need} for needextend does not exist. [needs]",
                                    type="needs",
                                    location=(current_needextend["docname"], current_needextend["lineno"]),
                                )
                                continue
                            need[option].append(ref_need)
                        for ref_need in need[option]:
                            if found_need["id"] not in all_needs[ref_need][f"{option}_back"]:
                                all_needs[ref_need][f"{option}_back"] += [found_need["id"]]
                    elif option in list_values:
                        need[option] = [i.strip() for i in re.split(";|,", value)]
                    else:
                        need[option] = value


def remove_needextend_node(node: Needextend) -> None:
    """
    Remove needextend from docutils node-tree, so that no output gets generated for it.
    Ok, this is really dirty.
    If we replace a node, docutils checks, if it will not lose any attributes.
    But this is here the case, because we are using the attribute "ids" of a node.
    However, I do not understand, why losing an attribute is such a big deal, so we delete everything
    before docutils claims about it.
    """

    for att in ("ids", "names", "classes", "dupnames"):
        node[att] = []
    node.replace_self([])
