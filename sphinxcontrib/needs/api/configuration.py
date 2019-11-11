"""
API to get or add specific sphinx needs configuration parameters.

All functions here are available under ``sphinxcontrib.api``. So dot not import this module directly.
"""

from sphinxcontrib.needs.api.exceptions import NeedsNotLoadedException, NeedsApiConfigException
import sphinxcontrib.needs.directives.need


def get_need_types(app):
    """
    Returns a list of directive-names from all configured need_types.

    **Usage**::

        from sphinxcontrib.needs.api import get_need_types
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
