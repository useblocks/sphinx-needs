from docutils import nodes
from sphinx.environment import NoUri
from sphinx.util.nodes import make_refnode
import sphinx
from pkg_resources import parse_version
sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
log = logging.getLogger(__name__)


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
        ref_need = env.needs_all_needs[node_need_ref['reftarget']]

        # Lets check if Need_incoming shall follow a specific link type
        if "link_type" in node_need_ref.attributes.keys():
            links = ref_need[node_need_ref.attributes['link_type']]
        # if not, follow back to default links
        else:
            links = ref_need["links_back"]

        for index, link in enumerate(links):
            link_split = link.split('.')
            link = link_split[0]
            try:
                link_part = link_split[1]
            except IndexError:
                link_part = None

            # If need target exists, let's create the reference
            if link in env.needs_all_needs:
                target_need = env.needs_all_needs[node_need_ref['reftarget']]
                try:
                    target_need = env.needs_all_needs[link]
                    if link_part is not None and link_part in target_need['parts'].keys():
                        part_content = target_need['parts'][link_part]['content']
                        target_title = part_content if len(part_content) < 30 else part_content[:27] + '...'
                        target_id = '.'.join([link, link_part])
                    else:
                        target_title = target_need["title"]
                        target_id = target_need["id"]

                    if getattr(env.config, "needs_show_link_title", False) is True:
                        link_text = "{title} ({id})".format(title=target_title, id=target_id)
                    else:
                        link_text = target_id
                    if getattr(env.config, "needs_show_link_type", False) is True:
                        link_text += " [{type}]".format(type=target_need["type_name"])

                    # if index+1 < len(ref_need["links"]):
                    #     link_text += ", "
                    node_need_ref[0] = nodes.Text(link_text, link_text)

                    new_node_ref = make_refnode(app.builder,
                                                fromdocname,
                                                target_need['docname'],
                                                target_id,
                                                node_need_ref[0].deepcopy(),
                                                node_need_ref['reftarget'])

                    node_link_container += new_node_ref

                    # If we have several links, we add an empty text between them
                    if index + 1 < len(links):
                        node_link_container += nodes.Text(" ", " ")

                except NoUri:
                    # If the given need id can not be found, we must pass here....
                    pass

            else:
                if node_need_ref is not None and node_need_ref.line is not None:
                    log.warning('Needs: linked need %s not found (Line %i of file %s)' % (
                        link, node_need_ref.line, node_need_ref.source))
                else:
                    log.warning('Needs: outgoing linked need %s not found (document: %s, '
                                'source need %s on line %s )' %
                                (link, ref_need['docname'], ref_need['id'], ref_need['lineno']))

        if len(node_link_container.children) == 0:
            node_link_container += nodes.Text("None", "None")

        node_need_ref.replace_self(node_link_container)
