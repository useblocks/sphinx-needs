from docutils import nodes
from sphinx.environment import NoUri
from sphinx.util.nodes import make_refnode


class Need_outgoing(nodes.Inline, nodes.Element):
    pass


def process_need_outgoing(app, doctree, fromdocname):
    for node_need_ref in doctree.traverse(Need_outgoing):
        env = app.builder.env
        # Let's create a dummy node, for the case we will not be able to create a real reference
        # new_node_ref = make_refnode(app.builder,
        #                             fromdocname,
        #                             fromdocname,
        #                             'Unknown need',
        #                             node_need_ref[0].deepcopy(),
        #                             node_need_ref['reftarget'] + '?')

        node_link_container = nodes.inline()
        ref_need = env.need_all_needs[node_need_ref['reftarget'].upper()]

        for link in ref_need["links"]:
            # If need target exists, let's create the reference
            if link in env.need_all_needs:
                target_need = env.need_all_needs[node_need_ref['reftarget'].upper()]
                try:
                    target_need = env.need_all_needs[link]
                    link_text = "{0} ; ".format(link)
                    node_need_ref[0].children[0] = nodes.Text(link_text, link_text)

                    new_node_ref = make_refnode(app.builder,
                                                fromdocname,
                                                target_need['docname'],
                                                target_need['target']['refid'],
                                                node_need_ref[0].deepcopy(),
                                                node_need_ref['reftarget'].upper())

                    node_link_container += new_node_ref

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                env.warn_node(
                    'Needs: need %s not found' % node_need_ref['reftarget'], node_need_ref)

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None", "None")

        node_need_ref.replace_self(node_link_container)
