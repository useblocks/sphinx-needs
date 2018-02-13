import sys
import urllib
import re

from docutils import nodes
from docutils.parsers.rst import directives
from sphinxcontrib.needs.utils import row_col_maker, status_sorter

from sphinxcontrib.needs.filter_base import FilterBase, procces_filters

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


class Needtable(nodes.General, nodes.Element):
    pass


class NeedtableDirective(FilterBase):
    """
    Directive present filtered needs inside a table.
    """
    option_spec = {'show_filters': directives.flag,
                   'columns': directives.unchanged_required,
                   }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needtables'):
            env.need_all_needtables = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'need_all_needs'):
            env.need_all_needs = {}

        targetid = "needtable-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needtable'))
        targetnode = nodes.target('', '', ids=[targetid])

        columns = self.options.get("columns", [])
        if len(columns) == 0:
            env.app.config.needs_table_layout
            columns = "ID;TITLE;STATUS;TYPE;OUTGOING;TAGS"
        if isinstance(columns, str):
            columns = [col.strip() for col in re.split(";|,", columns)]
        columns = [col.upper() for col in columns if col.upper() in ["ID", "TITLE", "TAGS", "STATUS", "TYPE",
                                                                     "INCOMING", "OUTGOING"]]
        # Add the need and all needed information
        env.need_all_needtables[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target': targetnode,
            'columns': columns,
            'show_filters': True if self.options.get("show_filters", False) is None else False
        }
        env.need_all_needtables[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needtable('')]


def process_needtables(app, doctree, fromdocname):
    """
    Replace all needtables nodes with a tale of filtered noded.

    :param app:
    :param doctree:
    :param fromdocname:
    :return:
    """
    env = app.builder.env

    for node in doctree.traverse(Needtable):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ('ids', 'names', 'classes', 'dupnames'):
                node[att] = []
            node.replace_self([])
            continue

        id = node.attributes["ids"][0]
        current_needtable = env.need_all_needtables[id]
        all_needs = env.need_all_needs

        # Prepare table
        content = nodes.table()
        tgroup = nodes.tgroup()

        # Define Table column width
        # ToDo: Find a way to chosen to perfect width automatically.
        for col in current_needtable["columns"]:
            if col == "TITLE":
                tgroup += nodes.colspec(colwidth=15)
            else:
                tgroup += nodes.colspec(colwidth=5)

        node_columns = []
        for col in current_needtable["columns"]:
            if col == "ID":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'ID')))
            elif col == "TITLE":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Title')))
            elif col == "STATUS":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Status')))
            elif col == "TYPE":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Type')))
            elif col == "TAGS":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Tags')))
            elif col == "INCOMING":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Incoming')))
            elif col == "OUTGOING":
                node_columns.append(nodes.entry('', nodes.paragraph('', 'Outgoing')))

        tgroup += nodes.thead('', nodes.row(
            '', *node_columns))
        tbody = nodes.tbody()
        tgroup += tbody
        content += tgroup

        all_needs = list(all_needs.values())

        if current_needtable["sort_by"] is not None:
            if current_needtable["sort_by"] == "id":
                all_needs = sorted(all_needs, key=lambda node: node["id"])
            elif current_needtable["sort_by"] == "status":
                all_needs = sorted(all_needs, key=status_sorter)

        # Perform filtering of needs
        found_needs = procces_filters(all_needs, current_needtable)

        for need_info in found_needs:
            row = nodes.row()
            for col in current_needtable["columns"]:
                if col == "ID":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "id", make_ref=True)
                elif col == "TITLE":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "title")
                elif col == "STATUS":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "status")
                elif col == "TYPE":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "type_name")
                elif col == "TAGS":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "tags")
                elif col == "INCOMING":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "links_back", ref_lookup=True)
                elif col == "OUTGOING":
                    row += row_col_maker(app, fromdocname, env.need_all_needs, need_info, "links", ref_lookup=True)
            tbody += row

        if len(found_needs) == 0:
            nothing_found = "No needs passed the filters"
            para = nodes.line()
            nothing_found_node = nodes.Text(nothing_found, nothing_found)
            para += nothing_found_node
            content.append(para)

        # add filter information to output
        if current_needtable["show_filters"]:
            para = nodes.paragraph()
            filter_text = "Used filter:"
            filter_text += " status(%s)" % " OR ".join(current_needtable["status"]) if len(
                current_needtable["status"]) > 0 else ""
            if len(current_needtable["status"]) > 0 and len(current_needtable["tags"]) > 0:
                filter_text += " AND "
            filter_text += " tags(%s)" % " OR ".join(current_needtable["tags"]) if len(
                current_needtable["tags"]) > 0 else ""
            if (len(current_needtable["status"]) > 0 or len(current_needtable["tags"]) > 0) and len(
                    current_needtable["types"]) > 0:
                filter_text += " AND "
            filter_text += " types(%s)" % " OR ".join(current_needtable["types"]) if len(
                current_needtable["types"]) > 0 else ""

            filter_node = nodes.emphasis(filter_text, filter_text)
            para += filter_node
            content.append(para)

        node.replace_self(content)
