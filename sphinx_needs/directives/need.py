from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any, Final

from docutils import nodes
from sphinx.addnodes import desc_name, desc_signature
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, add_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.needextend import Needextend, extend_needs_data
from sphinx_needs.functions.functions import (
    check_and_get_content,
    find_and_replace_node_content,
    resolve_functions,
)
from sphinx_needs.layout import build_need_repr
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.need_constraints import process_constraints
from sphinx_needs.need_item import NeedItem, NeedItemSourceDirective
from sphinx_needs.nodes import Need
from sphinx_needs.utils import (
    DummyOptionSpec,
    add_doc,
    coerce_to_boolean,
    profile,
    remove_node_from_tree,
    split_need_id,
)

LOGGER = get_logger(__name__)

NON_BREAKING_SPACE = re.compile("\xa0+")


class NeedDirective(SphinxDirective):
    """Collect the specification for a requirement, validate it and store it."""

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec: Final[DummyOptionSpec] = DummyOptionSpec()
    has_content = True

    options: dict[str, str | None]

    def _log_warning(
        self, message: str, code: WarningSubTypes = "directive", /
    ) -> None:
        """Log a warning with the given message and code."""
        log_warning(
            LOGGER,
            message,
            code,
            location=self.get_location(),
        )

    @measure_time("need")
    def run(self) -> Sequence[nodes.Node]:
        # throughout this function, we gradually pop values from self.options
        # so that we can warn about unknown options at the end
        options: dict[str, str | None] = self.options

        try:
            delete = (
                coerce_to_boolean(options.pop("delete"))
                if "delete" in options
                else False
            )
        except ValueError as err:
            self._log_warning(f"Invalid value for 'delete' option: {err}")
            return []
        if delete:
            return []

        needs_config = NeedsSphinxConfig(self.env.config)

        try:
            # override global title_from_content if user set it in the directive
            title_from_content = (
                coerce_to_boolean(options.pop("title_from_content"))
                if "title_from_content" in options
                else needs_config.title_from_content
            )
        except ValueError as err:
            self._log_warning(f"Invalid value for 'title_from_content' option: {err}")
            return []

        title, full_title = _get_title(
            self.arguments,
            self.content,
            title_optional=needs_config.title_optional,
            title_from_content=title_from_content,
            max_title_length=needs_config.max_title_length,
            warn=self._log_warning,
        )

        id: str | None = None
        collapse: str | bool | None = None
        hide: str | bool | None = None
        jinja_content: bool | None = None
        status: str | None = None
        tags: str | None = None
        style: str | None = None
        layout: str | None = None
        template: str | None = None
        pre_template: str | None = None
        post_template: str | None = None
        constraints: str | None = None
        extras: dict[str, str] = {}
        links: dict[str, str] = {}

        link_keys = {li["option"] for li in needs_config.extra_links}

        while options:
            key, value = options.popitem()
            try:
                match key:
                    case "id":
                        assert value, "'id' must not be empty"
                        id = value
                    case "jinja_content":
                        jinja_content = coerce_to_boolean(value)
                    case "status":
                        status = value or ""
                    case "tags":
                        tags = value or ""
                    case "collapse":
                        collapse = value or ""
                    case "hide":
                        hide = value or ""
                    case "style":
                        style = value or ""
                    case "layout":
                        layout = value or ""
                    case "template":
                        template = value or ""
                    case "pre_template":
                        pre_template = value or ""
                    case "post_template":
                        post_template = value or ""
                    case "constraints":
                        constraints = value or ""
                    case key if key in needs_config.extra_options:
                        extras[key] = value or ""
                    case key if key in link_keys:
                        links[key] = value or ""
                    case _:
                        self._log_warning(f"Unknown option '{key}'")
            except (AssertionError, ValueError) as err:
                self._log_warning(f"Invalid value for '{key}' option: {err}")
                return []

        source = NeedItemSourceDirective(
            docname=self.env.docname,
            lineno=self.lineno,
            lineno_content=self.content_offset + 1,
        )

        try:
            need_nodes = add_need(
                app=self.env.app,
                state=self.state,
                need_source=source,
                need_type=self.name,
                title=title,
                full_title=full_title,
                id=id,
                content=self.content,
                status=status,
                tags=tags,
                template=template,
                pre_template=pre_template,
                post_template=post_template,
                hide=hide,
                collapse=collapse,
                style=style,
                layout=layout,
                jinja_content=jinja_content,
                constraints=constraints,
                **extras,  # type: ignore[arg-type]
                **links,  # type: ignore[arg-type]
            )
        except InvalidNeedException as err:
            self._log_warning(
                f"Need could not be created: {err.message}", "create_need"
            )
            return []
        add_doc(self.env, self.env.docname)
        return need_nodes


def _get_title(
    args: list[str],
    content: str,
    *,
    title_optional: bool,
    title_from_content: bool,
    max_title_length: int,
    warn: Callable[[str], None],
) -> tuple[str, str | None]:
    """Determines the title for the need in order of precedence:
    directive argument, first sentence of requirement
    (if `:title_from_content:` was set, and '' if no title is to be derived).

    :return: The title and the full title (if title was trimmed)
    """
    if len(args) > 0:  # a title was passed
        if title_from_content:
            warn("title_from_content set to True, but a title was provided.")
        return args[0], None
    elif title_from_content:
        first_sentence = re.split(r"[.\n]", "\n".join(content))[0]
        if not first_sentence:
            warn("title_from_content set to True, but no content provided.")
        title = first_sentence or ""
        # Trim title if it is too long
        if max_title_length == -1 or len(title) <= max_title_length:
            return title, None
        elif max_title_length <= 3:
            return title[:max_title_length], title
        else:
            return title[: max_title_length - 3] + "...", title
    else:
        if not title_optional:
            warn("No title given, but title is required by configuration.")
        return "", None


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

        # Fetch values from need
        # Start from the target node, which is a sibling of the current need node
        sections, signature, parent_needs = get_sections_and_signature_and_needs(
            previous_sibling(need_node)
        )

        # append / set values from need
        need_info["sections"] = tuple(sections)
        need_info["signature"] = str(signature) if signature is not None else None
        need_info["parent_needs"] = parent_needs

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
        resolve_functions(app, needs, needs_config)
        update_back_links(needs, needs_config)
        process_constraints(needs, needs_config)
        app.emit("needs-before-sealing", needs)
        # run a last check to ensure all needs are of the correct type
        # this is done as a back-compatibility check,
        # in case users are using sphinx-needs in an unexpected way that may previously work.
        for need in needs.values():
            if not isinstance(need, NeedItem):
                raise AssertionError(
                    f"Found at least one need item that is not a NeedItem instance: {type(need)}\n"
                    "If you are adding needs manually, consider using the add_need API."
                )
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


def update_back_links(needs: NeedsMutable, config: NeedsSphinxConfig) -> None:
    """Update needs with back-links, i.e. for each need A that links to need B,"""
    for need in needs.values():
        need.reset_backlinks()

    for key, need in needs.items():
        dead_links = []

        for link_type, references in need.iter_links_items():
            for need_id_full in references:
                need_id_main, need_id_part = split_need_id(need_id_full)
                if linked_need := needs.get(need_id_main):
                    linked_need.add_backlink(link_type, key)
                    if need_id_part is not None:
                        if linked_part := linked_need.get_part(need_id_part):
                            if link_type not in linked_part.backlinks:
                                linked_part.backlinks[link_type] = []
                            linked_part.backlinks[link_type].append(key)
                        else:
                            dead_links.append((link_type, need_id_full))
                else:
                    dead_links.append((link_type, need_id_full))

        need["has_dead_links"] = bool(dead_links)
        allow_dead_links = {
            li["option"]: li.get("allow_dead_links", False) for li in config.extra_links
        }
        need["has_forbidden_dead_links"] = bool(
            any(not allow_dead_links.get(lt, False) for lt, _ in dead_links)
        )
        if need["has_forbidden_dead_links"] and config.report_dead_links:
            for link_type, need_id_full in dead_links:
                message = f"Need '{need.id}' has unknown outgoing link '{need_id_full}' in field '{link_type}'"
                # if the need has been imported from an external URL,
                # we want to provide that URL as the location of the warning,
                # otherwise we use the location of the need in the source file
                if need["is_external"]:
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
