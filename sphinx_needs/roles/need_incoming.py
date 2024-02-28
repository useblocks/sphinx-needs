from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.errors import NoUri
from sphinx_needs.utils import check_and_calc_base_url_rel_path, logger


class NeedIncoming(nodes.Inline, nodes.Element):
    pass


def process_need_incoming(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    builder = app.builder
    env = app.env
    needs_config = NeedsSphinxConfig(env.config)
    all_needs = SphinxNeedsData(env).get_or_create_needs()

    # for node_need_backref in doctree.findall(NeedIncoming):
    for node_need_backref in found_nodes:
        node_link_container = nodes.inline()
        ref_need = all_needs[node_need_backref["reftarget"]]

        # Let's check if NeedIncoming shall follow a specific link type
        if "link_type" in node_need_backref.attributes:
            links_back = ref_need[node_need_backref.attributes["link_type"]]  # type: ignore[literal-required]
        # if not, follow back to default links
        else:
            links_back = ref_need["links_back"]

        for index, back_link in enumerate(links_back):
            # If need back_link target exists, let's create the reference
            if back_link in all_needs:
                try:
                    target_need = all_needs[back_link]
                    if needs_config.show_link_title:
                        link_text = f'{target_need["title"]}'

                        if needs_config.show_link_id:
                            link_text += f' ({target_need["id"]})'
                    else:
                        link_text = target_need["id"]

                    if needs_config.show_link_type:
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    # if index + 1 < len(ref_need["links_back"]):
                    #     link_text += ", "
                    node_need_backref[0] = nodes.Text(link_text)

                    if not target_need["is_external"] and (
                        _docname := target_need["docname"]
                    ):
                        new_node_ref = make_refnode(
                            builder,
                            fromdocname,
                            _docname,
                            target_need["target_id"],
                            node_need_backref[0].deepcopy(),
                            node_need_backref["reftarget"],
                        )
                    else:
                        assert (
                            target_need["external_url"] is not None
                        ), "External URL must not be set"
                        new_node_ref = nodes.reference(
                            target_need["id"], target_need["id"]
                        )
                        new_node_ref["refuri"] = check_and_calc_base_url_rel_path(
                            target_need["external_url"], fromdocname
                        )
                        new_node_ref["classes"].append(target_need["external_css"])

                    node_link_container += new_node_ref

                    # If we have several links, we add an empty text between them
                    if index + 1 < len(links_back):
                        node_link_container += nodes.Text(", ")

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                logger.warning(
                    f"need {node_need_backref['reftarget']} not found [needs]",
                    location=node_need_backref,
                )

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None")

        node_need_backref.replace_self(node_link_container)
