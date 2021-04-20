from docutils import nodes

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0
from sphinx.util.nodes import make_refnode

from sphinxcontrib.needs.logging import get_logger

log = get_logger(__name__)


class NeedRef(nodes.Inline, nodes.Element):
    pass


def process_need_ref(app, doctree, fromdocname):
    for node_need_ref in doctree.traverse(NeedRef):
        env = app.builder.env
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(
            app.builder,
            fromdocname,
            fromdocname,
            "Unknown need",
            node_need_ref[0].deepcopy(),
            node_need_ref["reftarget"] + "?",
        )

        # findings = re.match(r'([\w ]+)(\<(.*)\>)?', node_need_ref.children[0].rawsource)
        # if findings.group(2):
        #     ref_id = findings.group(3)
        #     ref_name = findings.group(1)
        # else:
        #     ref_id = findings.group(1)
        #     ref_name = None
        ref_id_complete = node_need_ref["reftarget"]
        ref_name = node_need_ref.children[0].children[0]
        # Only use ref_name, if it differs from ref_id
        if str(ref_id_complete) == str(ref_name):
            ref_name = None

        if "." in ref_id_complete:
            ref_id, part_id = ref_id_complete.split(".")
        else:
            ref_id = ref_id_complete
            part_id = None

        if ref_id in env.needs_all_needs:
            target_need = env.needs_all_needs[ref_id]
            try:
                if ref_name:
                    title = ref_name
                elif part_id:
                    title = target_need["parts"][part_id]["content"]
                else:
                    title = target_need["title"]

                # Shorten title, if necessary
                max_length = app.config.needs_role_need_max_title_length
                if max_length > 3:
                    title = title if len(title) < max_length else u"{}...".format(title[: max_length - 3])

                link_text = app.config.needs_role_need_template.format(
                    title=title,
                    id=ref_id_complete,
                    type=target_need["type"],
                    type_name=target_need["type_name"],
                    status=target_need["status"],
                    content=target_need["content"],
                    tags=";".join(target_need["tags"]),
                    links=";".join(target_need["links"]),
                    links_back=";".join(target_need["links_back"]),
                )

                node_need_ref[0].children[0] = nodes.Text(link_text, link_text)

                new_node_ref = make_refnode(
                    app.builder,
                    fromdocname,
                    target_need["docname"],
                    node_need_ref["reftarget"],
                    node_need_ref[0].deepcopy(),
                    node_need_ref["reftarget"],
                )
            except NoUri:
                # If the given need id can not be found, we must pass here....
                pass
            except KeyError as e:
                log.warning(
                    "Needs: the config parameter needs_role_need_template uses not supported placeholders: %s " % e
                )

        else:
            log.warning(
                "Needs: linked need %s not found (Line %i of file %s)"
                % (node_need_ref["reftarget"], node_need_ref.line, node_need_ref.source)
            )

        node_need_ref.replace_self(new_node_ref)
