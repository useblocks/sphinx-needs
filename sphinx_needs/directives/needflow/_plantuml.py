from __future__ import annotations

import html
from collections.abc import Iterable, Mapping

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs._jinja import render_template_string
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFlowType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.diagrams_common import (
    calculate_link,
    create_legend,
    set_plantuml_paths,
)
from sphinx_needs.directives.needflow._directive import NeedflowPlantuml
from sphinx_needs.directives.utils import no_needs_found_paragraph, report_max_items
from sphinx_needs.filter_common import (
    apply_max_items,
    filter_single_need,
    process_filters,
)
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.needs_schema import LinkSchema
from sphinx_needs.utils import remove_node_from_tree
from sphinx_needs.variants import match_variants
from sphinx_needs.views import NeedsView

from ._shared import (
    create_filter_paragraph,
    filter_by_tree,
    get_root_needs,
    resolve_color,
)

logger = get_logger(__name__)


def make_entity_name(name: str) -> str:
    """Creates a valid PlantUML entity name from the given value."""
    invalid_chars = "-=!#$%^&*[](){}/~'`<>:;"
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def make_entity_names(ids: Iterable[str]) -> dict[str, str]:
    """Create a stable, injective mapping of need ids to PlantUML entity names.

    :func:`make_entity_name` folds every character PlantUML forbids in an entity name
    to ``_``, so distinct need ids can sanitise to the same name -- ``R-1`` and ``R=1``
    both become ``R_1`` -- and would then be drawn as a single node.
    Any id that would reuse an already taken name is therefore given a numeric suffix.

    The ids are processed in sorted order, so the mapping depends only on the set of
    ids and not on the order in which they happen to be filtered.

    :param ids: The complete ids of all needs to be rendered.
    :return: A mapping of each id to a unique PlantUML entity name.
    """
    entity_names: dict[str, str] = {}
    taken: set[str] = set()
    for id in sorted(set(ids)):
        name = base = make_entity_name(id)
        suffix = 1
        while name in taken:
            suffix += 1
            name = f"{base}_{suffix}"
        taken.add(name)
        entity_names[id] = name
    return entity_names


def get_entity_name(entity_names: Mapping[str, str], id: str) -> str:
    """Look up the PlantUML entity name of a need id.

    :param entity_names: The mapping created by :func:`make_entity_names`.
    :param id: The complete id of the need.
    :return: The mapped entity name, or a direct conversion for an unmapped id.
    """
    return entity_names.get(id) or make_entity_name(id)


def get_need_node_rep_for_plantuml(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    needs_view: NeedsView,
    need_info: NeedItem | NeedPartItem,
    entity_names: Mapping[str, str],
) -> str:
    """Calculate need node representation for plantuml.

    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    needs_config = NeedsSphinxConfig(app.config)

    node_text = render_template_string(
        needs_config.diagram_template,
        {**need_info.filter_context(), **needs_config.render_context},
        autoescape=False,
    )

    node_link = calculate_link(app, need_info, fromdocname)

    node_colors = []
    if need_info["type_color"]:
        # We set # later, as the user may not have given a color and the node must get highlighted
        node_colors.append(need_info["type_color"].replace("#", ""))

    if current_needflow["highlight"] and filter_single_need(
        need_info, needs_config, current_needflow["highlight"], needs_view.values()
    ):
        node_colors.append("line:FF0000")

    elif current_needflow["border_color"]:
        color = resolve_color(
            match_variants(
                current_needflow["border_color"],
                need_info.filter_context(),
                needs_config.variants,
                location=(current_needflow["docname"], current_needflow["lineno"]),
            )
        )
        if color:
            # the whole color list is prefixed with a single "#" below
            node_colors.append(f"line:{color}")

    # need parts style use default "rectangle"
    node_style = need_info["type_style"] if need_info["is_need"] else "rectangle"

    # node representation for plantuml
    color_suffix = f" #{';'.join(node_colors)}" if node_colors else ""
    need_node_code = '{style} "{node_text}" as {id} [[{link}]]{color_suffix}'.format(
        id=get_entity_name(entity_names, need_info["id_complete"]),
        node_text=node_text,
        link=node_link,
        color_suffix=color_suffix,
        style=node_style,
    )
    return need_node_code


def walk_curr_need_tree(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    needs_view: NeedsView,
    found_needs: list[NeedItem | NeedPartItem],
    need: NeedItem | NeedPartItem,
    entity_names: Mapping[str, str],
) -> str:
    """
    Walk through each need to find all its child needs and need parts recursively and wrap them together in nested structure.

    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """

    curr_need_tree = ""

    if not need["parts"] and not need["parent_needs_back"]:
        return curr_need_tree

    # We do have embedded needs or need parts, so we will add a open "{"
    curr_need_tree += "{\n"

    if need["is_need"] and need["parts"]:
        # add comment for easy debugging
        curr_need_tree += "'parts:\n"
        for need_part_id in need["parts"]:
            # cal need part node
            need_part_id = need["id"] + "." + need_part_id
            # get need part from need part id
            for found_need in found_needs:
                if need_part_id == found_need["id_complete"]:
                    curr_need_tree += (
                        get_need_node_rep_for_plantuml(
                            app,
                            fromdocname,
                            current_needflow,
                            needs_view,
                            found_need,
                            entity_names,
                        )
                        + "\n"
                    )
                    break

    # check if curr need has children
    if need["parent_needs_back"]:
        # add comment for easy debugging
        curr_need_tree += "'child needs:\n"
        # walk through all child needs one by one
        for curr_child_need_id in need["parent_needs_back"]:
            for curr_child_need in found_needs:
                if curr_child_need["id_complete"] == curr_child_need_id:
                    curr_need_tree += get_need_node_rep_for_plantuml(
                        app,
                        fromdocname,
                        current_needflow,
                        needs_view,
                        curr_child_need,
                        entity_names,
                    )
                    # check curr need child has children or has parts
                    if curr_child_need["parent_needs_back"] or curr_child_need["parts"]:
                        curr_need_tree += walk_curr_need_tree(
                            app,
                            fromdocname,
                            current_needflow,
                            needs_view,
                            found_needs,
                            curr_child_need,
                            entity_names,
                        )
                    # add newline for next element
                    curr_need_tree += "\n"
                    break

    # We processed embedded needs or need parts, so we will close with "}"
    curr_need_tree += "}"

    return curr_need_tree


def cal_needs_node(
    app: Sphinx,
    fromdocname: str,
    current_needflow: NeedsFlowType,
    needs_view: NeedsView,
    found_needs: list[NeedItem | NeedPartItem],
    entity_names: Mapping[str, str],
) -> str:
    """Calculate and get needs node representaion for plantuml including all child needs and need parts.

    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    top_needs = get_root_needs(found_needs)
    curr_need_tree = ""
    for top_need in top_needs:
        top_need_node = get_need_node_rep_for_plantuml(
            app, fromdocname, current_needflow, needs_view, top_need, entity_names
        )
        curr_need_tree += (
            top_need_node
            + walk_curr_need_tree(
                app,
                fromdocname,
                current_needflow,
                needs_view,
                found_needs,
                top_need,
                entity_names,
            )
            + "\n"
        )
    return curr_need_tree


@measure_time("needflow_plantuml")
def process_needflow_plantuml(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # Replace all needflow nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    env_data = SphinxNeedsData(env)
    needs_view = env_data.get_needs_view()
    needs_schema = env_data.get_schema()

    link_type_names = [link.name.upper() for link in needs_schema.iter_link_fields()]
    allowed_link_types_options = [link.upper() for link in needs_config.flow_link_types]

    node: NeedflowPlantuml
    for node in found_nodes:  # type: ignore[assignment]
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        current_needflow: NeedsFlowType = node.attributes

        option_link_types = [link.upper() for link in current_needflow["link_types"]]
        for lt in option_link_types:
            if lt not in link_type_names:
                log_warning(
                    logger,
                    "Unknown link type {link_type} in needflow {flow}. Allowed values: {link_types}".format(
                        link_type=lt,
                        flow=current_needflow["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    "needflow",
                    location=node,
                )

        # compute the allowed link types
        allowed_link_types: list[LinkSchema] = []
        for link_field in needs_schema.iter_link_fields():
            # Skip link-type handling, if it is not part of a specified list of allowed link_types or
            # if not part of the overall configuration of needs_flow_link_types
            if (
                current_needflow["link_types"]
                and link_field.name.upper() not in option_link_types
            ) or (
                not current_needflow["link_types"]
                and link_field.name.upper() not in allowed_link_types_options
            ):
                continue
            # skip creating links from child needs to their own parent need
            if link_field.name == "parent_needs":
                continue
            allowed_link_types.append(link_field)

        try:
            if "sphinxcontrib.plantuml" not in app.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import generate_name, plantuml
        except ImportError:
            error_node = nodes.error()
            para = nodes.paragraph()
            text = nodes.Text("PlantUML is not available!")
            para += text
            error_node.append(para)
            node.replace_self(error_node)
            continue

        content: list[nodes.Element] = []

        need_values = (
            filter_by_tree(
                needs_view,
                root_id,
                [lt.name for lt in allowed_link_types],
                current_needflow["root_direction"],
                current_needflow["root_depth"],
            )
            if (root_id := current_needflow.get("root_id"))
            else needs_view
        )

        found_needs = process_filters(
            app,
            need_values,
            current_needflow,
            origin="needflow",
            location=node,
        )
        found_needs, total_needs = apply_max_items(
            found_needs, current_needflow.get("max_items"), needs_config
        )

        if found_needs:
            plantuml_block_text = ".. plantuml::\n\n   @startuml   @enduml"
            puml_node = plantuml(plantuml_block_text)
            # TODO if an alt is not set then sphinxcontrib.plantuml uses the plantuml source code as alt text.
            # I think this is not great, but currently setting a more sensible default breaks some tests
            if current_needflow["alt"]:
                puml_node["alt"] = current_needflow["alt"]

            # Add source origin
            puml_node.line = current_needflow["lineno"]
            puml_node.source = env.doc2path(current_needflow["docname"])

            puml_node["uml"] = "@startuml\n"

            # Adding config
            config = current_needflow["config"]
            if config and len(config) >= 3:
                # Remove all empty lines
                config = "\n".join(
                    [line.strip() for line in config.split("\n") if line.strip()]
                )
                puml_node["uml"] += "\n' Config\n\n"
                puml_node["uml"] += config
                puml_node["uml"] += "\n\n"

            # the entity names must be assigned for the whole diagram at once,
            # so that ids sanitising to the same name stay distinct nodes
            entity_names = make_entity_names(
                need["id_complete"] for need in found_needs
            )

            puml_node["uml"] += "\n' Nodes definition \n\n"
            puml_node["uml"] += cal_needs_node(
                app,
                fromdocname,
                current_needflow,
                needs_view,
                found_needs,
                entity_names,
            )

            puml_node["uml"] += "\n' Connection definition \n\n"
            puml_node["uml"] += render_connections(
                found_needs,
                allowed_link_types,
                current_needflow["show_link_names"] or needs_config.flow_show_links,
                entity_names,
            )

            # Create a legend
            if current_needflow["show_legend"]:
                puml_node["uml"] += create_legend(needs_config.types)

            puml_node["uml"] += "\n@enduml"
            set_plantuml_paths(puml_node, env, current_needflow["docname"])

            scale = int(current_needflow["scale"])
            # if scale != 100:
            puml_node["scale"] = scale

            puml_node = nodes.figure("", puml_node)

            if current_needflow["align"]:
                puml_node["align"] = current_needflow["align"]
            else:
                puml_node["align"] = "center"

            if current_needflow["caption"]:
                # Make the caption to a link to the original file.
                try:
                    if "SVG" in app.config.plantuml_output_format.upper():
                        file_ext = "svg"
                    else:
                        file_ext = "png"
                except Exception:
                    file_ext = "png"

                gen_flow_link = generate_name(app, puml_node.children[0], file_ext)
                current_file_parts = fromdocname.split("/")
                subfolder_amount = len(current_file_parts) - 1
                img_locaton = (
                    "../" * subfolder_amount
                    + "_images/"
                    + gen_flow_link[0].split("/")[-1]
                )
                flow_ref = nodes.reference(
                    "t", current_needflow["caption"], refuri=img_locaton
                )
                puml_node += nodes.caption("", "", flow_ref)

            # Add lineno to node
            puml_node.line = current_needflow["lineno"]

            content.append(puml_node)
        else:  # no needs found
            content.append(
                no_needs_found_paragraph(current_needflow.get("filter_warning"))
            )

        if len(found_needs) < total_needs:
            content.append(
                report_max_items(
                    len(found_needs),
                    total_needs,
                    origin="needflow",
                    location=node,
                )
            )

        if current_needflow["show_filters"]:
            para = create_filter_paragraph(current_needflow)
            content.append(para)

        # We have to restrustructer the needflow
        # If this block should be organized differently
        if current_needflow["debug"] and found_needs:
            # We can only access puml_node if found_needs is set.
            # Otherwise it was not been set, or we get outdated data
            debug_container = nodes.container()
            if isinstance(puml_node, nodes.figure):
                data = puml_node.children[0]["uml"]  # type: ignore[index]
            else:
                data = puml_node["uml"]
            data = "\n".join([html.escape(line) for line in data.split("\n")])
            debug_para = nodes.raw("", f"<pre>{data}</pre>", format="html")
            debug_container += debug_para
            content.append(debug_container)

        node.replace_self(content)


def render_connections(
    found_needs: list[NeedItem | NeedPartItem],
    allowed_link_types: list[LinkSchema],
    show_links: bool,
    entity_names: Mapping[str, str],
) -> str:
    """
    Render the connections between the needs.

    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    puml_connections = ""
    for need_info in found_needs:
        for link_type in allowed_link_types:
            for link in need_info[link_type.name]:
                # Do not create an links, if the link target is not part of the search result.
                if link not in [
                    x["id"] for x in found_needs if x["is_need"]
                ] and link not in [
                    x["id_complete"] for x in found_needs if x["is_part"]
                ]:
                    continue

                if show_links:
                    desc = link_type.display.outgoing + "\\n"
                    comment = f": {desc}"
                else:
                    comment = ""

                # If source or target of link is a need_part, a specific style is needed
                if "." in link or "." in need_info["id_complete"]:
                    link_style = f"[{link_type.display.style_part}]"
                else:
                    link_style = (
                        f"[{link_type.display.style}]"
                        if link_type.display.style
                        else ""
                    )

                # TODO also use link_type.display.color?
                puml_connections += "{id} {style_start}{link_style}{style_end} {link}{comment}\n".format(
                    id=get_entity_name(entity_names, need_info["id_complete"]),
                    link=get_entity_name(entity_names, link),
                    comment=comment,
                    link_style=link_style,
                    style_start=link_type.display.style_start,
                    style_end=link_type.display.style_end,
                )
    return puml_connections
