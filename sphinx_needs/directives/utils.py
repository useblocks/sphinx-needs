import re
from typing import Any, Dict, List, Tuple

from docutils import nodes
from sphinx.environment import BuildEnvironment

from sphinx_needs.defaults import TITLE_REGEX


def no_needs_found_paragraph() -> nodes.paragraph:
    nothing_found = "No needs passed the filters"
    para = nodes.paragraph()
    nothing_found_node = nodes.Text(nothing_found)
    para += nothing_found_node
    return para


def used_filter_paragraph(current_needfilter) -> nodes.paragraph:
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += (
        " status(%s)" % " OR ".join(current_needfilter["status"]) if len(current_needfilter["status"]) > 0 else ""
    )
    if len(current_needfilter["status"]) > 0 and len(current_needfilter["tags"]) > 0:
        filter_text += " AND "
    filter_text += " tags(%s)" % " OR ".join(current_needfilter["tags"]) if len(current_needfilter["tags"]) > 0 else ""
    if (len(current_needfilter["status"]) > 0 or len(current_needfilter["tags"]) > 0) and len(
        current_needfilter["types"]
    ) > 0:
        filter_text += " AND "
    filter_text += (
        " types(%s)" % " OR ".join(current_needfilter["types"]) if len(current_needfilter["types"]) > 0 else ""
    )

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node
    return para


def get_link_type_option(name: str, env: BuildEnvironment, node, default: str = "") -> List[str]:
    link_types = [x.strip() for x in re.split(";|,", node.options.get(name, default))]
    conf_link_types = env.config.needs_extra_links
    conf_link_types_name = [x["option"] for x in conf_link_types]

    final_link_types = []
    for link_type in link_types:
        if link_type is None or link_type == "":
            continue
        if link_type not in conf_link_types_name:
            raise SphinxNeedsLinkTypeException(link_type + "does not exist in configuration option needs_extra_links")

        final_link_types.append(link_type)
    return final_link_types


def get_title(option_string: str) -> Tuple[str, str]:
    """
    Returns a tuple of uppercase option and calculated title of given option string.

    :param option_string:
    :return: string
    """
    if option_string.upper() == "ID":
        return "ID", "ID"
    match = re.search(TITLE_REGEX, option_string)
    if not match:
        return option_string.upper(), option_string.title().replace("_", " ")

    option_name = match.group(1)
    title = match.group(2)

    return option_name.upper(), title


def get_option_list(options, name: str) -> List[str]:
    """
    Gets and creates a list of a given directive option value in a safe way
    :param options: List of options
    :param name: Name of the option
    :return: List with strings
    """
    values = str(options.get(name, ""))
    values_list = []
    if isinstance(values, str):
        values_list = [value.strip() for value in re.split("[;,]", values)]

    return values_list


def analyse_needs_metrics(env: BuildEnvironment) -> Dict[str, Any]:
    """
    Function to generate metrics about need objects.

    :param env: Sphinx build environment
    :return: Dictionary consisting of needs metrics.
    """
    needs: Dict = env.needs_all_needs
    metric_data = {"needs_amount": len(needs)}
    needs_types = {i["directive"]: 0 for i in env.app.config.needs_types}

    for i in needs.values():
        if i["type"] in needs_types:
            needs_types[i["type"]] += 1

    metric_data["needs_types"] = {i[0]: i[1] for i in sorted(needs_types.items(), key=lambda x: x[0])}
    return metric_data


class SphinxNeedsLinkTypeException(BaseException):
    """Raised if problems with link types happen"""
