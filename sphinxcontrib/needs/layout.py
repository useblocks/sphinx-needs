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

from sphinxcontrib.needs.utils import INTERNALS


def create_need(need_id, app, layout=None, style=None, docname=None):
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
    env = app.builder.env
    needs = env.needs_all_needs

    if need_id not in needs.keys():
        raise SphinxNeedLayoutException('Given need id {} does not exist.'.format(need_id))
    need_data = needs[need_id]

    node_container = nodes.container()
    node_inner = needs[need_id]['content_node']
    # Resolve internal refernces.
    # This is done for original need content automatically.
    # But as we are working on  a copy, we have to trigger this on our own.
    if docname is None:
        docname = needs[need_id]['docname']  # needed to calculate relative references

    # resolve_references() ignores the given docname and takes the docname from the pending_xref node.
    # Therefore we need to manipulate this first, before we can ask Sphinx to perform the normal
    # reference handling for us.
    replace_pending_xref_refdoc(node_inner, docname)
    env.resolve_references(node_inner, docname, env.app.builder)

    node_container.append(node_inner)

    node_inner.attributes['ids'].append(need_id)

    if layout is None:
        if need_data['layout'] is None or len(need_data['layout']) == 0:
            layout = getattr(app.config, 'needs_default_layout', 'clean')
        else:
            layout = need_data['layout']

    if style is None:
        if need_data['style'] is None or len(need_data['style']) == 0:
            style = getattr(app.config, 'needs_default_style', 'None')
        else:
            style = need_data['style']

    build_need(layout, node_inner, app, style, docname)

    return node_container


def replace_pending_xref_refdoc(node, new_refdoc):
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
        node.attributes['refdoc'] = new_refdoc
    else:
        for child in node.children:
            replace_pending_xref_refdoc(child, new_refdoc)


def build_need(layout, node, app, style=None, fromdocname=None):
    """
    Builds a need based on a given layout for a given need-node.

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
    :param style:
    :param fromdocname:
    :return:
    """

    env = app.builder.env
    needs = env.needs_all_needs

    need_layout = layout
    need_id = node.attributes["ids"][0]
    need_data = needs[need_id]

    if need_data['hide']:
        node.parent.replace(node, [])
        return

    if fromdocname is None:
        fromdocname = need_data['docname']

    lh = LayoutHandler(app, need_data, need_layout, node, style, fromdocname)
    new_need_node = lh.get_need_table()

    # We need to replace the current need-node (containing content only) with our new table need node.
    node.parent.replace(node, new_need_node)


class LayoutHandler:
    """
    Cares about the correct layout handling
    """
    def __init__(self, app, need, layout, node, style=None, fromdocname=None):
        self.app = app
        self.need = need

        self.layout_name = layout
        available_layouts = getattr(app.config, 'needs_layouts', {})
        if self.layout_name not in available_layouts.keys():
            raise SphinxNeedLayoutException(
                'Given layout "{}" is unknown for need {}. Registered layouts are: {}'.format(
                    self.layout_name, need['id'], ' ,'.join(available_layouts.keys())))
        self.layout = available_layouts[self.layout_name]

        self.node = node

        # Used, if need is referenced from another page
        if fromdocname is None:
            self.fromdocname = need['docname']
        else:
            self.fromdocname = fromdocname

        classes = ["need",
                   'needs_grid_' + self.layout['grid'],
                   'needs_layout_' + self.layout_name]

        if style is not None:
            self.style = style
        elif self.need['style'] is not None:
            self.style = self.need['style']
        else:
            self.style = getattr(self.app.config, 'needs_default_style', None)

        if self.style and len(self.style) > 0:
            for style in self.style.strip().split(','):
                style = style.strip()
                classes.append('needs_style_' + style)
        else:
            classes.append('needs_style_none')

        classes.append('needs_type_' + ''.join(self.need['type'].split()))

        self.node_table = nodes.table(classes=classes, ids=[self.need['id']])
        self.node_tbody = nodes.tbody()

        self.grids = {
            'simple': {
                'func': self._grid_simple,
                'configs': {
                    'colwidths': [100],
                    'side_left': False,
                    'side_right': False,
                    'footer': False
                }
            },
            'simple_side_left': {
                'func': self._grid_simple,
                'configs': {
                    'colwidths': [30, 70],
                    'side_left': 'full',
                    'side_right': False,
                    'footer': False
                }
            },
            'simple_side_right': {
                'func': self._grid_simple,
                'configs': {
                    'colwidths': [70, 30],
                    'side_left': False,
                    'side_right': 'full',
                    'footer': False
                }
            },
            'simple_side_left_partial': {
                'func': self._grid_simple,
                'configs': {
                    'colwidths': [20, 80],
                    'side_left': 'part',
                    'side_right': False,
                    'footer': False
                }
            },
            'simple_side_right_partial': {
                'func': self._grid_simple,
                'configs': {
                    'colwidths': [80, 20],
                    'side_left': False,
                    'side_right': 'part',
                    'footer': False
                }
            },

            'complex': self._grid_complex,

            'content': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [100],
                    'side_left': False,
                    'side_right': False,
                    'footer': False
                }
            },

            'content_footer': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [100],
                    'side_left': False,
                    'side_right': False,
                    'footer': True
                }
            },
            'content_side_left': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [5, 95],
                    'side_left': True,
                    'side_right': False,
                    'footer': False
                }
            },
            'content_side_right': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [95, 5],
                    'side_left': False,
                    'side_right': True,
                    'footer': False
                }
            },
            'content_footer_side_left': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [5, 95],
                    'side_left': True,
                    'side_right': False,
                    'footer': True
                }
            },
            'content_footer_side_right': {
                'func': self._grid_content,
                'configs': {
                    'colwidths': [95, 5],
                    'side_left': False,
                    'side_right': True,
                    'footer': True
                }
            },
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

        self.functions = {
            'meta': self.meta,
            'meta_all': self.meta_all,
            'meta_links': self.meta_links,
            'meta_links_all': self.meta_links_all,
            'meta_id': self.meta_id,
            'image': self.image,
            'link': self.link,
            'collapse_button': self.collapse_button
        }

    def get_need_table(self):
        if self.layout['grid'] not in self.grids.keys():
            raise SphinxNeedLayoutException('Unknown layout-grid: {}. Supported are {}'.format(
                self.layout['grid'], ', '.join(self.grids.keys())
            ))

        func = self.grids[self.layout['grid']]
        if callable(func):
            func()
        else:
            func['func'](**func['configs'])

        return self.node_table

    def get_section(self, section):
        try:
            lines = self.layout['layout'][section]
        except KeyError:
            # Return nothing, if not specific configuration is given for layout section
            return []

        # Needed for PDF/Latex output, where empty line_blocks raise exceptions during build
        if len(lines) == 0:
            return []

        lines_container = nodes.line_block(classes=['needs_{}'.format(section)])

        for line in lines:
            # line_block_node = nodes.line_block()
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
        """
        Replaces a function definition like ``<<meta(a, ,b)>>`` with the related docutils nodes.

        It take an already existing docutils-node-tree and searches for Text-nodes containing ``<<..>>``.
        These nodes get then replaced by the return value (also a node) from the related function.

        :param section_nodes: docutils node (tree)
        :return: docutils nodes
        """
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

                line_elements = re.findall(r'(<<[^<>]+>>)|([^<>]+)', node_str)

                for line_element in line_elements:
                    text = line_element[1]
                    func_def = line_element[0]
                    # Check if normal string was detected
                    if len(text) > 0 and len(func_def) == 0:
                        node_line += nodes.Text(text, text)
                        result = nodes.Text(text, text)
                    # Check if function_definition was detected
                    elif len(text) == 0 and len(func_def) > 1:
                        from sphinxcontrib.needs.functions.functions import _analyze_func_string
                        func_def_clean = func_def.replace('<<', '').replace('>>', '')
                        func_name, func_args, func_kargs = _analyze_func_string(func_def_clean, None)

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
                                        e, func_def_clean, self.need['id']))

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
                                        e, func_def_clean, self.need['id']))

                        try:
                            func = self.functions[func_name]
                        except KeyError:
                            raise SphinxNeedLayoutException('Used function {} unknown. Please use {}'.format(
                                func_name, ', '.join(self.functions.keys())
                            ))
                        result = func(*func_args, **func_kargs)

                        if result is not None:
                            node_line += result
                    else:
                        raise SphinxNeedLayoutException(
                            'Error during layout line parsing. This looks strange: {}'.format(
                                line_element))

                return_nodes.append(node_line)
        return return_nodes

    def _replace_place_holder(self, data):
        replace_items = re.findall(r'{{(.*)}}', data)
        for item in replace_items:
            if item not in self.need.keys():
                raise SphinxNeedLayoutException(item)
            # To escape { we need to use 2 of them.
            # So {{ becomes {{{{
            replace_string = '{{{{{}}}}}'.format(item)
            data = data.replace(replace_string, self.need[item])
        return data

    def meta(self, name, prefix=None, show_empty=False):
        """
        Returns the specific meta data of a need inside docutils nodes.
        Usage::

            <<meta('status', prefix:'**status**', show_empty=True)>>

        :param name: name of the need item
        :param prefix: string as rst-code, will be added infront of the value output
        :param show_empty: If false and requested need-value is None or '', no output is returned. Default: false
        :return: docutils node
        """

        data_container = nodes.inline(classes=['needs_' + name])
        if prefix is not None:
            prefix_node = self._parse(prefix)
            label_node = nodes.inline(classes=['needs_label'])
            label_node += prefix_node
            data_container.append(label_node)
        try:
            data = self.need[name]
        except KeyError:
            data = ''

        if data is None and not show_empty:
            return []
        elif data is None and show_empty:
            data = ''

        if isinstance(data, str):
            if len(data) == 0 and not show_empty:
                return []
            data_node = nodes.inline(classes=['needs_data'])
            data_node.append(nodes.Text(data, data))
            data_container.append(data_node)
        elif isinstance(data, list):
            if len(data) == 0 and not show_empty:
                return []
            list_container = nodes.inline(classes=['needs_data_container'])
            for index, element in enumerate(data):
                if index > 0:
                    spacer = nodes.inline(classes=['needs_spacer'])
                    spacer += nodes.Text(', ', ', ')
                    list_container += spacer

                inline = nodes.inline(classes=['needs_data'])
                inline += nodes.Text(element, element)
                list_container += inline
            data_container += list_container
        else:
            data_container.append(nodes.Text(data, data))

        return data_container

    def meta_id(self):
        """
        Returns the current need id as clickable and linked reference.

        Usage::

            <<meta_id()>>

        :return: docutils node
        """
        from sphinx.util.nodes import make_refnode
        id_container = nodes.inline(classes=["needs-id"])

        nodes_id_text = nodes.Text(self.need['id'], self.need['id'])
        id_ref = make_refnode(self.app.builder,
                              # fromdocname=self.need['docname'],
                              fromdocname=self.fromdocname,
                              todocname=self.need['docname'],
                              targetid=self.need['id'],
                              child=nodes_id_text.deepcopy(),
                              title=self.need['id'])
        id_container += id_ref
        return id_container

    def meta_all(self, prefix='', postfix='', exclude=None, no_links=False, defaults=True, show_empty=False):
        """
        ``meta_all()`` excludes by default the output of: ``docname``, ``lineno``, ``target_node``, ``refid``,
        ``content``, ``collapse``, ``parts``, ``id_parent``,
        ``id_complete``, ``title``, ``full_title``, ``is_part``, ``is_need``,
        ``type_prefix``, ``type_color``, ``type_style``, ``type``, ``type_name``, ``id``,
        ``hide``, ``hide_status``, ``hide_tags``, ``sections``, ``section_name``.

        To exclude further need-data, use ``exclude``, like ``exclude=['status', 'tags']``

        To exclude nothing, set ``defaults`` to ``False``.

        Usage::

            <<meta_all(prefix='\*\*', postix='\*\*', no_links=True)>>

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
        default_excludes = INTERNALS.copy()

        if exclude is None or not isinstance(exclude, list):
            if defaults:
                exclude = default_excludes
            else:
                exclude = []
        elif defaults:
            exclude += default_excludes

        if no_links:
            link_names = [x['option'] for x in self.app.config.needs_extra_links]
            link_names += [x['option'] + '_back' for x in self.app.config.needs_extra_links]
            exclude += link_names
        data_container = nodes.inline()
        for data in self.need.keys():
            if data in exclude:
                continue

            data_line = nodes.line()
            label = prefix + '{}:'.format(data) + postfix + ' '
            result = self.meta(data, label, show_empty)
            if not show_empty and result is None or len(str(result)) == 0 or bool(result) is False:
                continue
            if isinstance(result, list):
                data_line += result
            else:
                data_line.append(result)

            data_container.append(data_line)

        return data_container

    def meta_links(self, name, incoming=False):
        """
        Documents the set links of a given link type.
        The documented links are all full clickable links to the target needs.

        :param name:  link type name
        :param incoming: If ``False``, outcoming links get documented. Use ``True`` for incoming
        :return: docutils nodes
        """
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

    def meta_links_all(self, prefix='', postfix='', exclude=None):
        """
        Documents all used link types for the current need automatically.

        :param prefix:  prefix string
        :param postfix:  postfix string
        :param exclude:  list of extra link type names, which are excluded from output
        :return: docutils nodes
        """
        if exclude is None:
            exclude = []
        data_container = []
        for link_type in self.app.config.needs_extra_links:
            type_key = link_type['option']
            if self.need[type_key] is not None and len(self.need[type_key]) > 0 and type_key not in exclude:
                outgoing_line = nodes.line()
                outgoing_label = prefix + '{}:'.format(link_type['outgoing']) + postfix + ' '
                outgoing_line += self._parse(outgoing_label)
                outgoing_line += self.meta_links(link_type['option'], incoming=False)
                data_container.append(outgoing_line)

            type_key = link_type['option'] + '_back'
            if self.need[type_key] is not None and len(self.need[type_key]) > 0 and type_key not in exclude:
                incoming_line = nodes.line()
                incoming_label = prefix + '{}:'.format(link_type['incoming']) + postfix + ' '
                incoming_line += self._parse(incoming_label)
                incoming_line += self.meta_links(link_type['option'], incoming=True)
                data_container.append(incoming_line)

        return data_container

    def image(self, url, height=None, width=None, align=None, no_link=False):
        """

        See https://docutils.sourceforge.io/docs/ref/rst/directives.html#images

        If url starts with ``icon:`` the following string is taken is icon-name and the related icon is shown.
        Example: ``icon:activity`` will show:

        .. image:: _static/activity.png

        For all icons, see https://feathericons.com/.

        Examples::

            '<<image("_images/useblocks_logo.png", height="50px", align="center")>>',
            '<<image("icon:bell", height="20px", align="center")>>'

        :param url:
        :param height:
        :param width:
        :param align:
        :return:
        """
        # from sphinx.addnodes import
        options = {}
        if height is not None:
            options['height'] = height
        if width is not None:
            options['width'] = width
        if align is not None:
            options['align'] = align

        if url is None or not isinstance(url, str):
            raise SphinxNeedLayoutException('not valid url given for image function in layout')

        if url.startswith('icon:'):
            if any(x in self.app.builder.name.upper() for x in ['PDF', 'LATEX']):
                # latexpdf can't handle svg files. We not to use the png format here.
                builder_extension = 'png'
            else:
                builder_extension = 'svg'

            # url = '_static/sphinx-needs/images/{}.{}'.format(url.split(':')[1], builder_extension)
            import os
            needs_location = os.path.dirname(__file__)
            url = os.path.join(needs_location,
                               'images',
                               'feather_{}'.format(builder_extension),
                               '{}.{}'.format(url.split(':')[1], builder_extension))

            # url = '../sphinxcontrib/needs/images/feather_{}/{}.{}'.format(builder_extension, url.split(':')[1], builder_extension)

            # if any(x in self.app.builder.name.upper() for x in ['PDF', 'LATEX']) is False:
            #     # This is not needed for Latex. as latex puts the complete content in a single text file on root level
            #     # The url needs to be relative to the current document where the need is defined
            #     # Otherwise the link is aiming "too high".
            #     # Normally sphinx is doing this kind of calculation, but it looks like not in the current state
            #     subfolder_amount = self.need['docname'].count('/')
            #     url = '../' * subfolder_amount + url
        elif url.startswith('field:'):
            field = url.split(':')[1]
            try:
                value = self.need[field]
            except KeyError:
                value = ''

            if value is None or len(value) == 0:
                return []

            url = value
            subfolder_amount = self.need['docname'].count('/')
            url = '../' * subfolder_amount + url

        image_node = nodes.image(url, classes=['needs_image'], **options)
        # image_node['candidates'] = {'*': url}
        image_node['candidates'] = '*'
        image_node['uri'] = url

        # Sphinx voodoo needed here.
        # It is not enough to just add a doctuils nodes.image, we also have to register the imag location for sphinx
        # Otherwise the images gets not copied to the later build-output location
        self.app.env.images.add_file(self.need['docname'], url)

        # Okay, this is really ugly.
        # Sphinx does automatically wrap all images into a reference node, which links to the image file.
        # See Bug: https://github.com/sphinx-doc/sphinx/issues/7032
        # This behavior can only be avoided by not using width/height attributes or by adding our
        # own reference node.
        # We do last one here and set class to "no_link", which is later used by some javascript to avoid
        # being clickable, so that the page does not "jump"
        if no_link:
            ref_node = nodes.reference('test', '', refuri='#', classes=['no_link'])
            ref_node.append(image_node)
            return ref_node

        return image_node

    def link(self, url, text=None, image_url=None, image_height=None, image_width=None):
        """
        Shows a link.
        Link can be a text, an image or both

        :param url:
        :param text:
        :param image_url:
        :param image_height:
        :param image_width:
        :return:
        """

        if text is None:  # May be needed if only image shall be shown
            text = ''

        link_node = nodes.reference(text, text, refuri=url)

        if image_url is not None:
            image_node = self.image(image_url, image_height, image_width)
            link_node.append(image_node)

        return link_node

    def collapse_button(self, target='meta', collapsed='Show', visible='Close', initial=False):
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
        if any(x in self.app.builder.name.upper() for x in ['PDF', 'LATEX']):
            # PDF/Latex output do not support collapse functions
            return

        coll_node_collapsed = nodes.inline(classes=['needs', 'collapsed'])
        coll_node_visible = nodes.inline(classes=['needs', 'visible'])

        if not collapsed.startswith('image:') and not collapsed.startswith('icon:'):
            coll_node_collapsed.append(nodes.Text(collapsed, collapsed))
        else:
            coll_node_collapsed.append(self.image(collapsed.replace('image:', ''), width='17px', no_link=True))

        if not visible.startswith('image:') and not visible.startswith('icon:'):
            coll_node_visible.append(nodes.Text(visible, visible))
        else:
            coll_node_visible.append(self.image(visible.replace('image:', ''), width='17px', no_link=True))

        coll_container = nodes.inline(classes=['needs', 'collapse'])
        # docutils does'nt allow has to add any html-attributes beside class and id to nodes.
        # So we misused "id" for this and use "__" (2x _) as separator for row-target names

        if (self.need['collapse'] is not None and self.need['collapse'] is False) or \
                (self.need['collapse'] is None and initial is False):
            status = 'show'
        elif (self.need['collapse'] is not None and self.need['collapse'] is True) or \
                (self.need['collapse'] is None and initial is True):
            status = 'hide'

        target_strings = target.split(',')
        final_targets = [x.strip() for x in target_strings]
        targets = ['target__' + status + '__' + '__'.join(final_targets)]
        coll_container.attributes['ids'] = targets
        coll_container.append(coll_node_collapsed)
        coll_container.append(coll_node_visible)

        return coll_container

    def _grid_simple(self, colwidths, side_left, side_right, footer):
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
            if side_left == 'full':
                side_left_morerows = 2
            else:
                side_left_morerows = 1
                common_more_cols += 1
            if footer:
                side_left_morerows += 1

        if side_right:
            if side_right == 'full':
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
        head_row = nodes.row(classes=['need', 'head'])

        if side_left:
            side_entry = nodes.entry(classes=['need', 'side'], morerows=side_left_morerows)
            side_entry += self.get_section('side')
            head_row += side_entry

        head_entry = nodes.entry(classes=['need', 'head'])
        head_entry += self.get_section('head')
        head_row += head_entry

        if side_right:
            side_entry = nodes.entry(classes=['need', 'side'], morerows=side_right_morerows)
            side_entry += self.get_section('side')
            head_row += side_entry

        # META row
        meta_row = nodes.row(classes=['need', 'meta'])
        meta_entry = nodes.entry(classes=['need', 'meta'])
        meta_entry += self.get_section('meta')
        meta_row += meta_entry

        # CONTENT row
        content_row = nodes.row(classes=['need', 'content'])
        content_entry = nodes.entry(classes=['need', 'content'], morecols=common_more_cols)
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        # FOOTER row
        if footer:
            footer_row = nodes.row(classes=['need', 'footer'])
            footer_entry = nodes.entry(classes=['need', 'footer'], morecols=common_more_cols)
            footer_entry += self.get_section('footer')
            footer_row += footer_entry

        # Construct table
        self.node_tbody += head_row
        self.node_tbody += meta_row
        self.node_tbody += content_row
        if footer:
            self.node_tbody += footer_row
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
        head_left_entry = nodes.entry(classes=['head_left'], morecols=1)
        head_left_entry += self.get_section('head_left')
        head_row += head_left_entry
        # HEAD mid
        head_entry = nodes.entry(classes=['head_center'], morecols=1)
        head_entry += self.get_section('head')
        head_row += head_entry
        # HEAD right
        head_right_entry = nodes.entry(classes=['head_right'], morecols=1)
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
        footer_left_entry = nodes.entry(classes=['footer_left'], morecols=1)
        footer_left_entry += self.get_section('footer_left')
        footer_row += footer_left_entry
        # FOOTER mid
        footer_entry = nodes.entry(classes=['footer'], morecols=1)
        footer_entry += self.get_section('footer')
        footer_row += footer_entry
        # FOOTER right
        footer_right_entry = nodes.entry(classes=['footer_right'], morecols=1)
        footer_right_entry += self.get_section('footer_right')
        footer_row += footer_right_entry

        # Construct table
        node_tgroup += self.node_tbody

    def _grid_content(self, colwidths, side_left, side_right, footer):
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
        content_row = nodes.row(classes=['content'])

        if side_left:
            side_entry = nodes.entry(classes=['side', 'left'], morerows=side_morerows)
            side_entry += self.get_section('side')
            content_row += side_entry

        content_entry = nodes.entry(classes=['content'])
        content_entry.insert(0, self.node.children)
        content_row += content_entry

        if side_right:
            side_entry = nodes.entry(classes=['side', 'right'], morerows=side_morerows)
            side_entry += self.get_section('side')
            content_row += side_entry

        # FOOTER row
        if footer:
            footer_row = nodes.row(classes=['footer'])
            footer_entry = nodes.entry(classes=['footer'])
            footer_entry += self.get_section('footer')
            footer_row += footer_entry

        # Construct table
        self.node_tbody += content_row
        if footer:
            self.node_tbody += footer_row
        node_tgroup += self.node_tbody


class SphinxNeedLayoutException(BaseException):
    """Raised if problems with layout handling occurs"""
