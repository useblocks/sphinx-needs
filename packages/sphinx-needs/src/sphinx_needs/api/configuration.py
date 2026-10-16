"""
API to get or add specific sphinx needs configuration parameters.

All functions here are available under ``sphinx_needs.api``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

from sphinx.application import Sphinx
from sphinx.util.logging import SphinxLoggerAdapter

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.defaults import LAYOUTS
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs.functions.functions import DynamicFunction
from sphinx_needs.need_item import NeedItem
from sphinx_needs.schema.config import FieldSchemaTypes

# TODO(mh) document exactly when API calls are allowed in the Sphinx event system


def get_need_types(app: Sphinx) -> list[str]:
    """
    Returns a list of directive-names from all need types: the configured
    :ref:`needs_types`, then those added with :func:`add_need_type` by extensions, then
    the GitHub services' ``issue``, ``pr`` and ``commit`` (each only where no earlier
    type has its directive).

    Call it from a ``config-inited`` handler at a priority above 12, or later: before
    that, a mapping-shaped ``needs_types`` is not yet resolved to its list.

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
    Adds a new need type, and registers its directive.

    The given directive must not be configured in :ref:`needs_types` or added with
    this function already, otherwise NeedsApiConfigException gets raised. The GitHub
    services' ``issue``, ``pr`` and ``commit`` do not count: a type added under one of
    those directives replaces the service's.

    The type is added to sphinx-needs' own registry, not to the :ref:`needs_types`
    configuration value, which holds only what the project configures (so Sphinx
    compares the same value on both sides of an incremental build). Read every type,
    the added ones included, with :func:`get_need_types`, or with
    ``NeedsSphinxConfig(app.config).types`` for the whole entries: the configured
    types, then the added ones, then the GitHub services' ones.

    Call it from a ``config-inited`` handler at a priority above 12, or later: before
    that, a mapping-shaped ``needs_types`` is not yet resolved to the list the
    duplicate check reads. Unlike a configured entry, the type is not validated.

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
    from sphinx_needs.needs import _register_need_directive

    configured = NeedsSphinxConfig(app.config)._types
    if directive in _NEEDS_CONFIG.types or any(
        need_type["directive"] == directive for need_type in configured
    ):
        raise NeedsApiConfigException(f"{directive} already exists as need type")

    _NEEDS_CONFIG.add_need_type(
        {
            "directive": directive,
            "title": title,
            "prefix": prefix,
            "color": color,
            "style": style,
        }
    )
    _register_need_directive(app, directive)


def add_need_layout(app: Sphinx, name: str, layout: dict[str, Any]) -> None:
    """
    Adds a new need layout, which a need then names with ``:layout:``.

    The given name must not be a layout of :ref:`needs_layouts` -- sphinx-needs' own
    layouts included -- or one added with this function already, otherwise
    NeedsApiConfigException gets raised. The GitHub services' ``github`` layout does not
    count: a layout added under that name replaces the service's.

    The layout is added to sphinx-needs' own registry, not to the :ref:`needs_layouts`
    configuration value, which holds only what the project configures (and
    sphinx-needs' own layouts and the compiled :ref:`needs_card_layouts`). Every reader
    sees it, through ``NeedsSphinxConfig(app.config).layouts``: the configured
    layouts, then the added ones, then the GitHub services' one. The layout is used as
    given, with the structure a :ref:`needs_layouts` entry has (see :ref:`layouts`).

    **Usage**::

        from sphinx_needs.api import add_need_layout

        add_need_layout(
            app, "my_card", {"grid": "simple", "layout": {"head": ["<<meta('title')>>"]}}
        )

    :param app: Sphinx application object
    :param name: Name of the layout, e.g. 'my_card'
    :param layout: The layout: its ``grid`` and ``layout`` (and optional ``style``)
    :raises NeedsApiConfigException: If a layout of the name is configured or added.
    """
    if name in LAYOUTS or name in NeedsSphinxConfig(app.config)._layouts:
        raise NeedsApiConfigException(f"{name} already exists as need layout")
    _NEEDS_CONFIG.add_layout(name, layout)


def add_extra_option(
    app: Sphinx,
    name: str,
    *,
    description: str = "Added by add_extra_option API",
    schema: FieldSchemaTypes | None = None,
    nullable: bool | None = None,
    parse_variants: bool | None = None,
    parse_dynamic_functions: bool | None = None,
) -> None:
    """
    Adds an extra option to the configuration. This option can then later be used inside needs or ``add_need``.

    Same impact as using :ref:`needs_extra_options` manually.

    .. deprecated::
        Use :func:`add_field` instead.

    **Usage**::

        from sphinx_needs.api import add_extra_option

        add_extra_option(app, 'my_extra_option')

    :param app: Sphinx application object
    :param name: Name of the extra option
    :param description: Description of the extra option
    :param schema: Schema definition for the extra option
    :param nullable: Whether the field allows unset values.
    :param parse_variants: Whether variants are parsed in this field.
    :param parse_dynamic_functions: Whether dynamic functions are parsed in this field.
    """
    warnings.warn(
        "add_extra_option is deprecated, use add_field instead",
        DeprecationWarning,
        stacklevel=2,
    )
    _NEEDS_CONFIG.add_field(
        name,
        description,
        "add_extra_option",
        schema=schema,
        nullable=nullable,
        parse_variants=parse_variants,
        parse_dynamic_functions=parse_dynamic_functions,
    )


def add_field(
    name: str,
    /,
    description: str,
    *,
    schema: FieldSchemaTypes | None = None,
    nullable: bool | None = None,
    default: Any | None = None,
    predicates: list[tuple[str, Any]] | None = None,
    parse_variants: bool | None = None,
    parse_dynamic_functions: bool | None = None,
    derive: dict[str, Any] | None = None,
    derive_by_type: dict[str, Any] | None = None,
) -> None:
    """
    Adds an need field to the configured need schema.

    Same impact as using :ref:`needs_fields` manually.

    **Usage**::

        from sphinx_needs.api import add_field

        add_field('my_field')

    :param name: Name of the field
    :param description: Description of the field
    :param schema: Schema definition for the field
    :param nullable: Whether the field allows unset values.
    :param default: Default value for the field, if not set in a need.
    :param predicates: List of (need filter, value) pairs for default predicate values.
    :param parse_variants: Whether variants are parsed in this field.
    :param parse_dynamic_functions: Whether dynamic functions are parsed in this field.
    :param derive: A rule computing the field for every need, which makes it a
        :ref:`derived field <needs_derive>`: a dict naming a ``kind`` and its roles.
    :param derive_by_type: Rules per need type, which make it a
        :ref:`derived field <needs_derive>` too: a dict of need type (the directive
        name) to a rule as ``derive`` takes one, overriding ``derive`` on that type.
        A need of a type without a rule holds ``default`` (given only without
        ``derive``), else ``None``, or the empty value of the field's type when it is
        not nullable.

    .. versionchanged:: 9.0.0

       The ``derive`` and ``derive_by_type`` parameters.
    """
    _NEEDS_CONFIG.add_field(
        name,
        description,
        "add_field",
        schema=schema,
        nullable=nullable,
        default=default,
        predicates=predicates,
        parse_variants=parse_variants,
        parse_dynamic_functions=parse_dynamic_functions,
        derive=derive,
        derive_by_type=derive_by_type,
    )


# TODO(mh) add add_link api


def add_dynamic_function(
    app: Sphinx, function: DynamicFunction, name: str | None = None
) -> None:
    """
    Registers a new dynamic function for sphinx-needs.

    If ``name`` is not given, the name to call the function is automatically taken from the provided function.
    A callable without a ``__name__``, such as a ``functools.partial``, must be given its ``name``,
    or ``NeedsApiConfigException`` is raised.
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
    _NEEDS_CONFIG.add_function(function, name)


# 'Need' is untyped, so we temporarily use 'Any' here
WarningCheck = Callable[[NeedItem, SphinxLoggerAdapter], bool]


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

    if name in _NEEDS_CONFIG.warnings:
        raise NeedsApiConfigException(f"Warning {name} already registered.")

    _NEEDS_CONFIG.add_warning(name, warning_check)
