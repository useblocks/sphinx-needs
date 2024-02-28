"""
Cares about the correct creation and handling of need layout.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/102
"""

from __future__ import annotations

import os
import re
import uuid
from contextlib import suppress
from functools import lru_cache
from optparse import Values
from typing import Callable, cast
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.frontend import OptionParser
from docutils.parsers.rst import Parser, languages
from docutils.parsers.rst.states import Inliner, Struct
from docutils.utils import new_document
from jinja2 import Environment
from sphinx.application import Sphinx
from sphinx.environment.collectors.asset import DownloadFileCollector, ImageCollector

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.utils import INTERNALS, match_string_link


@measure_time("need")
def create_need(
    need_id: str,
    app: Sphinx,
    layout: str | None = None,
    style: str | None = None,
    docname: str | None = None,
) -> nodes.container:
    """
    Creates a new need-node for a given layout.

    Need must already exist in internal dictionary.
    This creates a new representation only.
    :param need_id: need id
    :param app: sphinx application
    :param layout: layout to use, overrides layout set by need itself
    :param style: style to use, overrides styles set by need itself
    :param docname: Needed for calculating references
    :return:
    """
    env = app.env
    needs = SphinxNeedsData(env).get_or_create_needs()

    if need_id not in needs.keys():
        raise SphinxNeedLayoutException(f"Given need id {need_id} does not exist.")

    need_data = needs[need_id]

    # Resolve internal references.
    # This is done for original need content automatically.
    # But as we are working on  a copy, we have to trigger this on our own.
    if docname is None:
        # needed to calculate relative references
        # TODO ideally we should not cast here:
        # the docname can still be None, if the need is external, although practically these are not rendered
        docname = cast(str, needs[need_id]["docname"])

    node_container = nodes.container()
    # node_container += needs[need_id]["need_node"].children

    # We must create a standalone copy of the content_node, as it may be reused several time
    # (multiple needextract for the same need) and the Sphinx ImageTransformator add location specific
    # uri to some nodes, which are not valid for all locations.
    content_node = needs[need_id]["content_node"]
    assert content_node is not None, f"Need {need_id} has no content node."
    node_inner = content_node.deepcopy()

    # Rerun some important Sphinx collectors for need-content coming from "needsexternal".
    # This is needed, as Sphinx needs to know images and download paths.
    # Normally this gets done much earlier in the process, so that for the copied need-content this
    # handling was and will not be done by Sphinx itself anymore.

    # Overwrite the docname, which must be the original one from the reused need, as all used paths are relative
    # to the original location, not to the current document.
    env.temp_data["docname"] = need_data[
        "docname"
    ]  # Dirty, as in this phase normally no docname is set anymore in env
    ImageCollector().process_doc(app, node_inner)  # type: ignore[arg-type]
    DownloadFileCollector().process_doc(app, node_inner)  # type: ignore[arg-type]

    del env.temp_data["docname"]  # Be sure our env is as it was before

    node_container.append(node_inner)

    # resolve_references() ignores the given docname and takes the docname from the pending_xref node.
    # Therefore, we need to manipulate this first, before we can ask Sphinx to perform the normal
    # reference handling for us.
    replace_pending_xref_refdoc(node_container, docname)
    env.resolve_references(node_container, docname, env.app.builder)  # type: ignore[arg-type]

    node_container.attributes["ids"].append(need_id)

    needs_config = NeedsSphinxConfig(app.config)
    layout = layout or need_data["layout"] or needs_config.default_layout
    style = style or need_data["style"] or needs_config.default_style

    build_need(layout, node_container, app, style, docname)

    # set the layout and style for the new need
    node_container[0].attributes = node_container.parent.children[0].attributes  # type: ignore
    node_container[0].children[0].attributes = (  # type: ignore
        node_container.parent.children[0].children[0].attributes  # type: ignore
    )

    node_container.attributes["ids"] = []

    return node_container


def replace_pending_xref_refdoc(node: nodes.Element, new_refdoc: str) -> None:
    """
    Overwrites the refdoc attribute of all pending_xref nodes.
    This is needed, if a doctree with references gets copied used somewhereelse in the documentation.
    What is the normal case when using needextract.
    :param node: doctree
    :param new_refdoc: string, should be an existing docname
    :return: None
    """
    from sphinx.addnodes import pending_xref

    if isinstance(node, pending_xref):
        node.attributes["refdoc"] = new_refdoc
    else:
        for child in node.children:
            replace_pending_xref_refdoc(child, new_refdoc)  # type: ignore[arg-type]


@measure_time("need")
def build_need(
    layout: str,
    node: nodes.Element,
    app: Sphinx,
    style: str | None = None,
    fromdocname: str | None = None,
) -> None:
    """
    Builds a need based on a given layout for a given need-node.

    The created table must have the following docutils structure::

        - table
        -- tgroup
        --- colspec (partial used)
        --- thead (not used)
        --- tbody
        ---- row
        ----- entry
        ------ custom layout nodes

    The level structure must be kept, otherwise docutils can not handle it!
    """

    env = app.env
    needs = SphinxNeedsData(env).get_or_create_needs()
    node_container = nodes.container()

    need_id = node.attributes["ids"][0]
    need_data = needs[need_id]

    if need_data["hide"]:
        if node.parent:
            node.parent.replace(node, [])
        return

    if fromdocname is None:
        fromdocname = need_data["docname"]

    lh = LayoutHandler(app, need_data, layout, node, style, fromdocname)
    new_need_node = lh.get_need_table()
    node_container.append(new_need_node)

    container_id = "SNCB-" + str(uuid.uuid4())[:8]
    node_container.attributes["ids"] = [container_id]
    node_container.attributes["classes"] = ["need_container"]

    # We need to replace the current need-node (containing content only) with our new table need node.
    # node.parent.replace(node, node_container)
    node.parent.replace(node, node_container)


@lru_cache(1)
def _generate_inline_parser() -> tuple[Values, Inliner]:
    doc_settings = OptionParser(components=(Parser,)).get_default_values()
    inline_parser = Inliner()
    inline_parser.init_customizations(doc_settings)  # type: ignore
    return doc_settings, inline_parser


class LayoutHandler:
    """
    Cares about the correct layout handling
    """

    def __init__(
        self,
        app: Sphinx,
        need: NeedsInfoType,
        layout: str,
        node: nodes.Element,
        style: str | None = None,
        fromdocname: str | None = None,
    ) -> None:
        self.app = app
        self.need = need
        self.needs_config = NeedsSphinxConfig(app.config)

        self.layout_name = layout
        available_layouts = self.needs_config.layouts
        if self.layout_name not in available_layouts:
            raise SphinxNeedLayoutException(
                'Given layout "{}" is unknown for need {}. Registered layouts are: {}'.format(
                    self.layout_name, need["id"], " ,".join(available_layouts)
                )
            )
        self.layout = available_layouts[self.layout_name]

        self.node = node

        # Used, if you need is referenced from another page
        if fromdocname is None:
            self.fromdocname = need["docname"]
        else:
            self.fromdocname = fromdocname

        # For ReadTheDocs Theme we need to add 'rtd-exclude-wy-table'.
        classes = [
            "need",
            "needs_grid_" + self.layout["grid"],
            "needs_layout_" + self.layout_name,
        ]
        classes.extend(self.needs_config.table_classes)

        self.style = style or self.need["style"] or self.needs_config.default_style

        if self.style:
            for style in self.style.strip().split(","):
                style = style.strip()
                classes.append("needs_style_" + style)
        else:
            classes.append("needs_style_none")

        classes.append("needs_type_" + "".join(self.need["type"].split()))

        self.node_table = nodes.table(classes=classes, ids=[self.need["id"]])
        self.node_tbody = nodes.tbody()

        self.grids = {
            "simple": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [100],
                    "side_left": False,
                    "side_right": False,
                    "footer": False,
                },
            },
            "simple_footer": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [100],
                    "side_left": False,
                    "side_right": False,
                    "footer": True,
                },
            },
            "simple_side_left": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [30, 70],
                    "side_left": "full",
                    "side_right": False,
                    "footer": False,
                },
            },
            "simple_side_right": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [70, 30],
                    "side_left": False,
                    "side_right": "full",
                    "footer": False,
                },
            },
            "simple_side_left_partial": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [20, 80],
                    "side_left": "part",
                    "side_right": False,
                    "footer": False,
                },
            },
            "simple_side_right_partial": {
                "func": self._grid_simple,
                "configs": {
                    "colwidths": [80, 20],
                    "side_left": False,
                    "side_right": "part",
                    "footer": False,
                },
            },
            "complex": self._grid_complex,
            "content": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [100],
                    "side_left": False,
                    "side_right": False,
                    "footer": False,
                },
            },
            "content_footer": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [100],
                    "side_left": False,
                    "side_right": False,
                    "footer": True,
                },
            },
            "content_side_left": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [5, 95],
                    "side_left": True,
                    "side_right": False,
                    "footer": False,
                },
            },
            "content_side_right": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [95, 5],
                    "side_left": False,
                    "side_right": True,
                    "footer": False,
                },
            },
            "content_footer_side_left": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [5, 95],
                    "side_left": True,
                    "side_right": False,
                    "footer": True,
                },
            },
            "content_footer_side_right": {
                "func": self._grid_content,
                "configs": {
                    "colwidths": [95, 5],
                    "side_left": False,
                    "side_right": True,
                    "footer": True,
                },
            },
        }

        # Dummy Document setup
        self.doc_settings, self.inline_parser = _generate_inline_parser()
        self.dummy_doc = new_document("dummy", self.doc_settings)
        self.doc_language = languages.get_language(
            self.dummy_doc.settings.language_code
        )
        self.doc_memo = Struct(
            document=self.dummy_doc,
            reporter=self.dummy_doc.reporter,
            language=self.doc_language,
            title_styles=[],
            section_level=0,
            section_bubble_up_kludge=False,
            inliner=None,
        )

        self.functions: dict[
            str, Callable[..., None | nodes.Node | list[nodes.Node]]
        ] = {
            "meta": self.meta,  # type: ignore[dict-item]
            "meta_all": self.meta_all,
            "meta_links": self.meta_links,
            "meta_links_all": self.meta_links_all,  # type: ignore[dict-item]
            "meta_id": self.meta_id,
            "image": self.image,  # type: ignore[dict-item]
            "link": self.link,
            "collapse_button": self.collapse_button,
            "permalink": self.permalink,
        }

        # Prepare string_links dict, so that regex and templates get not recompiled too often.
        #
        # Do not set needs_string_links here and update it.
        # This would lead to deepcopy()-errors, as needs_string_links gets some "pickled" and jinja Environment is
        # too complex for this.
        self.string_links = {}
        for link_name, link_conf in self.needs_config.string_links.items():
            self.string_links[link_name] = {
                "url_template": Environment().from_string(link_conf["link_url"]),
                "name_template": Environment().from_string(link_conf["link_name"]),
                "regex_compiled": re.compile(link_conf["regex"]),
                "options": link_conf["options"],
                "name": link_name,
            }

    def get_need_table(self) -> nodes.table:
        if self.layout["grid"] not in self.grids.keys():
            raise SphinxNeedLayoutException(
                "Unknown layout-grid: {}. Supported are {}".format(
                    self.layout["grid"], ", ".join(self.grids.keys())
                )
            )

        func = self.grids[self.layout["grid"]]
        if callable(func):
            func()
        else:
            func["func"](**func["configs"])  # type: ignore[index]

        return self.node_table

    def get_section(self, section: str) -> nodes.line_block | list[nodes.Element]:
        try:
            lines = self.layout["layout"][section]
        except KeyError:
            # Return nothing, if not specific configuration is given for layout section
            return []

        # Needed for PDF/Latex output, where empty line_blocks raise exceptions during build
        if len(lines) == 0:
            return []

        lines_container = nodes.line_block(classes=[f"needs_{section}"])

        for line in lines:
            # line_block_node = nodes.line_block()
            line_node = nodes.line()

            line_parsed = self._parse(line)
            line_ready = self._func_replace(line_parsed)
            line_node += line_ready
            lines_container.append(line_node)

        return lines_container

    def _parse(self, line: str) -> list[nodes.Node]:
        """
        Parses a single line/string for inline rst statements, like strong, emphasis, literal, ...

        :param line: string to parse
        :return: nodes
        """
        result, message = self.inline_parser.parse(  # type: ignore
            line, 0, self.doc_memo, self.dummy_doc
        )
        if message:
            raise SphinxNeedLayoutException(message)
        return result  # type: ignore[no-any-return]

    def _func_replace(self, section_nodes: list[nodes.Node]) -> list[nodes.Node]:
        """
        Replaces a function definition like ``<<meta(a, ,b)>>`` with the related docutils nodes.

        It takes an already existing docutils-node-tree and searches for Text-nodes containing ``<<..>>``.
        These nodes get then replaced by the return value (also a node) from the related function.

        :param section_nodes: docutils node (tree)
        :return: docutils nodes
        """
        return_nodes = []
        result: None | nodes.Node | list[nodes.Node]
        for node in section_nodes:
            if not isinstance(node, nodes.Text):
                for child in node.children:
                    new_child = self._func_replace([child])
                    node.replace(child, new_child)  # type: ignore[attr-defined]
                return_nodes.append(node)
            else:
                node_str = node.astext()
                # func_elements = re.findall(r'<<([a-z_()]*)>>', node_str)
                node_line = nodes.inline()

                line_elements = re.findall(r"(<<[^<>]+>>)|([^<>]+)", node_str)

                for line_element in line_elements:
                    text = line_element[1]
                    func_def = line_element[0]
                    # Check if normal string was detected
                    if len(text) > 0 and len(func_def) == 0:
                        node_line += nodes.Text(text)
                        result = nodes.Text(text)
                    # Check if function_definition was detected
                    elif len(text) == 0 and len(func_def) > 1:
                        from sphinx_needs.functions.functions import (
                            _analyze_func_string,
                        )

                        func_def_clean = func_def.replace("<<", "").replace(">>", "")
                        func_name, func_args, func_kargs = _analyze_func_string(
                            func_def_clean, None
                        )

                        # Replace place holders
                        # Looks for {{name}}, where name must be an option of need, and replaces it with the
                        # related need content
                        for index, arg in enumerate(func_args):
                            # If argument is not a string, nothing to replace
                            # (replacement in string-lists is not supported)
                            if not isinstance(arg, str):
                                continue
                            try:
                                func_args[index] = self._replace_place_holder(arg)
                            except SphinxNeedLayoutException as e:
                                raise SphinxNeedLayoutException(
                                    'Referenced item "{}" in {} not available in need {}'.format(
                                        e, func_def_clean, self.need["id"]
                                    )
                                )

                        for key, karg in func_kargs.items():
                            # If argument is not a string, nothing to replace
                            # (replacement in string-lists is not supported)
                            if not isinstance(karg, str):
                                continue
                            try:
                                func_kargs[key] = self._replace_place_holder(karg)
                            except SphinxNeedLayoutException as e:
                                raise SphinxNeedLayoutException(
                                    'Referenced item "{}" in {} not available in need {}'.format(
                                        e, func_def_clean, self.need["id"]
                                    )
                                )

                        try:
                            func = self.functions[func_name]
                        except KeyError:
                            raise SphinxNeedLayoutException(
                                "Used function {} unknown. Please use {}".format(
                                    func_name, ", ".join(self.functions.keys())
                                )
                            )
                        result = func(*func_args, **func_kargs)

                        if result:
                            node_line += result
                    else:
                        raise SphinxNeedLayoutException(
                            f"Error during layout line parsing. This looks strange: {line_element}"
                        )

                return_nodes.append(node_line)
        return return_nodes

    def _replace_place_holder(self, data: str) -> str:
        replace_items = re.findall(r"{{(.*)}}", data)
        for item in replace_items:
            if item not in self.need:
                raise SphinxNeedLayoutException(item)
            # To escape { we need to use 2 of them.
            # So {{ becomes {{{{
            replace_string = f"{{{{{item}}}}}"
            data = data.replace(replace_string, self.need[item])  # type: ignore[literal-required]
        return data

    def meta(
        self, name: str, prefix: str | None = None, show_empty: bool = False
    ) -> nodes.inline | list[nodes.Element]:
        """
        Returns the specific metadata of a need inside docutils nodes.
        Usage::

            <<meta('status', prefix='\\*\\*status\\*\\*: ', show_empty=True)>>

        .. note::

           You must escape all rst_content in your function strings! E.g. to get `**` one must use `\\\\*\\\\*`.

        :param name: name of the need item
        :param prefix: string as rst-code, will be added infront of the value output
        :param show_empty: If false and requested need-value is None or '', no output is returned. Default: false
        :return: docutils node
        """
        data_container = nodes.inline(classes=["needs_" + name])
        if prefix:
            prefix_node = self._parse(prefix)
            label_node = nodes.inline(classes=["needs_label"])
            label_node += prefix_node
            data_container.append(label_node)
        try:
            data = self.need[name]  # type: ignore[literal-required]
        except KeyError:
            data = ""

        if data is None and not show_empty:
            return []
        elif data is None and show_empty:
            data = ""

        if isinstance(data, str):
            if len(data) == 0 and not show_empty:
                return []

            needs_string_links_option: list[str] = []
            for v in self.needs_config.string_links.values():
                needs_string_links_option.extend(v["options"])

            data_list: list[str] = (
                [i.strip() for i in re.split(r",|;", data) if len(i) != 0]
                if name in needs_string_links_option
                else [data]
            )

            matching_link_confs = []
            for link_conf in self.string_links.values():
                if name in link_conf["options"]:
                    matching_link_confs.append(link_conf)

            data_node = nodes.inline(classes=["needs_data"])
            for index, datum in enumerate(data_list):
                if matching_link_confs:
                    data_node += match_string_link(
                        text_item=datum,
                        data=datum,
                        need_key=name,
                        matching_link_confs=matching_link_confs,
                        render_context=self.needs_config.render_context,
                    )
                else:
                    # Normal text handling
                    ref_item = nodes.Text(datum)
                    data_node += ref_item

                if (
                    name in needs_string_links_option and index + 1 < len(data)
                ) or index + 1 < len([data]):
                    data_node += nodes.emphasis("; ", "; ")

            data_container.append(data_node)

        elif isinstance(data, list):
            if len(data) == 0 and not show_empty:
                return []
            list_container = nodes.inline(classes=["needs_data_container"])
            for index, element in enumerate(data):
                if index > 0:
                    spacer = nodes.inline(classes=["needs_spacer"])
                    spacer += nodes.Text(", ")
                    list_container += spacer

                inline = nodes.inline(classes=["needs_data"])
                inline += nodes.Text(element)
                list_container += inline
            data_container += list_container
        else:
            data_container.append(nodes.Text(data))

        return data_container

    def meta_id(self) -> nodes.inline:
        """
        Returns the current need id as clickable and linked reference.

        Usage::

            <<meta_id()>>

        :return: docutils node
        """
        from sphinx.util.nodes import make_refnode

        id_container = nodes.inline(classes=["needs-id"])

        nodes_id_text = nodes.Text(self.need["id"])
        if self.fromdocname and (_docname := self.need["docname"]):
            id_ref = make_refnode(
                self.app.builder,
                fromdocname=self.fromdocname,
                todocname=_docname,
                targetid=self.need["id"],
                child=nodes_id_text.deepcopy(),
                title=self.need["id"],
            )
            id_container += id_ref
        return id_container

    def meta_all(
        self,
        prefix: str = "",
        postfix: str = "",
        exclude: list[str] | None = None,
        no_links: bool = False,
        defaults: bool = True,
        show_empty: bool = False,
    ) -> nodes.inline:
        """
        ``meta_all()`` excludes by default the output of: ``docname``, ``lineno``, ``refid``,
        ``content``, ``collapse``, ``parts``, ``id_parent``,
        ``id_complete``, ``title``, ``full_title``, ``is_part``, ``is_need``,
        ``type_prefix``, ``type_color``, ``type_style``, ``type``, ``type_name``, ``id``,
        ``hide``, ``sections``, ``section_name``.

        To exclude further need-data, use ``exclude``, like ``exclude=['status', 'tags']``

        To exclude nothing, set ``defaults`` to ``False``.

        Usage::

            <<meta_all(prefix='\\*\\*', postfix='\\*\\*', no_links=True)>>

        .. note::

           You must escape all rst_content in your function strings! E.g. to get `**` one must use `\\\\*\\\\*`.

        :param prefix:
        :param postfix:
        :param exclude: List of value names, which are excluded from output
        :param no_links: excludes all incoming and outgoing extra link types from output
        :param defaults: If True, default excludes are added. This filters out all internal data, which is normally not
                         relevant for the user.
        :param show_empty: If true, also need data with no value will be printed. Mostly useful for debugging.
        :return: docutils nodes
        """
        default_excludes = list(INTERNALS)

        if exclude is None or not isinstance(exclude, list):
            if defaults:
                exclude = default_excludes
            else:
                exclude = []
        elif defaults:
            exclude += default_excludes

        if no_links:
            link_names = [x["option"] for x in self.needs_config.extra_links]
            link_names += [x["option"] + "_back" for x in self.needs_config.extra_links]
            exclude += link_names
        data_container = nodes.inline()
        for data in self.need.keys():
            if data in exclude:
                continue

            data_line = nodes.line()
            label = prefix + f"{data}:" + postfix + " "
            result = self.meta(data, label, show_empty)
            if not (show_empty or result):
                continue
            if isinstance(result, list):
                data_line += result
            else:
                data_line.append(result)

            data_container.append(data_line)

        return data_container

    def meta_links(self, name: str, incoming: bool = False) -> nodes.inline:
        """
        Documents the set links of a given link type.
        The documented links are all full clickable links to the target needs.

        :param name:  link type name
        :param incoming: If ``False``, outcoming links get documented. Use ``True`` for incoming
        :return: docutils nodes
        """
        data_container = nodes.inline(classes=[name])
        if name not in [x["option"] for x in self.needs_config.extra_links]:
            raise SphinxNeedLayoutException(f"Invalid link name {name} for link-type")

        # if incoming:
        #     link_name = self.config.extra_links[name]['incoming']
        # else:
        #     link_name = self.config.extra_links[name]['outgoing']

        from sphinx_needs.roles.need_incoming import NeedIncoming
        from sphinx_needs.roles.need_outgoing import NeedOutgoing

        node_links = (
            NeedIncoming(reftarget=self.need["id"], link_type=f"{name}_back")
            if incoming
            else NeedOutgoing(reftarget=self.need["id"], link_type=f"{name}")
        )
        node_links.append(nodes.inline(self.need["id"], self.need["id"]))
        data_container.append(node_links)
        return data_container

    def meta_links_all(
        self, prefix: str = "", postfix: str = "", exclude: list[str] | None = None
    ) -> list[nodes.line]:
        """
        Documents all used link types for the current need automatically.

        :param prefix:  prefix string
        :param postfix:  postfix string
        :param exclude:  list of extra link type names, which are excluded from output
        :return: docutils nodes
        """
        exclude = exclude or []
        data_container = []
        for link_type in self.needs_config.extra_links:
            type_key = link_type["option"]
            if self.need[type_key] and type_key not in exclude:  # type: ignore[literal-required]
                outgoing_line = nodes.line()
                outgoing_label = (
                    prefix + "{}:".format(link_type["outgoing"]) + postfix + " "
                )
                outgoing_line += self._parse(outgoing_label)
                outgoing_line += self.meta_links(link_type["option"], incoming=False)
                data_container.append(outgoing_line)

            type_key = link_type["option"] + "_back"
            if self.need[type_key] and type_key not in exclude:  # type: ignore[literal-required]
                incoming_line = nodes.line()
                incoming_label = (
                    prefix + "{}:".format(link_type["incoming"]) + postfix + " "
                )
                incoming_line += self._parse(incoming_label)
                incoming_line += self.meta_links(link_type["option"], incoming=True)
                data_container.append(incoming_line)

        return data_container

    def image(
        self,
        url: str,
        height: str | None = None,
        width: str | None = None,
        align: str | None = None,
        no_link: bool = False,
        prefix: str = "",
        is_external: bool = False,
        img_class: str = "",
    ) -> nodes.inline | list[nodes.Element]:
        """
        See https://docutils.sourceforge.io/docs/ref/rst/directives.html#images

        If **url** starts with ``icon:`` the following string is taken as icon-name and the related icon is shown.
        Example: ``icon:activity`` will show:

        .. image:: _static/activity.png

        For all icons, see https://feathericons.com/.

        Examples::

            '<<image("_images/useblocks_logo.png", height="50px", align="center")>>',
            '<<image("icon:bell", height="20px", align="center")>>'
            '<<image("field:url", height="60px", align="center")>>'  # Get url from need['url']

        If **url** starts with ``:field`` the URL value is taken from the defined field of the current need
        object.

        .. hint:: Relative URLs

           If a relative path for the URL parameter is given, it must be relative to the documentation
           root folder and not relative to the current need location, for which it gets executed.

           Example: ``<<image("_static/picture.png")>>``,

        :param url: Relative path to the project folder or an absolute path
        :param height:
        :param width:
        :param align:
        :param no_link:
        :param prefix: Prefix string in front of the image
        :param is_external: If ``True`` url references an external image, which needs to be downloaded
        :param img_class: Custom class name for image element
        :return: An inline docutils node element
        :rtype: :class: docutils.nodes.inline
        """
        builder = self.app.builder
        env = self.app.env

        data_container = nodes.inline()
        if prefix:
            prefix_node = self._parse(prefix)
            label_node = nodes.inline(classes=["needs_label"])
            label_node += prefix_node
            data_container.append(label_node)

        # from sphinx.addnodes import
        options = {}
        if height:
            options["height"] = height
        if width:
            options["width"] = width
        if align:
            options["align"] = align

        if url is None or not isinstance(url, str):
            raise SphinxNeedLayoutException(
                "not valid url given for image function in layout"
            )

        if url.startswith("icon:"):
            if any(x in builder.name.upper() for x in ["PDF", "LATEX"]):
                # latexpdf can't handle svg files. We not to use the png format here.
                builder_extension = "png"
            else:
                builder_extension = "svg"

            # url = '_static/sphinx-needs/images/{}.{}'.format(url.split(':')[1], builder_extension)
            needs_location = os.path.dirname(__file__)
            url = os.path.join(
                needs_location,
                "images",
                f"feather_{builder_extension}",
                "{}.{}".format(url.split(":")[1], builder_extension),
            )

            # if not any(x in self.app.builder.name.upper() for x in ['PDF', 'LATEX']):
            #     # This is not needed for Latex. as latex puts the complete content in a single text file on root level
            #     # The url needs to be relative to the current document where the need is defined
            #     # Otherwise the link is aiming "too high".
            #     # Normally sphinx is doing this kind of calculation, but it looks like not in the current state
            #     subfolder_amount = self.need['docname'].count('/')
            #     url = '../' * subfolder_amount + url
        elif url.startswith("field:"):
            field = url.split(":")[1]
            try:
                value = self.need[field]  # type: ignore[literal-required]
            except KeyError:
                value = ""

            if value is None or len(value) == 0:
                return []

            url = value

        if is_external:
            url_parsed = urlparse(url)
            filename = os.path.basename(url_parsed.path) + ".png"
            path = os.path.join(self.app.srcdir, "images")
            file_path = os.path.join(path, filename)

            # Download only, if file not downloaded yet
            if not os.path.exists(file_path):
                with suppress(FileExistsError):
                    os.mkdir(path)
                response = requests.get(url)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)

            url = file_path

        classes = []
        if len(img_class) != 0 and no_link:
            classes.extend([img_class, "no-scaled-link"])

        if len(img_class) == 0 and no_link:
            classes.extend(["needs_image", "no-scaled-link"])

        if len(img_class) == 0 and not no_link:
            classes.append("needs_image")

        image_node = nodes.image(url, classes=classes, **options)
        image_node["candidates"] = {"*": url}
        # image_node['candidates'] = '*'
        image_node["uri"] = url

        # Sphinx voodoo needed here.
        # It is not enough to just add a doctuils nodes.image, we also have to register the imag location for sphinx
        # Otherwise the images gets not copied to the later build-output location
        if _docname := self.need["docname"]:
            env.images.add_file(_docname, url)

        data_container.append(image_node)
        return data_container

    def link(
        self,
        url: str,
        text: str | None = None,
        image_url: str | None = None,
        image_height: str | None = None,
        image_width: str | None = None,
        prefix: str = "",
        is_dynamic: bool = False,
    ) -> nodes.inline:
        """
        Shows a link.
        Link can be a text, an image or both

        :param url:
        :param text:
        :param image_url:
        :param image_height:
        :param image_width:
        :param prefix: Additional string infront of the string
        :param is_dynamic: if ``True``, ``url`` is not static and gets read from need
        :return:

        Examples::

            <<link('http://sphinx-docs.org', 'Sphinx')>>
            <<link('url', 'Link', is_dynamic=True)>>  # Reads url from need[url]
        """
        data_container = nodes.inline()
        if prefix:
            prefix_node = self._parse(prefix)
            label_node = nodes.inline(classes=["needs_label"])
            label_node += prefix_node
            data_container.append(label_node)

        text = text or ""  # May be needed if only image shall be shown

        if is_dynamic:
            try:
                url = self.need[url]  # type: ignore[literal-required]
            except KeyError:
                url = ""

        link_node = nodes.reference(text, text, refuri=url)

        if image_url:
            image_node = self.image(image_url, image_height, image_width, no_link=True)
            link_node.append(image_node)

        data_container.append(link_node)

        return data_container

    def collapse_button(
        self,
        target: str = "meta",
        collapsed: str = "Show",
        visible: str = "Close",
        initial: bool = False,
    ) -> nodes.inline | None:
        """
        To show icons instead of text on the button, use collapse_button() like this::

            <<collapse_button("icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>>

        For the builders ``latex`` and ``latexpdf`` no output is returned, as their build results are really static
        and collapse-feature can not be implemented..

        :param target: css_name of row to collapse. Default is ``meta``
        :param collapsed: Text or image/icon string to show when target rows are collapsed
        :param visible: Text or image/icon string to show when target rows are visible
        :param initial: If True, initial status will hide rows after loading page.
        :return: docutils nodes
        """
        builder = self.app.builder
        if any(x in builder.name.upper() for x in ["PDF", "LATEX"]):
            # PDF/Latex output do not support collapse functions
            return None

        coll_node_collapsed = nodes.inline(classes=["needs", "collapsed"])
        coll_node_visible = nodes.inline(classes=["needs", "visible"])

        if collapsed.startswith("image:") or collapsed.startswith("icon:"):
            coll_node_collapsed.append(
                self.image(
                    collapsed.replace("image:", ""),
                    width="17px",
                    no_link=True,
                    img_class="sn_collapse_img",
                )
            )
        elif collapsed.startswith("Debug view"):
            coll_node_collapsed.append(
                nodes.container(classes=["debug_on_layout_btn"])
            )  # For debug layout
        else:
            coll_node_collapsed.append(nodes.Text(collapsed))

        if visible.startswith("image:") or visible.startswith("icon:"):
            coll_node_visible.append(
                self.image(
                    visible.replace("image:", ""),
                    width="17px",
                    no_link=True,
                    img_class="sn_collapse_img",
                )
            )
        elif visible.startswith("Debug view"):
            coll_node_visible.append(nodes.container(classes=["debug_off_layout_btn"]))
        else:
            coll_node_visible.append(nodes.Text(visible))

        coll_container = nodes.inline(classes=["needs", "needs_collapse"])
        # docutils doesn't allow has to add any html-attributes beside class and id to nodes.
        # So we misused "id" for this and use "__" (2x _) as separator for row-target names

        if (not self.need["collapse"]) or (
            self.need["collapse"] is None and not initial
        ):
            status = "show"

        if (self.need["collapse"]) or (not self.need["collapse"] and initial):
            status = "hide"

        target_strings = target.split(",")
        final_targets = [x.strip() for x in target_strings]
        targets = ["target__" + status + "__" + "__".join(final_targets)]
        coll_container.attributes["ids"] = targets
        coll_container.append(coll_node_collapsed)
        coll_container.append(coll_node_visible)

        return coll_container

    def permalink(
        self,
        image_url: str | None = None,
        image_height: str | None = None,
        image_width: str | None = None,
        text: str | None = None,
        prefix: str = "",
    ) -> nodes.inline:
        """
        Shows a permanent link to the need.
        Link can be a text, an image or both

        :param image_url: image for an image link
        :param image_height: None
        :param image_width: None
        :param text: text for a text link
        :param prefix: Additional string infront of the string
        :return:

        Examples::

            <<permalink()>>
            <<permalink(image_url="icon:link")>>
            <<permalink(text='¶')>>
        """

        if image_url is None and text is None:
            image_url = "icon:share-2"
            image_width = "17px"

        permalink = self.needs_config.permalink_file
        id = self.need["id"]
        permalink_url = ""
        if docname := self.need["docname"]:
            for _ in range(0, len(docname.split("/")) - 1):
                permalink_url += "../"
        permalink_url += permalink + "?id=" + id

        return self.link(
            url=permalink_url,
            text=text,
            image_url=image_url,
            image_width=image_width,
            image_height=image_height,
            prefix=prefix,
        )

    def _grid_simple(
        self,
        colwidths: list[int],
        side_left: bool | str,
        side_right: bool | str,
        footer: bool,
    ) -> None:
        """
        Creates most "simple" grid layouts.
        Side parts and footer can be activated via config.

        .. code-block:: text

            +------+---------+------+
            |      | Head    |      |
            |      +---------+      |
            |      | Meta    |      |
            | Side +---------+ Side |
            |      | Content |      |
            |      +---------+      |
            |      | Footer  |      |
            +------+---------+------+

        Only one active side is supported, as the section name is "side" for left and right section.

        If ``side_right`` or ``side_left`` is set to ``partial``, the table grids looks like::

        +------+------+------+
        |      | Head |      |
        | Side +------+ Side |
        |      | Meta |      |
        +------+------+------+
        | Content            |
        +--------------------+
        | Footer             |
        +--------------------+


        :param colwidths: List of integer for column widths
        :param side_left: False, 'full' or 'part'
        :param side_right: False, 'full' or 'part'
        :param footer:  True or False
        :return: need-table node
        """
        common_more_cols = 0

        if side_left:
            if side_left == "full":
                side_left_morerows = 2
            else:
                side_left_morerows = 1
                common_more_cols += 1
            if footer:
                side_left_morerows += 1

        if side_right:
            if side_right == "full":
                side_right_morerows = 2
            else:
                side_right_morerows = 1
                common_more_cols += 1
            if footer:
                side_right_morerows += 1

        # Table definition
        node_tgroup = nodes.tgroup(cols=common_more_cols)
        self.node_table += node_tgroup

        for width in colwidths:
            node_colspec = nodes.colspec(colwidth=width)
            node_tgroup += node_colspec

        # HEAD row
        head_row = nodes.row(classes=["need", "head"])

        if side_left:
            side_entry = nodes.entry(
                classes=["need", "side"], morerows=side_left_morerows
            )
            side_entry += self.get_section("side")
            head_row += side_entry

        head_entry = nodes.entry(classes=["need", "head"])
        head_entry += self.get_section("head")
        head_row += head_entry

        if side_right:
            side_entry = nodes.entry(
                classes=["need", "side"], morerows=side_right_morerows
            )
            side_entry += self.get_section("side")
            head_row += side_entry

        # META row
        meta_row = nodes.row(classes=["need", "meta"])
        meta_entry = nodes.entry(classes=["need", "meta"])
        meta_entry += self.get_section("meta")
        meta_row += meta_entry

        # CONTENT row
        content_row = nodes.row(classes=["need", "content"])
        content_entry = nodes.entry(
            classes=["need", "content"], morecols=common_more_cols
        )
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        # FOOTER row
        if footer:
            footer_row = nodes.row(classes=["need", "footer"])
            footer_entry = nodes.entry(
                classes=["need", "footer"], morecols=common_more_cols
            )
            footer_entry += self.get_section("footer")
            footer_row += footer_entry

        # Construct table
        self.node_tbody += head_row
        self.node_tbody += meta_row
        self.node_tbody += content_row
        if footer:
            self.node_tbody += footer_row
        node_tgroup += self.node_tbody

    def _grid_complex(self) -> None:
        node_tgroup = nodes.tgroup(cols=6)
        self.node_table += node_tgroup

        col_widths = [10, 10, 30, 30, 10, 10]
        for width in col_widths:
            node_colspec = nodes.colspec(colwidth=width)
            node_tgroup += node_colspec

        # HEAD row
        head_row = nodes.row(classes=["head"])
        self.node_tbody += head_row
        # HEAD left
        head_left_entry = nodes.entry(classes=["head_left"], morecols=1)
        head_left_entry += self.get_section("head_left")
        head_row += head_left_entry
        # HEAD mid
        head_entry = nodes.entry(classes=["head_center"], morecols=1)
        head_entry += self.get_section("head")
        head_row += head_entry
        # HEAD right
        head_right_entry = nodes.entry(classes=["head_right"], morecols=1)
        head_right_entry += self.get_section("head_right")
        head_row += head_right_entry

        # META row
        meta_row = nodes.row(classes=["meta"])
        self.node_tbody += meta_row
        # META left
        meta_left_entry = nodes.entry(classes=["meta"], morecols=2)
        meta_left_entry += self.get_section("meta_left")
        meta_row += meta_left_entry
        # META right
        meta_right_entry = nodes.entry(classes=["meta"], morecols=2)
        meta_right_entry += self.get_section("meta_right")
        meta_row += meta_right_entry

        # CONTENT row
        content_row = nodes.row(classes=["content"])
        self.node_tbody += content_row
        content_entry = nodes.entry(classes=["content"], morecols=5)
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        # FOOTER row
        footer_row = nodes.row(classes=["footer"])
        self.node_tbody += footer_row
        # FOOTER left
        footer_left_entry = nodes.entry(classes=["footer_left"], morecols=1)
        footer_left_entry += self.get_section("footer_left")
        footer_row += footer_left_entry
        # FOOTER mid
        footer_entry = nodes.entry(classes=["footer"], morecols=1)
        footer_entry += self.get_section("footer")
        footer_row += footer_entry
        # FOOTER right
        footer_right_entry = nodes.entry(classes=["footer_right"], morecols=1)
        footer_right_entry += self.get_section("footer_right")
        footer_row += footer_right_entry

        # Construct table
        node_tgroup += self.node_tbody

    def _grid_content(
        self, colwidths: list[int], side_left: bool, side_right: bool, footer: bool
    ) -> None:
        """
        Creates most "content" based grid layouts.
        Side parts and footer can be activated via config.

        +------+---------+------+
        |      | Content |      |
        | Side +---------+ Side |
        |      | Footer  |      |
        +------+---------+------+

        Only one active side is supported, as the section name is "side" for left and right section.

        :param colwidths: List of integer for column widths
        :param side_left: True or False
        :param side_right: True or False
        :param footer:  True or False
        :return: need-table node
        """
        side_morerows = 0
        if footer:
            side_morerows = 1

        # Table definition
        node_tgroup = nodes.tgroup(cols=len(colwidths))
        self.node_table += node_tgroup

        for width in colwidths:
            node_colspec = nodes.colspec(colwidth=width)
            node_tgroup += node_colspec

        # CONTENT row
        content_row = nodes.row(classes=["content"])

        if side_left:
            side_entry = nodes.entry(classes=["side", "left"], morerows=side_morerows)
            side_entry += self.get_section("side")
            content_row += side_entry

        content_entry = nodes.entry(classes=["content"])
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        if side_right:
            side_entry = nodes.entry(classes=["side", "right"], morerows=side_morerows)
            side_entry += self.get_section("side")
            content_row += side_entry

        # FOOTER row
        if footer:
            footer_row = nodes.row(classes=["footer"])
            footer_entry = nodes.entry(classes=["footer"])
            footer_entry += self.get_section("footer")
            footer_row += footer_entry

        # Construct table
        self.node_tbody += content_row
        if footer:
            self.node_tbody += footer_row
        node_tgroup += self.node_tbody


class SphinxNeedLayoutException(BaseException):
    """Raised if problems with layout handling occurs"""
