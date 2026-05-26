"""Variant data loading, validation, and proxy for filter expressions.

This module provides:
- Validation of variant data structures
- Loading variant data from JSON files
- Deep-merging of variant data dicts
- :class:`VariantDataProxy` for dotted attribute access in filter eval contexts
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Allowed scalar types for leaf values
_SCALAR_TYPES = (str, bool, int, float)


class VariantDataError(Exception):
    """Raised when variant data fails validation."""


def validate_variant_data(data: dict[str, Any], path: str = "var") -> None:
    """Validate that data conforms to allowed shape.

    :param data: The data to validate.
    :param path: The dotted path prefix for error messages.
    :raises VariantDataError: If data contains invalid types.
    """
    if not isinstance(data, dict):
        raise VariantDataError(f"{path}: expected a dict, got {type(data).__name__}")
    for key, value in data.items():
        if not isinstance(key, str):
            raise VariantDataError(
                f"{path}: all keys must be strings, got {type(key).__name__}"
            )
        full = f"{path}.{key}"
        if isinstance(value, dict):
            validate_variant_data(value, full)
        elif isinstance(value, list):
            if not value:
                continue  # empty list is fine
            first_type = type(value[0])
            if first_type not in _SCALAR_TYPES:
                raise VariantDataError(
                    f"{full}: array elements must be str/bool/int/float, "
                    f"got {first_type.__name__}"
                )
            for i, item in enumerate(value):
                if type(item) is not first_type:
                    raise VariantDataError(
                        f"{full}[{i}]: expected {first_type.__name__}, "
                        f"got {type(item).__name__} (arrays must be uniform type)"
                    )
        elif not isinstance(value, _SCALAR_TYPES):
            raise VariantDataError(
                f"{full}: expected str/bool/int/float/list/dict, "
                f"got {type(value).__name__}"
            )


def load_variant_data_file(path: str | Path) -> dict[str, Any]:
    """Load and validate variant data from a JSON file.

    :param path: Path to a JSON file.
    :returns: The validated data dictionary.
    :raises VariantDataError: If the file is missing or contains invalid data.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise VariantDataError(f"Variant data file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise VariantDataError(f"Invalid JSON in {file_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise VariantDataError(
            f"Variant data file must contain a JSON object, got {type(data).__name__}"
        )
    validate_variant_data(data)
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge override into base (override wins at leaf level).

    :param base: The base dictionary.
    :param override: The override dictionary (wins on conflict).
    :returns: A new merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_variant_data(
    variant_data: dict[str, Any],
    variant_data_file: str | None,
) -> dict[str, Any]:
    """Resolve variant data from inline config and/or file.

    File is loaded first, then inline values are deep-merged on top.

    :param variant_data: Inline variant data dict from config.
    :param variant_data_file: Optional path to a JSON file.
    :returns: The fully resolved and validated variant data dict.
    :raises VariantDataError: If validation fails.
    """
    base: dict[str, Any] = {}
    if variant_data_file:
        base = load_variant_data_file(variant_data_file)
    if variant_data:
        validate_variant_data(variant_data)
    if base and variant_data:
        return deep_merge(base, variant_data)
    return variant_data or base


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
