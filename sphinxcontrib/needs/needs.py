# -*- coding: utf-8 -*-

import os
import random
import string

import sphinx
from sphinx.errors import SphinxError
from docutils import nodes
from docutils.parsers.rst import directives
from pkg_resources import parse_version
from sphinx.roles import XRefRole
from sphinxcontrib.needs.directives.need import Need, NeedDirective, \
    process_need_nodes, purge_needs, add_sections, html_visit, html_depart, latex_visit, latex_depart
from sphinxcontrib.needs.directives.needimport import Needimport, NeedimportDirective
from sphinxcontrib.needs.directives.needtable import Needtable, NeedtableDirective, process_needtables
from sphinxcontrib.needs.directives.needlist import Needlist, NeedlistDirective, process_needlist
from sphinxcontrib.needs.directives.needflow import Needflow, NeedflowDirective, process_needflow

from sphinxcontrib.needs.builder import NeedsBuilder
from sphinxcontrib.needs.directives.needfilter import Needfilter, NeedfilterDirective, process_needfilters
from sphinxcontrib.needs.environment import install_styles_static_files, install_datatables_static_files, \
    install_collapse_static_files
from sphinxcontrib.needs.roles.need_incoming import Need_incoming, process_need_incoming
from sphinxcontrib.needs.roles.need_outgoing import Need_outgoing, process_need_outgoing
from sphinxcontrib.needs.roles.need_ref import Need_ref, process_need_ref
from sphinxcontrib.needs.roles.need_part import NeedPart, process_need_part
from sphinxcontrib.needs.roles.need_count import NeedCount, process_need_count
from sphinxcontrib.needs.utils import process_dynamic_values
from sphinxcontrib.needs.functions import register_func, needs_common_functions

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

    logging.basicConfig()  # Only need to do this once

VERSION = '0.3.12'

DEFAULT_TEMPLATE_COLLAPSE = """
.. _{{id}}:

{% if hide == false -%}
.. role:: needs_tag
.. role:: needs_status
.. role:: needs_type
.. role:: needs_id
.. role:: needs_title

.. rst-class:: need
.. rst-class:: need_{{type_name}}

.. container:: need

    .. container:: toggle

        .. container:: header

            :needs_type:`{{type_name}}`: {% if title %}:needs_title:`{{title}}`{% endif %} :needs_id:`{{id}}`

{% if status and  status|upper != "NONE" and not hide_status %}        | status: :needs_status:`{{status}}`{% endif %}
{% if tags and not hide_tags %}        | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`{% endif %}
        | links incoming: :need_incoming:`{{id}}`
        | links outgoing: :need_outgoing:`{{id}}`

    {{content|indent(4) }}

{% endif -%}
"""

DEFAULT_TEMPLATE = """
.. _{{id}}:

{% if hide == false -%}
.. role:: needs_tag
.. role:: needs_status
.. role:: needs_type
.. role:: needs_id
.. role:: needs_title

.. rst-class:: need
.. rst-class:: need_{{type_name}}

.. container:: need

    :needs_type:`{{type_name}}`: :needs_title:`{{title}}` :needs_id:`{{id}}`


{%- if status and  status|upper != "NONE" and not hide_status %}
        | status: :needs_status:`{{status}}`
{%- endif %}
{%- if tags and not hide_tags %}
        | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`
{%- endif %}
        | links incoming: :need_incoming:`{{id}}`
        | links outgoing: :need_outgoing:`{{id}}`

    {{content|indent(4) }}

{% endif -%}
"""

DEFAULT_DIAGRAM_TEMPLATE = \
    """
{%- if is_need -%}
<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>
{%- else -%}
<size:12>{{type_name}} (part)</size>\\n**{{content|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id_parent}}.**{{id}}**</size>
{%- endif -%}
"""


def setup(app):
    log = logging.getLogger(__name__)
    app.add_builder(NeedsBuilder)
    app.add_config_value('needs_types',
                         [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
                          dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
                          dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
                          dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
                          # Kept for backwards compatibility
                          dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node")],
                         'html')
    app.add_config_value('needs_template', DEFAULT_TEMPLATE, 'html')
    app.add_config_value('needs_template_collapse', DEFAULT_TEMPLATE_COLLAPSE, 'html')

    app.add_config_value('needs_include_needs', True, 'html')
    app.add_config_value('needs_need_name', "Need", 'html')
    app.add_config_value('needs_spec_name', "Specification", 'html')
    app.add_config_value('needs_id_prefix_needs', "", 'html')
    app.add_config_value('needs_id_prefix_specs', "", 'html')
    app.add_config_value('needs_id_length', 5, 'html')
    app.add_config_value('needs_specs_show_needlist', False, 'html')
    app.add_config_value('needs_id_required', False, 'html')
    app.add_config_value('needs_id_regex', "^[A-Z0-9_]{{{id_length},}}".format(
        id_length=app.config.needs_id_length), 'html')
    app.add_config_value('needs_show_link_type', False, 'html')
    app.add_config_value('needs_show_link_title', False, 'html')
    app.add_config_value('needs_file', "needs.json", 'html')
    app.add_config_value('needs_table_columns', "ID;TITLE;STATUS;TYPE;OUTGOING;TAGS", 'html')
    app.add_config_value('needs_table_style', "DATATABLES", 'html')

    app.add_config_value('needs_collapse_details', True, 'html')

    app.add_config_value('needs_role_need_template', u"{title} ({id})", 'html')

    app.add_config_value('needs_extra_options', {}, 'html')
    app.add_config_value('needs_title_optional', False, 'html')
    app.add_config_value('needs_max_title_length', -1, 'html')
    app.add_config_value('needs_title_from_content', False, 'html')

    app.add_config_value('needs_diagram_template',
                         DEFAULT_DIAGRAM_TEMPLATE,
                         'html')

    # app.add_config_value('needs_functions', None, 'html')
    app.add_config_value('needs_global_options', {}, 'html')
    app.add_config_value('needs_hide_options', [], 'html')

    # If given, only the defined status are allowed.
    # Values needed for each status:
    # * name
    # * description
    # Example: [{"name": "open", "description": "open status"}, {...}, {...}]
    app.add_config_value('needs_statuses', False, 'html')

    # If given, only the defined tags are allowed.
    # Values needed for each tag:
    # * name
    # * description
    # Example: [{"name": "new", "description": "new needs"}, {...}, {...}]
    app.add_config_value('needs_tags', False, 'html')

    # Path of css file, which shall be used for need style
    app.add_config_value('needs_css', "modern.css", 'html')

    # Prefix for need_part output in tables
    app.add_config_value('needs_part_prefix', u'\u2192\u00a0', 'html')

    # List of additional links, which can be used by setting related option
    # Values needed for each new link:
    # * name (will also be the option name)
    # * incoming
    # * copy_link (copy to common links data. Default: True)
    # * color (used for needflow. Default: #000000)
    # Example: [{"name": "blocks, "incoming": "is blocked by", "copy_link": True, "color": "#ffcc00"}]
    app.add_config_value('needs_extra_links', [], 'html')

    app.add_config_value('needs_flow_show_links', False, 'html')
    app.add_config_value('needs_flow_link_types', ["links"], 'html')

    # Define nodes
    app.add_node(Need, html=(html_visit, html_depart), latex=(latex_visit, latex_depart))
    app.add_node(Needfilter, )
    app.add_node(Needimport)
    app.add_node(Needlist)
    app.add_node(Needtable)
    app.add_node(Needflow)
    app.add_node(NeedPart, html=(visitor_dummy, visitor_dummy), latex=(visitor_dummy, visitor_dummy))

    ########################################################################
    # DIRECTIVES
    ########################################################################

    # Define directives
    # As values from conf.py are not available during setup phase, we have to import and read them by our own.
    # Otherwise this "app.config.needs_types" would always return the default values only.
    try:
        import imp
        # If sphinx gets started multiple times inside a python process, the following module gets also
        # loaded several times. This has a drawback, as the config from the current build gets somehow merged
        # with the config from the previous builds.
        # So if the current config does not define a parameter, which was set in build before, the "old" value is
        # taken. This is dangerous, because a developer may simply want to use the defaults (like the predefined types)
        # and therefore does not set this specific value. But instead he would get the value from a previous build.
        # So we generate a random module name for our configuration, so that this is loaded for the first time.
        # Drawback: The old modules will still exist (but are not used).
        #
        # From https://docs.python.org/2.7/library/functions.html#reload
        # "When a module is reloaded, its dictionary (containing the module’s global variables) is retained.
        # Redefinitions of names will override the old definitions, so this is generally not a problem.
        # If the new version of a module does not define a name that was defined by the old version,
        # the old definition remains"

        # Be sure, our current working directory is the folder, which stores the conf.py.
        # Inside the conf.py there may be relatives paths, which would be incorrect, if our cwd is wrong.
        old_cwd = os.getcwd()
        os.chdir(app.confdir)
        module_name = "needs_app_conf_" + ''.join(random.choice(string.ascii_uppercase) for _ in range(5))
        config = imp.load_source(module_name, os.path.join(app.confdir, "conf.py"))
        os.chdir(old_cwd)  # Lets switch back the cwd, otherwise other stuff may not run...
        types = getattr(config, "needs_types", app.config.needs_types)
        extra_options = getattr(config, "needs_extra_options", app.config.needs_extra_options)

        # Get extra links and create a dictionary of needed options.
        extra_links_raw = getattr(config, "needs_extra_links", app.config.needs_extra_links)
        extra_links = {}
        for extra_link in extra_links_raw:
            extra_links[extra_link['option']] = directives.unchanged

        title_optional = getattr(config, "needs_title_optional", app.config.needs_title_optional)
        title_from_content = getattr(config, "needs_title_from_content", app.config.needs_title_from_content)
        app.needs_functions = getattr(config, "needs_functions", [])
    except IOError:
        types = app.config.needs_types
    except Exception as e:
        log.error("Error during sphinxcontrib-needs setup: {0}, {1}".format(
            os.path.join(app.confdir, "conf.py"), e))
        types = app.config.needs_types

    # Update NeedDirective to use customized options
    NeedDirective.option_spec.update(extra_options)

    # Update NeedDirective to use customized links
    NeedDirective.option_spec.update(extra_links)

    if title_optional or title_from_content:
        NeedDirective.required_arguments = 0
        NeedDirective.optional_arguments = 1

    for type in types:
        # Register requested types of needs
        app.add_directive(type["directive"], NeedDirective)
        app.add_directive("{0}_list".format(type["directive"]), NeedDirective)

    app.add_directive('needfilter', NeedfilterDirective)
    app.add_directive('needlist', NeedlistDirective)
    app.add_directive('needtable', NeedtableDirective)
    app.add_directive('needflow', NeedflowDirective)

    app.add_directive('needimport', NeedimportDirective)

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

    app.add_role('need_part', XRefRole(nodeclass=NeedPart,
                                       innernodeclass=nodes.inline,
                                       warn_dangling=True))
    # Shortcut for need_inline
    app.add_role('np', XRefRole(nodeclass=NeedPart,
                                innernodeclass=nodes.inline,
                                warn_dangling=True))

    app.add_role('need_count', XRefRole(nodeclass=NeedCount,
                                        innernodeclass=nodes.inline,
                                        warn_dangling=True))

    ########################################################################
    # EVENTS
    ########################################################################
    # Make connections to events
    app.connect('env-purge-doc', purge_needs)
    app.connect('env-before-read-docs', prepare_env)
    app.connect('doctree-resolved', add_sections)
    app.connect('doctree-resolved', process_need_nodes)
    app.connect('doctree-resolved', process_dynamic_values)
    app.connect('doctree-resolved', process_needfilters)
    app.connect('doctree-resolved', process_needlist)
    app.connect('doctree-resolved', process_needtables)
    app.connect('doctree-resolved', process_needflow)
    app.connect('doctree-resolved', process_need_part)
    app.connect('doctree-resolved', process_need_ref)
    app.connect('doctree-resolved', process_need_incoming)
    app.connect('doctree-resolved', process_need_outgoing)
    app.connect('doctree-resolved', process_need_count)
    app.connect('env-updated', install_datatables_static_files)

    # Call this after all JS files, which perform DOM manipulation, have been called.
    # Otherwise newly added dom objects can not be collapsed
    app.connect('env-updated', install_collapse_static_files)

    # This should be called last, so that need-styles can override styles from used libraries
    app.connect('env-updated', install_styles_static_files)

    return {'version': VERSION}  # identifies the version of our extension


def visitor_dummy(*args, **kwargs):
    """
    Dummy class for visitor methods, which does nothing.
    """
    pass


def prepare_env(app, env, docname):
    """
    Prepares the sphinx environment to store sphinx-needs internal data.
    """
    if not hasattr(env, 'needs_all_needs'):
        # Used to store all needed information about all needs in document
        env.needs_all_needs = {}

    if not hasattr(env, 'needs_all_filters'):
        # Used to store all needed information about all filters in document
        env.needs_all_filters = {}

    if not hasattr(env, 'needs_functions'):
        # Used to store all registered functions for supporting dynamic need values.
        env.needs_functions = {}

        # needs_functions = getattr(app.config, 'needs_functions', [])
        needs_functions = app.needs_functions
        if needs_functions is None:
            needs_functions = []
        if not isinstance(needs_functions, list):
            raise SphinxError('Config parameter needs_functions must be a list!')

        # Register built-in functions
        for need_common_func in needs_common_functions:
            register_func(env, need_common_func)

        # Register functions configured by user
        for needs_func in needs_functions:
            register_func(env, needs_func)

    app.config.needs_hide_options += ['hidden']
    app.config.needs_extra_options['hidden'] = directives.unchanged

    # The default link name. Must exist in all configurations. Therefore we set it here for the user.
    common_links = []
    link_types = app.config.needs_extra_links
    basic_link_type_found = False
    for link_type in link_types:
        if link_type['option'] == 'links':
            basic_link_type_found = True
            break

    if not basic_link_type_found:
        common_links.append({
            'option': 'links',
            'outgoing': 'links outgoing',
            'incoming': 'link incoming',
            'copy': False,
            'color': '#000000'
        })

    app.config.needs_extra_links = common_links + app.config.needs_extra_links

    if not hasattr(env, 'needs_workflow'):
        # Used to store workflow status information for already executed tasks.
        # Some tasks like backlink_creation need be be performed only once.
        # But most sphinx-events get called several times (for each single document file), which would also
        # execute our code several times...
        env.needs_workflow = {
            'backlink_creation_links': False,
            'dynamic_values_resolved': False
        }
        for link_type in app.config.needs_extra_links:
            env.needs_workflow['backlink_creation_{}'.format(link_type['option'])] = False
