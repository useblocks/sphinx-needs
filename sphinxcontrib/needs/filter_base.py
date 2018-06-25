"""
filter_base is used to provide common filter functionality for directives
like needtable, needlist and needflow.
"""

import re
import sys
import urllib

from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives

from sphinxcontrib.needs.utils import status_sorter

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class FilterBase(Directive):
    def sort_by(argument):
        return directives.choice(argument, ("status", "id"))

    base_option_spec = {'status': directives.unchanged_required,
                        'tags': directives.unchanged_required,
                        'types': directives.unchanged_required,
                        'filter': directives.unchanged_required,
                        'sort_by': sort_by}

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

    if current_needlist["sort_by"] is not None:
        if current_needlist["sort_by"] == "id":
            all_needs = sorted(all_needs, key=lambda node: node["id"])
        elif current_needlist["sort_by"] == "status":
            all_needs = sorted(all_needs, key=status_sorter)

    found_needs = []
    for need_info in all_needs:
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

        if current_needlist["filter"] is None:
            python_filter_passed = True
        else:
            python_filter_passed = False
            filter_context = need_info.copy()
            filter_context["search"] = re.search
            try:
                # python_filter_passed = eval(current_needlist["filter"], globals(), filter_context)
                python_filter_passed = eval(current_needlist["filter"], None, filter_context)
            except Exception as e:
                print("Filter {0} not valid: Error: {1}".format(current_needlist["filter"], e))

        if status_filter_passed and tags_filter_passed and type_filter_passed and python_filter_passed:
            found_needs.append(need_info)

    return found_needs
