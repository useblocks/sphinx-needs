import cProfile
import importlib
import operator
import os
import re
from functools import reduce, wraps
from re import Pattern
from typing import Any, Dict, List, Optional, TypeVar, Union
from urllib.parse import urlparse

from docutils import nodes
from jinja2 import BaseLoader, Environment, Template
from matplotlib.figure import FigureBase
from sphinx.application import BuildEnvironment, Sphinx

from sphinx_needs.defaults import NEEDS_PROFILING
from sphinx_needs.logging import get_logger

logger = get_logger(__name__)

NEEDS_FUNCTIONS = {}

# List of internal need option names. They should not be used by or presented to user.
INTERNALS = [
    "docname",
    "doctype",
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
    "content_id",
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
    "arch",
    "target_id",
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

    needs_string_links_option: List[str] = []
    for v in app.config.needs_string_links.values():
        needs_string_links_option.extend(v["options"])

    if need_key in need_info and need_info[need_key] is not None:
        if isinstance(need_info[need_key], (list, set)):
            data = need_info[need_key]
        elif isinstance(need_info[need_key], str) and need_key in needs_string_links_option:
            data = re.split(r",|;", need_info[need_key])
            data = [i.strip() for i in data if len(i) != 0]
        else:
            data = [need_info[need_key]]

        for index, datum in enumerate(data):
            link_id = datum
            link_part = None

            link_list = []
            for link_type in env.config.needs_extra_links:
                link_list.append(link_type["option"])
                link_list.append(link_type["option"] + "_back")

            # For needs_string_links
            link_string_list = {}
            for link_name, link_conf in app.config.needs_string_links.items():
                link_string_list[link_name] = {
                    "url_template": Environment(loader=BaseLoader, autoescape=True).from_string(link_conf["link_url"]),
                    "name_template": Environment(loader=BaseLoader, autoescape=True).from_string(
                        link_conf["link_name"]
                    ),
                    "regex_compiled": re.compile(link_conf["regex"]),
                    "options": link_conf["options"],
                    "name": link_name,
                }

            matching_link_confs = []
            for link_conf in link_string_list.values():
                if need_key in link_conf["options"] and len(datum) != 0:
                    matching_link_confs.append(link_conf)

            if need_key in link_list and "." in datum:
                link_id = datum.split(".")[0]
                link_part = datum.split(".")[1]

            datum_text = prefix + str(datum)
            text_col = nodes.Text(datum_text)
            if make_ref or ref_lookup:
                try:
                    if need_info["is_external"]:
                        ref_col = nodes.reference("", "")
                    else:
                        # Mark references as "internal" so that if the rinohtype builder is being used it produces an
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
            elif matching_link_confs:
                para_col += match_string_link(
                    datum_text, datum, need_key, matching_link_confs, render_context=app.config.needs_render_context
                )
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
    rendered = builder.templates.render_string(src, app.config.html_context, **app.config.needs_render_context)
    source[0] = rendered


def import_prefix_link_edit(needs: Dict[str, Any], id_prefix: str, needs_extra_links: List[Dict[str, Any]]) -> None:
    """
    Changes existing links to support given prefix.
    Only link-ids get touched, which are part of ``needs`` (so are linking them).
    Other links do not get the prefix, as they are treated as "external" links.

    :param needs: Dict of all needs
    :param id_prefix: Prefix as string
    :param needs_extra_links: config var of all supported extra links. Normally coming from env.config.needs_extra_links
    :return:
    """
    if not id_prefix:
        return

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

    filter_func_ref = current_needlist.get("filter_func")

    if filter_func_ref:
        try:
            filter_module, filter_function = filter_func_ref.rsplit(".")
        except ValueError:
            logger.warning(f'Filter function not valid "{filter_func_ref}". Example: my_module:my_func')
            return []  # No needs were found because of invalid filter function

        result = re.search(r"^(\w+)(?:\((.*)\))*$", filter_function)
        filter_function = result.group(1)
        filter_args = result.group(2) or []

        try:
            final_module = importlib.import_module(filter_module)
            filter_func = getattr(final_module, filter_function)
        except Exception:
            logger.warning(f"Could not import filter function: {filter_func_ref}")
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


def save_matplotlib_figure(app: Sphinx, figure: FigureBase, basename: str, fromdocname: str) -> nodes.image:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    image_folder = os.path.join(builder.outdir, builder.imagedir)
    os.makedirs(image_folder, exist_ok=True)

    # Determine a common mimetype between matplotlib and the builder.
    matplotlib_types = {
        "image/svg+xml": "svg",
        "application/pdf": "pdf",
        "image/png": "png",
    }

    for builder_mimetype in builder.supported_image_types:
        if builder_mimetype in matplotlib_types:
            mimetype = builder_mimetype
            break
    else:
        # No matching type?  Surprising, but just save as .png to mimic the old behavior.
        # (More than likely the build will not work...)
        mimetype = "image/png"

    ext = matplotlib_types[mimetype]

    abs_file_path = os.path.join(image_folder, f"{basename}.{ext}")
    if abs_file_path not in env.images:
        figure.savefig(os.path.join(env.app.srcdir, abs_file_path))
        env.images.add_file(fromdocname, abs_file_path)

    image_node = nodes.image()
    image_node["uri"] = abs_file_path

    # look at uri value for source path, relative to the srcdir folder
    image_node["candidates"] = {mimetype: abs_file_path}

    return image_node


def dict_get(root, items, default=None) -> Any:
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


def match_string_link(
    text_item: str, data: str, need_key: str, matching_link_confs: List[Dict], render_context: Dict[str, Any]
) -> Any:
    try:
        link_name = None
        link_url = None
        link_conf = matching_link_confs[0]  # We only handle the first matching string_link
        match = link_conf["regex_compiled"].search(data)
        if match:
            render_content = match.groupdict()
            link_url = link_conf["url_template"].render(**render_content, **render_context)
            link_name = link_conf["name_template"].render(**render_content, **render_context)
        if link_name:
            ref_item = nodes.reference(link_name, link_name, refuri=link_url)
        else:
            # if no string_link match was made, we handle it as normal string value
            ref_item = nodes.Text(text_item)

    except Exception as e:
        logger.warning(
            f'Problems dealing with string to link transformation for value "{data}" of '
            f'option "{need_key}". Error: {e}'
        )
    else:
        return ref_item


def match_variants(option_value: Union[str, List], keywords: Dict, needs_variants: Dict) -> Union[str, List, None]:
    """
    Function to handle variant option management.

    :param option_value: Value assigned to an option
    :type option_value: Union[str, List]
    :param keywords: Data to use as filtering context
    :type keywords: Dict
    :param needs_variants: Needs variants data set in users conf.py
    :type needs_variants: Dict
    :return: A string, list, or None to be used as value for option.
    :rtype: Union[str, List, None]
    """

    def variant_handling(
        variant_definitions: List, variant_data: Dict, variant_pattern: Pattern
    ) -> Union[str, List, None]:
        filter_context = variant_data
        # filter_result = []
        no_variants_in_option = False
        variants_in_option = False
        for variant_definition in variant_definitions:
            # Test if definition is a variant definition
            check_definition = variant_pattern.search(variant_definition)
            if check_definition:
                variants_in_option = True
                # Separate variant definition from value to use for the option
                filter_string, output, _ = re.split(r"(:[\w':.\-\" ]+)$", variant_definition)
                filter_string = re.sub(r"^\[|[:\]]$", "", filter_string)
                filter_string = needs_variants[filter_string] if filter_string in needs_variants else filter_string
                try:
                    # https://docs.python.org/3/library/functions.html?highlight=compile#compile
                    filter_compiled = compile(filter_string, "<string>", "eval")
                    # Set filter_context as globals and not only locals in eval()!
                    # Otherwise, the vars not be accessed in list comprehensions.
                    if filter_compiled:
                        eval_result = bool(eval(filter_compiled, filter_context))
                    else:
                        eval_result = bool(eval(filter_string, filter_context))
                    # First matching variant definition defines the output
                    if eval_result:
                        no_variants_in_option = False
                        return output.lstrip(":")
                except Exception as e:
                    logger.warning(f'There was an error in the filter statement: "{filter_string}". ' f"Error Msg: {e}")
            else:
                no_variants_in_option = True

        if no_variants_in_option and not variants_in_option:
            return None

        # If no variant-rule is True, set to last, variant-free option. If this does not exist, set to None.
        defaults_to = variant_definitions[-1]
        if variants_in_option and variant_pattern.search(defaults_to):
            return None
        return re.sub(r"[;,] ", "", defaults_to)

    split_pattern = r"([\[\]]{1}[\w=:'. \-\"]+[\[\(\{]{1}[\w=,.': \-\"]*[\]\)\}]{1}[\[\]]{1}:[\w.\- ]+)|([\[\]]{1}[\w=:.'\-\[\] \"]+[\[\]]{1}:[\w.\- ]+)|([\w.: ]+[,;]{1})"
    variant_rule_pattern = r"^[\w'=,:.\-\"\[\] ]+:[\w'=:.\-\"\[\] ]+$"
    variant_splitting = re.compile(split_pattern)
    variant_rule_matching = re.compile(variant_rule_pattern)

    # Handling multiple variant definitions
    if isinstance(option_value, str):
        multiple_variants: List = variant_splitting.split(rf"""{option_value}""")
        multiple_variants: List = [
            re.sub(r"^([;, ]+)|([;, ]+$)", "", i) for i in multiple_variants if i not in (None, ";", "", " ")
        ]
        if len(multiple_variants) == 1 and not variant_rule_matching.search(multiple_variants[0]):
            return option_value
        new_option_value = variant_handling(multiple_variants, keywords, variant_rule_matching)
        if new_option_value is None:
            return option_value
        return new_option_value
    elif isinstance(option_value, (list, set, tuple)):
        multiple_variants: List = list(option_value)
        # In case an option value is a list (:tags: open; close), and does not contain any variant definition,
        # then return the unmodified value
        # options = all([bool(not variant_rule_matching.search(i)) for i in multiple_variants])
        options = all(bool(not variant_rule_matching.search(i)) for i in multiple_variants)
        if options:
            return option_value
        new_option_value = variant_handling(multiple_variants, keywords, variant_rule_matching)
        return new_option_value
    else:
        return option_value


pattern = r"(https://|http://|www\.|[\w]*?)([\w\-/.]+):([\w\-/.]+)@([\w\-/.]+)"
data_compile = re.compile(pattern)


def clean_log(data: str) -> str:
    """
     Function for cleaning login credentials like username & password from log output.

    :param data: The login url entered by the user.
    :type data: str
    :return: Cleaned login string or None
    """

    clean_credentials = data_compile.sub(r"\1****:****@\4", data)
    return clean_credentials


T = TypeVar("T")


def unwrap(obj: Optional[T]) -> T:
    assert obj is not None
    return obj


def node_match(node_types):
    """
    Returns a condition function for doctuils.nodes.findall()

    It takes a single or a list of node-types, if a findall() finds that node-type, the node
    get returned by findall() inside a generator-object.

    Use it like::

    for node_need in doctree.findall(node_mathc([Need, NeedTable])):
        if isinstance(node_nee, Need):
            pass  # some need voodoo
        elif isinstance(node_nee, NeedTable):
            pass  # some needtable voodoo
        else:
            raise Exception('Not requested node type')

    :param node_types: List of docutils node types
    :return: function, which can be used as constraint-function for docutils findall()
    """
    if not isinstance(node_types, list):
        node_types = [node_types]

    def condition(node, node_types=node_types):
        return any(isinstance(node, x) for x in node_types)

    return condition


def add_doc(env: BuildEnvironment, docname: str, category=None):
    """Stores a docname, to know later all need-relevant docs"""
    if docname not in env.needs_all_docs["all"]:
        env.needs_all_docs["all"].append(docname)

    if category:
        if category not in env.needs_all_docs:
            env.needs_all_docs[category] = []
        if docname not in env.needs_all_docs[category]:
            env.needs_all_docs[category].append(docname)
