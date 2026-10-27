"""
Cares about the correct handling with ``needs.json`` files.

Creates, checks and imports ``needs.json`` files.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from typing import Any, NotRequired, TypedDict

from jsonschema_rs import Draft7Validator, ValidationError
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedLink, _link_natural_sort_key
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkSchema,
    LinksLiteralValue,
)

log = get_logger(__name__)


class NeedsJsonCreatorType(TypedDict):
    """The ``creator`` of a version in a ``needs.json``: the program that wrote it."""

    program: str
    version: str


class NeedsJsonVersionType(TypedDict, total=False):
    """One entry of ``versions`` in a ``needs.json``.

    Every key is optional: :meth:`NeedsList.update_or_add_version` writes ``needs``,
    ``needs_amount`` and ``creator`` for a version it creates, and the other three
    by configuration, but a version kept from a file read by
    :meth:`NeedsList.load_json` may be of an older shape that has any of them
    missing (before 3.0 there was no ``creator`` or ``needs_schema``).
    """

    created: str
    creator: NeedsJsonCreatorType
    needs: dict[str, dict[str, Any]]
    """The needs of the version by ID, each a JSON object of its fields."""
    needs_amount: int
    needs_defaults_removed: bool
    needs_schema: dict[str, Any]
    """The JSON schema of one need, from :func:`generate_needs_schema`."""


class NeedsJsonType(TypedDict):
    """The envelope of a ``needs.json``, as :class:`NeedsList` holds and writes it."""

    project: str
    current_version: str
    versions: dict[str, NeedsJsonVersionType]
    created: NotRequired[str]
    """Left out under ``needs_reproducible_json``."""


def generate_needs_schema(
    needs_schema: FieldsSchema, exclude_properties: Iterable[str] = ()
) -> dict[str, Any]:
    """Generate a JSON schema for all fields in each need item.

    It is based on:
    * the core fields defined in NeedsCoreFields, those in the fields schema as the
      project declares them (a ``needs_fields`` entry may narrow one)
    * the extra fields defined dynamically
    * the global options defined dynamically
    * the links defined dynamically

    A derived field or link type (one with a ``derive`` or ``derive_by_type`` rule) is
    marked ``"readOnly": true``; its ``default`` is the value of a need type without a
    rule.

    It is the schema of the fields every need type shares: the global view of the
    schema (:meth:`~sphinx_needs.needs_schema.FieldsSchema.for_type` of no need type),
    whatever a need type declares anew.
    """
    # the union by design: one projection for the needs of every type
    needs_schema = needs_schema.for_type(None)
    properties: dict[str, Any] = {}

    for field in needs_schema.iter_extra_fields():
        properties[field.name] = _field_property(field, "extra")

    # TODO currently extra fields can overlap with core fields,
    # in which case they are ignored,
    # (this is the case for `type` added by the github service)
    # hence this is why we add the core options after the extra fields
    for name, core_params in NeedsCoreFields.items():
        if (field := needs_schema.get_core_field(name)) is not None:
            # as the project declares it, a needs_fields entry narrowing it included
            properties[name] = _field_property(field, "core")
            continue
        properties[name] = deepcopy(core_params["schema"])
        properties[name]["description"] = f"{core_params['description']}"
        properties[name]["field_type"] = "core"

    for link in needs_schema.iter_link_fields():
        properties[link.name] = {
            "type": "array",
            "items": {"type": "string"},
            "description": link.description,
            "field_type": "links",
            "default": [
                li.to_link_string()
                # in the order the export writes a link list
                for li in sorted(set(_link_default(link)), key=_link_natural_sort_key)
            ],
        }
        if link.derived:
            properties[link.name]["readOnly"] = True
        properties[link.name + "_back"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Backlink field",
            "field_type": "backlinks",
            "default": [],
        }

    for name in exclude_properties:
        properties.pop(name, None)

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
    }


def _link_default(link: LinkSchema, /) -> list[NeedLink]:
    """The links the ``needs_schema`` gives as a link type's ``default``: the links of a
    need type without a rule, for a link type derived by type alone (its literal
    default); the literal default, for a link type that is not derived; else none -- a
    derived link type is computed, and a default computed by a dynamic function or a
    variant has no value before a need is in hand. A need type's own default is its
    type's, not the link type's, and is not given."""
    if link.derive is None and link.derive_by_type is not None:
        return link.off_type_value()
    if not link.derived and isinstance(link.default, LinksLiteralValue):
        return list(link.default.value)
    return []


def _field_property(field: FieldSchema, field_type: str, /) -> dict[str, Any]:
    """The ``needs_schema`` property of a field, from its global declaration: its type
    (with ``null`` where it is nullable), item type and default; its other constraints
    (an ``enum``, a ``pattern``) are not written."""
    prop: dict[str, Any] = {
        "type": [field.type, "null"] if field.nullable else field.type,
        "description": field.description,
        "field_type": field_type,
    }
    if field.item_type is not None:
        prop["items"] = {"type": field.item_type}
    if isinstance(field.default, FieldLiteralValue):
        prop["default"] = field.default.value
    elif field.nullable:
        prop["default"] = None
    if field.derived:
        # derived: an importer takes the value as data, and does not compute it
        prop["readOnly"] = True
    return prop


def _is_json_default(value: Any, default: Any, /) -> bool:
    """Whether *value* is *default* as a JSON value: equal, and of the same JSON type
    (``bool`` is not ``int``, ``int`` is not ``float``: ``1.0`` is not ``1``), through
    lists and objects."""
    if value != default:
        return False
    if isinstance(value, bool | int | float):
        return type(value) is type(default)
    if isinstance(value, list | tuple):
        return all(map(_is_json_default, value, default))
    if isinstance(value, Mapping):
        return all(_is_json_default(item, default[key]) for key, item in value.items())
    return True


class NeedsList:
    def __init__(
        self,
        env: BuildEnvironment,
        outdir: str | os.PathLike[str],
        confdir: str | os.PathLike[str],
        add_schema: bool = True,
    ) -> None:
        self.config = env.config
        self.needs_config = NeedsSphinxConfig(self.config)
        self.outdir = outdir
        self.confdir = confdir
        self.current_version = self.config.version
        self.project = self.config.project
        self.needs_list: NeedsJsonType = {
            "project": self.project,
            "current_version": self.current_version,
            "versions": {},
        }
        if not self.needs_config.reproducible_json:
            self.needs_list["created"] = ""
        self.log = log

        self._exclude_need_keys = set(self.needs_config.json_exclude_fields)

        schema = SphinxNeedsData(env).get_schema()
        self._schema = (
            generate_needs_schema(schema, exclude_properties=self._exclude_need_keys)
            if add_schema
            else None
        )
        self._need_defaults = (
            {
                name: value["default"]
                for name, value in self._schema["properties"].items()
                if "default" in value
            }
            if self._schema
            else {}
        )

    def update_or_add_version(self, version: str) -> None:
        from sphinx_needs import __version__

        if version not in self.needs_list["versions"]:
            self.needs_list["versions"][version] = {
                "needs_amount": 0,
                "needs": {},
                "creator": {
                    "program": "sphinx_needs",
                    "version": __version__,
                },
            }
            if self._schema:
                self.needs_list["versions"][version]["needs_schema"] = self._schema
            if self.needs_config.json_remove_defaults:
                self.needs_list["versions"][version]["needs_defaults_removed"] = True
            if not self.needs_config.reproducible_json:
                self.needs_list["versions"][version]["created"] = ""

        if "needs" not in self.needs_list["versions"][version]:
            self.needs_list["versions"][version]["needs"] = {}

        if not self.needs_config.reproducible_json:
            self.needs_list["versions"][version]["created"] = datetime.now().isoformat()

    def add_need(self, version: str, need_info: NeedItem) -> None:
        self.update_or_add_version(version)
        writable_needs = {
            key: value
            for key, value in need_info.items()
            if key not in self._exclude_need_keys
        }
        if self.needs_config.json_include_link_conditions:
            # Overwrite link fields with serializations that include conditions
            for key, links in need_info.iter_links_items(as_str=False):
                if key not in self._exclude_need_keys:
                    writable_needs[key] = [li.to_link_string() for li in links]
        if self.needs_config.json_remove_defaults:
            writable_needs = {
                key: value
                for key, value in writable_needs.items()
                if not (
                    key in self._need_defaults
                    and _is_json_default(value, self._need_defaults[key])
                )
            }
        # `needs` is optional in a version, but `update_or_add_version` above has set it
        self.needs_list["versions"][version]["needs"][need_info["id"]] = writable_needs
        self.needs_list["versions"][version]["needs_amount"] = len(
            self.needs_list["versions"][version]["needs"]
        )

    def wipe_version(self, version: str) -> None:
        if version in self.needs_list["versions"]:
            del self.needs_list["versions"][version]

    def _finalise(self) -> None:
        self.update_or_add_version(self.current_version)
        # We need to rewrite some data, because this kind of data gets overwritten during needs.json import
        if not self.needs_config.reproducible_json:
            self.needs_list["created"] = datetime.now().isoformat()
        else:
            self.needs_list.pop("created", None)
        self.needs_list["current_version"] = self.current_version
        self.needs_list["project"] = self.project

    def write_json(self, needs_file: str = "needs.json", needs_path: str = "") -> None:
        self._finalise()
        needs_dir = needs_path if needs_path else self.outdir
        with open(os.path.join(needs_dir, needs_file), "w") as f:
            json.dump(self.needs_list, f, sort_keys=True)

    def dump_json(self) -> str:
        self._finalise()
        return json.dumps(self.needs_list, sort_keys=True)

    def load_json(self, file: str) -> None:
        if not os.path.isabs(file):
            file = os.path.join(self.confdir, file)

        if not os.path.exists(file):
            log_warning(
                self.log, f"Could not load needs json file {file}", "json_load", None
            )
        else:
            errors = check_needs_file(file)
            # We only care for schema errors here, all other possible errors
            # are not important for need-imports.
            if errors.schema:
                self.log.info(f"Schema validation errors detected in file {file}:")
                for error in errors.schema:
                    self.log.info(
                        f"  {error.message} -> {'.'.join(str(p) for p in error.instance_path)}"
                    )

            with open(file) as needs_file:
                try:
                    needs_list = json.load(needs_file)
                except json.JSONDecodeError:
                    log_warning(
                        self.log,
                        f"Could not decode json file {file}",
                        "json_load",
                        None,
                    )
                else:
                    # JSON from disk is `Any`: it is taken as a `NeedsJsonType` unchecked,
                    # since the schema errors above are only logged
                    self.needs_list = needs_list

            self.log.debug(f"needs.json file loaded: {file}")


class Errors:
    def __init__(self, schema_errors: list[ValidationError]):
        self.schema = schema_errors


def check_needs_file(path: str) -> Errors:
    """
    Checks a given json-file, if it passes our needs.json structure tests.

    Current checks:
    * Schema validation

    :param path: File path to a needs.json file
    :return: Dict, with error reports
    """
    with open(path) as needs_file:
        try:
            data = json.load(needs_file)
        except json.JSONDecodeError as e:
            raise SphinxNeedsFileException(
                f'Problems loading json file "{path}". '
                f"Maybe it is empty or has an invalid json format. Original exception: {e}"
            )
    return check_needs_data(data)


@lru_cache
def _load_schema() -> dict[str, Any]:
    schema_path = os.path.join(os.path.dirname(__file__), "needsfile.json")
    with open(schema_path) as schema_file:
        return json.load(schema_file)


def check_needs_data(data: Any) -> Errors:
    """
    Checks a given json-file, if it passes our needs.json structure tests.

    Current checks:
    * Schema validation

    :param data: Loaded needs.json file
    :return: Dict, with error reports
    """
    needs_schema = _load_schema()

    validator = Draft7Validator(needs_schema)
    schema_errors = list(validator.iter_errors(data))

    # In future there may be additional types of validations.
    # So lets already use a class for all errors
    return Errors(schema_errors)


if "main" in __name__:
    """
    Allows a simple call via CLI::

        python needsfile.py docs/needs/needs.json
    """
    try:
        needs_file = sys.argv[1]
    except IndexError:
        needs_file = "needs.json"
    check_needs_file(needs_file)


class SphinxNeedsFileException(BaseException):
    """Exception for any file handling problems inside Sphinx-Needs"""
