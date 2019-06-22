"""
filter_base is used to provide common filter functionality for directives
like needtable, needlist and needflow.
"""

import re
import sys
import urllib

from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives

from sphinxcontrib.needs.utils import status_sorter, merge_two_dicts, logger

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class FilterBase(Directive):
    base_option_spec = {
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "types": directives.unchanged_required,
        "filter": directives.unchanged_required,
        "sort_by": directives.unchanged,
        'export_id': directives.unchanged,
    }

    def collect_filter_attributes(self):
        tags = str(self.options.get("tags", ""))
        if isinstance(tags, str) and len(tags) > 0:

            # Be sure our strings end with a separator. Otherwise in python2 our string will be cut in
            # single pieces.
            if tags[-1] not in [";", ","]:
                tags += ";"

            tags = [tag.strip() for tag in re.split(";|,", tags) if len(tag) > 0]

        status = self.options.get("status", None)
        if status is not None:
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
            'status': status,
            'tags': tags,
            'types': types,
            'filter': self.options.get("filter", None),
            'sort_by': self.options.get("sort_by", None),
        }
        return collected_filter_options


def procces_filters(all_needs, current_needlist):
    """
    Filters all needs with given configuration

    :param current_needlist: needlist object, which stores all filters
    :param all_needs: List of all needs inside document

    :return: list of needs, which passed the filters
    """

    sort_key = current_needlist["sort_by"]
    if sort_key is not None:
        if sort_key == "status":
            all_needs = sorted(all_needs, key=status_sorter)
        else:
            try:
                sorted_needs = sorted(all_needs, key=lambda node: node[sort_key])
                all_needs = sorted_needs
            except Exception as e:
                logger.warning(
                    "Sorting parameter {0} not valid: Error: {1}".format(sort_key, e)
                )

    found_needs_by_options = []

    # Add all need_parts of given needs to the search list
    all_needs_incl_parts = prepare_need_list(all_needs)

    for need_info in all_needs_incl_parts:
        status_filter_passed = False
        if current_needlist["status"] is None or len(current_needlist["status"]) == 0:
            # Filtering for status was not requested
            status_filter_passed = True
        elif need_info["status"] is not None and need_info["status"] in current_needlist["status"]:
            # Match was found
            status_filter_passed = True

        tags_filter_passed = False
        if len(set(need_info["tags"]) & set(current_needlist["tags"])) > 0 or len(current_needlist["tags"]) == 0:
            tags_filter_passed = True

        type_filter_passed = False
        if need_info["type"] in current_needlist["types"] \
                or need_info["type_name"] in current_needlist["types"] \
                or len(current_needlist["types"]) == 0:
            type_filter_passed = True

        if status_filter_passed and tags_filter_passed and type_filter_passed:
            found_needs_by_options.append(need_info)

    found_needs_by_string = filter_needs(all_needs_incl_parts, current_needlist["filter"])

    # found_needs = [x for x in found_needs_by_string if x in found_needs_by_options]

    found_needs = check_need_list(found_needs_by_options, found_needs_by_string)

    # Store basic filter configuration and result global list.
    # Needed mainly for exporting the result to needs.json (if builder "needs" is used).
    env = current_needlist['env']
    filter_list = env.needs_all_filters
    found_needs_ids = [need['id'] for need in found_needs]

    filter_list[current_needlist['target_node']] = {
        'target_node': current_needlist['target_node'],
        'filter': current_needlist['filter'] if current_needlist['filter'] is not None else "",
        'status': current_needlist['status'],
        'tags': current_needlist['tags'],
        'types': current_needlist['types'],
        'export_id': current_needlist['export_id'].upper(),
        'result': found_needs_ids,
        'amount': len(found_needs_ids)
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
        for part_id, part in need['parts'].items():
            filter_part = merge_two_dicts(need, part)
            filter_part['id_parent'] = need['id']
            filter_part['id_complete'] = ".".join([need['id'], filter_part['id']])
            all_needs_incl_parts.append(filter_part)

    return all_needs_incl_parts


def check_need_list(list_a, list_b):
    common_list = []

    for element_a in list_a:
        element_a_id = element_a['id']
        if element_a['is_part']:
            element_a_id = element_a['id_parent'] + '.' + element_a_id

        for element_b in list_b:
            element_b_id = element_b['id']
            if element_b['is_part']:
                element_b_id = element_b['id_parent'] + '.' + element_b_id

            if element_a_id == element_b_id:
                common_list.append(element_a)
                break

    return common_list


def filter_needs(needs, filter_string="", filter_parts=True, merge_part_with_parent=True):
    """
    Filters given needs based on a given filter string.
    Returns all needs, which pass the given filter.

    :param merge_part_with_parent: If True, need_parts inherit options from their parent need
    :param filter_parts: If True, need_parts get also filtered
    :param filter_string: strings, which gets evaluated against each need
    :param needs: list of needs, which shall be filtered
    :return:
    """

    if filter_string is None or filter_string == "":
        return needs

    found_needs = []

    for filter_need in needs:
        try:
            if filter_single_need(filter_need, filter_string):
                found_needs.append(filter_need)
        except Exception as e:
            logger.warning("Filter {0} not valid: Error: {1}".format(filter_string, e))

    return found_needs


def filter_single_need(need, filter_string=""):
    """
    Checks if a single need/need_part passes a filter_string

    :param need: need or need_part
    :param filter_string: string, which is used as input for eval()
    :return: True, if need as passed the filter_string, else False
    """
    filter_context = need.copy()
    filter_context["search"] = re.search
    result = False
    try:
        result = bool(eval(filter_string, None, filter_context))
    except Exception as e:
        raise NeedInvalidFilter("Filter {0} not valid: Error: {1}".format(filter_string, e))
    return result


class NeedInvalidFilter(BaseException):
    pass
