"""
Cares about the correct creation and handling of need layout.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/102
"""
import re
from docutils import nodes
from docutils.frontend import OptionParser
from docutils.parsers.rst import languages, Parser
from docutils.parsers.rst.states import Inliner, Struct
from docutils.utils import new_document


def build_need(layout, node, app):
    """
    Creates a need based on a given layout.

    The created table must have ethe following docutils structure::

        - table
        -- tgroup
        --- colspec (partial used)
        --- thead (not used)
        --- tbody
        ---- row
        ----- entry
        ------ custom layout nodes

    The level structure must be kept, otherwise docutils can not handle it!

    :param layout:
    :param node:
    :param app:
    :return:
    """

    env = app.builder.env
    needs = env.needs_all_needs

    available_layouts = getattr(app.config, 'needs_layouts', {})
    if layout not in available_layouts.keys():
        raise SphinxNeedLayoutException('Given layout "{}" is unknown. Registered layouts are: {}'.format(
            layout, ', '.join(available_layouts.keys())))

    need_layout = available_layouts[layout]
    need_id = node.attributes["ids"][0]
    need_data = needs[need_id]

    lh = LayoutHandler(app, need_data, need_layout, node)
    new_need_node = lh.get_need_table()

    # We need to replace the current need-node (containing content only) with our new table need node.
    node.parent.replace(node, new_need_node)


class LayoutHandler:
    def __init__(self, app, need, layout, node):
        self.app = app
        self.need = need
        self.layout = layout
        self.node = node

        self.node_table = nodes.table(classes=["need"], ids=[self.need['id']])
        self.node_tbody = nodes.tbody()

        self.grids = {
            'simple': self._grid_simple,
            'complex': self._grid_complex
        }

        # Dummy Document setup
        self.doc_settings = OptionParser(
            components=(Parser,)
        ).get_default_values()
        self.dummy_doc = new_document("dummy", self.doc_settings)
        self.doc_language = languages.get_language(
            self.dummy_doc.settings.language_code)
        self.doc_memo = Struct(document=self.dummy_doc,
                               reporter=self.dummy_doc.reporter,
                               language=self.doc_language,
                               title_styles=[],
                               section_level=0,
                               section_bubble_up_kludge=False,
                               inliner=None)

    def get_need_table(self):
        if self.layout['grid'] not in self.grids.keys():
            raise SphinxNeedLayoutException('Unknown layout-grid: {}. Supported are {}'.format(
                self.layout['grid'], ', '.join(self.grids.keys())
            ))

        self.grids[self.layout['grid']]()
        return self.node_table

    def _grid_simple(self):
        # Table definition
        node_tgroup = nodes.tgroup(cols=1)
        self.node_table += node_tgroup

        node_colspec = nodes.colspec(colwidth=100)
        node_tgroup += node_colspec

        # HEAD row
        head_row = nodes.row(classes=['head'])
        head_entry = nodes.entry(classes=['head'])
        head_entry += self.get_section('head')
        head_row += head_entry

        # META row
        meta_row = nodes.row(classes=['meta'])
        meta_entry = nodes.entry(classes=['meta'])
        meta_entry += self.get_section('meta')
        meta_row += meta_entry

        # CONTENT row
        content_row = nodes.row(classes=['content'])
        content_entry = nodes.entry(classes=['content'])
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        # Construct table
        self.node_tbody += head_row
        self.node_tbody += meta_row
        self.node_tbody += content_row
        node_tgroup += self.node_tbody

    def _grid_complex(self):
        node_tgroup = nodes.tgroup(cols=6)
        self.node_table += node_tgroup

        col_widths = [10, 10, 30, 30, 10, 10]
        for width in col_widths:
            node_colspec = nodes.colspec(colwidth=width)
            node_tgroup += node_colspec

        # HEAD row
        head_row = nodes.row(classes=['head'])
        self.node_tbody += head_row
        # HEAD left
        head_left_entry = nodes.entry(classes=['head'], morecols=1)
        head_left_entry += self.get_section('head_left')
        head_row += head_left_entry
        # HEAD mid
        head_entry = nodes.entry(classes=['head'], morecols=1)
        head_entry += self.get_section('head')
        head_row += head_entry
        # HEAD right
        head_right_entry = nodes.entry(classes=['head'], morecols=1)
        head_right_entry += self.get_section('head_right')
        head_row += head_right_entry

        # META row
        meta_row = nodes.row(classes=['meta'])
        self.node_tbody += meta_row
        # META left
        meta_left_entry = nodes.entry(classes=['meta'], morecols=2)
        meta_left_entry += self.get_section('meta_left')
        meta_row += meta_left_entry
        # META right
        meta_right_entry = nodes.entry(classes=['meta'], morecols=2)
        meta_right_entry += self.get_section('meta_right')
        meta_row += meta_right_entry

        # CONTENT row
        content_row = nodes.row(classes=['content'])
        self.node_tbody += content_row
        content_entry = nodes.entry(classes=['content'], morecols=5)
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        # FOOTER row
        footer_row = nodes.row(classes=['footer'])
        self.node_tbody += footer_row
        # FOOTER left
        footer_left_entry = nodes.entry(classes=['footer'], morecols=1)
        footer_left_entry += self.get_section('footer_left')
        footer_row += footer_left_entry
        # FOOTER mid
        footer_entry = nodes.entry(classes=['footer'], morecols=1)
        footer_entry += self.get_section('footer')
        footer_row += footer_entry
        # FOOTER right
        footer_right_entry = nodes.entry(classes=['footer'], morecols=1)
        footer_right_entry += self.get_section('footer_right')
        footer_row += footer_right_entry

        # Construct table
        node_tgroup += self.node_tbody

    def get_section(self, section):
        try:
            lines = self.layout['layout'][section]
        except KeyError:
            # Return nothing, if not specific configuration is given for layout section
            return []

        lines_container = nodes.container(classes=['needs_{}'.format(section)])

        for line in lines:
            line_node = nodes.line()

            line_parsed = self._parse(line)
            line_ready = self._func_replace(line_parsed)
            line_node += line_ready
            lines_container.append(line_node)

        return lines_container

    def _parse(self, line):
        """
        Parses a single line/string for inline rst statements, like strong, emphasis, literal, ...

        :param line: string to parse
        :return: nodes
        """
        inline_parser = Inliner()
        inline_parser.init_customizations(self.doc_settings)
        result, message = inline_parser.parse(line, 0, self.doc_memo, self.dummy_doc)
        if message:
            raise SphinxNeedLayoutException(message)
        return result

    def _func_replace(self, section_nodes):
        return_nodes = []
        for node in section_nodes:
            if not isinstance(node, nodes.Text):
                for child in node.children:
                    new_child = self._func_replace([child])
                    node.replace(child, new_child)
                return_nodes.append(node)
            else:
                node_str = str(node)
                # func_elements = re.findall(r'<<([a-z_()]*)>>', node_str)
                node_line = nodes.inline()

                line_elements = re.findall(r'([^<>]+)|(<<[a-zA-Z_(),\-:;* ]*>>)', node_str)

                for line_element in line_elements:
                    text = line_element[0]
                    func_def = line_element[1]
                    # Check if normal string was detected
                    if len(text) > 0 and len(func_def) == 0:
                        node_line += nodes.Text(text, text)
                        result = nodes.Text(text, text)
                    # Check if function_definition was detected
                    elif len(text) == 0 and len(func_def) > 1:
                        func_name, func_args = re.findall(r'([\w_]+)(\(.*\))?', func_def)[0]
                        func_name = '_' + func_name
                        func = getattr(self, func_name, None)
                        if func is not None:
                            attrs = func_args[1:-1].split(',')
                            attrs = [x for x in attrs if len(x) > 0]
                            result = func(*attrs)
                        else:
                            result = nodes.Text(func_def, func_def)
                        node_line += result
                    else:
                        raise SphinxNeedLayoutException('Error during layout line parsing. This looks strange: {}'.format(
                            line_element))

                return_nodes.append(node_line)
        return return_nodes

    def _meta(self, name, prefix=None):
        data_container = nodes.inline(classes=[name])
        if prefix is not None:
            prefix_node = self._parse(prefix)
            data_container += prefix_node
        try:
            data = self.need[name]
        except KeyError:
            data = ''

        if data is None:
            return []

        if isinstance(data, str):
            if len(data) == 0:
                return []
            data_container.append(nodes.Text(data, data))
        elif isinstance(data, list):
            if len(data) == 0:
                return []
            list_container = nodes.inline(classes=[name])
            for index, element in enumerate(data):
                if index > 0:
                    spacer = nodes.inline(classes=['spacer'])
                    spacer += nodes.Text(', ', ', ')
                    list_container += spacer

                inline = nodes.inline(classes=[element.replace(' ', '_').lower()])
                inline += nodes.Text(element, element)
                list_container += inline
            data_container += list_container
        else:
            data_container.append(nodes.Text(data, data))

        return data_container

    def _meta_id(self):
        from sphinx.util.nodes import make_refnode
        id_container = nodes.inline(classes=["needs-id"])

        nodes_id_text = nodes.Text(self.need['id'], self.need['id'])
        id_ref = make_refnode(self.app.builder,
                              fromdocname=self.need['docname'],
                              todocname=self.need['docname'],
                              targetid=self.need['id'],
                              child=nodes_id_text.deepcopy(),
                              title=self.need['id'])
        id_container += id_ref
        return id_container


    def _meta_links(self, name, incoming=False):
        data_container = nodes.inline(classes=[name])
        if name not in [x['option'] for x in self.app.config.needs_extra_links]:
            raise SphinxNeedLayoutException('Invalid link name {} for link-type'.format(name))

        # if incoming:
        #     link_name = self.app.config.needs_extra_links[name]['incoming']
        # else:
        #     link_name = self.app.config.needs_extra_links[name]['outgoing']

        from sphinxcontrib.needs.roles.need_outgoing import Need_outgoing
        from sphinxcontrib.needs.roles.need_incoming import Need_incoming
        if incoming:
            node_links = Need_incoming(reftarget=self.need['id'], link_type='{}_back'.format(name))
        else:
            node_links = Need_outgoing(reftarget=self.need['id'], link_type='{}'.format(name))
        node_links.append(nodes.inline(self.need['id'], self.need['id']))
        data_container.append(node_links)
        return data_container

    def _meta_links_all(self, prefix='', postfix=''):
        data_container = []
        for link_type in self.app.config.needs_extra_links:
            type_key = link_type['option']
            if self.need[type_key] is not None and len(self.need[type_key]) > 0:
                outgoing_line = nodes.line()
                outgoing_label = prefix + '{}:'.format(link_type['outgoing']) + postfix + ' '
                outgoing_line += self._parse(outgoing_label)
                outgoing_line += self._meta_links(link_type['option'], incoming=False)
                data_container.append(outgoing_line)

            type_key = link_type['option'] + '_back'
            if self.need[type_key] is not None and len(self.need[type_key]) > 0:
                incoming_line = nodes.line()
                incoming_label = prefix + '{}:'.format(link_type['incoming']) + postfix + ' '
                incoming_line += self._parse(incoming_label)
                incoming_line += self._meta_links(link_type['option'], incoming=True)
                data_container.append(incoming_line)

        return data_container



class SphinxNeedLayoutException(BaseException):
    """Raised if problems with layout handling occurs"""
