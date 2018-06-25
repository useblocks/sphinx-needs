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


class Need_ref(nodes.Inline, nodes.Element):
    pass


def process_need_ref(app, doctree, fromdocname):
    for node_need_ref in doctree.traverse(Need_ref):
        env = app.builder.env
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(app.builder,
                                    fromdocname,
                                    fromdocname,
                                    'Unknown need',
                                    node_need_ref[0].deepcopy(),
                                    node_need_ref['reftarget'] + '?')

        # If need target exists, let's create the reference
        if node_need_ref['reftarget'] in env.need_all_needs:
            target_need = env.need_all_needs[node_need_ref['reftarget']]
            try:
                link_text = app.config.needs_role_need_template.format(title=target_need["title"],
                                                                       id=target_need["id"],
                                                                       type=target_need["type"],
                                                                       type_name=target_need["type_name"],
                                                                       status=target_need["status"],
                                                                       content=target_need["content"],
                                                                       tags=";".join(target_need["tags"]),
                                                                       links=";".join(target_need["links"]),
                                                                       links_back=";".join(target_need["links_back"]))

                node_need_ref[0].children[0] = nodes.Text(link_text, link_text)

                new_node_ref = make_refnode(app.builder,
                                            fromdocname,
                                            target_need['docname'],
                                            target_need['target_node']['refid'],
                                            node_need_ref[0].deepcopy(),
                                            node_need_ref['reftarget'])
            except NoUri:
                # If the given need id can not be found, we must pass here....
                pass
            except KeyError as e:
                log.warning('Needs: the config parameter needs_role_need_template uses not supported placeholders: %s '
                            % e)

        else:
            log.warning('Needs: linked need %s not found (Line %i of file %s)' % (
                node_need_ref['reftarget'], node_need_ref.line, node_need_ref.source))

        node_need_ref.replace_self(new_node_ref)
