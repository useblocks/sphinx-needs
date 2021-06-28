# -*- coding: utf-8 -*-
import hashlib
import re

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.addnodes import desc_name, desc_signature

from sphinxcontrib.needs.api import add_need
from sphinxcontrib.needs.api.exceptions import NeedsInvalidException
from sphinxcontrib.needs.defaults import NEED_DEFAULT_OPTIONS
from sphinxcontrib.needs.functions import (
    find_and_replace_node_content,
    resolve_dynamic_values,
)
from sphinxcontrib.needs.functions.functions import check_and_get_content
from sphinxcontrib.needs.layout import build_need
from sphinxcontrib.needs.logging import get_logger

logger = get_logger(__name__)

NON_BREAKING_SPACE = re.compile("\xa0+")


class Need(nodes.General, nodes.Element):
    """
    Node for containing a complete need.
    Node structure:

    - need
      - headline container
      - meta container ()
      - content container

    As the content container gets rendered RST input, this must already be created during
    node handling and can not be done later during event handling.
    Reason: nested_parse_with_titles() needs self.state, which is available only during node handling.

    headline and content container get added later during event handling (process_need_nodes()).
    """

    child_text_separator = "\n"


class NeedDirective(Directive):
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

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.log = get_logger(__name__)
        self.full_title = self._get_full_title()

    def run(self):
        #############################################################################################
        # Get environment
        #############################################################################################
        env = self.env

        # ToDo: Keep this in directive!!!
        collapse = self.options.get("collapse", None)
        if isinstance(collapse, str):
            if collapse.upper() in ["TRUE", 1, "YES"]:
                collapse = True
            elif collapse.upper() in ["FALSE", 0, "NO"]:
                collapse = False
            else:
                raise Exception("collapse attribute must be true or false")

        hide = True if "hide" in self.options.keys() else False

        id = self.options.get("id", None)
        content = "\n".join(self.content)
        status = self.options.get("status", None)
        if status:
            status = status.replace("__", "")  # Support for multiline options, which must use __ for empty lines
        tags = self.options.get("tags", "")
        style = self.options.get("style", None)
        layout = self.options.get("layout", "")
        template = self.options.get("template", None)
        pre_template = self.options.get("pre_template", None)
        post_template = self.options.get("post_template", None)
        duration = self.options.get("duration", None)
        completion = self.options.get("completion", None)

        need_extra_options = {"duration": duration, "completion": completion}
        for extra_link in env.config.needs_extra_links:
            need_extra_options[extra_link["option"]] = self.options.get(extra_link["option"], "")

        for extra_option in env.config.needs_extra_options.keys():
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
            **need_extra_options,
        )
        return need_nodes

    def read_in_links(self, name):
        # Get links
        links_string = self.options.get(name, [])
        links = []
        if links_string:
            # links = [link.strip() for link in re.split(";|,", links) if not link.isspace()]
            for link in re.split(";|,", links_string):
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

    def make_hashed_id(self, type_prefix, id_length):
        hashable_content = self.full_title or "\n".join(self.content)
        return "%s%s" % (type_prefix, hashlib.sha1(hashable_content.encode("UTF-8")).hexdigest().upper()[:id_length])

    @property
    def env(self):
        return self.state.document.settings.env

    @property
    def title_from_content(self):
        return "title_from_content" in self.options or self.env.config.needs_title_from_content

    @property
    def docname(self):
        return self.state.document.settings.env.docname

    @property
    def trimmed_title(self):
        title = self.full_title
        max_length = self.max_title_length
        if max_length == -1 or len(title) <= max_length:
            return title
        elif max_length <= 3:
            return title[: self.max_title_length]
        else:
            return title[: self.max_title_length - 3] + "..."

    @property
    def max_title_length(self):
        return self.state.document.settings.env.config.needs_max_title_length

    # ToDo. Keep this in directive
    def _get_full_title(self):
        """
        Determines the title for the need in order of precedence:
        directive argument, first sentence of requirement (if
        `:title_from_content:` was set, and '' if no title is to be derived."""
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


def get_sections_and_signature_and_needs(need_info):
    """Gets the hierarchy of the section nodes as a list starting at the
    section of the current need and then its parent sections"""
    sections = []
    parent_needs = []
    signature = None
    current_node = need_info["target_node"]
    while current_node:
        if isinstance(current_node, nodes.section):
            title = current_node.children[0].astext()
            # If using auto-section numbering, then Sphinx inserts
            # multiple non-breaking space unicode characters into the title
            # we'll replace those with a simple space to make them easier to
            # use in filters
            title = NON_BREAKING_SPACE.sub(" ", title)
            sections.append(title)

        # Checking for a signature defined "above" the need.
        # Used and set normally by directives like automodule.
        # Only check as long as we haven't found a signature
        if signature and current_node.parent and current_node.parent.children:
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
        if isinstance(current_node, Need):
            parent_needs.append(current_node["refid"])  # Store the need id, not more

        current_node = getattr(current_node, "parent", None)
    return sections, signature, parent_needs


def purge_needs(app, env, docname):
    """
    Gets executed, if a doc file needs to be purged/ read in again.
    So this code delete all found needs for the given docname.
    """
    if not hasattr(env, "needs_all_needs"):
        return
    env.needs_all_needs = {key: need for key, need in env.needs_all_needs.items() if need["docname"] != docname}


def add_sections(app, doctree, fromdocname):
    """Add section titles to the needs as additional attributes that can
    be used in tables and filters"""
    needs = getattr(app.builder.env, "needs_all_needs", {})
    for need_info in needs.values():
        sections, signature, parent_needs = get_sections_and_signature_and_needs(need_info)
        need_info["sections"] = sections
        need_info["section_name"] = sections[0] if sections else ""
        need_info["signature"] = signature if signature else ""
        need_info["parent_needs"] = parent_needs
        need_info["parent_need"] = parent_needs[0] if parent_needs else None

        # for parent_need_id in need_info["parent_needs"]:
        #     needs[parent_need_id]["child_needs"].append(need_info["id"])


def process_need_nodes(app, doctree, fromdocname):
    """
    Event handler to add title meta data (status, tags, links, ...) information to the Need node.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    if not app.config.needs_include_needs:
        for node in doctree.traverse(Need):
            node.parent.remove(node)
        return

    env = app.builder.env

    # If no needs were defined, we do not need to do anything
    if not hasattr(env, "needs_all_needs"):
        return

    # Call dynamic functions and replace related note data with their return values
    resolve_dynamic_values(env)

    # check if we have dead links
    check_links(env)

    # Create back links of common links and extra links
    for links in env.config.needs_extra_links:
        create_back_links(env, links["option"])


def print_need_nodes(app, doctree, fromdocname):
    """
    Finally creates the need-node in the docurils node-tree.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    env = app.builder.env
    needs = env.needs_all_needs

    for node_need in doctree.traverse(Need):
        need_id = node_need.attributes["ids"][0]
        need_data = needs[need_id]

        find_and_replace_node_content(node_need, env, need_data)
        for index, attribute in enumerate(node_need.attributes["classes"]):
            node_need.attributes["classes"][index] = check_and_get_content(attribute, need_data, env)

        layout = need_data["layout"] or app.config.needs_default_layout

        build_need(layout, node_need, app)


def check_links(env):
    """
    Checks if set links are valid or are dead (referenced need does not exist.)
    :param env: Sphinx environment
    :return:
    """
    needs = env.needs_all_needs
    extra_links = getattr(env.config, "needs_extra_links", [])
    for need in needs.values():
        for link_type in extra_links:
            dead_links_allowed = link_type.get("allow_dead_links", False)
            for link in need[link_type["option"]]:
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


def create_back_links(env, option):
    """
    Create back-links in all found needs.
    But do this only once, as all needs are already collected and this sorting is for all
    needs and not only for the ones of the current document.

    :param env: sphinx enviroment
    :return: None
    """
    option_back = "{}_back".format(option)
    if env.needs_workflow["backlink_creation_{}".format(option)]:
        return

    needs = env.needs_all_needs
    for key, need in needs.items():
        for link in need[option]:
            link_main = link.split(".")[0]
            try:
                link_part = link.split(".")[1]
            except IndexError:
                link_part = None

            if link_main in needs:
                if key not in needs[link_main][option_back]:
                    needs[link_main][option_back].append(key)

                # Handling of links to need_parts inside a need
                if link_part:
                    if link_part in needs[link_main]["parts"]:
                        if option_back not in needs[link_main]["parts"][link_part].keys():
                            needs[link_main]["parts"][link_part][option_back] = []
                        needs[link_main]["parts"][link_part][option_back].append(key)

    env.needs_workflow["backlink_creation_{}".format(option)] = True


def _fix_list_dyn_func(list):
    """
    This searches a list for dynamic function fragments, which may have been cut by generic searches for ",|;".

    Example:
    `link_a, [[copy('links', need_id)]]` this will be splitted in list of 3 parts:

    #. link_a
    #. [[copy('links'
    #. need_id)]]

    This function fixes the above list to the following:

    #. link_a
    #. [[copy('links', need_id)]]

    :param list: list which may contain splitted function calls
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


def html_visit(self, node):
    """
    Visitor method for Need-node of builder 'html'.
    Does only wrap the Need-content into an extra <div> with class=need
    """
    self.body.append(self.starttag(node, "div", "", CLASS="need"))


def html_depart(self, node):
    self.body.append("</div>")


def latex_visit(self, node):
    pass


def latex_depart(self, node):
    pass
