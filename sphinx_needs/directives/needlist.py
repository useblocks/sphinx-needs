from __future__ import annotations

from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.utils import (
    add_doc,
    check_and_calc_base_url_rel_path,
    remove_node_from_tree,
)


class Needlist(nodes.General, nodes.Element):
    pass


class NeedlistDirective(FilterBase):
    """
    Directive to filter needs and present them inside a list
    """

    option_spec = {
        "show_status": directives.flag,
        "show_tags": directives.flag,
        "show_filters": directives.flag,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        targetid = "needlist-{docname}-{id}".format(
            docname=env.docname, id=env.new_serialno("needlist")
        )
        targetnode = nodes.target("", "", ids=[targetid])

        # Add the need and all needed information
        SphinxNeedsData(env).get_or_create_lists()[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "show_tags": "show_tags" in self.options,
            "show_status": "show_status" in self.options,
            "show_filters": "show_filters" in self.options,
            **self.collect_filter_attributes(),
        }

        add_doc(env, env.docname)

        return [targetnode, Needlist("")]


def process_needlist(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    """
    Replace all needlist nodes with a list of the collected needs.
    Augment each need with a backlink to the original location.
    """
    builder = app.builder
    env = app.env

    include_needs = NeedsSphinxConfig(env.config).include_needs
    # for node in doctree.findall(Needlist):
    for node in found_nodes:
        if not include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needfilter = SphinxNeedsData(env).get_or_create_lists()[id]
        content: list[nodes.Node] = []
        all_needs = list(SphinxNeedsData(env).get_or_create_needs().values())
        found_needs = process_filters(app, all_needs, current_needfilter)

        if len(found_needs) > 0:
            line_block = nodes.line_block()

            # Add lineno to node
            line_block.line = current_needfilter["lineno"]
            for need_info in found_needs:
                para = nodes.line()
                description = "{}: {}".format(need_info["id"], need_info["title"])

                if current_needfilter["show_status"] and need_info["status"]:
                    description += " ({})".format(need_info["status"])

                if current_needfilter["show_tags"] and need_info["tags"]:
                    description += " [{}]".format("; ".join(need_info["tags"]))

                title = nodes.Text(description)

                # Create a reference
                if need_info["hide"]:
                    para += title
                elif need_info["is_external"]:
                    assert (
                        need_info["external_url"] is not None
                    ), "External need without URL"
                    ref = nodes.reference("", "")

                    ref["refuri"] = check_and_calc_base_url_rel_path(
                        need_info["external_url"], fromdocname
                    )

                    ref["classes"].append(need_info["external_css"])
                    ref.append(title)
                    para += ref
                elif _docname := need_info["docname"]:
                    target_id = need_info["target_id"]
                    ref = nodes.reference("", "")
                    ref["refdocname"] = _docname
                    ref["refuri"] = builder.get_relative_uri(fromdocname, _docname)
                    ref["refuri"] += "#" + target_id
                    ref.append(title)
                    para += ref
                line_block.append(para)
            content.append(line_block)

        if len(content) == 0:
            content.append(
                no_needs_found_paragraph(current_needfilter.get("filter_warning"))
            )
        if current_needfilter["show_filters"]:
            content.append(used_filter_paragraph(current_needfilter))

        node.replace_self(content)
