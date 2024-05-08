from __future__ import annotations

import json
import os
import re
from typing import Sequence
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import directives
from requests_file import FileAdapter
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need
from sphinx_needs.config import NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.needsfile import check_needs_file
from sphinx_needs.utils import add_doc, logger


class Needimport(nodes.General, nodes.Element):
    pass


class NeedimportDirective(SphinxDirective):
    has_content = False

    required_arguments = 1
    optional_arguments = 0

    option_spec = {
        "version": directives.unchanged_required,
        "hide": directives.flag,
        "collapse": directives.unchanged_required,
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
        # needs_list = {}
        version = self.options.get("version")
        filter_string = self.options.get("filter")
        id_prefix = self.options.get("id_prefix", "")

        tags = self.options.get("tags", [])
        if len(tags) > 0:
            tags = [tag.strip() for tag in re.split("[;,]", tags)]

        need_import_path = self.arguments[0]

        # check if given arguemnt is downloadable needs.json path
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
                        logger.warning(
                            "Deprecation warning: Relative path must be relative to the current document in future, "
                            "not to the conf.py location. Use a starting '/', like '/needs.json', to make the path "
                            "relative to conf.py. [needs]",
                            type="needs",
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

            errors = check_needs_file(correct_need_import_path)
            if errors.schema:
                logger.info(
                    f"Schema validation errors detected in file {correct_need_import_path}:"
                )
                for error in errors.schema:
                    logger.info(f'  {error.message} -> {".".join(error.path)}')

            try:
                with open(correct_need_import_path) as needs_file:
                    needs_import_list = json.load(needs_file)
            except json.JSONDecodeError as e:
                # TODO: Add exception handling
                raise e

        if version is None:
            try:
                version = needs_import_list["current_version"]
                if not isinstance(version, str):
                    raise KeyError
            except KeyError:
                raise CorruptedNeedsFile(
                    f"Key 'current_version' missing or corrupted in {correct_need_import_path}"
                )
        if version not in needs_import_list["versions"].keys():
            raise VersionNotFound(
                f"Version {version} not found in needs import file {correct_need_import_path}"
            )

        needs_config = NeedsSphinxConfig(self.config)
        # TODO this is not exactly NeedsInfoType, because the export removes/adds some keys
        needs_list: dict[str, NeedsInfoType] = needs_import_list["versions"][version][
            "needs"
        ]

        # Filter imported needs
        needs_list_filtered = {}
        for key, need in needs_list.items():
            if filter_string is None:
                needs_list_filtered[key] = need
            else:
                filter_context = need.copy()

                # Support both ways of addressing the description, as "description" is used in json file, but
                # "content" is the sphinx internal name for this kind of information
                filter_context["content"] = need["description"]  # type: ignore[typeddict-item]
                try:
                    if filter_single_need(filter_context, needs_config, filter_string):
                        needs_list_filtered[key] = need
                except Exception as e:
                    logger.warning(
                        f"needimport: Filter {filter_string} not valid. Error: {e}. {self.docname}{self.lineno} [needs]",
                        type="needs",
                        location=(self.env.docname, self.lineno),
                    )

        needs_list = needs_list_filtered

        # If we need to set an id prefix, we also need to manipulate all used ids in the imported data.
        extra_links = needs_config.extra_links
        if id_prefix:
            for need in needs_list.values():
                for id in needs_list:
                    # Manipulate links in all link types
                    for extra_link in extra_links:
                        if (
                            extra_link["option"] in need
                            and id in need[extra_link["option"]]  # type: ignore[literal-required]
                        ):
                            for n, link in enumerate(need[extra_link["option"]]):  # type: ignore[literal-required]
                                if id == link:
                                    need[extra_link["option"]][n] = "".join(  # type: ignore[literal-required]
                                        [id_prefix, id]
                                    )
                    # Manipulate descriptions
                    # ToDo: Use regex for better matches.
                    need["description"] = need["description"].replace(  # type: ignore[typeddict-item]
                        id, "".join([id_prefix, id])
                    )

        # tags update
        for need in needs_list.values():
            need["tags"] = need["tags"] + tags

        known_options = (
            "title",
            "status",
            "content",
            "id",
            "tags",
            "hide",
            "template",
            "pre_template",
            "post_template",
            "collapse",
            "style",
            "layout",
            "need_type",
            "constraints",
            *[x["option"] for x in extra_links],
            *NEEDS_CONFIG.extra_options,
        )
        need_nodes = []
        for need in needs_list.values():
            # Set some values based on given option or value from imported need.
            need["template"] = self.options.get("template", need.get("template"))
            need["pre_template"] = self.options.get(
                "pre_template", need.get("pre_template")
            )
            need["post_template"] = self.options.get(
                "post_template", need.get("post_template")
            )
            need["layout"] = self.options.get("layout", need.get("layout"))
            need["style"] = self.options.get("style", need.get("style"))

            if "hide" in self.options:
                need["hide"] = True
            else:
                need["hide"] = need.get("hide", False)
            need["collapse"] = self.options.get("collapse", need.get("collapse"))

            # The key needs to be different for add_need() api call.
            need["need_type"] = need["type"]  # type: ignore[typeddict-unknown-key]

            # Replace id, to get unique ids
            need["id"] = id_prefix + need["id"]

            need["content"] = need["description"]  # type: ignore[typeddict-item]

            # Remove unknown options, as they may be defined in source system, but not in this sphinx project
            for option in list(need):
                if option not in known_options:
                    del need[option]  # type: ignore

            need["docname"] = self.docname
            need["lineno"] = self.lineno

            nodes = add_need(self.env.app, self.state, **need)  # type: ignore[call-arg]
            need_nodes.extend(nodes)

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
