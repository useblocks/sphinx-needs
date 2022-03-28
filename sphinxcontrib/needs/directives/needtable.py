import re

from docutils import nodes
from docutils.parsers.rst import directives

from sphinxcontrib.needs.api.exceptions import NeedsInvalidException
from sphinxcontrib.needs.directives.utils import (
    get_option_list,
    get_title,
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinxcontrib.needs.filter_common import FilterBase, process_filters
from sphinxcontrib.needs.functions.functions import check_and_get_content
from sphinxcontrib.needs.utils import profile, row_col_maker


class Needtable(nodes.General, nodes.Element):
    pass


class NeedtableDirective(FilterBase):
    """
    Directive present filtered needs inside a table.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "show_filters": directives.flag,
        "show_parts": directives.flag,
        "columns": directives.unchanged_required,
        "colwidths": directives.unchanged_required,
        "style": directives.unchanged_required,
        "style_row": directives.unchanged_required,
        "style_col": directives.unchanged_required,
        "sort": directives.unchanged_required,
        "class": directives.unchanged_required,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)

    @profile("NEEDTABLE_RUN")
    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needtables"):
            env.need_all_needtables = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        targetid = "needtable-{docname}-{id}".format(docname=env.docname, id=env.new_serialno("needtable"))
        targetnode = nodes.target("", "", ids=[targetid])

        columns = str(self.options.get("columns", ""))
        if len(columns) == 0:
            columns = env.app.config.needs_table_columns
        if isinstance(columns, str):
            columns = [col.strip() for col in re.split(";|,", columns)]

        columns = [get_title(col) for col in columns]

        colwidths = str(self.options.get("colwidths", ""))
        colwidths_list = []
        if colwidths:
            colwidths_list = [int(width.strip()) for width in re.split(";|,", colwidths)]
            if len(columns) != len(colwidths_list):
                raise NeedsInvalidException(
                    f"Amount of elements in colwidths and columns do not match: "
                    f"colwidths: {len(colwidths_list)} and columns: {len(columns)}"
                )

        classes = get_option_list(self.options, "class")

        style = self.options.get("style", "").upper()
        style_row = self.options.get("style_row", "")
        style_col = self.options.get("style_col", "")

        sort = self.options.get("sort", "id_complete")

        title = None
        if self.arguments:
            title = self.arguments[0]

        # Add the need and all needed information
        env.need_all_needtables[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "caption": title,
            "classes": classes,
            "columns": columns,
            "colwidths": colwidths_list,
            "style": style,
            "style_row": style_row,
            "style_col": style_col,
            "sort": sort,
            # As the following options are flags, the content is None, if set.
            # If not set, the options.get() method returns False
            "show_filters": self.options.get("show_filters", False) is None,
            "show_parts": self.options.get("show_parts", False) is None,
            "env": env,
        }
        env.need_all_needtables[targetid].update(self.collect_filter_attributes())

        return [targetnode] + [Needtable("")]


@profile("NEEDTABLE")
def process_needtables(app, doctree, fromdocname):
    """
    Replace all needtables nodes with a table of filtered nodes.

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
        link_type_list[link_type["option"].upper() + "_BACK"] = link_type
        link_type_list[link_type["incoming"].upper()] = link_type
        link_type_list[link_type["outgoing"].upper()] = link_type

        # Extra handling tb backward compatible, as INCOMING and OUTGOING are
        # known und used column names for incoming/outgoing links
        if link_type["option"] == "links":
            link_type_list["OUTGOING"] = link_type
            link_type_list["INCOMING"] = link_type

    for node in doctree.traverse(Needtable):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ("ids", "names", "classes", "dupnames"):
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
        classes = [f"NEEDS_{style}"] + current_needtable["classes"]

        # Only add the theme specific "do not touch this table" class, if we use a style which
        # care about table layout and styling. The normal "TABLE" style is using the Sphinx default table
        # css classes and therefore must be handled by the themes.
        if style != "TABLE":
            classes.extend(app.config.needs_table_classes)

        content = nodes.table(classes=classes)
        tgroup = nodes.tgroup()

        # Define Table column width
        colwidths = current_needtable["colwidths"]
        for index, value in enumerate(current_needtable["columns"]):
            option, _title = value

            if colwidths:  # Get values from given colwidths option
                tgroup += nodes.colspec(colwidth=colwidths[index])
            elif option == "TITLE":  # if nothing in colwidths...
                tgroup += nodes.colspec(colwidth=15)
            else:
                tgroup += nodes.colspec(colwidth=5)

        node_columns = []
        for _option, title in current_needtable["columns"]:
            header_name = title
            node_columns.append(nodes.entry("", nodes.paragraph("", header_name)))

        tgroup += nodes.thead("", nodes.row("", *node_columns))
        tbody = nodes.tbody()
        tgroup += tbody
        content += tgroup

        # Add lineno to node
        content.line = current_needtable["lineno"]

        all_needs = list(all_needs.values())

        # Perform filtering of needs
        try:
            found_needs = process_filters(app, all_needs, current_needtable)
        except Exception as e:
            raise e

        def get_sorter(key):
            """
            Returns a sort-function for a given need-key.
            :param key: key of need object as string
            :return:  function to use in sort(key=x)
            """

            def sort(need):
                """
                Returns a given value of need, which is used for list sorting.
                :param need: need-element, which gets sort
                :return: value of need
                """
                if isinstance(need[key], str):
                    # if we filter for string (e.g. id) everything should be lowercase.
                    # Otherwise "Z" will be above "a"
                    return need[key].lower()
                return need[key]

            return sort

        found_needs.sort(key=get_sorter(current_needtable["sort"]))

        for need_info in found_needs:
            style_row = check_and_get_content(current_needtable["style_row"], need_info, env)
            style_row = style_row.replace(" ", "_")  # Replace whitespaces with _ to get valid css name

            temp_need = need_info.copy()
            if temp_need["is_need"]:
                row = nodes.row(classes=["need", style_row])
                prefix = ""
            else:
                row = nodes.row(classes=["need_part", style_row])
                temp_need["id"] = temp_need["id_complete"]
                prefix = app.config.needs_part_prefix
                temp_need["title"] = temp_need["content"]

            for option, _title in current_needtable["columns"]:
                if option == "ID":
                    row += row_col_maker(
                        app, fromdocname, env.needs_all_needs, temp_need, "id", make_ref=True, prefix=prefix
                    )
                elif option == "TITLE":
                    row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need, "title", prefix=prefix)
                elif option in link_type_list:
                    link_type = link_type_list[option]
                    if option in ["INCOMING", link_type["option"].upper() + "_BACK", link_type["incoming"].upper()]:
                        row += row_col_maker(
                            app,
                            fromdocname,
                            env.needs_all_needs,
                            temp_need,
                            link_type["option"] + "_back",
                            ref_lookup=True,
                        )
                    else:
                        row += row_col_maker(
                            app, fromdocname, env.needs_all_needs, temp_need, link_type["option"], ref_lookup=True
                        )
                else:
                    row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_need, option.lower())
            tbody += row

            # Need part rows
            if current_needtable["show_parts"] and need_info["is_need"]:
                for part in need_info["parts"].values():
                    # update the part with all information from its parent
                    # this is required to make ID links work
                    temp_part = part.copy()  # The dict has to be manipulated, so that row_col_maker() can be used
                    temp_part = {**need_info, **temp_part}
                    temp_part["id_complete"] = f"{need_info['id']}.{temp_part['id']}"
                    temp_part["id_parent"] = need_info["id"]
                    temp_part["docname"] = need_info["docname"]

                    row = nodes.row(classes=["need_part"])

                    for option, _title in current_needtable["columns"]:
                        if option == "ID":
                            row += row_col_maker(
                                app,
                                fromdocname,
                                env.needs_all_needs,
                                temp_part,
                                "id_complete",
                                make_ref=True,
                                prefix=app.config.needs_part_prefix,
                            )
                        elif option == "TITLE":
                            row += row_col_maker(
                                app,
                                fromdocname,
                                env.needs_all_needs,
                                temp_part,
                                "content",
                                prefix=app.config.needs_part_prefix,
                            )
                        elif option in link_type_list and (
                            option
                            in [
                                "INCOMING",
                                link_type_list[option]["option"].upper() + "_BACK",
                                link_type_list[option]["incoming"].upper(),
                            ]
                        ):
                            row += row_col_maker(
                                app,
                                fromdocname,
                                env.needs_all_needs,
                                temp_part,
                                link_type_list[option]["option"] + "_back",
                                ref_lookup=True,
                            )
                        else:
                            row += row_col_maker(app, fromdocname, env.needs_all_needs, temp_part, option.lower())

                    tbody += row

        if len(found_needs) == 0:
            content.append(no_needs_found_paragraph())

        # add filter information to output
        if current_needtable["show_filters"]:
            content.append(used_filter_paragraph(current_needtable))

        if current_needtable["caption"]:
            title_text = current_needtable["caption"]
            title = nodes.title(title_text, "", nodes.Text(title_text))
            content.insert(0, title)

        # Put the table in a div-wrapper, so that we can control overflow / scroll layout
        if style == "TABLE":
            table_wrapper = nodes.container(classes=["needstable_wrapper"])
            table_wrapper.insert(0, content)
            node.replace_self(table_wrapper)

        else:
            node.replace_self(content)
