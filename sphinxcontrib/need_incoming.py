from docutils import nodes
from sphinx.environment import NoUri
from sphinx.util.nodes import make_refnode


class Need_incoming(nodes.Inline, nodes.Element):
    pass


def process_need_incoming(app, doctree, fromdocname):
    env = app.builder.env

    for node_need_backref in doctree.traverse(Need_incoming):
        # # Let's create a dummy node, for the case we will not be able to create a real reference
        # new_node_ref = make_refnode(app.builder,
        #                             fromdocname,
        #                             fromdocname,
        #                             'Unknown need',
        #                             node_need_backref[0].deepcopy(),
        #                             node_need_backref['reftarget'] + '?')

        node_link_container = nodes.inline()
        ref_need = env.need_all_needs[node_need_backref['reftarget'].upper()]
        for back_link in ref_need["links_back"]:
            # If need back_link target exists, let's create the reference
            if back_link in env.need_all_needs:
                try:
                    target_need = env.need_all_needs[back_link]
                    link_text = "{0} ; ".format(back_link)
                    node_need_backref[0].children[0] = nodes.Text(link_text, link_text)

                    new_node_ref = make_refnode(app.builder,
                                                fromdocname,
                                                target_need['docname'],
                                                target_need['target']['refid'] ,
                                                node_need_backref[0].deepcopy(),
                                                node_need_backref['reftarget'].upper())

                    node_link_container += new_node_ref
                except NoUri:
                    # Irf the given need id can not be found, we must pass here....
                    pass

            else:
                env.warn_node(
                    'Needs: need %s not found' % node_need_backref['reftarget'], node_need_backref)

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None", "None")

        node_need_backref.replace_self(node_link_container)
