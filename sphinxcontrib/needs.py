# -*- coding: utf-8 -*-

from docutils import nodes
import os
from sphinx.roles import XRefRole

from sphinxcontrib.need import Need, NeedDirective, process_need_nodes, purge_needs
from sphinxcontrib.needfilter import Needfilter, NeedfilterDirective, process_needfilters
from sphinxcontrib.need_ref import Need_ref, process_need_ref
from sphinxcontrib.need_incoming import Need_incoming, process_need_incoming
from sphinxcontrib.need_outgoing import  Need_outgoing, process_need_outgoing

from sphinxcontrib.utils import rstjinja

DEFAULT_TEMPLATE = """
.. _{{id}}:

{% if hide == false -%}
{{type_name}}: **{{title}}** ({{id}})

    {{content|indent(4) }}

    {% if status and not hide_status -%}
    **status**: {{status}}
    {% endif %}

    {% if tags and not hide_tags -%}
    **tags**: {{"; ".join(tags)}}
    {% endif %}

    **links incoming**: :need_incoming:`{{id}}`

    **links outgoing**: :need_outgoing:`{{id}}`

{% endif -%}
"""

DEFAULT_DIAGRAM_TEMPLATE = \
    "<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>"


def setup(app):
    app.add_config_value('needs_types',
                         [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
                          dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
                          dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
                          dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
                          # Kept for backwards compatibility
                          dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node")
                          ],
                         'html')
    app.add_config_value('needs_template',
                         DEFAULT_TEMPLATE,
                         'html')

    app.add_config_value('needs_include_needs', True, 'html')
    app.add_config_value('needs_need_name', "Need", 'html')
    app.add_config_value('needs_spec_name', "Specification", 'html')
    app.add_config_value('needs_id_prefix_needs', "", 'html')
    app.add_config_value('needs_id_prefix_specs', "", 'html')
    app.add_config_value('needs_id_length', 5, 'html')
    app.add_config_value('needs_specs_show_needlist', False, 'html')
    app.add_config_value('needs_id_required', False, 'html')
    app.add_config_value('needs_show_link_type', False, 'html')
    app.add_config_value('needs_show_link_title', False, 'html')

    app.add_config_value('needs_diagram_template',
                         DEFAULT_DIAGRAM_TEMPLATE,
                         'html')

    # Define nodes
    app.add_node(Need)
    app.add_node(Needfilter)

    ########################################################################
    # DIRECTIVES
    ########################################################################

    # Define directives
    # As values from conf.py are not available during setup phase, we have to import and read them by our own.
    # Otherwise this "app.config.needs_types" would always return the default values only.
    try:
        import imp
        config = imp.load_source("needs.app_conf", os.path.join(app.confdir, "conf.py"))
        types = getattr(config, "needs_types", app.config.needs_types)
    except Exception as e:
        types = app.config.needs_types

    for type in types:
        # Register requested types of needs
        app.add_directive(type["directive"], NeedDirective)
        app.add_directive("{0}_list".format(type["directive"]), NeedDirective)

    app.add_directive('needfilter', NeedfilterDirective)

    # Kept for backwards compatibility
    app.add_directive('needlist', NeedfilterDirective)

    ########################################################################
    # ROLES
    ########################################################################
    # Provides :need:`ABC_123` for inline links.
    app.add_role('need', XRefRole(nodeclass=Need_ref,
                                  innernodeclass=nodes.emphasis,
                                  warn_dangling=True))

    app.add_role('need_incoming', XRefRole(nodeclass=Need_incoming,
                                           innernodeclass=nodes.emphasis,
                                           warn_dangling=True))

    app.add_role('need_outgoing', XRefRole(nodeclass=Need_outgoing,
                                           innernodeclass=nodes.emphasis,
                                           warn_dangling=True))

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect('env-purge-doc', purge_needs)
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('doctree-resolved', process_needfilters)
    app.connect('doctree-resolved', process_need_ref)
    app.connect('doctree-resolved', process_need_incoming)
    app.connect('doctree-resolved', process_need_outgoing)

    # Allows jinja statements in rst files
    app.connect("source-read", rstjinja)

    return {'version': '0.1'}  # identifies the version of our extension
