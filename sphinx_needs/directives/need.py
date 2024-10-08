from __future__ import annotations

import re
from typing import Any, Sequence

from docutils import nodes
from sphinx.addnodes import desc_name, desc_signature
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, add_need
from sphinx_needs.config import NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.defaults import NEED_DEFAULT_OPTIONS
from sphinx_needs.directives.needextend import Needextend, extend_needs_data
from sphinx_needs.functions.functions import (
    check_and_get_content,
    find_and_replace_node_content,
    resolve_dynamic_values,
    resolve_variants_options,
)
from sphinx_needs.layout import build_need_repr
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_constraints import process_constraints
from sphinx_needs.nodes import Need
from sphinx_needs.utils import (
    add_doc,
    profile,
    remove_node_from_tree,
    split_need_id,
)

LOGGER = get_logger(__name__)

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

    @measure_time("need")
    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.env.config)

        delete_opt = self.options.get("delete")
        collapse = self.options.get("collapse")
        jinja_content = self.options.get("jinja_content")
        hide = "hide" in self.options

        id = self.options.get("id")
        status = self.options.get("status")
        tags = self.options.get("tags", "")
        style = self.options.get("style")
        layout = self.options.get("layout", "")
        template = self.options.get("template")
        pre_template = self.options.get("pre_template")
        post_template = self.options.get("post_template")
        constraints = self.options.get("constraints", [])

        title = self._get_title(needs_config)

        need_extra_options = {}
        for extra_link in needs_config.extra_links:
            need_extra_options[extra_link["option"]] = self.options.get(
                extra_link["option"], ""
            )

        for extra_option in NEEDS_CONFIG.extra_options:
            need_extra_options[extra_option] = self.options.get(extra_option, "")

        try:
            need_nodes = add_need(
                self.env.app,
                self.state,
                self.env.docname,
                self.lineno,
                need_type=self.name,
                title=title,
                id=id,
                content=self.content,
                lineno_content=self.content_offset + 1,
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
                constraints=constraints,
                **need_extra_options,
            )
        except InvalidNeedException as err:
            log_warning(
                LOGGER,
                f"Need could not be created: {err.message}",
                "create_need",
                location=self.get_location(),
            )
            return []
        add_doc(self.env, self.env.docname)
        return need_nodes

    def _get_title(self, config: NeedsSphinxConfig) -> str:
        """Determines the title for the need in order of precedence:
        directive argument, first sentence of requirement
        (if `:title_from_content:` was set, and '' if no title is to be derived).
        """
        if len(self.arguments) > 0:  # a title was passed
            if "title_from_content" in self.options:
                log_warning(
                    LOGGER,
                    "need directive has :title_from_content: set, but a title was provided.",
                    "title",
                    location=self.get_location(),
                )
            return self.arguments[0]  # type: ignore[no-any-return]
        elif "title_from_content" in self.options or config.title_from_content:
            first_sentence = re.split(r"[.\n]", "\n".join(self.content))[0]
            if not first_sentence:
                log_warning(
                    LOGGER,
                    ":title_from_content: set, but no content provided.",
                    "title",
                    location=self.get_location(),
                )
            return first_sentence or ""
        else:
            return ""


def get_sections_and_signature_and_needs(
    need_node: nodes.Node | None,
) -> tuple[list[str], nodes.Text | None, list[str]]:
    """Gets the hierarchy of the section nodes as a list starting at the
    section of the current need and then its parent sections"""
    sections = []
    parent_needs: list[str] = []
    signature = None
    current_node = need_node
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
        if not signature and current_node.parent and current_node.parent.children:
            for sibling in current_node.parent.children:
                # We want to check only "above" current node, so no need to check sibling after current_node.
                if sibling == current_node:
                    break
                if isinstance(sibling, desc_signature):
                    # Check the child of the found signature for the text content/node.
                    for desc_child in sibling.children:
                        if isinstance(desc_child, desc_name) and isinstance(
                            desc_child.children[0], nodes.Text
                        ):
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
    SphinxNeedsData(env).remove_doc(docname)


def analyse_need_locations(app: Sphinx, doctree: nodes.document) -> None:
    """Determine the location of each need in the doctree,
    relative to its parent section(s) and need(s).

    This data is added to the need's data stored in the Sphinx environment,
    so that it can be used in tables and filters.

    Once this data is determined, any hidden needs
    (i.e. ones that should not be rendered in the output)
    are removed from the doctree.
    """
    env = app.env

    needs = SphinxNeedsData(env).get_needs_mutable()

    hidden_needs: list[Need] = []
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
        sections, signature, parent_needs = get_sections_and_signature_and_needs(
            previous_sibling(need_node)
        )

        # append / set values from need
        if sections:
            need_info["sections"] = sections
            need_info["section_name"] = sections[0]

        if signature:
            need_info["signature"] = signature

        if parent_needs:
            need_info["parent_needs"] = parent_needs
            need_info["parent_need"] = parent_needs[0]

        if need_node.get("hidden"):
            hidden_needs.append(need_node)

    # now we have gathered all the information we need,
    # we can remove the hidden needs from the doctree
    for need_node in hidden_needs:
        if need_node.parent is not None:
            need_node.parent.remove(need_node)


def previous_sibling(node: nodes.Node) -> nodes.Node | None:
    """Return preceding sibling node or ``None``."""
    try:
        i = node.parent.index(node)
    except AttributeError:
        return None
    return node.parent[i - 1] if i > 0 else None


@profile("NEEDS_POST_PROCESS")
@measure_time("need_post_process")
def post_process_needs_data(app: Sphinx) -> None:
    """In-place post-processing of needs data.

    This should be called after all needs (and extend) data has been collected.

    This function is idempotent;
    it will only be run on the first call, and will not be run again.

    After this function has been run, one should assume that the needs data is finalised,
    and so in principle should be treated as read-only.
    """
    needs_data = SphinxNeedsData(app.env)
    if not needs_data.needs_is_post_processed:
        needs_config = NeedsSphinxConfig(app.config)
        needs = needs_data.get_needs_mutable()
        app.emit("needs-before-post-processing", needs)
        extend_needs_data(needs, needs_data.get_or_create_extends(), needs_config)
        resolve_dynamic_values(needs, app)
        resolve_variants_options(needs, needs_config, app.builder.tags)
        check_links(needs, needs_config)
        create_back_links(needs, needs_config)
        process_constraints(needs, needs_config)
        app.emit("needs-before-sealing", needs)
        needs_data.needs_is_post_processed = True


def process_need_nodes(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    """
    Event handler to add title meta data (status, tags, links, ...) information to the Need node. Also processes
    constraints.
    """
    needs_config = NeedsSphinxConfig(app.config)
    if not needs_config.include_needs:
        for node in doctree.findall(Need):
            if node.parent is not None:
                node.parent.remove(node)
        return

    needs_data = SphinxNeedsData(app.env)

    # If no needs were defined, we do not need to do anything
    if not needs_data.get_needs_view():
        return

    for extend_node in list(doctree.findall(Needextend)):
        remove_node_from_tree(extend_node)

    format_need_nodes(app, doctree, fromdocname, list(doctree.findall(Need)))


@profile("NEED_FORMAT")
def format_need_nodes(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_needs_nodes: list[Need],
) -> None:
    """Replace need nodes in the document with node trees suitable for output"""
    env = app.env
    needs = SphinxNeedsData(env).get_needs_view()

    # We try to avoid findall as much as possibles. so we reuse the already found need nodes in the current document.
    # for node_need in doctree.findall(Need):
    for node_need in found_needs_nodes:
        need_id = node_need.attributes["ids"][0]
        need_data = needs[need_id]

        if need_data["hide"]:
            remove_node_from_tree(node_need)
            continue

        find_and_replace_node_content(node_need, env, need_data)
        for index, attribute in enumerate(node_need.attributes["classes"]):
            node_need.attributes["classes"][index] = check_and_get_content(
                attribute, need_data, env, node_need
            )

        rendered_node = build_need_repr(node_need, need_data, app, docname=fromdocname)
        node_need.parent.replace(node_need, rendered_node)


def check_links(needs: NeedsMutable, config: NeedsSphinxConfig) -> None:
    """Checks if set links are valid or are dead (referenced need does not exist.)

    For needs with dead links, an extra ``has_dead_links`` field is added and,
    if the link is not allowed to be dead,
    the ``has_forbidden_dead_links`` field is also added.
    """
    extra_links = config.extra_links
    report_dead_links = config.report_dead_links
    for need in needs.values():
        for link_type in extra_links:
            _value = need[link_type["option"]]  # type: ignore[literal-required]
            need_link_value = [_value] if isinstance(_value, str) else _value
            for need_id_full in need_link_value:
                need_id_main, need_id_part = split_need_id(need_id_full)

                if need_id_main not in needs or (
                    need_id_main in needs
                    and need_id_part
                    and need_id_part not in needs[need_id_main]["parts"]
                ):
                    need["has_dead_links"] = True
                    if not link_type.get("allow_dead_links", False):
                        need["has_forbidden_dead_links"] = True
                        if report_dead_links:
                            message = f"Need '{need['id']}' has unknown outgoing link '{need_id_full}' in field '{link_type['option']}'"
                            # if the need has been imported from an external URL,
                            # we want to provide that URL as the location of the warning,
                            # otherwise we use the location of the need in the source file
                            if need.get("is_external", False):
                                log_warning(
                                    LOGGER,
                                    f"{need['external_url']}: {message}",
                                    "external_link_outgoing",
                                    None,
                                )
                            else:
                                log_warning(
                                    LOGGER,
                                    message,
                                    "link_outgoing",
                                    location=(need["docname"], need["lineno"]),
                                )


def create_back_links(needs: NeedsMutable, config: NeedsSphinxConfig) -> None:
    """Create back-links in all found needs.

    These are fields for each link type, ``<link_name>_back``,
    which contain a list of all IDs of needs that link to the current need.
    """
    for links in config.extra_links:
        option = links["option"]
        option_back = f"{option}_back"

        for key, need in needs.items():
            need_link_value: list[str] = (
                [need[option]] if isinstance(need[option], str) else need[option]  # type: ignore[literal-required]
            )
            for need_id_full in need_link_value:
                need_id_main, need_id_part = split_need_id(need_id_full)

                if need_id_main in needs:
                    if key not in needs[need_id_main][option_back]:  # type: ignore[literal-required]
                        needs[need_id_main][option_back].append(key)  # type: ignore[literal-required]

                    # Handling of links to need_parts inside a need
                    if need_id_part and need_id_part in needs[need_id_main]["parts"]:
                        if (
                            option_back
                            not in needs[need_id_main]["parts"][need_id_part]
                        ):
                            needs[need_id_main]["parts"][need_id_part][option_back] = []  # type: ignore[literal-required]
                        needs[need_id_main]["parts"][need_id_part][option_back].append(  # type: ignore[literal-required]
                            key
                        )


def _fix_list_dyn_func(list: list[str]) -> list[str]:
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


def html_visit(self: Any, node: nodes.Node) -> None:
    """
    Visitor method for Need-node of builder 'html'.
    Does only wrap the Need-content into an extra <div> with class=need
    """
    self.body.append(self.starttag(node, "div", "", CLASS="need"))


def html_depart(self: Any, node: nodes.Node) -> None:
    """Visitor method for departing Need-node of builder 'html' (closes extra div)"""
    self.body.append("</div>")


def latex_visit(self: Any, node: nodes.Node) -> None:
    """Visitor method for entering Need-node of builder 'latex' (no-op)"""


def latex_depart(self: Any, node: nodes.Node) -> None:
    """Visitor method for departing Need-node of builder 'latex' (no-op)"""
