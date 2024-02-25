from __future__ import annotations

import re
from typing import Any, Callable, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsInvalidException
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.utils import (
    get_option_list,
    get_title,
    no_needs_found_paragraph,
    used_filter_paragraph,
)
from sphinx_needs.filter_common import FilterBase, process_filters
from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.roles.need_part import iter_need_parts
from sphinx_needs.utils import add_doc, profile, remove_node_from_tree, row_col_maker


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
    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        targetid = "needtable-{docname}-{id}".format(
            docname=env.docname, id=env.new_serialno("needtable")
        )
        targetnode = nodes.target("", "", ids=[targetid])

        columns_str = str(self.options.get("columns", ""))
        if len(columns_str) == 0:
            columns_str = NeedsSphinxConfig(env.app.config).table_columns
        if isinstance(columns_str, str):
            _columns = [col.strip() for col in re.split(";|,", columns_str)]
        else:
            _columns = columns_str

        columns = [get_title(col) for col in _columns]

        colwidths = str(self.options.get("colwidths", ""))
        colwidths_list = []
        if colwidths:
            colwidths_list = [
                int(width.strip()) for width in re.split(";|,", colwidths)
            ]
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
        SphinxNeedsData(env).get_or_create_tables()[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
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
            "show_filters": "show_filters" in self.options,
            "show_parts": self.options.get("show_parts", False) is None,
            **self.collect_filter_attributes(),
        }

        add_doc(env, env.docname)

        return [targetnode] + [Needtable("")]


@measure_time("needtable")
@profile("NEEDTABLE")
def process_needtables(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    """
    Replace all needtables nodes with a table of filtered nodes.
    """
    env = app.env
    needs_config = NeedsSphinxConfig(app.config)
    needs_data = SphinxNeedsData(env)

    # Create a link_type dictionary, which keys-list can be easily used to find columns
    link_type_list = {}
    for link_type in needs_config.extra_links:
        link_type_list[link_type["option"].upper()] = link_type
        link_type_list[link_type["option"].upper() + "_BACK"] = link_type
        link_type_list[link_type["incoming"].upper()] = link_type
        link_type_list[link_type["outgoing"].upper()] = link_type

        # Extra handling for backward compatibility, as INCOMING and OUTGOING are
        # known und used column names for incoming/outgoing links
        if link_type["option"] == "links":
            link_type_list["OUTGOING"] = link_type
            link_type_list["INCOMING"] = link_type

    all_needs = needs_data.get_or_create_needs()

    # for node in doctree.findall(Needtable):
    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needtable = needs_data.get_or_create_tables()[id]

        if current_needtable["style"] == "" or current_needtable[
            "style"
        ].upper() not in ["TABLE", "DATATABLES"]:
            if needs_config.table_style == "":
                style = "DATATABLES"
            else:
                style = needs_config.table_style.upper()
        else:
            style = current_needtable["style"].upper()

        # Prepare table

        # class "colwidths-given" must be set since docutils-0.18.1, otherwise the table will not have
        # any colgroup definitions.
        classes = [f"NEEDS_{style}", "colwidths-given"] + current_needtable["classes"]

        # Only add the theme specific "do not touch this table" class, if we use a style which
        # care about table layout and styling. The normal "TABLE" style is using the Sphinx default table
        # css classes and therefore must be handled by the themes.
        if style != "TABLE":
            classes.extend(needs_config.table_classes)

        table_node = nodes.table(classes=classes, ids=[id + "-table_node"])
        tgroup = nodes.tgroup(cols=len(current_needtable["columns"]))

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
        table_node += tgroup

        # Add lineno to node
        table_node.line = current_needtable["lineno"]

        # Perform filtering of needs
        try:
            filtered_needs = process_filters(
                app, list(all_needs.values()), current_needtable
            )
        except Exception as e:
            raise e

        def get_sorter(key: str) -> Callable[[NeedsInfoType], Any]:
            """
            Returns a sort-function for a given need-key.
            :param key: key of need object as string
            :return:  function to use in sort(key=x)
            """

            def sort(need: NeedsInfoType) -> Any:
                """
                Returns a given value of need, which is used for list sorting.
                :param need: need-element, which gets sort
                :return: value of need
                """
                value = need[key]  # type: ignore[literal-required]
                if isinstance(value, str):
                    # if we filter for string (e.g. id) everything should be lowercase.
                    # Otherwise, "Z" will be above "a"
                    return value.lower()
                return value

            return sort

        filtered_needs.sort(key=get_sorter(current_needtable["sort"]))

        for need_info in filtered_needs:
            style_row = check_and_get_content(
                current_needtable["style_row"], need_info, env
            )
            style_row = style_row.replace(
                " ", "_"
            )  # Replace whitespaces with _ to get valid css name

            temp_need = need_info.copy()
            if temp_need["is_need"]:
                row = nodes.row(classes=["need", style_row])
                prefix = ""
            else:
                row = nodes.row(classes=["need_part", style_row])
                temp_need["id"] = temp_need["id_complete"]
                prefix = needs_config.part_prefix
                temp_need["title"] = temp_need["content"]

            for option, _title in current_needtable["columns"]:
                if option == "ID":
                    row += row_col_maker(
                        app,
                        fromdocname,
                        all_needs,
                        temp_need,
                        "id",
                        make_ref=True,
                        prefix=prefix,
                    )
                elif option == "TITLE":
                    row += row_col_maker(
                        app, fromdocname, all_needs, temp_need, "title", prefix=prefix
                    )
                elif option in link_type_list:
                    link_type = link_type_list[option]
                    if option in [
                        "INCOMING",
                        link_type["option"].upper() + "_BACK",
                        link_type["incoming"].upper(),
                    ]:
                        row += row_col_maker(
                            app,
                            fromdocname,
                            all_needs,
                            temp_need,
                            link_type["option"] + "_back",
                            ref_lookup=True,
                        )
                    else:
                        row += row_col_maker(
                            app,
                            fromdocname,
                            all_needs,
                            temp_need,
                            link_type["option"],
                            ref_lookup=True,
                        )
                else:
                    row += row_col_maker(
                        app, fromdocname, all_needs, temp_need, option.lower()
                    )
            tbody += row

            # Need part rows
            if current_needtable["show_parts"] and need_info["is_need"]:
                for temp_part in iter_need_parts(need_info):
                    row = nodes.row(classes=["need_part"])

                    for option, _title in current_needtable["columns"]:
                        if option == "ID":
                            row += row_col_maker(
                                app,
                                fromdocname,
                                all_needs,
                                temp_part,
                                "id_complete",
                                make_ref=True,
                                prefix=needs_config.part_prefix,
                            )
                        elif option == "TITLE":
                            row += row_col_maker(
                                app,
                                fromdocname,
                                all_needs,
                                temp_part,
                                "content",
                                prefix=needs_config.part_prefix,
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
                                all_needs,
                                temp_part,
                                link_type_list[option]["option"] + "_back",
                                ref_lookup=True,
                            )
                        else:
                            row += row_col_maker(
                                app, fromdocname, all_needs, temp_part, option.lower()
                            )

                    tbody += row

        content: nodes.Element
        if len(filtered_needs) == 0:
            content = no_needs_found_paragraph(current_needtable.get("filter_warning"))
        else:
            # Put the table in a div-wrapper, so that we can control overflow / scroll layout
            if style == "TABLE":
                table_wrapper = nodes.container(classes=["needstable_wrapper"])
                table_wrapper.insert(0, table_node)
                content = table_wrapper
            else:
                content = table_node
        # add filter information to output
        if current_needtable["show_filters"]:
            table_node.append(used_filter_paragraph(current_needtable))

        if current_needtable["caption"]:
            title_text = current_needtable["caption"]
            title_node = nodes.title(title_text, "", nodes.Text(title_text))
            table_node.insert(0, title_node)

        node.replace_self(content)
