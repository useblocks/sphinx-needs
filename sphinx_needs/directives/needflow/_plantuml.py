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
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.utils import remove_node_from_tree

from ._model import (
    GraphNode,
    NeedflowGraph,
    build_graph,
    resolve_link_types,
)
from ._shared import create_filter_paragraph

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

    Every id that is rendered is mapped up front, so an unmapped id means an emission
    site was not given the mapping of the diagram it is drawing. That would silently
    reintroduce the collisions :func:`make_entity_names` exists to prevent, so it is
    reported; a diagram with plainer names is still better than a failed build, hence
    the direct conversion is returned rather than raising.

    :param entity_names: The mapping created by :func:`make_entity_names`.
    :param id: The complete id of the need.
    :return: The mapped entity name, or a direct conversion for an unmapped id.
    """
    if (name := entity_names.get(id)) is not None:
        return name
    log_warning(
        logger,
        f"Need id {id!r} was not mapped to a plantuml entity name, "
        "so it may collide with another need in the diagram",
        "needflow",
        location=None,
    )
    return make_entity_name(id)


def get_need_node_rep_for_plantuml(
    app: Sphinx,
    fromdocname: str,
    graph_node: GraphNode,
    entity_names: Mapping[str, str],
) -> str:
    """Emit the plantuml representation of a single need or need part.

    :param graph_node: The node to emit, carrying its resolved presentation.
    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    needs_config = NeedsSphinxConfig(app.config)
    need_info = graph_node.need
    presentation = graph_node.presentation

    node_text = render_template_string(
        needs_config.diagram_template,
        {**need_info.filter_context(), **needs_config.render_context},
        autoescape=False,
    )

    node_link = calculate_link(app, need_info, fromdocname)

    node_colors = []
    if presentation.type_color:
        # We set # later, as the user may not have given a color and the node must get highlighted
        node_colors.append(presentation.type_color.replace("#", ""))

    if presentation.highlight:
        node_colors.append("line:FF0000")
    elif presentation.border_color:
        # the whole color list is prefixed with a single "#" below
        node_colors.append(f"line:{presentation.border_color}")

    # node representation for plantuml
    color_suffix = f" #{';'.join(node_colors)}" if node_colors else ""
    need_node_code = '{style} "{node_text}" as {id} [[{link}]]{color_suffix}'.format(
        id=get_entity_name(entity_names, need_info["id_complete"]),
        node_text=node_text,
        link=node_link,
        color_suffix=color_suffix,
        style=presentation.type_style,
    )
    return need_node_code


def walk_curr_need_tree(
    app: Sphinx,
    fromdocname: str,
    graph_node: GraphNode,
    entity_names: Mapping[str, str],
) -> str:
    """Emit the need parts and child needs of a need, as a nested plantuml block.

    .. note:: Whether a block is opened, and whether each comment is written, is decided
       from the need itself rather than from what is drawn.  A need whose parts and
       children were all filtered out therefore still gets an (empty) block; it is kept
       as is.

    :param graph_node: The node whose nested nodes are to be emitted.
    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    need = graph_node.need
    curr_need_tree = ""

    if not need["parts"] and not need["parent_needs_back"]:
        return curr_need_tree

    # We do have embedded needs or need parts, so we will add a open "{"
    curr_need_tree += "{\n"

    if need["is_need"] and need["parts"]:
        # add comment for easy debugging
        curr_need_tree += "'parts:\n"
        for part_node in graph_node.parts:
            curr_need_tree += (
                get_need_node_rep_for_plantuml(
                    app, fromdocname, part_node, entity_names
                )
                + "\n"
            )

    # check if curr need has children
    if need["parent_needs_back"]:
        # add comment for easy debugging
        curr_need_tree += "'child needs:\n"
        # walk through all child needs one by one
        for child_node in graph_node.children:
            curr_need_tree += get_need_node_rep_for_plantuml(
                app, fromdocname, child_node, entity_names
            )
            curr_need_tree += walk_curr_need_tree(
                app, fromdocname, child_node, entity_names
            )
            # add newline for next element
            curr_need_tree += "\n"

    # We processed embedded needs or need parts, so we will close with "}"
    curr_need_tree += "}"

    return curr_need_tree


def cal_needs_node(
    app: Sphinx,
    fromdocname: str,
    graph: NeedflowGraph,
    entity_names: Mapping[str, str],
) -> str:
    """Emit the plantuml node definitions of a whole diagram.

    :param graph: The graph to emit.
    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    curr_need_tree = ""
    for root in graph.roots:
        curr_need_tree += (
            get_need_node_rep_for_plantuml(app, fromdocname, root, entity_names)
            + walk_curr_need_tree(app, fromdocname, root, entity_names)
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
    needs_schema = env_data.get_schema()

    node: NeedflowPlantuml
    for node in found_nodes:  # type: ignore[assignment]
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        current_needflow: NeedsFlowType = node.attributes

        allowed_link_types = resolve_link_types(
            current_needflow,
            schema=needs_schema,
            config=needs_config,
            location=node,
        )

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

        graph = build_graph(
            app,
            current_needflow,
            allowed_link_types,
            location=node,
            variant_location=(current_needflow["docname"], current_needflow["lineno"]),
        )
        found_needs = graph.needs

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
            puml_node["uml"] += cal_needs_node(app, fromdocname, graph, entity_names)

            puml_node["uml"] += "\n' Connection definition \n\n"
            puml_node["uml"] += render_connections(graph, entity_names)

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

        if len(found_needs) < graph.total_needs:
            content.append(
                report_max_items(
                    len(found_needs),
                    graph.total_needs,
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


def render_connections(graph: NeedflowGraph, entity_names: Mapping[str, str]) -> str:
    """Emit the plantuml connections between the needs.

    .. note:: An edge is emitted even when one of its ends is not drawn as a node -- a
       need part whose need was filtered out, say -- in which case plantuml creates a
       bare node for it; it is kept as is.

    :param graph: The graph to emit the connections of.
    :param entity_names: The id to entity name mapping of :func:`make_entity_names`.
    """
    puml_connections = ""
    for edge in graph.edges:
        if graph.show_link_names:
            desc = edge.link_type.display.outgoing + "\\n"
            comment = f": {desc}"
        else:
            comment = ""

        # If source or target of link is a need_part, a specific style is needed
        link_style = f"[{edge.style}]" if (edge.is_part or edge.style) else ""

        source = get_entity_name(entity_names, edge.source_id)
        target = get_entity_name(entity_names, edge.target_id)
        arrow = (
            edge.link_type.display.style_start
            + link_style
            + edge.link_type.display.style_end
        )
        # TODO also use link_type.display.color?
        puml_connections += f"{source} {arrow} {target}{comment}\n"
    return puml_connections
