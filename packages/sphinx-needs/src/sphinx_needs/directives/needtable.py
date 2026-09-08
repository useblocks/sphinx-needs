from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsTableType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.directives.utils import (
    get_option_list,
    get_title,
    no_needs_found_paragraph,
    report_max_items,
    used_filter_paragraph,
)
from sphinx_needs.exceptions import NeedsInvalidException
from sphinx_needs.filter_common import FilterBase, apply_max_items, process_filters
from sphinx_needs.functions.functions import check_and_get_content
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.needs_schema import FieldsSchema, LinkSchema
from sphinx_needs.utils import add_doc, profile, remove_node_from_tree, row_col_maker

LOGGER = get_logger(__name__)


class Needtable(nodes.General, nodes.Element):
    pass


#: Set on a resolved doctree that holds at least one INTERACTIVE needtable, so that
#: `environment.py` can register the client assets for that page and no other (#462).
#: The doctree the `html-page-context` handler is given is the very object this module
#: mutated moments earlier, in the same process, for both serial and parallel writes --
#: which is why no environment-stored, purged and merged set of document names is needed.
HAS_INTERACTIVE_TABLE = "needs_has_interactive_table"

#: Default number of rows the interactive table shows per page.
DEFAULT_PAGE_SIZE = 10
#: Default page sizes offered by the interactive table (``0`` means "All").
DEFAULT_PAGE_SIZES = (10, 25, 50, 0)


def validate_page_size(value: object) -> int | None:
    """A page size is a positive integer; ``0`` ("all") is not a page size.

    :return: the value if it is one, otherwise ``None``.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def validate_page_sizes(value: object) -> list[int] | None:
    """The offered page sizes are a non-empty list of non-negative integers.

    ``0`` is allowed here and means "All".

    :return: the sizes if they are ones, otherwise ``None``.
    """
    if not isinstance(value, list | tuple) or not value:
        return None
    sizes: list[int] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, int) or entry < 0:
            return None
        sizes.append(entry)
    return sizes


class NeedtableTable(nodes.table):
    """The ``<table>`` of a needtable.

    Behaves exactly like :class:`docutils.nodes.table` everywhere except the HTML
    builders, where the registered visitor adds this node's ``html_attributes`` to the
    start tag: the ``data-needstable-*`` options the client-side enhancer reads.
    See ``design/needstable-contract.md``.
    """


class NeedtableRow(nodes.row):
    """A body ``<tr>`` of a needtable, carrying ``data-need-id`` (and ``data-parent``)."""


class NeedtableHeader(nodes.entry):
    """A ``<th>`` of a needtable, carrying ``scope``, ``data-col`` and ``data-type``."""


#: Sentinel for "the translator carried no ``starttag`` of its own". Restoring means
#: putting back exactly what was there -- another extension's own instance-level patch, or
#: nothing at all -- and those two need different operations, so "nothing" needs a value
#: that cannot be confused with an attribute that is present.
_NO_INSTANCE_STARTTAG = object()


@contextmanager
def _with_html_attributes(translator: Any, node: nodes.Element) -> Iterator[None]:
    """Add ``node["html_attributes"]`` to the start tag the base visitor emits.

    docutils' HTML writer serialises only the attributes a visitor hands to
    ``starttag()``; a node carrying its own is not enough. Rather than re-implement
    ``visit_table`` / ``visit_row`` / ``visit_entry`` -- whose logic (Sphinx's even/odd
    row classes, docutils' ``morecols``/``morerows``, the ``head``/``stub`` classes and
    the ``self.context`` push that ``depart_entry`` pops) belongs to those writers and
    changes between releases -- we delegate to them with ``starttag`` wrapped for the
    duration of the one call, and RESTORED to whatever was there before -- which may be
    another extension's own instance-level patch, installed by exactly this technique.
    """
    extra = node.get("html_attributes") or {}
    original = translator.starttag
    # what the INSTANCE carried before, if anything: `del` would switch off another
    # extension's patch for the rest of the document, silently
    previous = translator.__dict__.get("starttag", _NO_INSTANCE_STARTTAG)

    def starttag(
        node_: nodes.Element,
        tagname: str,
        suffix: str = "\n",
        empty: bool = False,
        **attributes: Any,
    ) -> str:
        if node_ is node:
            attributes.update(extra)
        return original(node_, tagname, suffix, empty, **attributes)

    translator.starttag = starttag
    try:
        yield
    finally:
        if previous is _NO_INSTANCE_STARTTAG:
            del translator.starttag
        else:
            translator.starttag = previous


def html_visit_needtable_table(translator: Any, node: NeedtableTable) -> None:
    with _with_html_attributes(translator, node):
        translator.visit_table(node)


def html_depart_needtable_table(translator: Any, node: NeedtableTable) -> None:
    translator.depart_table(node)


def html_visit_needtable_row(translator: Any, node: NeedtableRow) -> None:
    with _with_html_attributes(translator, node):
        translator.visit_row(node)


def html_depart_needtable_row(translator: Any, node: NeedtableRow) -> None:
    translator.depart_row(node)


def html_visit_needtable_header(translator: Any, node: NeedtableHeader) -> None:
    with _with_html_attributes(translator, node):
        translator.visit_entry(node)


def html_depart_needtable_header(translator: Any, node: NeedtableHeader) -> None:
    translator.depart_entry(node)


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
        # Deprecated and unused: it has never had any effect (declared but never
        # read); accepted so existing documents keep building, with a warning.
        "style_col": directives.unchanged_required,
        "sort": directives.unchanged_required,
        "class": directives.unchanged_required,
        "max_items": directives.nonnegative_int,
        "page_size": directives.unchanged_required,
        # ubCode compatibility: accepted and ignored by Sphinx-Needs.
        "cypher": directives.unchanged,
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
        if "style_col" in self.options:
            log_warning(
                LOGGER,
                "The 'style_col' option has never had any effect (it was collected "
                "but never applied) and will be removed; the line can be deleted.",
                "deprecated",
                location=self.get_location(),
            )

        sort = self.options.get("sort", "id_complete")

        page_size: int | None = None
        if (raw_page_size := self.options.get("page_size")) is not None:
            try:
                page_size = validate_page_size(int(raw_page_size))
            except ValueError:
                page_size = None
            if page_size is None:
                log_warning(
                    LOGGER,
                    "The 'page_size' option must be a positive integer, "
                    f"got {raw_page_size!r}; ignoring it.",
                    "directive",
                    location=self.get_location(),
                )

        title = None
        if self.arguments:
            title = self.arguments[0]

        attributes: NeedsTableType = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "caption": title,
            "classes": classes,
            "columns": columns,
            "colwidths": colwidths_list,
            "style": style,
            "style_row": style_row,
            "sort": sort,
            # As the following options are flags, the content is None, if set.
            # If not set, the options.get() method returns False
            "show_filters": "show_filters" in self.options,
            "show_parts": self.options.get("show_parts", False) is None,
            "max_items": self.options.get("max_items"),
            "page_size": page_size,
            **self.collect_filter_attributes(),
        }
        node = Needtable("", **attributes)
        self.set_source_info(node)

        add_doc(env, env.docname)

        return [targetnode, node]


def _column_type(needs_schema: FieldsSchema, key: str) -> str | None:
    """The ``data-type`` a column's ``<th>`` should declare, or ``None``.

    Only types the *producer* knows are declared; anything else is left to the script's
    own detection, which reads the rendered cell text. A link field is deliberately not
    typed: its cell holds references, not a value.
    """
    field = needs_schema.get_any_field(key)
    if field is None or isinstance(field, LinkSchema):
        return None
    if field.schema.get("type") in ("integer", "number"):
        return "number"
    return None


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
    needs_schema = needs_data.get_schema()

    # Create a link_type dictionary, which keys-list can be easily used to find columns
    link_type_list: dict[str, LinkSchema] = {}
    for link in needs_schema.iter_link_fields():
        link_type_list[link.name.upper()] = link
        link_type_list[link.name.upper() + "_BACK"] = link
        link_type_list[link.display.incoming.upper()] = link
        link_type_list[link.display.outgoing.upper()] = link

        # Extra handling for backward compatibility, as INCOMING and OUTGOING are
        # known und used column names for incoming/outgoing links
        if link.name == "links":
            link_type_list["OUTGOING"] = link
            link_type_list["INCOMING"] = link

    all_needs = needs_data.get_needs_view()

    # for node in doctree.findall(Needtable):
    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        current_needtable: NeedsTableType = node.attributes  # ty: ignore[invalid-assignment]

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

        table_node = NeedtableTable(
            classes=classes, ids=[node.attributes["ids"][0] + "-table_node"]
        )
        if style != "TABLE":
            # per-table options for the client-side enhancer; a `:style: table` table
            # carries none of them and the script ignores it. A bad configuration value
            # is warned about once, at `config-inited`, and falls back here.
            page_size = (
                current_needtable.get("page_size")
                or validate_page_size(needs_config.table_page_size)
                or DEFAULT_PAGE_SIZE
            )
            page_sizes = validate_page_sizes(needs_config.table_page_sizes) or list(
                DEFAULT_PAGE_SIZES
            )
            table_node["html_attributes"] = {
                "data-needstable-page-size": str(page_size),
                "data-needstable-page-sizes": ",".join(
                    str(size) for size in page_sizes
                ),
            }
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
        for option, title in current_needtable["columns"]:
            key = option.lower()
            html_attributes = {"scope": "col", "data-col": key}
            if (col_type := _column_type(needs_schema, key)) is not None:
                html_attributes["data-type"] = col_type
            node_columns.append(
                NeedtableHeader(
                    "",
                    nodes.paragraph("", title),
                    classes=[f"needs_col_{key}"],
                    html_attributes=html_attributes,
                )
            )

        tgroup += nodes.thead("", nodes.row("", *node_columns))
        tbody = nodes.tbody()
        tgroup += tbody
        table_node += tgroup

        # Add lineno to node
        table_node.line = current_needtable["lineno"]

        # Perform filtering of needs
        filtered_needs = process_filters(
            app,
            all_needs,
            current_needtable,
            origin="needtable",
            location=node,
        )

        def get_sorter(key: str) -> Callable[[NeedItem | NeedPartItem], Any]:
            """
            Returns a sort-function for a given need-key.
            :param key: key of need object as string
            :return:  function to use in sort(key=x)
            """

            def sort(need: NeedItem | NeedPartItem) -> Any:
                """
                Returns a given value of need, which is used for list sorting.
                :param need: need-element, which gets sort
                :return: value of need
                """
                value = need[key]
                if isinstance(value, str):
                    # if we filter for string (e.g. id) everything should be lowercase.
                    # Otherwise, "Z" will be above "a"
                    return value.lower()
                return value

            return sort

        filtered_needs.sort(key=get_sorter(current_needtable["sort"]))

        # the cap is applied after the sort, so that it keeps the first N rows
        # of the table as it would otherwise have been rendered
        filtered_needs, total_needs = apply_max_items(
            filtered_needs, current_needtable.get("max_items"), needs_config
        )

        for need_info in filtered_needs:
            style_row = check_and_get_content(
                current_needtable["style_row"], need_info, env, node
            )
            style_row = style_row.replace(
                " ", "_"
            )  # Replace whitespaces with _ to get valid css name

            if need_info["is_need"] or isinstance(need_info, NeedItem):
                row = NeedtableRow(
                    classes=["need", style_row],
                    html_attributes={"data-need-id": need_info["id_complete"]},
                )
                prefix = ""
                temp_need = need_info.copy()
            else:
                row = NeedtableRow(
                    classes=["need_part", style_row],
                    html_attributes={
                        "data-need-id": need_info["id_complete"],
                        "data-parent": need_info["id_parent"],
                    },
                )
                prefix = needs_config.part_prefix
                temp_need = need_info.copy_for_needtable()

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
                    link = link_type_list[option]
                    if option in [
                        "INCOMING",
                        link.name.upper() + "_BACK",
                        link.display.incoming.upper(),
                    ]:
                        row += row_col_maker(
                            app,
                            fromdocname,
                            all_needs,
                            temp_need,
                            link.name + "_back",
                            ref_lookup=True,
                        )
                    else:
                        row += row_col_maker(
                            app,
                            fromdocname,
                            all_needs,
                            temp_need,
                            link.name,
                            ref_lookup=True,
                        )
                else:
                    row += row_col_maker(
                        app, fromdocname, all_needs, temp_need, option.lower()
                    )
            tbody += row

            # Need part rows
            if (
                current_needtable["show_parts"]
                and need_info["is_need"]
                and isinstance(need_info, NeedItem)
            ):
                for temp_part in need_info.iter_part_items():
                    row = NeedtableRow(
                        classes=["need_part"],
                        html_attributes={
                            "data-need-id": temp_part["id_complete"],
                            "data-parent": temp_part["id_parent"],
                        },
                    )

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
                        elif (
                            link_ := link_type_list.get(option)
                        ) is not None and option in [
                            "INCOMING",
                            link_.name.upper() + "_BACK",
                            link_.display.incoming.upper(),
                        ]:
                            row += row_col_maker(
                                app,
                                fromdocname,
                                all_needs,
                                temp_part,
                                link_.name + "_back",
                                ref_lookup=True,
                            )
                        else:
                            row += row_col_maker(
                                app, fromdocname, all_needs, temp_part, option.lower()
                            )

                    tbody += row

        if current_needtable["caption"]:
            title_text = current_needtable["caption"]
            title_node = nodes.title(title_text, "", nodes.Text(title_text))
            table_node.insert(0, title_node)

        # everything that replaces the directive node, in document order
        replacement: list[nodes.Node] = []
        if len(filtered_needs) == 0:
            replacement.append(
                no_needs_found_paragraph(current_needtable.get("filter_warning"))
            )
        else:
            # Put the table in a div-wrapper, so that we can control overflow / scroll layout
            if style == "TABLE":
                table_wrapper = nodes.container(classes=["needstable_wrapper"])
                table_wrapper.insert(0, table_node)
                replacement.append(table_wrapper)
            else:
                replacement.append(table_node)
                doctree[HAS_INTERACTIVE_TABLE] = True
            if current_needtable["show_filters"]:
                # the filter information goes AFTER the table: a paragraph inside a
                # `<table>` element is invalid HTML, which browsers hoist out again
                replacement.append(used_filter_paragraph(current_needtable))

        if len(filtered_needs) < total_needs:
            # the notice goes last, after the table and the filter information
            replacement.append(
                report_max_items(
                    len(filtered_needs),
                    total_needs,
                    origin="needtable",
                    location=node,
                )
            )

        node.replace_self(replacement)
