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

GRIDS = ['simple', 'complex', 'single', 'side_right', 'side_right_part']


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
    if need_layout['grid'] not in GRIDS:
        raise SphinxNeedLayoutException('Used grid "{}" is unknown. Known grids are: {}'.format(
            need_layout['grid'], ', '.join(GRIDS)
        ))
    need_id = node.attributes["ids"][0]
    need_data = needs[need_id]

    lh = LayoutHandler(need_data, need_layout, node)

    node_table = nodes.table(classes=["needtable"])

    node_tgroup = nodes.tgroup(cols=1)
    node_table += node_tgroup

    node_colspec = nodes.colspec(colwidth=100)
    node_tgroup += node_colspec

    node_tbody = nodes.tbody()

    if need_layout['grid'] == 'simple':
        # HEAD row
        head_row = nodes.row()
        head_entry = nodes.entry()
        head_entry += lh.get_section('head')
        head_row += head_entry

        # META row
        meta_row = nodes.row()
        meta_entry = nodes.entry()
        meta_entry += lh.get_section('meta')
        meta_row += meta_entry

        # CONTENT row
        content_row = nodes.row()
        content_entry = nodes.entry()
        content_entry += lh.get_section('content')
        content_row += content_entry

        # FOOTER row
        footer_row = nodes.row()
        footer_entry = nodes.entry()
        footer_entry += lh.get_section('footer')
        footer_row += footer_entry

        # Construct table
        node_tbody += head_row
        node_tbody += meta_row
        node_tbody += content_row
        node_tbody += footer_row
        node_tgroup += node_tbody

    elif need_layout['grid'] == 'complex':
        pass
    elif need_layout['grid'] == 'single':
        pass
    elif need_layout['grid'] == 'side_right':
        pass
    elif need_layout['grid'] == 'side_right_part':
        pass
    else:
        raise SphinxNeedLayoutException('Something went really wrong during layout handling.')

    node.insert(0, node_table)


class LayoutHandler:
    def __init__(self, need, layout, node):
        self.need = need
        self.layout = layout
        self.node = node
        self.content = nodes.container()
        self.content.extend(node.children)

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

    def get_section(self, section):
        try:
            lines = self.layout['layout'][section]
        except KeyError:
            # Return nothing, if not specific configuration is given for layout section
            return []

        lines_container = nodes.container(classes=['needs_{}'.format(section)])

        for line in lines:
            line_node = nodes.line()

            # ([^<>]+)|(<<[a-zA-Z_(),\- ]*>>)
            func_elements = re.findall(r'<<([a-z_()]*)>>', line)
            rst_elements = re.sub(r'<<([a-z_()]*)>>', '?+?', line).split('?+?')

            for index, rst_element in enumerate(rst_elements):
                rst_element_line = self._parse(rst_element)
                line_node += rst_element_line

                if index < len(func_elements):
                    func_def = func_elements[index]
                    func_name, func_args = re.findall(r'^([\w_]+)(\(.*\))?', func_def)[0]
                    func_name = '_' + func_name
                    func = getattr(self, func_name, None)
                    if func is not None:
                        attrs = func_args[1:-1].split(',')
                        attrs = [x for x in attrs if len(x) > 0]
                        result = func(*attrs)
                    else:
                        result = nodes.inline(func_elements[index], func_elements[index])

                    if result is not None:
                        line_node.append(result)

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

    def _meta(self, name):
        try:
            text = self.need[name]
        except KeyError:
            text = ''

        if text is None:
            return None

        return nodes.inline(text, text)

    def _content(self):
        return self.content


class SphinxNeedLayoutException(BaseException):
    """Raised if problems with layout handling occurs"""
