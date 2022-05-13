"""
Cares about the correct handling with ``needs.json`` files.

Creates, checks and imports ``needs.json`` files.
"""
import json
import os
import sys
from datetime import datetime

from jsonschema import Draft7Validator

from sphinxcontrib.needs.logging import get_logger

log = get_logger(__name__)


class NeedsList:
    JSON_KEY_EXCLUSIONS_NEEDS = {
        "links_back",
        "type_color",
        "hide_status",
        "target_node",
        "hide",
        "type_prefix",
        "lineno",
        "collapse",
        "type_style",
        "hide_tags",
        "content",
        "content_node",
    }

    JSON_KEY_EXCLUSIONS_FILTERS = {
        "links_back",
        "type_color",
        "hide_status",
        "target_node",
        "hide",
        "type_prefix",
        "lineno",
        "collapse",
        "type_style",
        "hide_tags",
        "content",
        "content_node",
    }

    def __init__(self, config, outdir, confdir):
        self.config = config
        self.outdir = outdir
        self.confdir = confdir
        self.current_version = config.version
        self.project = config.project
        self.needs_list = {
            "project": self.project,
            "current_version": self.current_version,
            "created": "",
            "versions": {},
        }
        self.log = log

    def update_or_add_version(self, version):
        if version not in self.needs_list["versions"].keys():
            self.needs_list["versions"][version] = {
                "created": "",
                "needs_amount": 0,
                "needs": {},
                "filters_amount": 0,
                "filters": {},
            }

        if "needs" not in self.needs_list["versions"][version].keys():
            self.needs_list["versions"][version]["needs"] = {}

        self.needs_list["versions"][version]["created"] = datetime.now().isoformat()

    def add_need(self, version, need_info):
        self.update_or_add_version(version)
        writable_needs = {key: need_info[key] for key in need_info if key not in self.JSON_KEY_EXCLUSIONS_NEEDS}
        writable_needs["description"] = need_info["content"]
        self.needs_list["versions"][version]["needs"][need_info["id"]] = writable_needs
        self.needs_list["versions"][version]["needs_amount"] = len(self.needs_list["versions"][version]["needs"])

    def add_filter(self, version, need_filter):
        self.update_or_add_version(version)
        writable_filters = {key: need_filter[key] for key in need_filter if key not in self.JSON_KEY_EXCLUSIONS_FILTERS}
        self.needs_list["versions"][version]["filters"][need_filter["export_id"].upper()] = writable_filters
        self.needs_list["versions"][version]["filters_amount"] = len(self.needs_list["versions"][version]["filters"])

    def wipe_version(self, version):
        if version in self.needs_list["versions"]:
            del self.needs_list["versions"][version]

    def write_json(self, needs_file="needs.json"):
        # We need to rewrite some data, because this kind of data gets overwritten during needs.json import.
        self.needs_list["created"] = datetime.now().isoformat()
        self.needs_list["current_version"] = self.current_version
        self.needs_list["project"] = self.project

        needs_json = json.dumps(self.needs_list, indent=4, sort_keys=True)
        file = os.path.join(self.outdir, needs_file)

        with open(file, "w") as needs_file:
            needs_file.write(needs_json)

    def load_json(self, file):
        if not os.path.isabs(file):
            file = os.path.join(self.confdir, file)

        if not os.path.exists(file):
            self.log.warning(f"Could not load needs json file {file}")
        else:
            errors = check_needs_file(file)
            # We only care for schema errors here, all other possible errors
            # are not important for need-imports.
            if errors["schema"]:
                self.log.info(f"Schema validation errors detected in file {file}:")
                for error in errors["schema"]:
                    self.log.info(f'  {error.message} -> {".".join(error.path)}')

            with open(file) as needs_file:
                needs_file_content = needs_file.read()
            try:
                needs_list = json.loads(needs_file_content)
            except json.JSONDecodeError:
                self.log.warning(f"Could not decode json file {file}")
            else:
                self.needs_list = needs_list

            self.log.debug(f"needs.json file loaded: {file}")


def check_needs_file(path):
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
    # So lets already use a dict for all errors
    errors = {"schema": schema_errors}
    errors["has_errors"] = any([bool(errors) for errors in errors.values()])

    return errors


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
