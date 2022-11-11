import os
from typing import Sequence
from urllib.parse import urlparse

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0

from sphinx.application import Sphinx

from sphinx_needs.diagrams_common import create_legend
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.utils import add_doc, row_col_maker, unwrap


class Needfilter(nodes.General, nodes.Element):
    pass


class NeedfilterDirective(FilterBase):
    """
    Directive to filter needs and present them inside a list, table or diagram.

    .. deprecated:: 0.2.0
       Use needlist, needtable or needdiagram instead
    """

    @staticmethod
    def layout(argument: str) -> str:
        return directives.choice(argument, ("list", "table", "diagram"))

    option_spec = {
        "show_status": directives.flag,
        "show_tags": directives.flag,
        "show_filters": directives.flag,
        "show_links": directives.flag,
        "show_legend": directives.flag,
        "layout": layout,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needfilters"):
            env.need_all_needfilters = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        targetid = "needfilter-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needfilter"))
        targetnode = nodes.target("", "", ids=[targetid])

        # Add the need and all needed information
        env.need_all_needfilters[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "show_tags": "show_tags" in self.options,
            "show_status": "show_status" in self.options,
            "show_filters": "show_filters" in self.options,
            "show_legend": "show_legend" in self.options,
            "layout": self.options.get("layout", "list"),
            "export_id": self.options.get("export_id", ""),
            # "env": env,
        }
        env.need_all_needfilters[targetid].update(self.collect_filter_attributes())

        add_doc(env, env.docname)

        return [targetnode, Needfilter("")]


def process_needfilters(app: Sphinx, doctree: nodes.document, fromdocname: str, found_nodes: list) -> None:
    # Replace all needlist nodes with a list of the collected needs.
    # Augment each need with a backlink to the original location.
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    # NEEDFILTER
    # for node in doctree.findall(Needfilter):
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
        current_needfilter = env.need_all_needfilters[id]
        all_needs = env.needs_all_needs

        if current_needfilter["layout"] == "list":
            content = []

        elif current_needfilter["layout"] == "diagram":
            content = []
            try:
                if "sphinxcontrib.plantuml" not in app.config.extensions:
                    raise ImportError
                from sphinxcontrib.plantuml import plantuml
            except ImportError:
                content = nodes.error()
                para = nodes.paragraph()
                text = nodes.Text("PlantUML is not available!")
                para += text
                content.append(para)
                node.replace_self(content)
                continue

            plantuml_block_text = ".. plantuml::\n" "\n" "   @startuml" "   @enduml"
            puml_node = plantuml(plantuml_block_text)
            puml_node["uml"] = "@startuml\n"
            puml_connections = ""

        elif current_needfilter["layout"] == "table":
            content = nodes.table()
            tgroup = nodes.tgroup()
            id_colspec = nodes.colspec(colwidth=5)
            title_colspec = nodes.colspec(colwidth=15)
            type_colspec = nodes.colspec(colwidth=5)
            status_colspec = nodes.colspec(colwidth=5)
            links_colspec = nodes.colspec(colwidth=5)
            tags_colspec = nodes.colspec(colwidth=5)
            tgroup += [id_colspec, title_colspec, type_colspec, status_colspec, links_colspec, tags_colspec]
            tgroup += nodes.thead(
                "",
                nodes.row(
                    "",
                    nodes.entry("", nodes.paragraph("", "ID")),
                    nodes.entry("", nodes.paragraph("", "Title")),
                    nodes.entry("", nodes.paragraph("", "Type")),
                    nodes.entry("", nodes.paragraph("", "Status")),
                    nodes.entry("", nodes.paragraph("", "Links")),
                    nodes.entry("", nodes.paragraph("", "Tags")),
                ),
            )
            tbody = nodes.tbody()
            tgroup += tbody
            content += tgroup

        all_needs = list(all_needs.values())
        found_needs = process_filters(app, all_needs, current_needfilter)

        line_block = nodes.line_block()
        for need_info in found_needs:
            if "target_node" in need_info:
                target_id = need_info["target_node"]["refid"]
            else:
                target_id = need_info["target_id"]

            if current_needfilter["layout"] == "list":
                para = nodes.line()
                description = "{}: {}".format(need_info["id"], need_info["title"])

                if current_needfilter["show_status"] and need_info["status"]:
                    description += " (%s)" % need_info["status"]

                if current_needfilter["show_tags"] and need_info["tags"]:
                    description += " [%s]" % "; ".join(need_info["tags"])

                title = nodes.Text(description)

                # Create a reference
                if need_info["hide"]:
                    para += title
                else:
                    ref = nodes.reference("", "")
                    ref["refdocname"] = need_info["docname"]
                    ref["refuri"] = builder.get_relative_uri(fromdocname, need_info["docname"])
                    ref["refuri"] += "#" + target_id
                    ref.append(title)
                    para += ref

                line_block.append(para)
            elif current_needfilter["layout"] == "table":
                row = nodes.row()
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "id", make_ref=True)
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "title")
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "type_name")
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "status")
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "links", ref_lookup=True)
                row += row_col_maker(app, fromdocname, env.needs_all_needs, need_info, "tags")
                tbody += row
            elif current_needfilter["layout"] == "diagram":
                # Link calculation
                # All links we can get from docutils functions will be relative.
                # But the generated link in the svg will be relative to the svg-file location
                # (e.g. server.com/docs/_images/sqwxo499cnq329439dfjne.svg)
                # and not to current documentation. Therefore we need to add ../ to get out of the image folder.
                try:
                    link = (
                        "../"
                        + builder.get_target_uri(need_info["docname"])
                        + "?highlight={}".format(urlparse(need_info["title"]))
                        + "#"
                        + target_id
                    )  # Gets mostly called during latex generation
                except NoUri:
                    link = ""

                diagram_template = Template(env.config.needs_diagram_template)
                node_text = diagram_template.render(**need_info, **app.config.needs_render_context)

                puml_node["uml"] += '{style} "{node_text}" as {id} [[{link}]] {color}\n'.format(
                    id=need_info["id"],
                    node_text=node_text,
                    link=link,
                    color=need_info["type_color"],
                    style=need_info["type_style"],
                )
                for link in need_info["links"]:
                    puml_connections += "{id} --> {link}\n".format(id=need_info["id"], link=link)

        if current_needfilter["layout"] == "list":
            content.append(line_block)

        if current_needfilter["layout"] == "diagram":
            puml_node["uml"] += puml_connections

            # Create a legend

            if current_needfilter["show_legend"]:
                puml_node["uml"] += create_legend(app.config.needs_types)
            puml_node["uml"] += "@enduml"
            puml_node["incdir"] = os.path.dirname(current_needfilter["docname"])
            puml_node["filename"] = os.path.split(current_needfilter["docname"])[1]  # Needed for plantuml >= 0.9
            content.append(puml_node)

        if len(content) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.line()
            nothing_found_node = nodes.Text(nothing_found)
            para += nothing_found_node
            content.append(para)
        if current_needfilter["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += (
                " status(%s)" % " OR ".join(current_needfilter["status"])
                if len(current_needfilter["status"]) > 0
                else ""
            )
            if len(current_needfilter["status"]) > 0 and len(current_needfilter["tags"]) > 0:
                filter_text += " AND "
            filter_text += (
                " tags(%s)" % " OR ".join(current_needfilter["tags"]) if len(current_needfilter["tags"]) > 0 else ""
            )
            if (len(current_needfilter["status"]) > 0 or len(current_needfilter["tags"]) > 0) and len(
                current_needfilter["types"]
            ) > 0:
                filter_text += " AND "
            filter_text += (
                " types(%s)" % " OR ".join(current_needfilter["types"]) if len(current_needfilter["types"]) > 0 else ""
            )

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)
