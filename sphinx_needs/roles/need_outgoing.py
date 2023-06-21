from typing import List

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import check_and_calc_base_url_rel_path, unwrap

log = get_logger(__name__)


class NeedOutgoing(nodes.Inline, nodes.Element):  # type: ignore
    pass


def process_need_outgoing(
    app: Sphinx, doctree: nodes.document, fromdocname: str, found_nodes: List[nodes.Element]
) -> None:
    # for node_need_ref in doctree.findall(NeedOutgoing):
    for node_need_ref in found_nodes:
        builder = unwrap(app.builder)
        env = unwrap(builder.env)

        node_link_container = nodes.inline()
        needs_all_needs = getattr(env, "needs_all_needs", {})
        ref_need = needs_all_needs[node_need_ref["reftarget"]]

        report_dead_links = getattr(env.config, "needs_report_dead_links", True)

        # Let's check if NeedIncoming shall follow a specific link type
        if "link_type" in node_need_ref.attributes:
            links = ref_need[node_need_ref.attributes["link_type"]]
            link_type = node_need_ref.attributes["link_type"]
        # if not, follow back to default links
        else:
            links = ref_need["links"]
            link_type = "links"

        link_list = [links] if isinstance(links, str) else links

        for index, link in enumerate(link_list):
            link_split = link.split(".")
            link = link_split[0]
            try:
                link_part = link_split[1]
            except IndexError:
                link_part = None

            # If the need target exists, let's create the reference
            if (link in needs_all_needs and not link_part) or (
                link_part and link in needs_all_needs and link_part in needs_all_needs[link]["parts"]
            ):
                try:
                    target_need = needs_all_needs[link]
                    if link_part and link_part in target_need["parts"]:
                        part_content = target_need["parts"][link_part]["content"]
                        target_title = part_content if len(part_content) < 30 else part_content[:27] + "..."
                        target_id = ".".join([link, link_part])
                    else:
                        target_title = target_need["title"]
                        target_id = target_need["id"]

                    if env.config.needs_show_link_title:
                        link_text = f"{target_title}"

                        if env.config.needs_show_link_id:
                            link_text += f" ({target_id})"
                    else:
                        link_text = target_id

                    if env.config.needs_show_link_type:
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    node_need_ref[0] = nodes.Text(link_text)

                    if not target_need["is_external"]:
                        new_node_ref = make_refnode(
                            builder,
                            fromdocname,
                            target_need["docname"],
                            target_id,
                            node_need_ref[0].deepcopy(),
                            node_need_ref["reftarget"],
                        )
                    else:
                        new_node_ref = nodes.reference(target_need["id"], target_need["id"])
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
                link_text = f"{link}"
                if link_part:
                    link_text += f".{link_part}"
                dead_link_text = nodes.Text(link_text)
                dead_link_para = nodes.inline(classes=["needs_dead_link"])
                dead_link_para.append(dead_link_text)
                node_link_container += dead_link_para

                extra_links = getattr(env.config, "needs_extra_links", [])
                extra_links_dict = {x["option"]: x for x in extra_links}

                # Reduce log level to INFO, if dead links are allowed
                if (
                    "allow_dead_links" in extra_links_dict[link_type]
                    and extra_links_dict[link_type]["allow_dead_links"]
                ):
                    log_level = "INFO"
                else:
                    # Set an extra css class, if link type is not configured to allow dead links
                    dead_link_para.attributes["classes"].append("forbidden")
                    log_level = "WARNING"

                if report_dead_links:
                    if node_need_ref and node_need_ref.line:
                        log.log(
                            log_level,
                            f"Needs: linked need {link} not found "
                            f"(Line {node_need_ref.line} of file {node_need_ref.source})",
                        )
                    else:
                        log.log(
                            log_level,
                            "Needs: outgoing linked need {} not found (document: {}, "
                            "source need {} on line {} )".format(
                                link, ref_need["docname"], ref_need["id"], ref_need["lineno"]
                            ),
                        )

            # If we have several links, we add an empty text between them
            if (index + 1) < len(link_list):
                node_link_container += nodes.Text(", ")

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None")

        node_need_ref.replace_self(node_link_container)
