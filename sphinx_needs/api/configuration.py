"""
API to get or add specific sphinx needs configuration parameters.

All functions here are available under ``sphinxcontrib.api``. So do not import this module directly.
"""

from __future__ import annotations

from typing import Callable

from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util.logging import SphinxLoggerAdapter

from sphinx_needs.api.exceptions import NeedsApiConfigException, NeedsApiConfigWarning
from sphinx_needs.config import NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType
from sphinx_needs.functions import register_func
from sphinx_needs.functions.functions import DynamicFunction


def get_need_types(app: Sphinx) -> list[str]:
    """
    Returns a list of directive-names from all configured need_types.

    **Usage**::

        from sphinx_needs.api import get_need_types

        all_types = get_need_types(app)

    :param app: Sphinx application object
    :return: list of strings
    """
    needs_types = NeedsSphinxConfig(app.config).types
    return [x["directive"] for x in needs_types]


def add_need_type(
    app: Sphinx,
    directive: str,
    title: str,
    prefix: str,
    color: str = "#ffffff",
    style: str = "node",
) -> None:
    """
    Adds a new need_type to the configuration.

    The given directive must no exist, otherwise NeedsApiConfigException gets raised.

    Same impact as using :ref:`needs_types` manually.

    **Usage**::

        from sphinx_needs.api import add_need_type

        add_need_type(app, 'awesome', 'Awesome', 'AW_', '#000000', 'cloud')

    :param app: Sphinx application object
    :param directive: Name of the directive, e.g. 'story'
    :param title: Long, human-readable title, e.g. 'User-Story'
    :param prefix: Prefix, if IDs get automatically generated. E.g.: ``'US_'``
    :param color: Hex-color code used in needflow representation. Default: ``'#ffffff'``
    :param style: Plantuml-style for needflow representation. Default: 'node'
    :return: None
    """
    import sphinx_needs.directives.need

    needs_types = NeedsSphinxConfig(app.config).types
    type_names = [x["directive"] for x in needs_types]

    if directive in type_names:
        raise NeedsApiConfigException(f"{directive} already exists as need type")

    needs_types.append(
        {
            "directive": directive,
            "title": title,
            "prefix": prefix,
            "color": color,
            "style": style,
        }
    )
    app.add_directive(directive, sphinx_needs.directives.need.NeedDirective)


def add_extra_option(app: Sphinx, name: str) -> None:
    """
    Adds an extra option to the configuration. This option can then later be used inside needs or ``add_need``.

    Same impact as using :ref:`needs_extra_options` manually.

    **Usage**::

        from sphinx_needs.api import add_extra_option

        add_extra_option(app, 'my_extra_option')

    :param app: Sphinx application object
    :param name: Name as string of the extra option
    :return: None
    """
    if name in NEEDS_CONFIG.extra_options:
        raise NeedsApiConfigWarning(f"Option {name} already registered.")
    NEEDS_CONFIG.extra_options[name] = directives.unchanged


def add_dynamic_function(
    app: Sphinx, function: DynamicFunction, name: str | None = None
) -> None:
    """
    Registers a new dynamic function for sphinx-needs.

    If ``name`` is not given, the name to call the function is automatically taken from the provided function.
    The used name must be unique.

    **Usage**::

        from sphinx_needs.api import add_dynamic_function

        def my_function(app, need, needs, *args, **kwargs):
            # Do magic here
            return "some data"

        add_dynamic_function(app, my_function)

    Read :ref:`dynamic_functions` for details about how to use dynamic functions.

    :param app: Sphinx application object
    :param function: Function to register
    :param name: Name of the dynamic function as string
    :return: None
    """
    register_func(function, name)


# 'Need' is untyped, so we temporarily use 'Any' here
WarningCheck = Callable[[NeedsInfoType, SphinxLoggerAdapter], bool]


def add_warning(
    app: Sphinx,
    name: str,
    function: WarningCheck | None = None,
    filter_string: str | None = None,
) -> None:
    """
    Registers a warning.

    A warning can be based on the result of a given filter_string or an own defined function.

    :param app: Sphinx app object
    :param name: Name as string for the warning
    :param function: function to execute to check the warning
    :param filter_string: filter_string to use for the warning
    :return: None
    """
    if function is None and filter_string is None:
        raise NeedsApiConfigException(
            "Function or filter_string must be given for add_warning_func"
        )

    if function is not None and filter_string is not None:
        raise NeedsApiConfigException(
            "For add_warning_func only function or filter_string is allowed to be set, "
            "not both."
        )

    warning_check = function or filter_string

    if warning_check is None:
        raise NeedsApiConfigException("either function or filter_string must be given")

    if name in NEEDS_CONFIG.warnings:
        raise NeedsApiConfigException(f"Warning {name} already registered.")

    NEEDS_CONFIG.warnings[name] = warning_check
