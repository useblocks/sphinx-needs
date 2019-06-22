import sys
import urllib
import re

from docutils import nodes
from docutils.parsers.rst import directives
from sphinxcontrib.needs.utils import row_col_maker, status_sorter
from sphinxcontrib.needs.filter_common import FilterBase, procces_filters
from sphinxcontrib.needs.directives.utils import no_needs_found_paragraph, used_filter_paragraph


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
                   'show_parts': directives.flag,
                   'columns': directives.unchanged_required,
                   'style': directives.unchanged_required}

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needtables'):
            env.need_all_needtables = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'needs_all_needs'):
            env.needs_all_needs = {}

        targetid = "needtable-{docname}-{id}".format(
            docname=env.docname,
            id=env.new_serialno('needtable'))
        targetnode = nodes.target('', '', ids=[targetid])

        columns = str(self.options.get("columns", ""))
        if len(columns) == 0:
            columns = env.app.config.needs_table_columns
        if isinstance(columns, str):
            columns = [col.strip() for col in re.split(";|,", columns)]

        columns = [col.upper() for col in columns]

        style = self.options.get("style", "").upper()

        # Add the need and all needed information
        env.need_all_needtables[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'columns': columns,
            'style': style,
            # As the following options are flags, the content is None, if set.
            # If not set, the options.get() method returns False
            'show_filters': True if self.options.get("show_filters", False) is None else False,
            'show_parts': True if self.options.get("show_parts", False) is None else False,
            'export_id': self.options.get("export_id", ""),
            'env': env,
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

    # Create a link_type dictionary, which keys-list can be easily used to find columns
    link_type_list = {}
    for link_type in app.config.needs_extra_links:
        link_type_list[link_type["option"].upper()] = link_type
        link_type_list[link_type["option"].upper() + '_BACK'] = link_type
        link_type_list[link_type["incoming"].upper()] = link_type
        link_type_list[link_type["outgoing"].upper()] = link_type

        # Extra handling tb backward compatible, as INCOMING and OUTGOING are
        # known und used column names for incoming/outgoing links
        if link_type['option'] == 'links':
            link_type_list['OUTGOING'] = link_type
            link_type_list['INCOMING'] = link_type

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
        all_needs = env.needs_all_needs

        if current_needtable["style"] == "" or current_needtable["style"].upper() not in ["TABLE", "DATATABLES"]:
            if app.config.needs_table_style == "":
                style = "DATATABLES"
            else:
                style = app.config.needs_table_style.upper()
        else:
            style = current_needtable["style"].upper()

        # Prepare table
        classes = ["NEEDS_{style}".format(style=style)]
        content = nodes.table(classes=classes)
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
            header_name = col.title() if col != "ID" else col
            header_name = header_name.replace("_", " ")
            node_columns.append(nodes.entry('', nodes.paragraph('', header_name)))

        tgroup += nodes.thead('', nodes.row(
            '', *node_columns))
        tbody = nodes.tbody()
        tgroup += tbody
        content += tgroup

        all_needs = list(all_needs.values())

        # Perform filtering of needs
        found_needs = procces_filters(all_needs, current_needtable)

        for need_info in found_needs:
            temp_need = need_info.copy()
            if temp_need['is_need']:
                row = nodes.row(classes=['need'])
                prefix = ''
            else:
                row = nodes.row(classes=['need_part'])
                temp_need['id'] = temp_need['id_complete']
                prefix = app.config.needs_part_prefix
                temp_need['title'] = temp_need['content']

            for col in current_needtable["columns"]:
                if col == "ID":
                    row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need, "id", make_ref=True,
                                         prefix=prefix)
                elif col == "TITLE":
                    row += row_col_maker(
                        app, fromdocname, env.needs_all_needs, temp_need, "title",
                        prefix=app.config.needs_part_prefix)
                elif col in link_type_list.keys():
                    link_type = link_type_list[col]
                    if col == 'INCOMING' or col == link_type['option'].upper() + '_BACK' or col == link_type['incoming'].upper():
                        row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need,
                                             link_type['option'] + '_back', ref_lookup=True)
                    else:
                        row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need,
                                             link_type['option'], ref_lookup=True)
                else:
                    row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need, col.lower())
            tbody += row

            # Need part rows
            if current_needtable["show_parts"] and need_info['is_need']:
                for key, part in need_info["parts"].items():
                    row = nodes.row(classes=['need_part'])
                    temp_part = part.copy()  # The dict needs to be manipulated, so that row_col_maker() can be used
                    temp_part['docname'] = need_info['docname']

                    for col in current_needtable["columns"]:
                        if col == "ID":
                            temp_part['id'] = '.'.join([need_info['id'], part['id']])
                            row += row_col_maker(
                                app, fromdocname, env.needs_all_needs, temp_part, "id",
                                make_ref=True, prefix=app.config.needs_part_prefix)
                        elif col == "TITLE":
                            row += row_col_maker(
                                app, fromdocname, env.needs_all_needs, temp_part, "content",
                                prefix=app.config.needs_part_prefix)
                        elif col in link_type_list.keys() and (
                            col == link_type_list[col]['option'].upper() + '_BACK' or
                            col == link_type_list[col]['incoming'].upper()):

                            row += row_col_maker(
                                app, fromdocname, env.needs_all_needs, temp_part,
                                link_type_list[col]['option'] + '_back', ref_lookup=True)
                        else:
                            row += row_col_maker(
                            app, fromdocname, env.needs_all_needs, temp_part, col.lower())

                tbody += row

        if len(found_needs) == 0:
            content.append(no_needs_found_paragraph())

        # add filter information to output
        if current_needtable["show_filters"]:
            content.append(used_filter_paragraph(current_needtable))

        node.replace_self(content)
