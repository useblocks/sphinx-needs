from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import check_and_calc_base_url_rel_path, unwrap

log = get_logger(__name__)


class NeedRef(nodes.Inline, nodes.Element):
    pass


def process_need_ref(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)
    for node_need_ref in doctree.traverse(NeedRef):
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(
            builder,
            fromdocname,
            fromdocname,
            "Unknown need",
            node_need_ref[0].deepcopy(),
            node_need_ref["reftarget"] + "?",
        )

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
                    title = title if len(title) < max_length else f"{title[: max_length - 3]}..."

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

                node_need_ref[0].children[0] = nodes.Text(link_text)

                if not target_need.get("is_external", False):
                    new_node_ref = make_refnode(
                        builder,
                        fromdocname,
                        target_need["docname"],
                        node_need_ref["reftarget"],
                        node_need_ref[0].deepcopy(),
                        node_need_ref["reftarget"],
                    )
                else:
                    new_node_ref = nodes.reference(target_need["id"], target_need["id"])
                    new_node_ref["refuri"] = check_and_calc_base_url_rel_path(target_need["external_url"], fromdocname)
                    new_node_ref["classes"].append(target_need["external_css"])
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
