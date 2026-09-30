"""Variant data: validate it, load it from a JSON file, merge it, resolve it.

The one copy of these four functions for the sphinx-needs family, to replace the copies
sphinx-needs and sphinx-mounts carry once they adopt it (mounts' copy exists so that it
never depends on sphinx-needs). Measured, the two copies differ in six places, and this
one takes a side on each:

* :func:`resolve_variant_data` always returns a FRESH merged mapping -- never one of its
  arguments -- so that a consumer can store and change it freely at the top level
  (mounts' behaviour; sphinx-needs handed back the inline object when there was no file);
* the error wording is the set below, each message naming the dotted path (``var.a.b``)
  and the rule it broke;
* every failure to load the file is an :class:`~ubproject.project.UbprojectError`
  (mounts'; sphinx-needs let ``OSError`` and ``UnicodeDecodeError`` escape);
* an empty path is not "no file": the API takes ``Path | None``, and ``""`` names nothing
  (mounts'; sphinx-needs read ``""`` as no file -- on the ``conf.py``/``-D`` route BOTH
  consumers do, so a consumer maps ``""`` to ``None`` before calling this);
* :func:`deep_merge` returns plain ``dict`` s at every level it builds, where both copies
  returned the input's own mapping type (``.copy()``) -- unobservable through TOML or JSON,
  which only produce plain dicts;
* :func:`load_variant_data_file` takes a ``str`` path as well as a ``Path`` (sphinx-needs';
  mounts' copy refused a ``str`` with ``AttributeError``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ubproject.project import UbprojectError

#: The types a leaf value, or every element of an array, may have. ``bool`` is listed
#: although it is an ``int``: an array is checked by EXACT type, so ``[1, True]`` is mixed.
_SCALAR_TYPES = (str, bool, int, float)

_SCALARS = "str, bool, int or float"


def validate_variant_data(data: object, path: str = "var") -> None:
    """Check that *data* has the shape a variant map is allowed to have.

    A table with string keys, whose values are scalars (``str``, ``bool``, ``int``,
    ``float``), arrays that are empty or hold scalars of one exact type, or tables of the
    same shape, recursively.

    :param data: The value to check.
    :param path: The dotted path of *data*, for the error message.
    :raises UbprojectError: On the first violation, naming its dotted path.
    """
    if not isinstance(data, dict):
        msg = f"{path}: variant data must be a table, got {type(data).__name__}"
        raise UbprojectError(msg)
    for key, value in data.items():
        if not isinstance(key, str):
            msg = f"{path}: keys must be strings, got {type(key).__name__} {key!r}"
            raise UbprojectError(msg)
        full = f"{path}.{key}"
        if isinstance(value, dict):
            validate_variant_data(value, full)
        elif isinstance(value, list):
            _validate_array(value, full)
        elif not isinstance(value, _SCALAR_TYPES):
            msg = (
                f"{full}: a value must be a {_SCALARS}, an array or a table, "
                f"got {type(value).__name__}"
            )
            raise UbprojectError(msg)


def _validate_array(value: list[Any], path: str) -> None:
    """An array must be empty, or hold scalars of one exact type."""
    if not value:
        return
    first = type(value[0])
    if first not in _SCALAR_TYPES:
        msg = f"{path}: array elements must be a {_SCALARS}, got {first.__name__}"
        raise UbprojectError(msg)
    for index, item in enumerate(value):
        if type(item) is not first:
            msg = (
                f"{path}[{index}]: an array must hold one type, expected "
                f"{first.__name__} but got {type(item).__name__}"
            )
            raise UbprojectError(msg)


def load_variant_data_file(path: Path | str) -> dict[str, Any]:
    """Load a variant-data JSON file and validate its shape.

    :param path: The file, already anchored by the caller.
    :return: The validated mapping.
    :raises UbprojectError: If the file is missing or unreadable, is not JSON, does not
        hold a JSON object, or holds one of the wrong shape.
    """
    file = Path(path)
    if file.is_dir():
        msg = f"variant data file {file} is a directory"
        raise UbprojectError(msg)
    if not file.is_file():
        msg = f"variant data file not found: {file}"
        raise UbprojectError(msg)
    try:
        raw: object = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        msg = f"variant data file {file} is not valid JSON: {error}"
        raise UbprojectError(msg) from error
    except OSError as error:
        msg = f"variant data file {file} cannot be read: {error}"
        raise UbprojectError(msg) from error
    if not isinstance(raw, dict):
        msg = (
            f"variant data file {file} must hold a JSON object, "
            f"got {type(raw).__name__}"
        )
        raise UbprojectError(msg)
    try:
        validate_variant_data(raw)
    except UbprojectError as error:
        msg = f"variant data file {file}: {error}"
        raise UbprojectError(msg) from error
    return raw


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge *override* into *base*; *override* wins at the leaves.

    Recurses ONLY when both sides hold a table under the same key. Everything else is a
    wholesale replacement: an array replaces an array, a scalar replaces a table and a
    table a scalar. That rule is what makes the merge idempotent --
    ``deep_merge(base, deep_merge(base, override)) == deep_merge(base, override)`` -- so
    re-merging an already-merged map is a no-op.

    Neither argument is modified, and the result is a new mapping at every level the merge
    recursed into. (Not a contract, and not something a second reader can reproduce: a
    value taken whole from one side is, in this implementation, that side's object.)
    """
    result = dict(base)
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = deep_merge(existing, value)
        else:
            result[key] = value
    return result


def resolve_variant_data(
    inline: Mapping[str, Any] | None, data_file: Path | None
) -> dict[str, Any]:
    """The merged variant map: the file first, the inline table deep-merged on top.

    :param inline: The inline table; ``None`` and an empty table both mean "none".
    :param data_file: An ALREADY ANCHORED path, or ``None``.
    :return: A fresh mapping, never *inline* itself, even when there is no file.
    :raises UbprojectError: If the file or the inline table is malformed.
    """
    base: dict[str, Any] = {}
    if data_file is not None:
        base = load_variant_data_file(data_file)
    if inline:
        validate_variant_data(inline)
    return deep_merge(base, inline or {})
