"""
Cares about the correct creation and handling of need layout.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/102
"""
import re
from docutils import nodes

GRIDS = ['simple', 'complex', 'single', 'side_right', 'side_right_part']


def build_need(layout, node, app):

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

    lh = LayoutHandler(need_data, need_layout)

    node_container = nodes.container()

    if need_layout['grid'] == 'simple':
        node_container += lh.get_section('head')
        node_container += lh.get_section('meta')
        node_container += lh.get_section('content')
        node_container += lh.get_section('footer')
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

    node.insert(0, node_container)


class LayoutHandler:
    def __init__(self, need, layout):
        self.need = need
        self.layout = layout

    def get_section(self, section):
        try:
            lines = self.layout['layout'][section]
        except KeyError:
            # Return nothing, if not specific configuration is given for layout section
            return []

        lines_block = nodes.line_block(classes=['needs_{}'.format(section)])

        for line in lines:
            line_node = nodes.line()

            func_elements = re.findall(r'<<([a-z]*)>>', line)
            rst_elements = re.sub(r'<<([a-z]*)>>', '?+?', line).split('?+?')

            for index, rst_element in enumerate(rst_elements):
                rst_element_line = nodes.inline(rst_element, rst_element)
                line_node.append(rst_element_line)

                if index < len(func_elements):
                    func_element_line = nodes.inline(func_elements[index], func_elements[index])
                    line_node.append(func_element_line)

            lines_block.append(line_node)

        return lines_block


    def type(self):
        return []

    def title(self):
        return []

    def id(self):
        return []




class SphinxNeedLayoutException(BaseException):
    """Raised if problems with layout handling occurs"""
