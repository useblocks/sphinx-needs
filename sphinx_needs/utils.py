import cProfile
import importlib
import operator
import os
import re
from functools import reduce, wraps
from typing import Any, Dict, List, Optional, TypeVar
from urllib.parse import urlparse

from docutils import nodes
from jinja2 import Template
from sphinx.application import Sphinx

from sphinx_needs.defaults import NEEDS_PROFILING
from sphinx_needs.logging import get_logger

logger = get_logger(__name__)

NEEDS_FUNCTIONS = {}

# List of internal need option names. They should not be used by or presented to user.
INTERNALS = [
    "docname",
    "lineno",
    "target_node",
    "refid",
    "content",
    "pre_content",
    "post_content",
    "collapse",
    "parts",
    "id_parent",
    "id_complete",
    "title",
    "full_title",
    "is_part",
    "is_need",
    "type_prefix",
    "type_color",
    "type_style",
    "type",
    "type_name",
    "id",
    "hide",
    "hide_status",
    "hide_tags",
    "sections",
    "section_name",
    "content_node",
    # "parent_needs",
    "parent_need",
    # "child_needs",
    "is_external",
    "external_css",
    "is_modified",
    "modifications",
    "constraints",
    "constraints_passed",
    "constraints_results",
    "diagram",
]

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def row_col_maker(
    app: Sphinx,
    fromdocname: str,
    all_needs,
    need_info,
    need_key,
    make_ref: bool = False,
    ref_lookup: bool = False,
    prefix: str = "",
):
    """
    Creates and returns a column.

    :param app: current sphinx app
    :param fromdocname: current document
    :param all_needs: Dictionary of all need objects
    :param need_info: need_info object, which stores all related need data
    :param need_key: The key to access the needed data from need_info
    :param make_ref: If true, creates a reference for the given data in need_key
    :param ref_lookup: If true, it uses the data to lookup for a related need and uses its data to create the reference
    :param prefix: string, which is used as prefix for the text output
    :return: column object (nodes.entry)
    """
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    row_col = nodes.entry(classes=["needs_" + need_key])
    para_col = nodes.paragraph()

    if need_key in need_info and need_info[need_key] is not None:
        if isinstance(need_info[need_key], (list, set)):
            data = need_info[need_key]
        else:
            data = [need_info[need_key]]

        for index, datum in enumerate(data):
            link_id = datum
            link_part = None

            link_list = []
            for link_type in env.config.needs_extra_links:
                link_list.append(link_type["option"])
                link_list.append(link_type["option"] + "_back")

            if need_key in link_list and "." in datum:
                link_id = datum.split(".")[0]
                link_part = datum.split(".")[1]

            datum_text = prefix + str(datum)
            text_col = nodes.Text(datum_text, datum_text)
            if make_ref or ref_lookup:
                try:
                    if need_info["is_external"]:
                        ref_col = nodes.reference("", "")
                    else:
                        # Mark reference as "internal" so that if the rinohtype builder is being used it produces an
                        # internal reference within the generated PDF instead of an external link. This replicates the
                        # behaviour of references created with the sphinx utility `make_refnode`.
                        ref_col = nodes.reference("", "", internal=True)

                    if make_ref:
                        if need_info["is_external"]:
                            ref_col["refuri"] = check_and_calc_base_url_rel_path(need_info["external_url"], fromdocname)
                            ref_col["classes"].append(need_info["external_css"])
                            row_col["classes"].append(need_info["external_css"])
                        else:
                            ref_col["refuri"] = builder.get_relative_uri(fromdocname, need_info["docname"])
                            ref_col["refuri"] += "#" + datum
                    elif ref_lookup:
                        temp_need = all_needs[link_id]
                        if temp_need["is_external"]:
                            ref_col["refuri"] = check_and_calc_base_url_rel_path(temp_need["external_url"], fromdocname)
                            ref_col["classes"].append(temp_need["external_css"])
                            row_col["classes"].append(temp_need["external_css"])
                        else:
                            ref_col["refuri"] = builder.get_relative_uri(fromdocname, temp_need["docname"])
                            ref_col["refuri"] += "#" + temp_need["id"]
                            if link_part:
                                ref_col["refuri"] += "." + link_part

                except KeyError:
                    para_col += text_col
                else:
                    ref_col.append(text_col)
                    para_col += ref_col
            else:
                para_col += text_col

            if index + 1 < len(data):
                para_col += nodes.emphasis("; ", "; ")

    row_col += para_col

    return row_col


def rstjinja(app: Sphinx, docname: str, source: List[str]) -> None:
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    builder = unwrap(app.builder)
    # Make sure we're outputting HTML
    if builder.format != "html":
        return
    src = source[0]
    rendered = builder.templates.render_string(src, app.config.html_context)
    source[0] = rendered


def import_prefix_link_edit(needs: Dict[str, Any], id_prefix: str, needs_extra_links: List[Dict[str, Any]]) -> None:
    """
    Changes existing links to support given prefix.
    Only link-ids get touched, which are part of ``needs`` (so are linking them).
    Other links do not get the prefix, as there are treated as "external" links.

    :param needs: Dict of all needs
    :param id_prefix: Prefix as string
    :param needs_extra_links: config var of all supported extra links. Normally coming from env.config.needs_extra_links
    :return:
    """
    needs_ids = needs.keys()

    for need in needs.values():
        for id in needs_ids:
            # Manipulate links in all link types
            for extra_link in needs_extra_links:
                if extra_link["option"] in need and id in need[extra_link["option"]]:
                    for n, link in enumerate(need[extra_link["option"]]):
                        if id == link:
                            need[extra_link["option"]][n] = f"{id_prefix}{id}"
            # Manipulate descriptions
            # ToDo: Use regex for better matches.
            need["description"] = need["description"].replace(id, "".join([id_prefix, id]))


def profile(keyword: str):
    """
    Activate profiling for a specific function.

    Activation only happens, if given keyword is part of ``needs_profiling``.
    """

    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with cProfile.Profile() as pr:
                result = func(*args, **kwargs)

            profile_folder = os.path.join(os.getcwd(), "profile")
            profile_file = os.path.join(profile_folder, f"{keyword}.prof")
            if not os.path.exists(profile_file):
                os.makedirs(profile_folder, exist_ok=True)
            pr.dump_stats(profile_file)
            return result

        if keyword in NEEDS_PROFILING:
            return wrapper
        return func

    return inner


def check_and_calc_base_url_rel_path(external_url: str, fromdocname: str) -> str:
    """
    Check given base_url from needs_external_needs and calculate relative path if base_url is relative path.

    :param external_url: Caculated external_url from base_url in needs_external_needs
    :param fromdocname: document name
    :return: calculated external_url
    """
    ref_uri = external_url
    # check if given base_url is url or relative path
    parsed_url = urlparse(external_url)
    # get path sep considering plattform dependency, '\' for Windows, '/' fro Unix
    curr_path_sep = os.path.sep
    # check / or \ to determine the relative path to conf.py directory
    if not parsed_url.scheme and not os.path.isabs(external_url) and curr_path_sep in fromdocname:
        sub_level = len(fromdocname.split(curr_path_sep)) - 1
        ref_uri = os.path.join(sub_level * (".." + curr_path_sep), external_url)

    return ref_uri


def check_and_get_external_filter_func(current_needlist):
    """Check and import filter function from external python file."""
    # Check if external filter code is defined
    filter_func = None
    filter_args = []

    filter_func_ref = current_needlist.get("filter_func", None)

    if filter_func_ref:
        try:
            filter_module, filter_function = filter_func_ref.rsplit(".")
        except ValueError:
            logger.warn(f'Filter function not valid "{filter_func_ref}". Example: my_module:my_func')
            return []  # No needs found because of invalid filter function

        result = re.search(r"^([\w]+)(?:\((.*)\))*$", filter_function)
        filter_function = result.group(1)
        filter_args = result.group(2) or []

        try:
            final_module = importlib.import_module(filter_module)
            filter_func = getattr(final_module, filter_function)
        except Exception:
            logger.warn(f"Could not import filter function: {filter_func_ref}")
            return []

    return filter_func, filter_args


def jinja_parse(context: Dict, jinja_string: str) -> str:
    """
    Function to parse mapping options set to a string containing jinja template format.

    :param context: Data to be used as context in rendering jinja template
    :type context: dict
    :param jinja_string: A jinja template string
    :type jinja_string: str
    :return: A rendered jinja template as string
    :rtype: str

    """
    try:
        content_template = Template(jinja_string, autoescape=True)
    except Exception as e:
        raise ReferenceError(f'There was an error in the jinja statement: "{jinja_string}". ' f"Error Msg: {e}")

    content = content_template.render(**context)
    return content


def dict_get(root, items, default=None):
    """
    Access a nested object in root by item sequence.

    Usage::
       data = {"nested": {"a_list": [{"finally": "target_data"}]}}
       value = dict_get(["nested", "a_list", 0, "finally"], "Not_found")

    """
    try:
        value = reduce(operator.getitem, items, root)
    except (KeyError, IndexError, TypeError) as e:
        logger.debug(e)
        return default
    return value


T = TypeVar("T")


def unwrap(obj: Optional[T]) -> T:
    assert obj is not None
    return obj
