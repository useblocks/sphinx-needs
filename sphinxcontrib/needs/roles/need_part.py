"""
NeedPart module
---------------
Provides the ability to mark specific parts of a need with an own id.

Most voodoo is done in need.py

"""
from docutils import nodes
import hashlib
import re
import sphinx

from pkg_resources import parse_version

sphinx_version = sphinx.__version__

if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
log = logging.getLogger(__name__)


class NeedPart(nodes.Inline, nodes.Element):
    pass


def process_need_part(app, doctree, fromdocname):
    pass


part_pattern = re.compile(r'\(([\w-]+)\)(.*)')


def update_need_with_parts(env, need, part_nodes):
    for part_node in part_nodes:
        content = part_node.children[0].children[0]  # ->inline->Text
        result = part_pattern.match(content)
        if result is not None:
            inline_id = result.group(1)
            part_content = result.group(2)
        else:
            part_content = content
            inline_id = hashlib.sha1(part_content.encode("UTF-8")).hexdigest().upper()[:3]

        if 'parts' not in need.keys():
            need['parts'] = {}

        if inline_id in need['parts'].keys():
            log.warning("part_need id {} in need {} is already taken. need_part may get overridden.".format(
                inline_id, need['id']))

        need['parts'][inline_id] = {
            'id': inline_id,
            'content': part_content,
            'document': need["docname"],
            'links_back': [],
            'is_part': True,
            'is_need': False,
            'links': [],
        }

        part_id_ref = '{}.{}'.format(need['id'], inline_id)
        part_id_show = inline_id
        part_node['reftarget'] = part_id_ref

        part_link_text = ' {}'.format(part_id_show)
        part_link_node = nodes.Text(part_link_text, part_link_text)
        part_text_node = nodes.Text(part_content, part_content)

        from sphinx.util.nodes import make_refnode

        part_ref_node = make_refnode(env.app.builder,
                                     need['docname'],
                                     need['docname'],
                                     part_id_ref,
                                     part_link_node)
        part_ref_node["classes"] += ['needs-id']

        part_node.children = []
        node_need_part_line = nodes.inline(ids=[part_id_ref], classes=["need-part"])
        node_need_part_line.append(part_text_node)
        node_need_part_line.append(part_ref_node)
        part_node.append(node_need_part_line)


def find_parts(node):
    found_nodes = []
    for child in node.children:
        if isinstance(child, NeedPart):
            found_nodes.append(child)
        else:
            found_nodes += find_parts(child)
    return found_nodes
