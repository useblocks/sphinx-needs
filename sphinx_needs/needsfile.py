"""
Cares about the correct handling with ``needs.json`` files.

Creates, checks and imports ``needs.json`` files.
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable

from jsonschema import Draft7Validator
from sphinx.config import Config

from sphinx_needs.config import NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, NeedsFilterType, NeedsInfoType
from sphinx_needs.logging import get_logger, log_warning

log = get_logger(__name__)


def generate_needs_schema(
    config: Config, exclude_properties: Iterable[str] = ()
) -> dict[str, Any]:
    """Generate a JSON schema for all fields in each need item.

    It is based on:
    * the core fields defined in NeedsCoreFields
    * the extra options defined dynamically
    * the global options defined dynamically
    * the extra links defined dynamically
    """
    properties: dict[str, Any] = {}

    for name, extra_params in NEEDS_CONFIG.extra_options.items():
        properties[name] = {
            "type": "string",
            "description": extra_params.description,
            "field_type": "extra",
            "default": "",
        }

    # TODO currently extra options can overlap with core fields,
    # in which case they are ignored,
    # (this is the case for `type` added by the github service)
    # hence this is why we add the core options after the extra options
    for name, core_params in NeedsCoreFields.items():
        properties[name] = deepcopy(core_params["schema"])
        properties[name]["description"] = f"{core_params['description']}"
        properties[name]["field_type"] = "core"

    needs_config = NeedsSphinxConfig(config)

    for link in needs_config.extra_links:
        properties[link["option"]] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Link field",
            "field_type": "links",
            "default": [],
        }
        properties[link["option"] + "_back"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Backlink field",
            "field_type": "backlinks",
            "default": [],
        }

    for name in needs_config.global_options:
        if name not in properties:
            properties[name] = {
                "type": "string",
                "description": "Added by needs_global_options configuration",
                "field_type": "global",
                "default": "",
            }

    for name in exclude_properties:
        if name in properties:
            del properties[name]

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
    }


class NeedsList:
    def __init__(
        self, config: Config, outdir: str, confdir: str, add_schema: bool = True
    ) -> None:
        self.config = config
        self.needs_config = NeedsSphinxConfig(config)
        self.outdir = outdir
        self.confdir = confdir
        self.current_version = config.version
        self.project = config.project
        self.needs_list = {
            "project": self.project,
            "current_version": self.current_version,
            "versions": {},
        }
        if not self.needs_config.reproducible_json:
            self.needs_list["created"] = ""
        self.log = log

        self._exclude_need_keys = set(self.needs_config.json_exclude_fields)

        self._schema = (
            generate_needs_schema(config, exclude_properties=self._exclude_need_keys)
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
        if version not in self.needs_list["versions"].keys():
            self.needs_list["versions"][version] = {
                "needs_amount": 0,
                "needs": {},
                "filters_amount": 0,
                "filters": {},
            }
            if self._schema:
                self.needs_list["versions"][version]["needs_schema"] = self._schema
            if self.needs_config.json_remove_defaults:
                self.needs_list["versions"][version]["needs_defaults_removed"] = True
            if not self.needs_config.reproducible_json:
                self.needs_list["versions"][version]["created"] = ""

        if "needs" not in self.needs_list["versions"][version].keys():
            self.needs_list["versions"][version]["needs"] = {}

        if not self.needs_config.reproducible_json:
            self.needs_list["versions"][version]["created"] = datetime.now().isoformat()

    def add_need(self, version: str, need_info: NeedsInfoType) -> None:
        self.update_or_add_version(version)
        writable_needs = {
            key: value
            for key, value in need_info.items()
            if key not in self._exclude_need_keys
        }
        if self.needs_config.json_remove_defaults:
            writable_needs = {
                key: value
                for key, value in writable_needs.items()
                if not (
                    key in self._need_defaults and value == self._need_defaults[key]
                )
            }
        writable_needs["description"] = need_info["content"]  # TODO why this?
        self.needs_list["versions"][version]["needs"][need_info["id"]] = writable_needs
        self.needs_list["versions"][version]["needs_amount"] = len(
            self.needs_list["versions"][version]["needs"]
        )

    def add_filter(self, version: str, need_filter: NeedsFilterType) -> None:
        self.update_or_add_version(version)
        writable_filters = {**need_filter}
        self.needs_list["versions"][version]["filters"][
            need_filter["export_id"].upper()
        ] = writable_filters
        self.needs_list["versions"][version]["filters_amount"] = len(
            self.needs_list["versions"][version]["filters"]
        )

    def wipe_version(self, version: str) -> None:
        if version in self.needs_list["versions"]:
            del self.needs_list["versions"][version]

    def write_json(self, needs_file: str = "needs.json", needs_path: str = "") -> None:
        # We need to rewrite some data, because this kind of data gets overwritten during needs.json import.
        if not self.needs_config.reproducible_json:
            self.needs_list["created"] = datetime.now().isoformat()
        else:
            self.needs_list.pop("created", None)
        self.needs_list["current_version"] = self.current_version
        self.needs_list["project"] = self.project
        if needs_path:
            needs_dir = needs_path
        else:
            needs_dir = self.outdir

        with open(os.path.join(needs_dir, needs_file), "w") as f:
            json.dump(self.needs_list, f, sort_keys=True)

    def load_json(self, file: str) -> None:
        if not os.path.isabs(file):
            file = os.path.join(self.confdir, file)

        if not os.path.exists(file):
            log_warning(self.log, f"Could not load needs json file {file}", None, None)
        else:
            errors = check_needs_file(file)
            # We only care for schema errors here, all other possible errors
            # are not important for need-imports.
            if errors.schema:
                self.log.info(f"Schema validation errors detected in file {file}:")
                for error in errors.schema:
                    self.log.info(f'  {error.message} -> {".".join(error.path)}')

            with open(file) as needs_file:
                try:
                    needs_list = json.load(needs_file)
                except json.JSONDecodeError:
                    log_warning(
                        self.log, f"Could not decode json file {file}", None, None
                    )
                else:
                    self.needs_list = needs_list

            self.log.debug(f"needs.json file loaded: {file}")


class Errors:
    def __init__(self, schema_errors: list[Any]):
        self.schema = schema_errors


def check_needs_file(path: str) -> Errors:
    """
    Checks a given json-file, if it passes our needs.json structure tests.

    Current checks:
    * Schema validation

    :param path: File path to a needs.json file
    :return: Dict, with error reports
    """
    schema_path = os.path.join(os.path.dirname(__file__), "needsfile.json")
    with open(schema_path) as schema_file:
        needs_schema = json.load(schema_file)

    with open(path) as needs_file:
        try:
            needs_data = json.load(needs_file)
        except json.JSONDecodeError as e:
            raise SphinxNeedsFileException(
                f'Problems loading json file "{path}". '
                f"Maybe it is empty or has an invalid json format. Original exception: {e}"
            )

    validator = Draft7Validator(needs_schema)
    schema_errors = list(validator.iter_errors(needs_data))

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
