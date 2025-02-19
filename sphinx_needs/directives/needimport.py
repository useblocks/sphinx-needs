from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import directives
from requests_file import FileAdapter
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, add_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, NeedsInfoType
from sphinx_needs.debug import measure_time
from sphinx_needs.defaults import string_to_boolean
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.logging import log_warning
from sphinx_needs.needsfile import SphinxNeedsFileException, check_needs_data
from sphinx_needs.utils import add_doc, import_prefix_link_edit, logger


class Needimport(nodes.General, nodes.Element):
    pass


class NeedimportDirective(SphinxDirective):
    has_content = False

    required_arguments = 1
    optional_arguments = 0

    option_spec = {
        "version": directives.unchanged_required,
        "hide": directives.flag,
        "collapse": string_to_boolean,
        "ids": directives.unchanged_required,
        "filter": directives.unchanged_required,
        "id_prefix": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "style": directives.unchanged_required,
        "layout": directives.unchanged_required,
        "template": directives.unchanged_required,
        "pre_template": directives.unchanged_required,
        "post_template": directives.unchanged_required,
    }

    final_argument_whitespace = True

    @measure_time("needimport")
    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.config)

        version = self.options.get("version")
        filter_string = self.options.get("filter")
        id_prefix = self.options.get("id_prefix", "")

        need_import_path = needs_config.import_keys.get(
            self.arguments[0], self.arguments[0]
        )

        # check if given argument is downloadable needs.json path
        url = urlparse(need_import_path)
        if url.scheme and url.netloc:
            # download needs.json
            logger.info(f"Downloading needs.json from url {need_import_path}")
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(need_import_path)
                needs_import_list = (
                    response.json()
                )  # The downloaded file MUST be json. Everything else we do not handle!
            except Exception as e:
                raise NeedimportException(
                    f"Getting {need_import_path} didn't work. Reason: {e}."
                )
        else:
            logger.info(f"Importing needs from {need_import_path}")

            if not os.path.isabs(need_import_path):
                # Relative path should start from current rst file directory
                curr_dir = os.path.dirname(self.docname)
                new_need_import_path = os.path.join(
                    self.env.app.srcdir, curr_dir, need_import_path
                )

                correct_need_import_path = new_need_import_path
                if not os.path.exists(new_need_import_path):
                    # Check the old way that calculates relative path starting from conf.py directory
                    old_need_import_path = os.path.join(
                        self.env.app.srcdir, need_import_path
                    )
                    if os.path.exists(old_need_import_path):
                        correct_need_import_path = old_need_import_path
                        log_warning(
                            logger,
                            "Deprecation warning: Relative path must be relative to the current document in future, "
                            "not to the conf.py location. Use a starting '/', like '/needs.json', to make the path "
                            "relative to conf.py.",
                            "deprecated",
                            location=(self.env.docname, self.lineno),
                        )
            else:
                # Absolute path starts with /, based on the source directory. The / need to be striped
                correct_need_import_path = os.path.join(
                    self.env.app.srcdir, need_import_path[1:]
                )

            if not os.path.exists(correct_need_import_path):
                raise ReferenceError(
                    f"Could not load needs import file {correct_need_import_path}"
                )

            try:
                with open(correct_need_import_path) as needs_file:
                    needs_import_list = json.load(needs_file)
            except (OSError, json.JSONDecodeError) as e:
                # TODO: Add exception handling
                raise SphinxNeedsFileException(correct_need_import_path) from e

            errors = check_needs_data(needs_import_list)
            if errors.schema:
                logger.info(
                    f"Schema validation errors detected in file {correct_need_import_path}:"
                )
                for error in errors.schema:
                    logger.info(f"  {error.message} -> {'.'.join(error.path)}")

        if version is None:
            try:
                version = needs_import_list["current_version"]
                if not isinstance(version, str):
                    raise KeyError
            except KeyError:
                raise CorruptedNeedsFile(
                    f"Key 'current_version' missing or corrupted in {correct_need_import_path}"
                )
        if version not in needs_import_list["versions"]:
            raise VersionNotFound(
                f"Version {version} not found in needs import file {correct_need_import_path}"
            )

        data = needs_import_list["versions"][version]

        if ids := self.options.get("ids"):
            id_list = [i.strip() for i in ids.split(",") if i.strip()]
            data["needs"] = {
                key: data["needs"][key] for key in id_list if key in data["needs"]
            }

        # TODO this is not exactly NeedsInfoType, because the export removes/adds some keys
        needs_list: dict[str, NeedsInfoType] = data["needs"]
        if schema := data.get("needs_schema"):
            # Set defaults from schema
            defaults = {
                name: value["default"]
                for name, value in schema["properties"].items()
                if "default" in value
            }
            needs_list = {
                key: {**defaults, **value} for key, value in needs_list.items()
            }

        # Filter imported needs
        needs_list_filtered = {}
        for key, need in needs_list.items():
            if filter_string is None:
                needs_list_filtered[key] = need
            else:
                filter_context = need.copy()

                if "description" in need and not need.get("content"):
                    # legacy versions of sphinx-needs changed "description" to "content" when outputting to json
                    filter_context["content"] = need["description"]  # type: ignore[typeddict-item]
                try:
                    if filter_single_need(filter_context, needs_config, filter_string):
                        needs_list_filtered[key] = need
                except Exception as e:
                    log_warning(
                        logger,
                        f"needimport: Filter {filter_string} not valid. Error: {e}. {self.docname}{self.lineno}",
                        "needimport",
                        location=(self.env.docname, self.lineno),
                    )

        needs_list = needs_list_filtered

        # tags update
        if tags := [
            tag.strip()
            for tag in re.split("[;,]", self.options.get("tags", ""))
            if tag.strip()
        ]:
            for need in needs_list.values():
                need["tags"] = need["tags"] + tags

        import_prefix_link_edit(needs_list, id_prefix, needs_config.extra_links)

        # all known need fields in the project
        known_keys = {
            "full_title",  # legacy
            *NeedsCoreFields,
            *(x["option"] for x in needs_config.extra_links),
            *(x["option"] + "_back" for x in needs_config.extra_links),
            *needs_config.extra_options,
        }
        # all keys that should not be imported from external needs
        omitted_keys = {
            "full_title",  # legacy
            *(k for k, v in NeedsCoreFields.items() if v.get("exclude_import")),
            *(x["option"] + "_back" for x in needs_config.extra_links),
        }

        # collect keys for warning logs, so that we only log one warning per key
        unknown_keys: set[str] = set()
        non_string_extra_keys: set[str] = set()

        # directive options that can be override need fields
        override_options = (
            "collapse",
            "style",
            "layout",
            "template",
            "pre_template",
            "post_template",
        )

        need_nodes = []
        for need_params in needs_list.values():
            if "description" in need_params and not need_params.get("content"):
                # legacy versions of sphinx-needs changed "description" to "content" when outputting to json
                need_params["content"] = need_params["description"]  # type: ignore[typeddict-item]
                del need_params["description"]  # type: ignore[typeddict-item]

            # Remove unknown options, as they may be defined in source system, but not in this sphinx project
            for option in list(need_params):
                if option not in known_keys:
                    unknown_keys.add(option)
                    del need_params[option]  # type: ignore[misc]
                elif option in omitted_keys:
                    del need_params[option]  # type: ignore[misc]
                if option in needs_config.extra_options and not isinstance(
                    need_params[option],  # type: ignore[literal-required]
                    str,
                ):
                    non_string_extra_keys.add(option)

            for override_option in override_options:
                if override_option in self.options:
                    need_params[override_option] = self.options[override_option]  # type: ignore[literal-required]
            if "hide" in self.options:
                need_params["hide"] = True

            # These keys need to be different for add_need() api call.
            need_params["need_type"] = need_params.pop("type", "")  # type: ignore[misc,typeddict-unknown-key]

            # Replace id, to get unique ids
            need_id = need_params["id"] = id_prefix + need_params["id"]

            # override location
            need_params["docname"] = self.docname
            need_params["lineno"] = self.lineno

            try:
                nodes = add_need(self.env.app, self.state, **need_params)  # type: ignore[call-arg]
            except InvalidNeedException as err:
                log_warning(
                    logger,
                    f"Need {need_id!r} could not be imported: {err.message}",
                    "import_need",
                    location=self.get_location(),
                )
            else:
                need_nodes.extend(nodes)

        if unknown_keys:
            log_warning(
                logger,
                f"Unknown keys in import need source: {sorted(unknown_keys)!r}",
                "unknown_import_keys",
                location=self.get_location(),
            )
        if non_string_extra_keys:
            log_warning(
                logger,
                f"Non-string values in extra options of import need source: {sorted(non_string_extra_keys)!r}",
                "mistyped_import_values",
                location=self.get_location(),
            )

        add_doc(self.env, self.env.docname)

        return need_nodes

    @property
    def docname(self) -> str:
        return self.env.docname


class VersionNotFound(BaseException):
    pass


class CorruptedNeedsFile(BaseException):
    pass


class NeedimportException(BaseException):
    pass
