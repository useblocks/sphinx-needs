from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.nodes import make_refnode

from sphinx_needs.nodes import Need
from sphinx_needs.errors import NoUri
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import check_and_calc_base_url_rel_path, unwrap

from collections.abc import Iterable

from typing import Dict

log = get_logger(__name__)


class NeedRef(nodes.Inline, nodes.Element):
    pass

def transform_need_to_dict(need: Need) -> Dict[str, str]:
    '''
    The function will transform a need in a dictionary of strings. Used to 
    be given to a python format string. 
    
    Parameters
    ----------
    need : need
        A need object.

    Returns
    -------
    dict : dictionary of strings
        Can be easily used for python format strings

    '''
    dict_need = {}

    for element in need:
        if isinstance(need[element], str):
            # As string are iterable, we have to handle strings first.
            dict_need[element] = need[element]
        elif isinstance(need[element], list):
            dict_need[element] = ";".join(need[element])
        elif isinstance(need[element], dict):
            dict_need[element] = ";".join( [str(i) for i in need[element].items()] ) 
        elif isinstance(need[element], Iterable):
            dict_need[element] = ";".join( [str(i) for i in need[element] ] )
        else:
            dict_need[element] = need[element]

    return dict_need

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

        prefix = "[["
        postfix = "]]"

        if ref_id in env.needs_all_needs:
            target_need = env.needs_all_needs[ref_id]
            try:
                if ref_name and not prefix in ref_name:
                    # we change the title only to customer refname, if we will not process the ref later.
                    title = ref_name
                elif part_id:
                    title = target_need["parts"][part_id]["content"]
                else:
                    title = target_need["title"]

                # Shorten title, if necessary
                max_length = app.config.needs_role_need_max_title_length
                if max_length > 3:
                    title = title if len(title) < max_length else f"{title[: max_length - 3]}..."

                dict_need = transform_need_to_dict(target_need)
                # we set title and id, after the transform_need_to_dict to overwrite the values
                dict_need["title"] = title
                dict_need["id"] = ref_id_complete

                if ref_name and prefix in ref_name:
                    # if ref_name is set and has prefix to process, we will do so
                    ref_name = ref_name.replace(prefix, "{").replace(postfix, "}")
                    link_text = ref_name.format(**dict_need)
                else:
                    link_text = app.config.needs_role_need_template.format(**dict_need)

                node_need_ref[0].children[0] = nodes.Text(link_text, link_text)

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
