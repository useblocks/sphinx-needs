from docutils import nodes
from sphinx.util.nodes import make_refnode

from sphinxcontrib.needs.utils import check_and_calc_base_url_rel_path

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0


class NeedIncoming(nodes.Inline, nodes.Element):
    pass


def process_need_incoming(app, doctree, fromdocname):
    env = app.builder.env

    for node_need_backref in doctree.traverse(NeedIncoming):
        node_link_container = nodes.inline()
        ref_need = env.needs_all_needs[node_need_backref["reftarget"]]

        # Lets check if NeedIncoming shall follow a specific link type
        if "link_type" in node_need_backref.attributes:
            links_back = ref_need[node_need_backref.attributes["link_type"]]
        # if not, follow back to default links
        else:
            links_back = ref_need["links_back"]

        for index, back_link in enumerate(links_back):
            # If need back_link target exists, let's create the reference
            if back_link in env.needs_all_needs:
                try:
                    target_need = env.needs_all_needs[back_link]
                    if env.config.needs_show_link_title:
                        link_text = "{title} ({id})".format(title=target_need["title"], id=target_need["id"])
                    else:
                        link_text = target_need["id"]
                    if env.config.needs_show_link_type:
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    # if index + 1 < len(ref_need["links_back"]):
                    #     link_text += ", "
                    node_need_backref[0] = nodes.Text(link_text, link_text)

                    if not target_need["is_external"]:
                        new_node_ref = make_refnode(
                            app.builder,
                            fromdocname,
                            target_need["docname"],
                            target_need["target_node"]["refid"],
                            node_need_backref[0].deepcopy(),
                            node_need_backref["reftarget"],
                        )
                    else:
                        new_node_ref = nodes.reference(target_need["id"], target_need["id"])
                        new_node_ref["refuri"] = check_and_calc_base_url_rel_path(
                            target_need["external_url"], fromdocname
                        )
                        new_node_ref["classes"].append(target_need["external_css"])

                    node_link_container += new_node_ref

                    # If we have several links, we add an empty text between them
                    if index + 1 < len(links_back):
                        node_link_container += nodes.Text(", ", ", ")

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                env.warn_node("Needs: need %s not found" % node_need_backref["reftarget"], node_need_backref)

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None", "None")

        node_need_backref.replace_self(node_link_container)
