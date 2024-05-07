"""
Cares about the correct handling with ``needs.json`` files.

Creates, checks and imports ``needs.json`` files.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

from jsonschema import Draft7Validator
from sphinx.config import Config

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFilterType, NeedsInfoType
from sphinx_needs.logging import get_logger

log = get_logger(__name__)


class NeedsList:
    JSON_KEY_EXCLUSIONS_NEEDS = {
        "links_back",
        "type_color",
        "hide",
        "type_prefix",
        "lineno",
        "lineno_content",
        "collapse",
        "type_style",
        "content",
        "content_node",
        # id_parent, id_parent are added on calls to `prepare_need_list`
        # but are only relevant to parts
        "id_parent",
        "id_complete",
    }

    JSON_KEY_EXCLUSIONS_FILTERS = {
        "links_back",
        "type_color",
        "hide_status",
        "hide",
        "type_prefix",
        "lineno",
        "lineno_content",
        "collapse",
        "type_style",
        "hide_tags",
        "content",
        "content_node",
    }

    def __init__(self, config: Config, outdir: str, confdir: str) -> None:
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
        # also exclude back links for link types dynamically set by the user
        back_link_keys = {x["option"] + "_back" for x in self.needs_config.extra_links}
        self._exclude_need_keys = self.JSON_KEY_EXCLUSIONS_NEEDS | back_link_keys
        self._exclude_filter_keys = self.JSON_KEY_EXCLUSIONS_FILTERS | back_link_keys

    def update_or_add_version(self, version: str) -> None:
        if version not in self.needs_list["versions"].keys():
            self.needs_list["versions"][version] = {
                "needs_amount": 0,
                "needs": {},
                "filters_amount": 0,
                "filters": {},
            }
            if not self.needs_config.reproducible_json:
                self.needs_list["versions"][version]["created"] = ""

        if "needs" not in self.needs_list["versions"][version].keys():
            self.needs_list["versions"][version]["needs"] = {}

        if not self.needs_config.reproducible_json:
            self.needs_list["versions"][version]["created"] = datetime.now().isoformat()

    def add_need(self, version: str, need_info: NeedsInfoType) -> None:
        self.update_or_add_version(version)
        writable_needs = {
            key: need_info[key]  # type: ignore[literal-required]
            for key in need_info
            if key not in self._exclude_need_keys
        }
        writable_needs["description"] = need_info["content"]
        self.needs_list["versions"][version]["needs"][need_info["id"]] = writable_needs
        self.needs_list["versions"][version]["needs_amount"] = len(
            self.needs_list["versions"][version]["needs"]
        )

    def add_filter(self, version: str, need_filter: NeedsFilterType) -> None:
        self.update_or_add_version(version)
        writable_filters = {
            key: need_filter[key]  # type: ignore[literal-required]
            for key in need_filter
            if key not in self._exclude_filter_keys
        }
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
            json.dump(self.needs_list, f, indent=4, sort_keys=True)

    def load_json(self, file: str) -> None:
        if not os.path.isabs(file):
            file = os.path.join(self.confdir, file)

        if not os.path.exists(file):
            self.log.warning(
                f"Could not load needs json file {file} [needs]", type="needs"
            )
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
                    self.log.warning(
                        f"Could not decode json file {file} [needs]", type="needs"
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
