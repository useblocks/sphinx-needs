from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import check_and_calc_base_url_rel_path, split_need_id

log = get_logger(__name__)


class NeedOutgoing(nodes.Inline, nodes.Element):
    pass


def process_need_outgoing(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    builder = app.builder
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    link_lookup = {link["option"]: link for link in needs_config.extra_links}

    # for node_need_ref in doctree.findall(NeedOutgoing):
    for node_need_ref in found_nodes:
        node_link_container = nodes.inline()
        needs_all_needs = SphinxNeedsData(env).get_or_create_needs()
        ref_need = needs_all_needs[node_need_ref["reftarget"]]

        # Let's check if NeedIncoming shall follow a specific link type
        if "link_type" in node_need_ref.attributes:
            links = ref_need[node_need_ref.attributes["link_type"]]  # type: ignore[literal-required]
            link_type = node_need_ref.attributes["link_type"]
        # if not, follow back to default links
        else:
            links = ref_need["links"]
            link_type = "links"

        link_list = [links] if isinstance(links, str) else links

        for index, need_id_full in enumerate(link_list):
            need_id_main, need_id_part = split_need_id(need_id_full)

            # If the need target exists, let's create the reference
            if (need_id_main in needs_all_needs and not need_id_part) or (
                need_id_part
                and need_id_main in needs_all_needs
                and need_id_part in needs_all_needs[need_id_main]["parts"]
            ):
                try:
                    target_need = needs_all_needs[need_id_main]
                    if need_id_part and need_id_part in target_need["parts"]:
                        part_content = target_need["parts"][need_id_part]["content"]
                        target_title = (
                            part_content
                            if len(part_content) < 30
                            else part_content[:27] + "..."
                        )
                        target_id = ".".join([need_id_main, need_id_part])
                    else:
                        target_title = target_need["title"]
                        target_id = target_need["id"]

                    if needs_config.show_link_title:
                        link_text = f"{target_title}"

                        if needs_config.show_link_id:
                            link_text += f" ({target_id})"
                    else:
                        link_text = target_id

                    if needs_config.show_link_type:
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    node_need_ref[0] = nodes.Text(link_text)

                    if not target_need["is_external"] and (
                        _docname := target_need["docname"]
                    ):
                        new_node_ref = make_refnode(
                            builder,
                            fromdocname,
                            _docname,
                            target_id,
                            node_need_ref[0].deepcopy(),
                            node_need_ref["reftarget"],
                        )
                    else:
                        assert (
                            target_need["external_url"] is not None
                        ), "External URL must be set"
                        new_node_ref = nodes.reference(
                            target_need["id"], target_need["id"]
                        )
                        new_node_ref["refuri"] = check_and_calc_base_url_rel_path(
                            target_need["external_url"], fromdocname
                        )
                        new_node_ref["classes"].append(target_need["external_css"])

                    node_link_container += new_node_ref

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                # Let's add a normal text here instead of a link.
                # So really each link set by the user gets shown.
                link_text = f"{need_id_main}"
                if need_id_part:
                    link_text += f".{need_id_part}"
                dead_link_text = nodes.Text(link_text)
                dead_link_para = nodes.inline(classes=["needs_dead_link"])
                dead_link_para.append(dead_link_text)
                node_link_container += dead_link_para

                # add a CSS class for disallowed unknown links
                # note a warning is already emitted when validating the needs list
                # so we don't need to do it here
                if not link_lookup.get(link_type, {}).get("allow_dead_links", False):  # type: ignore
                    dead_link_para.attributes["classes"].append("forbidden")

            # If we have several links, we add an empty text between them
            if (index + 1) < len(link_list):
                node_link_container += nodes.Text(", ")

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None")

        node_need_ref.replace_self(node_link_container)
