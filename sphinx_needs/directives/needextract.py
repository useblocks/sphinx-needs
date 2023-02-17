"""


"""
import re
from typing import List, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.transforms.references import Substitutions
from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.layout import create_need
from sphinx_needs.utils import add_doc, unwrap


class Needextract(nodes.General, nodes.Element):
    pass


class NeedextractDirective(FilterBase):
    """
    Directive to filter needs and present them as normal needs with given layout and style.
    """

    optional_arguments = 1
    final_argument_whitespace = True

    option_spec = {
        "layout": directives.unchanged_required,
        "style": directives.unchanged_required,
        "show_filters": directives.flag,
    }
    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needextracts"):
            env.need_all_needextracts = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        targetid = "needextract-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needextract"))
        targetnode = nodes.target("", "", ids=[targetid])

        filter_arg = self.arguments[0] if self.arguments else None

        # Add the need and all needed information
        env.need_all_needextracts[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "export_id": self.options.get("export_id", ""),
            "layout": self.options.get("layout"),
            "style": self.options.get("style"),
            "show_filters": "show_filters" in self.options,
            "filter_arg": filter_arg,
        }
        env.need_all_needextracts[targetid].update(self.collect_filter_attributes())

        add_doc(env, env.docname, "needextract")

        return [targetnode, Needextract("")]


def process_needextract(app: Sphinx, doctree: nodes.document, fromdocname: str, found_nodes: list) -> None:
    """
    Replace all needextract nodes with a list of the collected needs.
    """
    env = unwrap(app.env)

    for node in found_nodes:
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ("ids", "names", "classes", "dupnames"):
                node[att] = []
            node.replace_self([])
            continue

        id = node.attributes["ids"][0]
        current_needextract = env.need_all_needextracts[id]
        all_needs = env.needs_all_needs
        content: List[nodes.Element] = []
        all_needs = list(all_needs.values())

        # check if filter argument and option filter both exist
        need_filter_arg = current_needextract["filter_arg"]
        if need_filter_arg and current_needextract["filter"]:
            raise NeedsInvalidFilter("Needextract can't have filter arguments and option filter at the same time.")
        elif need_filter_arg:
            # check if given filter argument is need-id
            if need_filter_arg in env.needs_all_needs:
                need_filter_arg = f'id == "{need_filter_arg}"'
            elif re.fullmatch(app.config.needs_id_regex, need_filter_arg):
                # check if given filter argument is need-id, but not exists
                raise NeedsInvalidFilter(f"Provided id {need_filter_arg} for needextract does not exist.")
            current_needextract["filter"] = need_filter_arg

        found_needs = process_filters(app, all_needs, current_needextract)

        for need_info in found_needs:
            # if "is_target" is True:
            #   extract_target_node = current_needextract['target_node']
            #   extract_target_node[ids=[need_info["id"]]]
            #
            #   # Original need id replacement (needextract-{docname}-{id})
            #   need_info['target_node']['ids'] = [f"replaced_{need['id']}"]

            # filter out need_part from found_needs, in order to generate
            # copies of filtered needs with custom layout and style
            if need_info["is_need"] and not need_info["is_part"]:
                need_extract = create_need(
                    need_info["id"],
                    app,
                    layout=current_needextract["layout"],
                    style=current_needextract["style"],
                    docname=current_needextract["docname"],
                )

                # Add lineno to node
                need_extract.line = current_needextract["lineno"]

                content.append(need_extract)

        if len(content) == 0:
            content.append(no_needs_found_paragraph())

        if current_needextract["show_filters"]:
            content.append(used_filter_paragraph(current_needextract))

        node.replace_self(content)

    if found_needs:
        # Run docutils/sphinx transformers for the by needextract added nodes.
        # Transformers use the complete document (doctree), so we perform this action once per
        # needextract. No matter if one or multiple needs got copied
        Substitutions(doctree).apply()
