import hashlib
import re
import typing
from typing import Any, Dict, List, Optional, Sequence, Tuple

from docutils import nodes
from docutils.parsers.rst.states import RSTState, RSTStateMachine
from docutils.statemachine import StringList
from sphinx.addnodes import desc_name, desc_signature
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need
from sphinx_needs.api.exceptions import NeedsInvalidException
from sphinx_needs.config import NEEDS_CONFIG
from sphinx_needs.debug import measure_time
from sphinx_needs.defaults import NEED_DEFAULT_OPTIONS
from sphinx_needs.directives.needextend import process_needextend
from sphinx_needs.functions import (
    find_and_replace_node_content,
    resolve_dynamic_values,
    resolve_variants_options,
)
from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.layout import build_need
from sphinx_needs.logging import get_logger
from sphinx_needs.need_constraints import process_constraints
from sphinx_needs.nodes import Need
from sphinx_needs.utils import add_doc, profile, unwrap

logger = get_logger(__name__)

NON_BREAKING_SPACE = re.compile("\xa0+")


class NeedDirective(SphinxDirective):
    """
    Collects mainly all needed need-information and renders its rst-based content.

    It only creates a basic node-structure to support later manipulation.
    """

    # this enables content in the directive
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    option_spec = NEED_DEFAULT_OPTIONS

    final_argument_whitespace = True

    def __init__(
        self,
        name: str,
        arguments: List[str],
        options: Dict[str, Any],
        content: StringList,
        lineno: int,
        content_offset: int,
        block_text: str,
        state: RSTState,
        state_machine: RSTStateMachine,
    ):
        super().__init__(name, arguments, options, content, lineno, content_offset, block_text, state, state_machine)
        self.log = get_logger(__name__)
        self.full_title = self._get_full_title()

    @measure_time("need")
    def run(self) -> Sequence[nodes.Node]:
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.env

        delete_opt = self.options.get("delete")
        if isinstance(delete_opt, str):
            if delete_opt.upper() in ["TRUE", 1, "YES"]:
                delete_opt = True
            elif delete_opt.upper() in ["FALSE", 0, "NO"]:
                delete_opt = False
            else:
                raise Exception("delete attribute must be true or false")

        collapse = self.options.get("collapse")
        if isinstance(collapse, str):
            if collapse.upper() in ["TRUE", 1, "YES"]:
                collapse = True
            elif collapse.upper() in ["FALSE", 0, "NO"]:
                collapse = False
            else:
                raise Exception("collapse attribute must be true or false")

        jinja_content = self.options.get("jinja_content")
        if isinstance(jinja_content, str):
            if jinja_content.upper() in ["TRUE", 1, "YES"]:
                jinja_content = True
            elif jinja_content.upper() in ["FALSE", 0, "NO"]:
                jinja_content = False
            else:
                raise Exception("jinja_content attribute must be true or false")

        hide = "hide" in self.options

        id = self.options.get("id")
        content = "\n".join(self.content)
        status = self.options.get("status")
        if status:
            status = status.replace("__", "")  # Support for multiline options, which must use __ for empty lines
        tags = self.options.get("tags", "")
        style = self.options.get("style")
        layout = self.options.get("layout", "")
        template = self.options.get("template")
        pre_template = self.options.get("pre_template")
        post_template = self.options.get("post_template")
        duration = self.options.get("duration")
        completion = self.options.get("completion")

        need_extra_options = {"duration": duration, "completion": completion}
        for extra_link in env.config.needs_extra_links:
            need_extra_options[extra_link["option"]] = self.options.get(extra_link["option"], "")

        for extra_option in NEEDS_CONFIG.get("extra_options").keys():
            need_extra_options[extra_option] = self.options.get(extra_option, "")

        need_nodes = add_need(
            env.app,
            self.state,
            self.docname,
            self.lineno,
            need_type=self.name,
            title=self.trimmed_title,
            id=id,
            content=content,
            status=status,
            tags=tags,
            hide=hide,
            template=template,
            pre_template=pre_template,
            post_template=post_template,
            collapse=collapse,
            style=style,
            layout=layout,
            delete=delete_opt,
            jinja_content=jinja_content,
            **need_extra_options,
        )
        add_doc(env, self.docname)
        return need_nodes

    def read_in_links(self, name: str) -> List[str]:
        # Get links
        links_string = self.options.get(name)
        links = []
        if links_string:
            for link in re.split(r";|,", links_string):
                if link.isspace():
                    logger.warning(
                        f"Grubby link definition found in need '{self.trimmed_title}'. "
                        "Defined link contains spaces only."
                    )
                else:
                    links.append(link.strip())

            # This may have cut also dynamic function strings, as they can contain , as well.
            # So let put them together again
            # ToDo: There may be a smart regex for the splitting. This would avoid this mess of code...
        return _fix_list_dyn_func(links)

    def make_hashed_id(self, type_prefix: str, id_length: int) -> str:
        hashable_content = self.full_title or "\n".join(self.content)
        return "{}{}".format(
            type_prefix, hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()[:id_length]
        )

    @property
    def title_from_content(self):
        return "title_from_content" in self.options or self.env.config.needs_title_from_content

    @property
    def docname(self) -> str:
        return self.env.docname

    @property
    def trimmed_title(self) -> str:
        title = self.full_title
        max_length = self.max_title_length
        if max_length == -1 or len(title) <= max_length:
            return title
        elif max_length <= 3:
            return title[: self.max_title_length]
        else:
            return title[: self.max_title_length - 3] + "..."

    @property
    def max_title_length(self) -> int:
        max_title_length: int = self.env.config.needs_max_title_length
        return max_title_length

    # ToDo. Keep this in directive
    def _get_full_title(self) -> str:
        """
        Determines the title for the need in order of precedence:
        directive argument, first sentence of requirement (if
        `:title_from_content:` was set, and '' if no title is to be derived)."""
        if len(self.arguments) > 0:  # a title was passed
            if "title_from_content" in self.options:
                self.log.warning(
                    'Needs: need "{}" has :title_from_content: set, '
                    "but a title was provided. (see file {})".format(self.arguments[0], self.docname)
                )
            return self.arguments[0]
        elif self.title_from_content:
            first_sentence = re.split(r"[.\n]", "\n".join(self.content))[0]
            if not first_sentence:
                raise NeedsInvalidException(
                    ":title_from_content: set, but "
                    "no content provided. "
                    "(Line {} of file {}".format(self.lineno, self.docname)
                )
            return first_sentence
        else:
            return ""


def get_sections_and_signature_and_needs(need_node) -> Tuple[List[str], Optional[nodes.Text], List[str]]:
    """Gets the hierarchy of the section nodes as a list starting at the
    section of the current need and then its parent sections"""
    sections = []
    parent_needs: List[str] = []
    signature = None
    current_node = need_node
    while current_node:
        if isinstance(current_node, nodes.section):
            title = typing.cast(str, current_node.children[0].astext())  # type: ignore[no-untyped-call]
            # If using auto-section numbering, then Sphinx inserts
            # multiple non-breaking space unicode characters into the title
            # we'll replace those with a simple space to make them easier to
            # use in filters
            title = NON_BREAKING_SPACE.sub(" ", title)
            sections.append(title)

        # Checking for a signature defined "above" the need.
        # Used and set normally by directives like automodule.
        # Only check as long as we haven't found a signature
        if not signature and current_node.parent and current_node.parent.children:
            for sibling in current_node.parent.children:
                # We want to check only "above" current node, so no need to check sibling after current_node.
                if sibling == current_node:
                    break
                if isinstance(sibling, desc_signature):
                    # Check the child of the found signature for the text content/node.
                    for desc_child in sibling.children:
                        if isinstance(desc_child, desc_name) and isinstance(desc_child.children[0], nodes.Text):
                            signature = desc_child.children[0]
                if signature:
                    break

        # Check if the need is nested inside another need (so part of its content)
        # and we only want to find our parent and not add the grands, too.
        if isinstance(current_node, Need) and len(parent_needs) == 0:
            parent_needs.append(current_node["refid"])  # Store the need id, not more

        current_node = getattr(current_node, "parent", None)

    return sections, signature, parent_needs


def purge_needs(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """
    Gets executed, if a doc file needs to be purged/ read in again.
    So this code delete all found needs for the given docname.
    """
    if not hasattr(env, "needs_all_needs"):
        return
    env.needs_all_needs = {key: need for key, need in env.needs_all_needs.items() if need["docname"] != docname}


# def add_sections(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
def add_sections(app: Sphinx, doctree: nodes.document) -> None:
    """Add section titles to the needs as additional attributes that can
    be used in tables and filters"""
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    # if env.needs_workflow["add_sections"]:
    #     return

    needs = getattr(env, "needs_all_needs", {})

    for need_node in doctree.findall(Need):
        need_id = need_node["refid"]
        need_info = needs[need_id]

        # first we initialize to default values
        if "sections" not in need_info:
            need_info["sections"] = []

        if "section_name" not in need_info:
            need_info["section_name"] = ""

        if "signature" not in need_info:
            need_info["signature"] = ""

        if "parent_needs" not in need_info:
            need_info["parent_needs"] = []

        if "parent_need" not in need_info:
            need_info["parent_need"] = ""

        # Fetch values from need
        # Start from the target node, which is a sibling of the current need node
        sections, signature, parent_needs = get_sections_and_signature_and_needs(previous_sibling(need_node))

        # append / set values from need
        if sections:
            need_info["sections"] = sections
            need_info["section_name"] = sections[0]

        if signature:
            need_info["signature"] = signature

        if parent_needs:
            need_info["parent_needs"] = parent_needs
            need_info["parent_need"] = parent_needs[0]

    # Finally set a flag so that this function gets not executed several times
    # env.needs_workflow["add_sections"] = True


def previous_sibling(node):
    """Return preceding sibling node or ``None``."""
    try:
        i = node.parent.index(node)
    except AttributeError:
        return None
    return node.parent[i - 1] if i > 0 else None


@profile("NEED_PROCESS")
@measure_time("need")
def process_need_nodes(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    """
    Event handler to add title meta data (status, tags, links, ...) information to the Need node. Also processes
    constraints.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    if not app.config.needs_include_needs:
        for node in doctree.findall(Need):
            node.parent.remove(node)
        return

    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    # Call dynamic functions and replace related node data with their return values
    resolve_dynamic_values(env)

    # Apply variant handling on options and replace its values with their return values
    resolve_variants_options(env)

    # check if we have dead links
    check_links(env)

    # Create back links of common links and extra links
    for links in env.config.needs_extra_links:
        create_back_links(env, links["option"])

    """
    The output of this phase is a doctree for each source file; that is a tree of docutils nodes.

    https://www.sphinx-doc.org/en/master/extdev/index.html

    """
    needs = env.needs_all_needs

    # Used to store needs in the docs, which are needed again later
    found_needs_nodes = []
    for node_need in doctree.findall(Need):
        need_id = node_need.attributes["ids"][0]
        found_needs_nodes.append(node_need)
        need_data = needs[need_id]

        process_constraints(app, need_data)

    # We call process_needextend here by our own, so that we are able
    # to give print_need_nodes the already found need_nodes.
    process_needextend(app, doctree, fromdocname)

    print_need_nodes(app, doctree, fromdocname, found_needs_nodes)


@profile("NEED_PRINT")
def print_need_nodes(app: Sphinx, doctree: nodes.document, fromdocname: str, found_needs_nodes: list) -> None:
    """
    Finally creates the need-node in the docutils node-tree.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    builder = unwrap(app.builder)
    env = unwrap(builder.env)
    needs = env.needs_all_needs

    # We try to avoid findall as much as possibles. so we reuse the already found need nodes in the current document.
    # for node_need in doctree.findall(Need):
    for node_need in found_needs_nodes:
        need_id = node_need.attributes["ids"][0]
        need_data = needs[need_id]

        find_and_replace_node_content(node_need, env, need_data)
        for index, attribute in enumerate(node_need.attributes["classes"]):
            node_need.attributes["classes"][index] = check_and_get_content(attribute, need_data, env)

        layout = need_data["layout"] or app.config.needs_default_layout

        build_need(layout, node_need, app, fromdocname=fromdocname)


def check_links(env: BuildEnvironment) -> None:
    """
    Checks if set links are valid or are dead (referenced need does not exist.)
    :param env: Sphinx environment
    :return:
    """
    if env.needs_workflow["links_checked"]:
        return

    needs = env.needs_all_needs
    extra_links = getattr(env.config, "needs_extra_links", [])
    for need in needs.values():
        for link_type in extra_links:
            dead_links_allowed = link_type.get("allow_dead_links", False)
            need_link_value = (
                [need[link_type["option"]]] if isinstance(need[link_type["option"]], str) else need[link_type["option"]]
            )
            for link in need_link_value:
                if "." in link:
                    need_id, need_part_id = link.split(".")
                else:
                    need_id = link
                    need_part_id = None
                if need_id not in needs or (
                    need_id in needs and need_part_id and need_part_id not in needs[need_id]["parts"]
                ):
                    need["has_dead_links"] = True
                    if not dead_links_allowed:
                        need["has_forbidden_dead_links"] = True
                    break  # One found dead link is enough

    # Finally set a flag so that this function gets not executed several times
    env.needs_workflow["links_checked"] = True


def create_back_links(env: BuildEnvironment, option) -> None:
    """
    Create back-links in all found needs.
    But do this only once, as all needs are already collected and this sorting is for all
    needs and not only for the ones of the current document.

    :param env: sphinx environment
    """
    option_back = f"{option}_back"
    if env.needs_workflow[f"backlink_creation_{option}"]:
        return

    needs = env.needs_all_needs
    for key, need in needs.items():
        need_link_value = [need[option]] if isinstance(need[option], str) else need[option]
        for link in need_link_value:
            link_main = link.split(".")[0]
            try:
                link_part = link.split(".")[1]
            except IndexError:
                link_part = None

            if link_main in needs:
                if key not in needs[link_main][option_back]:
                    needs[link_main][option_back].append(key)

                # Handling of links to need_parts inside a need
                if link_part and link_part in needs[link_main]["parts"]:
                    if option_back not in needs[link_main]["parts"][link_part].keys():
                        needs[link_main]["parts"][link_part][option_back] = []
                    needs[link_main]["parts"][link_part][option_back].append(key)

    env.needs_workflow[f"backlink_creation_{option}"] = True


def _fix_list_dyn_func(list: List[str]) -> List[str]:
    """
    This searches a list for dynamic function fragments, which may have been cut by generic searches for ",|;".

    Example:
    `link_a, [[copy('links', need_id)]]` this will be split in list of 3 parts:

    #. link_a
    #. [[copy('links'
    #. need_id)]]

    This function fixes the above list to the following:

    #. link_a
    #. [[copy('links', need_id)]]

    :param list: list which may contain split function calls
    :return: list of fixed elements
    """
    open_func_string = False
    new_list = []
    for element in list:
        if "[[" in element:
            open_func_string = True
            new_link = [element]
        elif "]]" in element:
            new_link.append(element)
            open_func_string = False
            element = ",".join(new_link)
            new_list.append(element)
        elif open_func_string:
            new_link.append(element)
        else:
            new_list.append(element)
    return new_list


#####################
# Visitor functions #
#####################
# Used for builders like html or latex to tell them, what do, if they stumble on a Need-Node in the doctree.
# Normally nothing needs to be done, as all needed output-configuration is done in the child-nodes of the detected
# Need-Node.


def html_visit(self, node) -> None:
    """
    Visitor method for Need-node of builder 'html'.
    Does only wrap the Need-content into an extra <div> with class=need
    """
    self.body.append(self.starttag(node, "div", "", CLASS="need"))


def html_depart(self, node) -> None:
    self.body.append("</div>")


def latex_visit(self, node) -> None:
    pass


def latex_depart(self, node) -> None:
    pass
