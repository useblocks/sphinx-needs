"""
API to get or add specific sphinx needs configuration parameters.

All functions here are available under ``sphinxcontrib.api``. So do not import this module directly.
"""
from docutils.parsers.rst import directives

from sphinxcontrib.needs.api.exceptions import NeedsNotLoadedException, NeedsApiConfigException, NeedsApiConfigWarning
import sphinxcontrib.needs.directives.need


def get_need_types(app):
    """
    Returns a list of directive-names from all configured need_types.

    **Usage**::

        from sphinxcontrib.needs.api import get_need_types

        all_types = get_need_types(app)

    :param app: Sphinx application object
    :return: list of strings
    """
    needs_types = getattr(app.config, 'needs_types', [])
    return [x['directive'] for x in needs_types]


def add_need_type(app, directive, title, prefix, color='#ffffff', style='node'):
    """
    Adds a new need_type to the configuration.

    The given directive must no exist, otherwise NeedsApiConfigException gets raised.

    Same impact as using :ref:`need_types` manually.

    **Usage**::

        from sphinxcontrib.needs.api import add_need_type

        add_need_type(app, 'awesome', 'Awesome', 'AW_', '#000000', 'cloud')

    :param app: Sphinx application object
    :param directive: Name of the directive, e.g. 'story'
    :param title: Long, human-readable title, e.g. 'User-Story'
    :param prefix: Prefix, if IDs get automatically generated. E.g.: ``'US_'``
    :param color: Hex-color code used in needflow representation. Default: ``'#ffffff'``
    :param style: Plantuml-style for needflow representation. Default: 'node'
    :return: None
    """
    if not hasattr(app.config, 'needs_types'):
        raise NeedsNotLoadedException('needs_types missing in configuration.')

    needs_types = getattr(app.config, 'needs_types', [])
    type_names = [x['directive'] for x in needs_types]

    if directive in type_names:
        raise NeedsApiConfigException('{} already exists as need type'.format(directive))

    needs_types.append({
        'directive': directive,
        'title': title,
        'prefix': prefix,
        'color': color,
        'style': style
    })
    app.add_directive(directive, sphinxcontrib.needs.directives.need.NeedDirective)


def add_extra_option(app, name):
    """
    Adds an extra option to the configuration. This option can then later be used inside needs or ``add_need``.

    Same impact as using :ref:`needs_extra_options` manually.

    **Usage**::

        from sphinxcontrib.needs.api import add_extra_option

        add_extra_option(app, 'my_extra_option')

    :param app: Sphinx application object
    :param name: Name as string of the extra option
    :return: None
    """
    if not hasattr(app.config, 'needs_extra_options'):
        raise NeedsNotLoadedException('needs_extra_options missing in configuration.')

    extra_options = getattr(app.config, 'needs_extra_options', {})

    if name in extra_options.keys():
        raise NeedsApiConfigWarning('Option {} already registered.'.format(name))

    extra_options[name] = directives.unchanged


def add_dynamic_function(app, function):
    """
    Registers a new dynamic function for sphinx-needs.

    The name to call the function is automatically taken from the provided function
    and must be unique.

    **Usage**::

        from sphinxcontrib.needs.api import add_dynamic_function

        def my_function(app, need, needs, *args, **kwargs):
            # Do magic here
            return "some data"

        add_dynamic_function(app, my_function)

    Read :ref:`dynamic_functions` for details about how to use dynamic functions.

    :param app: Sphinx application object
    :param function: Function to register
    :return: None
    """
    if not hasattr(app, 'needs_functions'):
        raise NeedsNotLoadedException('needs_functions missing in configuration.')
    needs_functions = getattr(app, 'needs_functions', [])
    needs_functions.append(function)
