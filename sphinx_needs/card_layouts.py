"""Compilation of ``needs_card_layouts`` specifications into ``needs_layouts`` entries.

A *card specification* is a small, declarative description of what a need should show
(a header, a meta region, a footer, a side region, ...).
Specifications are compiled, once per build during ``config-inited``,
into ordinary :ref:`needs_layouts` entries,
so that everything downstream of the layout registry
(the ``:layout:`` option, :ref:`needs_default_layout`, ``needextract``, services, ...)
honours them without any change to the renderer.

The compiler only ever emits from the closed set of templates defined in this module.
The only user text that ever reaches a layout string is a field name
or a grammar-bound option value,
each validated against its strict allow-list first.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Final, Literal

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields
from sphinx_needs.defaults import LAYOUTS
from sphinx_needs.logging import get_logger, log_warning

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterable, Mapping

    from sphinx.application import Sphinx
    from sphinx.config import Config

LOGGER = get_logger(__name__)

MetaFieldTier = Literal["stored", "effective", "all"]
"""The tier of need fields shown in the meta region."""

CollapseMode = Literal["honour", "open", "closed"]
"""How the meta region disclosure behaves."""

SidePosition = Literal["left", "right"]
"""Which side of the card the side region sits on."""

SideSpan = Literal["full", "partial"]
"""How far down the card the side region reaches."""

BUILTIN_CARD_SPECS: Final[dict[str, dict[str, Any]]] = {
    # ``clean`` is, by definition, the specification with every key at its default.
    "clean": {},
    "clean_l": {
        "extends": "clean",
        "side": {"elements": ["image:image"], "position": "left", "span": "full"},
    },
    "clean_lp": {
        "extends": "clean",
        "side": {"elements": ["image:image"], "position": "left", "span": "partial"},
    },
    "clean_r": {
        "extends": "clean",
        "side": {"elements": ["image:image"], "position": "right", "span": "full"},
    },
    "clean_rp": {
        "extends": "clean",
        "side": {"elements": ["image:image"], "position": "right", "span": "partial"},
    },
    "complete": {
        "meta": {"fields": "effective", "exclude": ["layout", "style"]},
        "footer": ["layout_echo", "style_echo"],
    },
    "debug": {"meta": {"fields": "all", "empties": True}, "collapse": "open"},
    "focus": {
        "header": False,
        "meta": False,
        "footer": ["id"],
        "collapse": "honour",
    },
    "focus_f": {"extends": "focus"},
    "focus_l": {
        "header": False,
        "meta": False,
        "side": {"elements": ["id"], "position": "left", "span": "full"},
    },
    "focus_r": {
        "header": False,
        "meta": False,
        "side": {"elements": ["id"], "position": "right", "span": "full"},
    },
    "test": {"extends": "clean"},
}
"""The built-in card specifications, usable as ``extends`` bases.

These describe the built-in layouts of the same name in specification terms.
They are data only: nothing here is registered as a layout,
and a compiled card is always a freshly generated ``needs_layouts`` entry.

``test`` and ``focus_f`` are aliases, of ``clean`` and ``focus`` respectively.
"""

_SPEC_KEYS: Final = frozenset(
    {"extends", "header", "content", "meta", "footer", "side", "collapse"}
)
_META_KEYS: Final = frozenset(
    {"fields", "include", "exclude", "empties", "links", "links_back"}
)
_SIDE_KEYS: Final = frozenset({"elements", "position", "span"})

_META_FIELD_TIERS: Final[tuple[MetaFieldTier, ...]] = ("stored", "effective", "all")
_COLLAPSE_MODES: Final[tuple[CollapseMode, ...]] = ("honour", "open", "closed")
_SIDE_POSITIONS: Final[tuple[SidePosition, ...]] = ("left", "right")
_SIDE_SPANS: Final[tuple[SideSpan, ...]] = ("full", "partial")

_SIMPLE_ELEMENTS: Final = frozenset(
    {"id", "title", "type", "layout_echo", "style_echo"}
)
"""The element types that take neither a field nor any option."""

_ELEMENT_TYPES: Final = _SIMPLE_ELEMENTS | {"field", "image"}
"""Every value the ``type`` key of an object-form element may take."""

_ELEMENT_OPTION_KEYS: Final[dict[str, frozenset[str]]] = {
    "field": frozenset({"label"}),
    "image": frozenset({"height", "width"}),
}
"""The option keys each element type accepts, beyond ``type`` and ``field``."""

# Every grammar below is enforced with ``fullmatch``: a ``$`` anchor also matches
# just before a trailing newline, which would let e.g. ``"40px\n"`` through to the
# emitted layout string and abort the build when the layout call is parsed.

_NAME_PATTERN: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
"""Allow-list for a card name and for any field name interpolated into a layout string."""

_DIMENSION_PATTERN: Final = re.compile(r"[0-9]+(\.[0-9]+)?(px|em|rem|%|pt)?")
"""Allow-list for the ``height`` and ``width`` options; a bare number means pixels."""

_DIMENSION_MAX_LENGTH: Final = 16
"""Upper bound on the length of a ``height`` or ``width`` value."""

_LABEL_PATTERN: Final = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9 _().,/-]{0,62}[A-Za-z0-9])?"
)
"""Allow-list for the ``label`` option: 1-64 characters, alphanumeric at both ends."""

_LABEL_LOOSE_UNDERSCORE: Final = re.compile(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")
"""An underscore not sitting directly between two alphanumerics; forbidden in a label.

A word-leading or word-trailing underscore is RST reference syntax
(``name_``, ``__``), which would crash the HTML writer
when the label is RST-parsed as a ``prefix`` argument.
Every other RST-active character is excluded by the label charset itself.
"""

# --- the closed template set ------------------------------------------------
# Nothing else is ever emitted. No template contains ``{{``, which the layout
# parser would treat as a need placeholder, and none of them uses ``is_external``.

_HEAD_LINE: Final = '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>'
_COLLAPSE_BUTTON: Final = (
    '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
    'visible="icon:arrow-right-circle", initial={initial})>>'
)
_ELEMENT_TEMPLATES: Final[dict[str, str]] = {
    "id": "<<meta_id()>>",
    "title": '<<meta("title")>>',
    "type": '<<meta("type_name")>>',
    "layout_echo": 'layout: <<meta("layout")>>',
    "style_echo": 'style: <<meta("style")>>',
}
_FIELD_TEMPLATE: Final = '<<meta("{name}")>>'
_FIELD_EMPTIES_TEMPLATE: Final = '<<meta("{name}", show_empty=True)>>'
_FIELD_LABEL_TEMPLATE: Final = '<<meta("{name}", prefix="{label}: ")>>'
_IMAGE_TEMPLATE: Final = '<<image("field:{name}", {options}align="center")>>'
_IMAGE_OPTION_TEMPLATE: Final = '{key}="{value}", '
_META_ALL_TEMPLATE: Final = "<<meta_all({args})>>"
_META_LINKS_ALL: Final = "<<meta_links_all()>>"

_GRID_SECTIONS: Final[dict[str, frozenset[str]]] = {
    "simple": frozenset({"head", "meta"}),
    "simple_footer": frozenset({"head", "meta", "footer"}),
    "simple_side_left": frozenset({"head", "meta", "side"}),
    "simple_side_right": frozenset({"head", "meta", "side"}),
    "simple_side_left_partial": frozenset({"head", "meta", "side"}),
    "simple_side_right_partial": frozenset({"head", "meta", "side"}),
    "content": frozenset(),
    "content_footer": frozenset({"footer"}),
    "content_side_left": frozenset({"side"}),
    "content_side_right": frozenset({"side"}),
    "content_footer_side_left": frozenset({"side", "footer"}),
    "content_footer_side_right": frozenset({"side", "footer"}),
}
"""The layout section keys each grid actually reads.

Sections outside this set are silently dropped by the renderer,
so the compiler checks its own output against it.
"""


@dataclass(frozen=True)
class MetaSpec:
    """The validated ``meta`` region of a card specification."""

    fields: MetaFieldTier = "stored"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    empties: bool = False
    links: bool = True
    links_back: bool = True


@dataclass(frozen=True)
class ElementSpec:
    """A validated footer or side element.

    The string shorthand ``field:owner`` and the object form
    ``{"type": "field", "field": "owner"}`` both normalise to this,
    so the equivalence of the two spellings holds by construction.
    """

    type: str
    field: str | None = None
    height: str | None = None
    width: str | None = None
    label: str | None = None


@dataclass(frozen=True)
class SideSpec:
    """The validated ``side`` region of a card specification."""

    elements: tuple[ElementSpec, ...] = ()
    position: SidePosition = "left"
    span: SideSpan = "full"


@dataclass(frozen=True)
class CardSpec:
    """A fully resolved and validated card specification."""

    header: bool = True
    meta: MetaSpec | None = MetaSpec()
    footer: tuple[ElementSpec, ...] = ()
    side: SideSpec | None = None
    collapse: CollapseMode = "honour"


def _quote_list(items: Iterable[str], /) -> str:
    """Render validated names as a layout-function list literal.

    :param items: Already validated field names.
    :return: A list literal, e.g. ``["layout","style"]``.
    """
    return "[" + ",".join(f'"{item}"' for item in items) + "]"


def _resolve_extends(
    name: str,
    spec: Mapping[str, Any],
    specs: Mapping[str, Any],
    warn: Callable[[str], None],
) -> tuple[dict[str, Any], dict[str, str]] | None:
    """Resolve an ``extends`` chain into a single specification.

    :param name: Name of the card being compiled.
    :param spec: The card's own (raw) specification.
    :param specs: All user defined card specifications, for base lookup.
    :param warn: Called with a message for every problem found.
    :return: The merged specification and, per key, the name of the specification
        that supplied it, or ``None`` if the chain could not be resolved.
    """
    levels: list[tuple[str, Mapping[str, Any]]] = []
    seen = [name]
    current_name, current = name, spec
    while True:
        levels.append((current_name, current))
        base = current.get("extends")
        if base is None:
            break
        if not isinstance(base, str):
            warn(f"'extends' must be a string, got {base!r}, skipping.")
            return None
        if base in seen:
            warn(f"circular 'extends' chain ({' -> '.join([*seen, base])}), skipping.")
            return None
        # built-in names always denote the built-in specification
        next_spec = BUILTIN_CARD_SPECS.get(base, specs.get(base))
        if next_spec is None:
            warn(f"unknown 'extends' base {base!r}, skipping.")
            return None
        if not isinstance(next_spec, dict):
            warn(f"'extends' base {base!r} is not a dict, skipping.")
            return None
        seen.append(base)
        # deep-copy so that a base (built-in or user) is never mutated
        current_name, current = base, deepcopy(next_spec)

    merged: dict[str, Any] = {}
    origins: dict[str, str] = {}
    for level_name, level in reversed(levels):
        for key, value in level.items():
            if key == "extends":
                continue
            if (
                key in ("meta", "side")
                and isinstance(value, dict)
                and isinstance(merged.get(key), dict)
            ):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
                for stale in [k for k in origins if k.startswith(f"{key}.")]:
                    del origins[stale]
            if key in ("meta", "side") and isinstance(value, dict):
                for sub_key in value:
                    origins[f"{key}.{sub_key}"] = level_name
            origins[key] = level_name
    return merged, origins


def _parse_meta(
    value: Any,
    warn: Callable[[str], None],
) -> MetaSpec | None | Literal[False]:
    """Validate the ``meta`` key of a specification.

    :param value: The raw value of the ``meta`` key.
    :param warn: Called with a message for every problem found.
    :return: The validated region, ``False`` for "no meta region",
        or ``None`` if the value was invalid.
    """
    if value is False:
        return False
    if not isinstance(value, dict):
        warn(f"'meta' must be a dict or false, got {value!r}, skipping.")
        return None
    if unknown := sorted(set(value) - _META_KEYS):
        warn(
            f"unknown key(s) {', '.join(repr(k) for k in unknown)} in 'meta' "
            f"(allowed: {', '.join(sorted(_META_KEYS))}), skipping."
        )
        return None
    tier = value.get("fields", "stored")
    if tier not in _META_FIELD_TIERS:
        warn(
            f"'meta.fields' must be one of "
            f"{', '.join(repr(t) for t in _META_FIELD_TIERS)}, got {tier!r}, skipping."
        )
        return None
    names: dict[str, tuple[str, ...]] = {}
    for key in ("include", "exclude"):
        raw = value.get(key, [])
        if not isinstance(raw, (list, tuple)) or not all(
            isinstance(item, str) for item in raw
        ):
            warn(f"'meta.{key}' must be a list of strings, got {raw!r}, skipping.")
            return None
        for item in raw:
            if not _NAME_PATTERN.fullmatch(item):
                warn(f"invalid field name {item!r} in 'meta.{key}', skipping.")
                return None
        names[key] = tuple(raw)
    flags: dict[str, bool] = {}
    for key, default in (("empties", False), ("links", True), ("links_back", True)):
        raw = value.get(key, default)
        if not isinstance(raw, bool):
            warn(f"'meta.{key}' must be a boolean, got {raw!r}, skipping.")
            return None
        flags[key] = raw
    return MetaSpec(
        fields=tier,
        include=names["include"],
        exclude=names["exclude"],
        empties=flags["empties"],
        links=flags["links"],
        links_back=flags["links_back"],
    )


def _parse_side(
    value: Any, warn: Callable[[str], None]
) -> SideSpec | None | Literal[False]:
    """Validate the ``side`` key of a specification.

    :param value: The raw value of the ``side`` key.
    :param warn: Called with a message for every problem found.
    :return: The validated region, ``False`` for "no side region",
        or ``None`` if the value was invalid.
    """
    if value is False:
        return False
    if not isinstance(value, dict):
        warn(f"'side' must be a dict or false, got {value!r}, skipping.")
        return None
    if unknown := sorted(set(value) - _SIDE_KEYS):
        warn(
            f"unknown key(s) {', '.join(repr(k) for k in unknown)} in 'side' "
            f"(allowed: {', '.join(sorted(_SIDE_KEYS))}), skipping."
        )
        return None
    elements = value.get("elements", [])
    if not isinstance(elements, (list, tuple)):
        warn(
            f"'side.elements' must be a list of strings or dicts, "
            f"got {elements!r}, skipping."
        )
        return None
    parsed_elements = _parse_elements(elements, "side", warn)
    if parsed_elements is None:
        return None
    position = value.get("position", "left")
    if position not in _SIDE_POSITIONS:
        warn(
            f"'side.position' must be one of "
            f"{', '.join(repr(p) for p in _SIDE_POSITIONS)}, "
            f"got {position!r}, skipping."
        )
        return None
    span = value.get("span", "full")
    if span not in _SIDE_SPANS:
        warn(
            f"'side.span' must be one of {', '.join(repr(s) for s in _SIDE_SPANS)}, "
            f"got {span!r}, skipping."
        )
        return None
    return SideSpec(elements=parsed_elements, position=position, span=span)


def _parse_element_str(
    element: str, region: str, warn: Callable[[str], None]
) -> ElementSpec | None:
    """Validate a string-form element.

    :param element: The raw element string.
    :param region: Name of the region, used in messages.
    :param warn: Called with a message for every problem found.
    :return: The normalised element, or ``None`` if it was invalid.
    """
    if element in _SIMPLE_ELEMENTS:
        return ElementSpec(type=element)
    prefix, _, field_name = element.partition(":")
    if prefix not in ("field", "image") or not field_name:
        warn(
            f"unknown {region} element {element!r} (allowed: "
            f"{', '.join(sorted(_SIMPLE_ELEMENTS))}, 'field:<name>', "
            "'image:<name>'), skipping."
        )
        return None
    if not _NAME_PATTERN.fullmatch(field_name):
        warn(
            f"invalid field name {field_name!r} in {region} element "
            f"{element!r}, skipping."
        )
        return None
    return ElementSpec(type=prefix, field=field_name)


def _parse_element_dict(
    element: Mapping[str, Any], region: str, warn: Callable[[str], None]
) -> ElementSpec | None:
    """Validate an object-form element.

    :param element: The raw element dict.
    :param region: Name of the region, used in messages.
    :param warn: Called with a message for every problem found.
    :return: The normalised element, or ``None`` if it was invalid.
    """
    # guard before any key set arithmetic: mixed-type keys make ``sorted`` raise
    if any(not isinstance(key, str) for key in element):
        warn(f"{region} element keys must be strings, got {element!r}, skipping.")
        return None
    element_type = element.get("type")
    if element_type not in _ELEMENT_TYPES:
        warn(
            f"{region} element 'type' must be one of "
            f"{', '.join(repr(t) for t in sorted(_ELEMENT_TYPES))}, "
            f"got {element_type!r}, skipping."
        )
        return None
    takes_field = element_type in ("field", "image")
    allowed = ({"type", "field"} if takes_field else {"type"}) | (
        _ELEMENT_OPTION_KEYS.get(element_type, frozenset())
    )
    if unknown := sorted(set(element) - allowed):
        warn(
            f"key(s) {', '.join(repr(k) for k in unknown)} not allowed in a "
            f"{element_type!r} {region} element "
            f"(allowed: {', '.join(sorted(allowed))}), skipping."
        )
        return None
    field_name: str | None = None
    if takes_field:
        raw_field = element.get("field")
        if raw_field is None:
            warn(
                f"'field' is required in a {element_type!r} {region} element, skipping."
            )
            return None
        if not isinstance(raw_field, str) or not _NAME_PATTERN.fullmatch(raw_field):
            warn(f"invalid field name {raw_field!r} in {region} element, skipping.")
            return None
        field_name = raw_field
    dimensions: dict[str, str | None] = {"height": None, "width": None}
    for key in dimensions:
        if (raw := element.get(key)) is None:
            continue
        if (
            not isinstance(raw, str)
            or len(raw) > _DIMENSION_MAX_LENGTH
            or not _DIMENSION_PATTERN.fullmatch(raw)
        ):
            warn(
                f"'{key}' must be a number with an optional px/em/rem/%/pt unit, "
                f"at most {_DIMENSION_MAX_LENGTH} characters, "
                f"got {raw!r} in {region} element, skipping."
            )
            return None
        dimensions[key] = raw
    label = element.get("label")
    if label is not None and (
        not isinstance(label, str)
        or not _LABEL_PATTERN.fullmatch(label)
        or _LABEL_LOOSE_UNDERSCORE.search(label)
    ):
        warn(
            "'label' must be 1-64 characters from [A-Za-z0-9 _().,/-], "
            "starting and ending alphanumeric, with '_' only directly between "
            f"alphanumerics, got {label!r} in {region} element, skipping."
        )
        return None
    return ElementSpec(
        type=element_type,
        field=field_name,
        height=dimensions["height"],
        width=dimensions["width"],
        label=label,
    )


def _parse_elements(
    elements: Iterable[Any], region: str, warn: Callable[[str], None]
) -> tuple[ElementSpec, ...] | None:
    """Validate and normalise the elements of a footer or side region.

    :param elements: The raw element entries, strings or dicts.
    :param region: Name of the region, used in messages.
    :param warn: Called with a message for every problem found.
    :return: The normalised elements, or ``None`` if any entry was invalid.
    """
    parsed: list[ElementSpec] = []
    valid = True
    for element in elements:
        item: ElementSpec | None
        if isinstance(element, str):
            item = _parse_element_str(element, region, warn)
        elif isinstance(element, dict):
            item = _parse_element_dict(element, region, warn)
        else:
            warn(
                f"{region} element must be a string or a dict, "
                f"got {element!r}, skipping."
            )
            item = None
        if item is None:
            valid = False
        else:
            parsed.append(item)
    return tuple(parsed) if valid else None


def _warn_unregistered_fields(
    elements: Iterable[ElementSpec],
    region: str,
    known_fields: Container[str],
    warn: Callable[[str], None],
) -> None:
    """Warn about elements referencing a field nobody registered.

    :param elements: The normalised elements of the region.
    :param region: Name of the region, used in messages.
    :param known_fields: The registered need field names.
    :param warn: Called with a message for every problem found.
    """
    for element in elements:
        if element.field is not None and element.field not in known_fields:
            warn(
                f"{region} element references the need field "
                f"{element.field!r}, which is not registered; it will render empty."
            )


def _parse_spec(
    merged: Mapping[str, Any],
    origins: Mapping[str, str],
    *,
    known_fields: Container[str],
    warn: Callable[[str], None],
) -> CardSpec | None:
    """Validate a resolved specification.

    :param merged: The specification after ``extends`` resolution.
    :param origins: Per key, the name of the specification that supplied it.
    :param known_fields: The registered need field names.
    :param warn: Called with a message for every problem found.
    :return: The validated specification, or ``None`` if it must be skipped.
    """
    if unknown := sorted(set(merged) - _SPEC_KEYS):
        warn(
            f"unknown key(s) {', '.join(repr(k) for k in unknown)} "
            f"(allowed: {', '.join(sorted(_SPEC_KEYS))}), skipping."
        )
        return None

    content = merged.get("content", True)
    if content is not True:
        warn(
            "'content' cannot be disabled, a need always renders its content, skipping."
        )
        return None

    header = merged.get("header", True)
    if not isinstance(header, bool):
        warn(f"'header' must be a boolean, got {header!r}, skipping.")
        return None

    collapse = merged.get("collapse", "honour")
    if collapse not in _COLLAPSE_MODES:
        warn(
            f"'collapse' must be one of "
            f"{', '.join(repr(c) for c in _COLLAPSE_MODES)}, "
            f"got {collapse!r}, skipping."
        )
        return None

    meta = _parse_meta(merged.get("meta", {}), warn)
    if meta is None:
        return None

    raw_footer = merged.get("footer", [])
    if not isinstance(raw_footer, (list, tuple)):
        warn(
            f"'footer' must be a list of strings or dicts, got {raw_footer!r}, "
            "skipping."
        )
        return None
    footer = _parse_elements(raw_footer, "footer", warn)
    if footer is None:
        return None

    side: SideSpec | None = None
    if (raw_side := merged.get("side")) is not None:
        # ``side = false`` and ``side = {"elements": []}`` are both spellings of
        # "no side region"; either one opts a card out of a base's side region.
        parsed_side = _parse_side(raw_side, warn)
        if parsed_side is None:
            return None
        side = None if parsed_side is False else parsed_side

    # The built-in-inheritance exemption is deliberately side-only: `clean_l` and its three
    # siblings are the only built-in specifications carrying a field element, and it sits in
    # their `side` region (upstream's `image` field, which nobody has to register). A footer
    # element is therefore always user-authored and always validated. Overriding an
    # inherited region re-keys its origin to the card, which restores validation there too.
    _warn_unregistered_fields(footer, "footer", known_fields, warn)
    if side is not None and origins.get("side.elements") not in BUILTIN_CARD_SPECS:
        _warn_unregistered_fields(side.elements, "side", known_fields, warn)

    title_regions = [
        region
        for region, elements in (
            ("footer", footer),
            ("side", () if side is None else side.elements),
        )
        if any(element.type == "title" for element in elements)
    ]
    if title_regions and header:
        warn(
            "the 'title' element is only allowed when 'header' is false "
            "(the header already shows the title), skipping."
        )
        return None
    if len(title_regions) > 1:
        warn("the 'title' element may only be used in one region, skipping.")
        return None

    return CardSpec(
        header=header,
        meta=None if meta is False else meta,
        footer=footer,
        side=None if side is not None and not side.elements else side,
        collapse=collapse,
    )


def _select_grid(
    spec: CardSpec, warn: Callable[[str], None]
) -> tuple[str, CardSpec] | None:
    """Choose the ``needs_layouts`` grid realising a specification.

    :param spec: The validated specification.
    :param warn: Called with a message for every problem found.
    :return: The grid name and the (possibly degraded) specification,
        or ``None`` if no grid can realise it.
    """
    has_footer = bool(spec.footer)
    if spec.header:
        if spec.side is not None and has_footer:
            warn(
                "a card with a header, a side region and a footer is not expressible "
                "by the needs_layouts grids, skipping."
            )
            return None
        if spec.side is not None:
            suffix = "_partial" if spec.side.span == "partial" else ""
            return f"simple_side_{spec.side.position}{suffix}", spec
        if has_footer:
            return "simple_footer", spec
        return "simple", spec

    if spec.meta is not None:
        warn(
            "a card with a meta region but no header is not expressible by the "
            "needs_layouts grids, skipping."
        )
        return None
    if (side := spec.side) is None:
        return ("content_footer" if has_footer else "content"), spec
    if side.span == "partial":
        warn(
            "a headerless card has no partial side grid, "
            "rendering 'side.span' as 'full'."
        )
        side = replace(side, span="full")
        spec = replace(spec, side=side)
    prefix = "content_footer_side" if has_footer else "content_side"
    return f"{prefix}_{side.position}", spec


def _build_meta_lines(meta: MetaSpec) -> list[str]:
    """Render the meta region of a specification.

    :param meta: The validated meta region.
    :return: The layout lines of the ``meta`` section.
    """
    lines: list[str] = []
    if meta.include:
        template = _FIELD_EMPTIES_TEMPLATE if meta.empties else _FIELD_TEMPLATE
        lines += [
            template.format(name=name)
            for name in meta.include
            if name not in meta.exclude
        ]
    elif meta.fields == "all":
        args = [f"exclude={_quote_list(meta.exclude)}"]
        if not meta.links:
            args.append("no_links=True")
        args.append("defaults=False")
        if meta.empties:
            args.append("show_empty=True")
        lines.append(_META_ALL_TEMPLATE.format(args=", ".join(args)))
    else:
        args = ["no_links=True"]
        if meta.exclude:
            args.append(f"exclude={_quote_list(meta.exclude)}")
        if meta.empties:
            args.append("show_empty=True")
        lines.append(_META_ALL_TEMPLATE.format(args=", ".join(args)))
    if meta.links and meta.fields != "all":
        lines.append(_META_LINKS_ALL)
    return lines


def _build_element_lines(elements: Iterable[ElementSpec]) -> list[str]:
    """Render footer or side elements.

    :param elements: The validated elements.
    :return: One layout line per element.
    """
    lines: list[str] = []
    for element in elements:
        if (template := _ELEMENT_TEMPLATES.get(element.type)) is not None:
            lines.append(template)
        elif element.type == "field":
            lines.append(
                _FIELD_LABEL_TEMPLATE.format(name=element.field, label=element.label)
                if element.label is not None
                else _FIELD_TEMPLATE.format(name=element.field)
            )
        else:
            # an optionless image renders the empty options string, so the object
            # form stays byte-identical to the ``image:<name>`` shorthand
            options = "".join(
                _IMAGE_OPTION_TEMPLATE.format(key=key, value=value)
                for key, value in (("height", element.height), ("width", element.width))
                if value is not None
            )
            lines.append(_IMAGE_TEMPLATE.format(name=element.field, options=options))
    return lines


def _build_layout(spec: CardSpec) -> dict[str, list[str]]:
    """Render a specification into ``needs_layouts`` sections.

    :param spec: The validated specification.
    :return: The ``layout`` mapping of section name to lines.
    """
    layout: dict[str, list[str]] = {}
    if spec.header:
        head = _HEAD_LINE
        # a collapse button is only ever emitted when its target row exists,
        # and never more than once
        if spec.meta is not None and spec.collapse != "open":
            initial = "True" if spec.collapse == "closed" else "False"
            head += " " + _COLLAPSE_BUTTON.format(initial=initial) + " "
        layout["head"] = [head]
    if spec.meta is not None:
        layout["meta"] = _build_meta_lines(spec.meta)
    if spec.side is not None and spec.side.elements:
        layout["side"] = _build_element_lines(spec.side.elements)
    if spec.footer:
        layout["footer"] = _build_element_lines(spec.footer)
    return layout


def compile_card_spec(
    name: str,
    spec: Mapping[str, Any],
    /,
    *,
    specs: Mapping[str, Any] | None = None,
    known_fields: Container[str] = (),
    warn: Callable[[str], None],
) -> dict[str, Any] | None:
    """Compile a single card specification into a ``needs_layouts`` entry.

    The function is pure: it neither reads nor writes any global state,
    and never mutates ``spec`` or any ``extends`` base.

    :param name: The name the compiled layout will be registered under.
    :param spec: The card specification.
    :param specs: All user defined card specifications, for ``extends`` lookup.
    :param known_fields: The registered need field names, used to warn about
        specifications referencing a field that will always render empty.
    :param warn: Called with a message for every problem found.
    :return: A ``{"grid": ..., "layout": ...}`` entry,
        or ``None`` if the specification must be skipped.
    """
    if not isinstance(spec, dict):
        warn(f"specification must be a dict, got {spec!r}, skipping.")
        return None
    resolved = _resolve_extends(name, spec, {} if specs is None else specs, warn)
    if resolved is None:
        return None
    parsed = _parse_spec(*resolved, known_fields=known_fields, warn=warn)
    if parsed is None:
        return None
    if parsed.meta is not None and parsed.meta.links and not parsed.meta.links_back:
        warn(
            "'meta.links_back' cannot be disabled on its own, since the link types "
            "are not yet known when card layouts are compiled; "
            "rendering the meta region with back links."
        )
    selected = _select_grid(parsed, warn)
    if selected is None:
        return None
    grid, parsed = selected
    layout = _build_layout(parsed)
    if unreadable := sorted(set(layout) - _GRID_SECTIONS[grid]):
        # unreachable by construction; guards against future grid/selection drift
        warn(
            f"section(s) {', '.join(repr(k) for k in unreadable)} are not rendered by "
            f"grid {grid!r}, skipping."
        )
        return None
    return {"grid": grid, "layout": layout}


def compile_card_layouts(_app: Sphinx, config: Config) -> None:
    """Compile ``needs_card_layouts`` into additional ``needs_layouts`` entries.

    Connected to ``config-inited`` at priority 550,
    i.e. after the built-in layouts have been merged in
    and before the configuration is checked.
    Invalid specifications are warned about and skipped,
    so that a single bad card never costs the user the rest of their build.

    :param config: The Sphinx configuration.
    """
    needs_config = NeedsSphinxConfig(config)
    specs = needs_config.card_layouts
    if not specs:
        return
    if not isinstance(specs, dict):
        log_warning(
            LOGGER,
            f"needs_card_layouts must be a dict, got {specs!r}.",
            "card_layout",
            None,
        )
        return

    known_fields = {*NeedsCoreFields, *_NEEDS_CONFIG.fields}
    generated: dict[str, dict[str, Any]] = {}
    for name, spec in specs.items():

        def warn(message: str, name: str = name) -> None:
            log_warning(
                LOGGER, f"needs_card_layouts[{name!r}]: {message}", "card_layout", None
            )

        if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
            warn(
                "name must match [A-Za-z_][A-Za-z0-9_-]* to be usable as a layout "
                "name, skipping."
            )
            continue
        if name in LAYOUTS:
            warn("name collides with a built-in layout, skipping.")
            continue
        if name in needs_config.layouts:
            warn("name collides with an existing needs_layouts entry, skipping.")
            continue
        if (
            compiled := compile_card_spec(
                name, spec, specs=specs, known_fields=known_fields, warn=warn
            )
        ) is not None:
            generated[name] = compiled

    if generated:
        # rebind, never mutate: the dict may still be the user's own conf.py object
        needs_config.layouts = {**needs_config.layouts, **generated}
