"""
API to get or add specific sphinx needs configuration parameters.

All functions here are available under ``sphinx_needs.api``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sphinx.application import Sphinx
from sphinx.util.logging import SphinxLoggerAdapter

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.defaults import LAYOUTS
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs.functions.functions import DynamicFunction, Reads
from sphinx_needs.need_item import NeedItem
from sphinx_needs.schema.config import FieldSchemaTypes

# TODO(mh) document exactly when API calls are allowed in the Sphinx event system


def get_need_types(app: Sphinx) -> list[str]:
    """
    Returns a list of directive-names from all need types: the configured
    :ref:`needs_types`, then those added with :func:`add_need_type` by extensions, then
    the ``issue``, ``pr`` and ``commit`` of the GitHub services :ref:`needs_services`
    configures (each only where no earlier type has its directive).

    Call it from a ``config-inited`` handler at a priority above 12, or later: before
    that, a mapping-shaped ``needs_types`` is not yet resolved to its list, and the
    configured GitHub services' types are not yet added. They are listed from
    sphinx-needs' own priority-12 handler on, so from a handler above 12, after the
    types added by then (they used to be added only at ``env-before-read-docs``).

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

    The given directive must not be added with this function already, nor be a default
    need type that no :ref:`needs_types` entry of the project names, otherwise
    NeedsApiConfigException gets raised. A project's entry naming the directive, with
    or without a ``title`` and a ``prefix``, narrows the type instead, however late it
    is added: the keys the entry gives win, the ``title``, ``prefix``, ``color`` and
    ``style`` it leaves out are the ones given here, and its ``inherits``, ``fields``
    and ``links`` apply
    (see :ref:`narrowing an extension's type <needs_types_extension>`).
    The configured GitHub services' ``issue``, ``pr`` and ``commit`` do not count:
    a type added under one of those directives replaces the service's.

    The type is added to sphinx-needs' own registry, not to the :ref:`needs_types`
    configuration value, which holds only what the project configures (so Sphinx
    compares the same value on both sides of an incremental build). Read every type,
    the added ones included, with :func:`get_need_types`, or with
    ``NeedsSphinxConfig(app.config).types`` for the whole entries: the configured
    types, then the added ones, then the configured GitHub services' ones.

    Call it from a ``config-inited`` handler at a priority above 12, or later, as
    :func:`get_need_types` reads it; an earlier call is narrowed by the project's
    entries all the same. Unlike a configured entry, the type is not validated.

    .. versionchanged:: 9.2.0

       A project's ``needs_types`` entry naming the directive narrows the type, where
       one with a ``title`` and a ``prefix`` raised NeedsApiConfigException and one
       with neither was ignored.

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
    from sphinx_needs.needs import _normalise_need_types, _register_need_directive

    configured = NeedsSphinxConfig(app.config)._types
    named = _NEEDS_CONFIG.type_entries
    if named is None and isinstance(configured, list | Mapping):
        # needs_types is not resolved yet: the list it resolves to, and what its
        # entries name, are read the same way
        configured, _, named, _ = _normalise_need_types(configured, defer=True)
    if directive in _NEEDS_CONFIG.types or (
        # a configured type no entry of the project names is a default type
        isinstance(configured, list)
        and directive not in (named or ())
        and any(
            isinstance(need_type, Mapping) and need_type.get("directive") == directive
            for need_type in configured
        )
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

    The given name must not be a layout of :ref:`needs_layouts` (sphinx-needs' own
    layouts included), a name of :ref:`needs_card_layouts` (whether or not its card
    compiles), or one added with this function already, otherwise
    NeedsApiConfigException gets raised: each is refused before the configured layouts
    are merged and the cards compiled, as after. The configured GitHub services'
    ``github`` layout does not count: a layout added under that name replaces the
    service's.

    The layout is added to sphinx-needs' own registry, not to the :ref:`needs_layouts`
    configuration value, which holds only what the project configures (and
    sphinx-needs' own layouts and the compiled :ref:`needs_card_layouts`). Every reader
    sees it, through ``NeedsSphinxConfig(app.config).layouts``: the configured
    layouts, then the added ones, then the configured GitHub services' one. The layout
    is used as given, with the structure a :ref:`needs_layouts` entry has (see
    :ref:`layouts`).

    Call it from a ``config-inited`` handler at a priority above 12, as
    :func:`add_need_type`, or later: before priority 10, the layouts and card layouts
    of a :ref:`needs_from_toml` file are not read yet, and one of their names would
    replace the added layout without a warning.

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
    needs_config = NeedsSphinxConfig(app.config)
    card_layouts = needs_config.card_layouts
    if (
        name in LAYOUTS
        or name in needs_config._layouts
        or (isinstance(card_layouts, dict) and name in card_layouts)
    ):
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
    types: Sequence[str] | None = None,
) -> None:
    """
    Adds an need field to the configured need schema.

    Same impact as using :ref:`needs_fields` manually, or, with ``types``, as declaring
    the field in the :ref:`needs_types` entries of those need types alone
    (:ref:`needs_types_fields`).

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
    :param types: The need types (their directive names) the field is declared on
        alone, as a field declared on need types alone (:ref:`needs_types_fields`):
        on each of them, and on each type inheriting from one, it is this declaration;
        on every other type it is absent, null, and a value set there is reported
        (``needs.undeclared_for_type``) and ignored. A project's :ref:`needs_types`
        entry naming the field on another type declares it there too; a project's
        :ref:`needs_fields` entry of the same name is the field, on every type. A type
        named that no configuration or extension declares by the time the schema is
        built is one ``needs.config`` warning. ``None`` (the default): every type.

    :raises NeedsApiConfigException: If ``types`` is not a sequence of at least one
        need type name (a bare string is refused, not read letter by letter).

    .. versionchanged:: 9.0.0

       The ``derive`` and ``derive_by_type`` parameters.

    .. versionchanged:: 9.2.0

       The ``types`` parameter.
    """
    if types is not None and (
        isinstance(types, str)
        or not types
        or not all(isinstance(t, str) and t for t in types)
    ):
        raise NeedsApiConfigException(
            f"add_field({name!r}): types must be a sequence of need type names, at "
            f"least one, got {types!r}"
        )
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
        types=None if types is None else tuple(dict.fromkeys(types)),
    )


# TODO(mh) add add_link api


def add_dynamic_function(
    app: Sphinx,
    function: DynamicFunction,
    name: str | None = None,
    *,
    reads: Reads | None = None,
) -> None:
    """
    Registers a new dynamic function for sphinx-needs.

    If ``name`` is not given, the name to call the function is automatically taken from the provided function.
    A callable without a ``__name__``, such as a ``functools.partial``, must be given its ``name``,
    or ``NeedsApiConfigException`` is raised.
    The used name must be unique.

    ``reads`` declares what the function reads, for a function you do not own:
    ``add_dynamic_function(app, their_function, reads=reads(own="option"))`` (see
    :func:`reads` and :ref:`dynamic_functions_reads`). It wins over a declaration the
    function carries itself.

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
    :param reads: What the function reads (see :func:`reads`)
    :return: None

    .. versionchanged:: 9.1.0
       The ``reads`` parameter.
    """
    _NEEDS_CONFIG.add_function(function, name, reads=reads)


def reads(*, own: str | Sequence[str] = (), every: str | Sequence[str] = ()) -> Reads:
    """Declare what a dynamic function of your own reads, so that it is computed in
    order, like a built-in function (see :ref:`dynamic_functions_reads`).

    Name the parameters whose argument is a field name the function reads, on the
    call's own need (``own``) or on every need (``every``), each a name or a tuple of
    names; the argument of a ``*args`` parameter is each a field name::

        from sphinx_needs.api import reads

        @reads(own="test_option", every="target_option")
        def my_link(app, need, needs, test_option, target_option):
            ...

    ``@reads()`` declares that the function reads no computed value; a field nothing
    computes need not be declared. A field the function reads by a name written in its
    code, not given as an argument, cannot be declared yet: such a function is
    computed after the built-in functions, as one that declares nothing.

    The result is a :class:`~sphinx_needs.functions.functions.Reads`, which declares the
    function it is applied to (its attribute ``needs_reads``), and which
    :func:`add_dynamic_function` takes as ``reads`` for a function you do not own. A
    wrapper made with :func:`functools.wraps` carries the declaration of the function
    it wraps. The names are checked against the function's parameters when it is
    registered: one that is not a parameter after ``app``, ``need`` and ``needs`` is
    one ``needs.config`` warning, and the function declares nothing.

    :param own: The parameters whose argument names a field read on the call's own
        need.
    :param every: The parameters whose argument names a field read on every need.
    :return: The declaration, which returns the function it is applied to, declared.
    :raises TypeError: If a name is not a string; ``@reads`` written without
        parentheses is refused by Python itself, as ``reads`` takes no positional
        argument.

    .. versionadded:: 9.1.0
    """
    names = tuple(
        (value,) if isinstance(value, str) else tuple(value) for value in (own, every)
    )
    for value in (*names[0], *names[1]):
        if not isinstance(value, str):
            raise TypeError(f"reads names parameters, and {value!r} is not a name")
    return Reads(names[0], names[1])


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
