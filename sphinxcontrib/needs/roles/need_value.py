from docutils import nodes

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0
from sphinx.util.nodes import make_refnode

from sphinxcontrib.needs.logging import get_logger

log = get_logger(__name__)


class NeedValue(nodes.Inline, nodes.Element):
    pass


def process_need_value(app, doctree, fromdocname):
    for node_need_value in doctree.traverse(NeedValue):
        env = app.builder.env
        # Let's create a dummy node, for the case we will not be able to create a real reference
        new_node_ref = make_refnode(
            app.builder,
            fromdocname,
            fromdocname,
            "Unknown need",
            node_need_value[0].deepcopy(),
            node_need_value["reftarget"] + "?",
        )

        # findings = re.match(r'([\w ]+)(\<(.*)\>)?', node_need_ref.children[0].rawsource)
        # if findings.group(2):
        #     ref_id = findings.group(3)
        #     ref_name = findings.group(1)
        # else:
        #     ref_id = findings.group(1)
        #     ref_name = None
        ref_id_complete = node_need_value["reftarget"]
        ref_name = node_need_value.children[0].children[0]
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

            print(app.config.needs_role_need_value)

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

                dict_need = {}

                for element in target_need:
                    if isinstance(target_need[element], list):
                        dict_need[element] = ";".join(target_need[element])
                    elif isinstance(target_need[element], dict):
                        dict_need[element] = target_need[element]
                    else:
                        dict_need[element] = target_need[element]

                dict_need["title"] = title
                dict_need["id"] = ref_id_complete

                if app.config.needs_role_need_value in dict_need:
                    link_text = dict_need[app.config.needs_role_need_value].format(**dict_need)
                else:
                    link_text = app.config.needs_role_need_template.format(**dict_need)

                node_need_value[0].children[0] = nodes.Text(link_text, link_text)

                new_node_ref = make_refnode(
                    app.builder,
                    fromdocname,
                    target_need["docname"],
                    node_need_value["reftarget"],
                    node_need_value[0].deepcopy(),
                    node_need_value["reftarget"],
                )
            except NoUri:
                # If the given need id can not be found, we must pass here....
                pass
            except KeyError as e:
                log.warning(
                    "Needs: the config parameter needs_role_need_value uses not supported placeholders: %s " % e
                )

        else:
            log.warning(
                "Needs: linked need %s not found (Line %i of file %s)"
                % (node_need_value["reftarget"], node_need_value.line, node_need_value.source)
            )

        node_need_value.replace_self(new_node_ref)
