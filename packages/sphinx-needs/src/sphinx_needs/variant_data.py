"""Variant data references, lookup, and proxy for filter expressions.

This module provides:
- :class:`VariantDataParsed` and :func:`lookup_variant_data` for ``<{ var.* }>`` references
- :class:`VariantDataProxy` for dotted attribute access in filter eval contexts

Validating, loading, merging and resolving variant data is ``ub_project``'s.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

# ub-project's own functions, re-exported under the names this module always had: they
# raise its ``ProjectConfigError``, not ``VariantDataError``, and the caller with a Sphinx
# vocabulary (``resolve_variant_data_config``) turns that into a ``NeedsConfigException``.
from ub_project import deep_merge as deep_merge
from ub_project import load_variant_data_file as load_variant_data_file
from ub_project import resolve_variant_data as resolve_variant_data
from ub_project import validate_variant_data as validate_variant_data


class VariantDataError(Exception):
    """Raised when a ``var.*`` reference cannot be resolved against the variant data."""


@dataclass(frozen=True, slots=True)
class VariantDataParsed:
    """A parsed variant data reference, e.g. ``<{ var.a.b }>``.

    Holds the inner expression (without the ``<{`` and ``}>`` delimiters),
    which must be a dotted path rooted at ``var`` (e.g. ``var.build.opt_level``).
    The reference is resolved against the variant data context (``var``)
    when dynamic fields are resolved.
    """

    expression: str
    """The inner expression, stripped of surrounding whitespace."""

    @classmethod
    def from_string(cls, text: str) -> VariantDataParsed:
        """Create a :class:`VariantDataParsed` from a raw inner string.

        :param text: The inner expression text (without delimiters).
        :returns: The parsed variant data reference.
        """
        return cls(text.strip())


def lookup_variant_data(data: dict[str, Any], expression: str) -> Any:
    """Resolve a ``var.*`` dotted-path reference against variant data.

    This is a constrained lookup, not an arbitrary expression evaluation:
    the expression must be a dotted path rooted at ``var``
    (e.g. ``var.build.opt_level``), with no operators, function calls,
    or item access. Each segment selects a key from the (nested) variant
    data mapping.

    :param data: The resolved variant data mapping.
    :param expression: The reference expression, e.g. ``var.build.debug``.
    :returns: The resolved leaf value (a scalar or list).
    :raises VariantDataError: If the expression is not a valid ``var.*`` path,
        a key along the path is missing, or an intermediate/leaf value has the
        wrong shape (e.g. selecting into a non-mapping, or resolving to a mapping).
    """
    segments = [segment.strip() for segment in expression.split(".")]
    if len(segments) < 2 or segments[0] != "var" or any(not s for s in segments):
        raise VariantDataError(
            f"variant data reference {expression!r} is invalid: "
            "expected a dotted 'var.*' path"
        )
    current: Any = data
    traversed: list[str] = []
    for segment in segments[1:]:
        if not isinstance(current, dict):
            raise VariantDataError(
                f"variant data reference {expression!r} is invalid: "
                f"'var.{'.'.join(traversed)}' is not a mapping"
            )
        if segment not in current:
            traversed.append(segment)
            raise VariantDataError(
                f"Unknown variant data key: 'var.{'.'.join(traversed)}'"
            )
        traversed.append(segment)
        current = current[segment]
    if isinstance(current, dict):
        raise VariantDataError(
            f"variant data reference {expression!r} resolves to a mapping "
            f"('var.{'.'.join(traversed)}'); access a leaf value instead"
        )
    return current


class VariantDataProxy:
    """Proxy enabling dotted attribute access to nested variant data.

    Used as ``var`` in filter eval contexts so that expressions like
    ``var.cpu == "arm"`` and ``var.build.debug`` work.

    Only attribute access is supported (no item access).
    Missing keys raise :class:`AttributeError`.
    """

    __slots__ = ("_data", "_path")

    def __init__(self, data: dict[str, object], path: tuple[str, ...] = ()) -> None:
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        data: dict[str, object] = object.__getattribute__(self, "_data")
        path: tuple[str, ...] = object.__getattribute__(self, "_path")
        if name not in data:
            full = "var." + ".".join((*path, name))
            raise AttributeError(f"Unknown variant key: {full}")
        value = data[name]
        if isinstance(value, dict):
            return VariantDataProxy(value, (*path, name))
        return value

    def __contains__(self, key: object) -> bool:
        data: dict[str, object] = object.__getattribute__(self, "_data")
        return isinstance(key, str) and key in data

    def __repr__(self) -> str:
        path: tuple[str, ...] = object.__getattribute__(self, "_path")
        data: dict[str, object] = object.__getattribute__(self, "_data")
        prefix = "var." + ".".join(path) if path else "var"
        return f"<VariantDataProxy {prefix} keys={list(data.keys())}>"

    def __bool__(self) -> bool:
        data: dict[str, object] = object.__getattribute__(self, "_data")
        return bool(data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VariantDataProxy):
            return bool(
                object.__getattribute__(self, "_data")
                == object.__getattribute__(other, "_data")
            )
        return NotImplemented

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys (supports ``for k in var.sub``)."""
        data: dict[str, object] = object.__getattribute__(self, "_data")
        return iter(data)
