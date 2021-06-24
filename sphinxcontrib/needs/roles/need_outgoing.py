from docutils import nodes
from sphinx.util.nodes import make_refnode

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0

from sphinxcontrib.needs.logging import get_logger

log = get_logger(__name__)


class NeedOutgoing(nodes.Inline, nodes.Element):
    pass


def process_need_outgoing(app, doctree, fromdocname):
    for node_need_ref in doctree.traverse(NeedOutgoing):
        env = app.builder.env

        node_link_container = nodes.inline()
        ref_need = env.needs_all_needs[node_need_ref["reftarget"]]

        # Lets check if NeedIncoming shall follow a specific link type
        if "link_type" in node_need_ref.attributes.keys():
            links = ref_need[node_need_ref.attributes["link_type"]]
            link_type = node_need_ref.attributes["link_type"]
        # if not, follow back to default links
        else:
            links = ref_need["links"]
            link_type = "links"

        for index, link in enumerate(links):
            link_split = link.split(".")
            link = link_split[0]
            try:
                link_part = link_split[1]
            except IndexError:
                link_part = None

            # If need target exists, let's create the reference
            if (link in env.needs_all_needs and not link_part) or (
                link_part and link in env.needs_all_needs and link_part in env.needs_all_needs[link]["parts"]
            ):
                try:
                    target_need = env.needs_all_needs[link]
                    if link_part and link_part in target_need["parts"].keys():
                        part_content = target_need["parts"][link_part]["content"]
                        target_title = part_content if len(part_content) < 30 else part_content[:27] + "..."
                        target_id = ".".join([link, link_part])
                    else:
                        target_title = target_need["title"]
                        target_id = target_need["id"]

                    if getattr(env.config, "needs_show_link_title"):
                        link_text = "{title} ({id})".format(title=target_title, id=target_id)
                    else:
                        link_text = target_id
                    if getattr(env.config, "needs_show_link_type"):
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    node_need_ref[0] = nodes.Text(link_text, link_text)

                    if not target_need["is_external"]:
                        new_node_ref = make_refnode(
                            app.builder,
                            fromdocname,
                            target_need["docname"],
                            target_id,
                            node_need_ref[0].deepcopy(),
                            node_need_ref["reftarget"],
                        )
                    else:
                        new_node_ref = nodes.reference(target_need["id"], target_need["id"])
                        new_node_ref["refuri"] = target_need["external_url"]
                        new_node_ref["classes"].append(target_need["external_css"])

                    node_link_container += new_node_ref

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                # Lets add a normal text here instead of a link.
                # So really each link set by the user gets shown.
                link_text = f"{link}"
                if link_part:
                    link_text += f".{link_part}"
                dead_link_text = nodes.Text(link_text, link_text)
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
            if (index + 1) < len(links):
                node_link_container += nodes.Text(", ", ", ")

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None", "None")

        node_need_ref.replace_self(node_link_container)
