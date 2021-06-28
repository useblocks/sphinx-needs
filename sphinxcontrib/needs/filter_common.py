"""
filter_base is used to provide common filter functionality for directives
like needtable, needlist and needflow.
"""

import copy
import re
from itertools import product
from typing import Any, Dict, List

from docutils.parsers.rst import Directive, directives

from sphinxcontrib.needs.api.exceptions import NeedsInvalidFilter
from sphinxcontrib.needs.utils import logger


class FilterBase(Directive):
    has_content = True

    base_option_spec = {
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "types": directives.unchanged_required,
        "filter": directives.unchanged_required,
        "sort_by": directives.unchanged,
        "export_id": directives.unchanged,
    }

    def collect_filter_attributes(self):
        tags = str(self.options.get("tags", ""))
        if tags:
            tags = [tag.strip() for tag in re.split(";|,", tags) if len(tag) > 0]

        status = self.options.get("status", None)
        if status:
            try:
                status = str(status)
                status = [stat.strip() for stat in re.split(";|,", status)]
            except Exception:
                # If we could not transform/use status information, we just skip this status
                pass
        else:
            status = []

        types = self.options.get("types", [])
        if isinstance(types, str):
            types = [typ.strip() for typ in re.split(";|,", types)]

        # Add the need and all needed information
        collected_filter_options = {
            "status": status,
            "tags": tags,
            "types": types,
            "filter": self.options.get("filter", None),
            "sort_by": self.options.get("sort_by", None),
            "filter_code": self.content,
            "export_id": self.options.get("export_id", ""),
        }
        return collected_filter_options


def process_filters(all_needs, current_needlist):
    """
    Filters all needs with given configuration.
    Used by needlist, needtable and needflow.

    :param current_needlist: needlist object, which stores all filters
    :param all_needs: List of all needs inside document

    :return: list of needs, which passed the filters
    """

    sort_key = current_needlist["sort_by"]
    if sort_key:
        try:
            all_needs = sorted(all_needs, key=lambda node: node[sort_key] or "")
        except KeyError as e:
            logger.warning("Sorting parameter {0} not valid: Error: {1}".format(sort_key, e))

    found_needs_by_options = []

    # Add all need_parts of given needs to the search list
    all_needs_incl_parts = prepare_need_list(all_needs)

    filter_code = "\n".join(current_needlist["filter_code"])
    if not filter_code or filter_code.isspace():
        for need_info in all_needs_incl_parts:
            status_filter_passed = False
            if not current_needlist["status"]:
                # Filtering for status was not requested
                status_filter_passed = True
            elif need_info["status"] and need_info["status"] in current_needlist["status"]:
                # Match was found
                status_filter_passed = True

            tags_filter_passed = False
            if len(set(need_info["tags"]) & set(current_needlist["tags"])) > 0 or len(current_needlist["tags"]) == 0:
                tags_filter_passed = True

            type_filter_passed = False
            if (
                need_info["type"] in current_needlist["types"]
                or need_info["type_name"] in current_needlist["types"]
                or len(current_needlist["types"]) == 0
            ):
                type_filter_passed = True

            if status_filter_passed and tags_filter_passed and type_filter_passed:
                found_needs_by_options.append(need_info)

        found_needs_by_string = filter_needs(all_needs_incl_parts, current_needlist["filter"])

        found_needs = check_need_list(found_needs_by_options, found_needs_by_string)

    else:
        # Provides only a copy of needs to avoid data manipulations.
        context = {
            "needs": copy.deepcopy(all_needs_incl_parts),
            "results": [],
        }
        exec(filter_code, context)

        # The filter results may be dirty, as it may continue manipulated needs.
        found_dirty_needs = context["results"]
        found_needs = []

        # Just take the ids from search result and use the related, but original need
        found_need_ids = [x["id_complete"] for x in found_dirty_needs]
        for need in all_needs_incl_parts:
            if need["id_complete"] in found_need_ids:
                found_needs.append(need)

    # Store basic filter configuration and result global list.
    # Needed mainly for exporting the result to needs.json (if builder "needs" is used).
    env = current_needlist["env"]
    filter_list = env.needs_all_filters
    found_needs_ids = [need["id_complete"] for need in found_needs]

    filter_list[current_needlist["target_node"]] = {
        "target_node": current_needlist["target_node"],
        "filter": current_needlist["filter"] or "",
        "status": current_needlist["status"],
        "tags": current_needlist["tags"],
        "types": current_needlist["types"],
        "export_id": current_needlist["export_id"].upper(),
        "result": found_needs_ids,
        "amount": len(found_needs_ids),
    }

    return found_needs


def prepare_need_list(need_list):
    # all_needs_incl_parts = need_list.copy()
    try:
        all_needs_incl_parts = need_list[:]
    except TypeError:
        try:
            all_needs_incl_parts = need_list.copy()
        except AttributeError:
            all_needs_incl_parts = list(need_list)[:]

    for need in need_list:
        for part in need["parts"].values():
            filter_part = {**need, **part}
            filter_part["id_parent"] = need["id"]
            filter_part["id_complete"] = ".".join([need["id"], filter_part["id"]])
            all_needs_incl_parts.append(filter_part)

        # Be sure extra attributes, which makes only sense for need_parts, are also available on
        # need level so that no KeyError gets raised, if search/filter get executed on needs with a need-part argument.
        if "id_parent" not in need.keys():
            need["id_parent"] = need["id"]
        if "id_complete" not in need.keys():
            need["id_complete"] = need["id"]
    return all_needs_incl_parts


def check_need_list(list_a, list_b) -> List[Dict[str, Any]]:
    def get_id(element: Dict[str, Any]) -> str:
        id = element["id"]
        if element["is_part"]:
            id = "{}.{}".format(element["id_parent"], id)
        return id

    return [a for a, b in product(list_a, list_b) if get_id(a) == get_id(b)]


def filter_needs(needs, filter_string="", current_need=None):
    """
    Filters given needs based on a given filter string.
    Returns all needs, which pass the given filter.

    :param needs: list of needs, which shall be filtered
    :param filter_string: strings, which gets evaluated against each need
    :param current_need: current need, which uses the filter.
    :return: list of found needs
    """

    if not filter_string:
        return needs

    found_needs = []

    for filter_need in needs:
        try:
            if filter_single_need(filter_need, filter_string, needs, current_need):
                found_needs.append(filter_need)
        except Exception as e:
            logger.warning("Filter {0} not valid: Error: {1}".format(filter_string, e))

    return found_needs


def filter_single_need(need, filter_string="", needs=None, current_need=None) -> bool:
    """
    Checks if a single need/need_part passes a filter_string

    :param need: need or need_part
    :param filter_string: string, which is used as input for eval()
    :param needs: list of all needs
    :return: True, if need as passed the filter_string, else False
    """
    filter_context = need.copy()
    if needs:
        filter_context["needs"] = needs
    if current_need:
        filter_context["current_need"] = current_need
    else:
        filter_context["current_need"] = need

    filter_context["search"] = re.search
    result = False
    try:
        # Set filter_context as globals and not only locals in eval()!
        # Otherwise the vars not not be accessed in list comprehensions.
        result = bool(eval(filter_string, filter_context))
    except Exception as e:
        raise NeedsInvalidFilter("Filter {0} not valid: Error: {1}".format(filter_string, e))
    return result
