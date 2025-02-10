from __future__ import annotations

import cProfile
import importlib
import operator
import os
import re
from dataclasses import dataclass
from functools import lru_cache, reduce, wraps
from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar
from urllib.parse import urlparse

from docutils import nodes
from jinja2 import Environment, Template
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import LinkOptionsType, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.defaults import NEEDS_PROFILING
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.views import NeedsAndPartsListView, NeedsView

if TYPE_CHECKING:
    import matplotlib
    from matplotlib.figure import FigureBase


logger = get_logger(__name__)


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


def split_need_id(need_id_full: str) -> tuple[str, str | None]:
    """A need id can be a combination of a main id and a part id,
    split by a dot.
    This function splits them:
    If there is no dot, the part id is None,
    otherwise everything before the first dot is the main id,
    and everything after the first dot is the part id.
    """
    if "." in need_id_full:
        need_id, need_part_id = need_id_full.split(".", maxsplit=1)
    else:
        need_id = need_id_full
        need_part_id = None
    return need_id, need_part_id


def row_col_maker(
    app: Sphinx,
    fromdocname: str,
    all_needs: NeedsView,
    need_info: NeedsInfoType,
    need_key: str,
    make_ref: bool = False,
    ref_lookup: bool = False,
    prefix: str = "",
) -> nodes.entry:
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
    builder = app.builder
    env = app.env
    needs_config = NeedsSphinxConfig(env.config)

    row_col = nodes.entry(classes=["needs_" + need_key])
    para_col = nodes.paragraph()

    needs_string_links_option: list[str] = []
    for v in needs_config.string_links.values():
        needs_string_links_option.extend(v["options"])

    if need_key in need_info and need_info[need_key] is not None:  # type: ignore[literal-required]
        value = need_info[need_key]  # type: ignore[literal-required]
        if isinstance(value, (list, set)):
            data = value
        elif isinstance(value, str) and need_key in needs_string_links_option:
            data = re.split(r",|;", value)
            data = [i.strip() for i in data if len(i) != 0]
        else:
            data = [value]

        for index, datum in enumerate(data):
            link_id = datum
            link_part = None

            link_list = []
            for link_type in needs_config.extra_links:
                link_list.append(link_type["option"])
                link_list.append(link_type["option"] + "_back")

            # For needs_string_links
            link_string_list = {}
            for link_name, link_conf in needs_config.string_links.items():
                link_string_list[link_name] = {
                    "url_template": Environment(autoescape=True).from_string(
                        link_conf["link_url"]
                    ),
                    "name_template": Environment(autoescape=True).from_string(
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
                            assert need_info["external_url"] is not None, (
                                "external_url must be set for external needs"
                            )
                            ref_col["refuri"] = check_and_calc_base_url_rel_path(
                                need_info["external_url"], fromdocname
                            )
                            ref_col["classes"].append(need_info["external_css"])
                            row_col["classes"].append(need_info["external_css"])
                        elif _docname := need_info["docname"]:
                            ref_col["refuri"] = builder.get_relative_uri(
                                fromdocname, _docname
                            )
                            ref_col["refuri"] += "#" + datum
                    elif ref_lookup:
                        temp_need = all_needs[link_id]
                        if temp_need["is_external"]:
                            assert temp_need["external_url"] is not None, (
                                "external_url must be set for external needs"
                            )
                            ref_col["refuri"] = check_and_calc_base_url_rel_path(
                                temp_need["external_url"], fromdocname
                            )
                            ref_col["classes"].append(temp_need["external_css"])
                            row_col["classes"].append(temp_need["external_css"])
                        elif _docname := temp_need["docname"]:
                            ref_col["refuri"] = builder.get_relative_uri(
                                fromdocname, _docname
                            )
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
                    datum_text,
                    datum,
                    need_key,
                    matching_link_confs,
                    render_context=needs_config.render_context,
                )
            else:
                para_col += text_col

            if index + 1 < len(data):
                para_col += nodes.emphasis("; ", "; ")

    row_col += para_col

    return row_col


def import_prefix_link_edit(
    needs: dict[str, Any], id_prefix: str, needs_extra_links: list[LinkOptionsType]
) -> None:
    """
    Changes existing links to support given prefix.
    Only link-ids get touched, which are part of ``needs`` (so are linking them).
    Other links do not get the prefix, as they are treated as "external" links.

    :param needs: Dict of all needs
    :param id_prefix: Prefix as string
    :param needs_extra_links: config var of all supported extra links.
        Normally coming from env.config.needs_extra_links
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
            for key in ("content", "description"):
                if key in need:
                    need[key] = need[key].replace(id, "".join([id_prefix, id]))


FuncT = TypeVar("FuncT")


def profile(keyword: str) -> Callable[[FuncT], FuncT]:
    """
    Activate profiling for a specific function.

    Activation only happens, if given keyword is part of ``needs_profiling``.
    """

    def inner(func):  # type: ignore
        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore
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
    if (
        not parsed_url.scheme
        and not os.path.isabs(external_url)
        and curr_path_sep in fromdocname
    ):
        sub_level = len(fromdocname.split(curr_path_sep)) - 1
        ref_uri = os.path.join(sub_level * (".." + curr_path_sep), external_url)

    return ref_uri


class FilterFunc(Protocol):
    def __call__(
        self,
        *,
        needs: NeedsAndPartsListView,
        results: list[Any],
        **kwargs: str,
    ) -> None: ...


@dataclass
class FilterFuncResult:
    """Dataclass for filter function."""

    sig: str
    func: FilterFunc
    args: str


@lru_cache(maxsize=32)
def check_and_get_external_filter_func(
    filter_func_ref: str | None,
) -> FilterFuncResult | None:
    """Check and import filter function from external python file."""
    if not filter_func_ref:
        return None

    try:
        filter_module, filter_function = filter_func_ref.rsplit(".", 1)
    except ValueError:
        raise NeedsInvalidFilter("does not contain a dot")

    result = re.search(r"^(\w+)(?:\((.*)\))*$", filter_function)
    if not result:
        raise NeedsInvalidFilter(f"malformed function signature: {filter_function!r}")
    filter_function = result.group(1)
    filter_args = result.group(2) or ""

    try:
        final_module = importlib.import_module(filter_module)
    except Exception:
        raise NeedsInvalidFilter(f"cannot import module: {filter_module}")

    try:
        filter_func = getattr(final_module, filter_function)
    except Exception:
        raise NeedsInvalidFilter(f"module does not have function: {filter_function}")

    return FilterFuncResult(filter_func_ref, filter_func, filter_args)


def jinja_parse(context: dict[str, Any], jinja_string: str) -> str:
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
        raise ReferenceError(
            f'There was an error in the jinja statement: "{jinja_string}". '
            f"Error Msg: {e}"
        )

    content = content_template.render(**context)
    return content


@lru_cache
def import_matplotlib() -> matplotlib | None:
    """Import and return matplotlib, or return None if it cannot be imported.

    Also sets the interactive backend to ``Agg``, if ``DISPLAY`` is not set.
    """
    try:
        import matplotlib
        import matplotlib.pyplot
    except ImportError:
        return None
    if not os.environ.get("DISPLAY"):
        matplotlib.use("Agg")
    return matplotlib


def save_matplotlib_figure(
    app: Sphinx, figure: FigureBase, basename: str, fromdocname: str
) -> nodes.image:
    builder = app.builder
    env = app.env

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


def dict_get(root: dict[str, Any], items: Any, default: Any = None) -> Any:
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
    text_item: str,
    data: str,
    need_key: str,
    matching_link_confs: list[dict[str, Any]],
    render_context: dict[str, Any],
) -> Any:
    try:
        link_name = None
        link_url = None
        link_conf = matching_link_confs[
            0
        ]  # We only handle the first matching string_link
        match = link_conf["regex_compiled"].search(data)
        if match:
            render_content = match.groupdict()
            link_url = link_conf["url_template"].render(
                **render_content, **render_context
            )
            link_name = link_conf["name_template"].render(
                **render_content, **render_context
            )

        # if no string_link match was made, we handle it as normal string value
        ref_item = (
            nodes.reference(link_name, link_name, refuri=link_url)
            if link_name
            else nodes.Text(text_item)
        )

    except Exception as e:
        log_warning(
            logger,
            f'Problems dealing with string to link transformation for value "{data}" of '
            f'option "{need_key}". Error: {e}',
            "layout",
            None,
        )
    else:
        return ref_item


def match_variants(
    options: str | list[str] | set[str] | tuple[str, ...],
    context: dict[str, Any],
    variants: dict[str, str],
    *,
    location: str | tuple[str | None, int | None] | nodes.Node | None = None,
) -> str | None:
    """Evaluate an options list and return the first matching variant.

    Each item should have the format ``<expression>:<value>``,
    where ``<expression>`` is evaluated in the context and if it is ``True``, the value is returned.

    The ``<expression>`` can also be a key in the ``variants`` dict,
    with the actual expression.

    The last item in the list can be a ``<value>`` without an expression,
    which is returned if no other variant matches.

    :param options: A string (delimited by , or ;) or iterable of strings,
        which are evaluated as variant rules
    :param context: Mapping of variables to values used in the expressions
    :param variants: mapping of variables to expressions
    :param location: The source location of the option value,
         which can be a string (the docname or docname:lineno), a tuple of (docname, lineno).
         Used for logging warnings.
    :return: A string if a variant is matched, else None
    """
    if not options:
        return None

    options_list: list[str]
    if isinstance(options, str):
        options_list = re.split(
            r"([\[\]]{1}[\w=:'. \-\"]+[\[\(\{]{1}[\w=,.': \-\"]*[\]\)\}]{1}[\[\]]{1}:[\w.\- ]+)|([\[\]]{1}[\w=:.'\-\[\] \"]+[\[\]]{1}:[\w.\- ]+)|([\w.: ]+[,;]{1})",
            rf"""{options}""",
        )
        options_list = [
            re.sub(r"^([;, ]+)|([;, ]+$)", "", i)
            for i in options_list
            if i not in (None, ";", "", " ")
        ]
    elif isinstance(options, (list, set, tuple)):
        options_list = [str(opt) for opt in options]
    else:
        raise TypeError(
            f"Option value must be a string or iterable of strings. {type(options)} found."
        )

    variant_regex = re.compile(r"^([\w'=,:.\-\"\[\] ]+):([\w'=:.\-\"\[\] ]+)$")
    is_variant_rule = []
    for option in options_list:
        if not (result := variant_regex.match(option)):
            is_variant_rule.append(False)
            continue
        is_variant_rule.append(True)
        filter_string = result.group(1)
        if filter_string.startswith("[") and filter_string.endswith("]"):
            filter_string = filter_string[1:-1]
        filter_string = variants.get(filter_string, filter_string)
        try:
            # First matching variant definition defines the output
            if bool(eval(filter_string, context.copy())):
                return result.group(2).lstrip(":")
        except Exception as e:
            log_warning(
                logger,
                f"Error in filter {filter_string!r}: {e}",
                "variant",
                location=location,
            )

    # If there were no variant-rules, return None
    if all(m is False for m in is_variant_rule):
        return None

    # If no variant-rule matched, set to last if it is a variant-free option
    if is_variant_rule[-1] is False:
        return re.sub(r"[;,] ", "", options_list[-1])

    return None


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


def node_match(
    node_types: type[nodes.Element] | list[type[nodes.Element]],
) -> Callable[[nodes.Node], bool]:
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
    node_types_list = node_types if isinstance(node_types, list) else [node_types]

    def condition(
        node: nodes.Node, node_types: list[type[nodes.Element]] = node_types_list
    ) -> bool:
        return any(isinstance(node, x) for x in node_types)

    return condition


def add_doc(env: BuildEnvironment, docname: str, category: str | None = None) -> None:
    """Stores a docname, to know later all need-relevant docs"""
    docs = SphinxNeedsData(env).get_or_create_docs()
    if docname not in docs["all"]:
        docs["all"].append(docname)

    if category:
        if category not in docs:
            docs[category] = []
        if docname not in docs[category]:
            docs[category].append(docname)


def split_link_types(link_types: str, location: Any) -> list[str]:
    """Split link_types string into list of link_types."""
    return [x.strip() for x in re.split(";|,", link_types) if x.strip()]


def get_scale(options: dict[str, Any], location: Any) -> str:
    """Get scale for diagram, from directive option."""
    scale: str = options.get("scale", "100").replace("%", "")
    if not scale.isdigit():
        log_warning(
            logger,
            f'scale value must be a number. "{scale}" found',
            "diagram_scale",
            location=location,
        )
        return "100"
    if int(scale) < 1 or int(scale) > 300:
        log_warning(
            logger,
            f'scale value must be between 1 and 300. "{scale}" found',
            "diagram_scale",
            location=location,
        )
        return "100"
    return scale


def remove_node_from_tree(node: nodes.Element) -> None:
    """Remove a docutils node in-place from its node-tree."""
    # Ok, this is really dirty.
    # If we replace a node, docutils checks, if it will not lose any attributes.
    # But this is here the case, because we are using the attribute "ids" of a node.
    # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
    # before docutils claims about it.
    for att in ("ids", "names", "classes", "dupnames"):
        node[att] = []
    node.replace_self([])
