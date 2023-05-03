import json
import os
import re
from typing import Sequence, cast
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from requests_file import FileAdapter
from sphinx.environment import BuildEnvironment

from sphinx_needs.api import add_need
from sphinx_needs.config import NEEDS_CONFIG
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import filter_single_need
from sphinx_needs.needsfile import check_needs_file
from sphinx_needs.utils import add_doc, logger


class Needimport(nodes.General, nodes.Element):  # type: ignore
    pass


class NeedimportDirective(Directive):
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
                raise NeedimportException(f"Getting {need_import_path} didn't work. Reason: {e}.")
        else:
            logger.info(f"Importing needs from {need_import_path}")

            if not os.path.isabs(need_import_path):
                # Relative path should start from current rst file directory
                curr_dir = os.path.dirname(self.docname)
                new_need_import_path = os.path.join(self.env.app.srcdir, curr_dir, need_import_path)

                correct_need_import_path = new_need_import_path
                if not os.path.exists(new_need_import_path):
                    # Check the old way that calculates relative path starting from conf.py directory
                    old_need_import_path = os.path.join(self.env.app.srcdir, need_import_path)
                    if os.path.exists(old_need_import_path):
                        correct_need_import_path = old_need_import_path
                        logger.warning(
                            "Deprecation warning: Relative path must be relative to the current document in future, "
                            "not to the conf.py location. Use a starting '/', like '/needs.json', to make the path "
                            "relative to conf.py."
                        )
            else:
                # Absolute path starts with /, based on the source directory. The / need to be striped
                correct_need_import_path = os.path.join(self.env.app.srcdir, need_import_path[1:])

            if not os.path.exists(correct_need_import_path):
                raise ReferenceError(f"Could not load needs import file {correct_need_import_path}")

            errors = check_needs_file(correct_need_import_path)
            if errors.schema:
                logger.info(f"Schema validation errors detected in file {correct_need_import_path}:")
                for error in errors.schema:
                    logger.info(f'  {error.message} -> {".".join(error.path)}')

            with open(correct_need_import_path) as needs_file:
                needs_file_content = needs_file.read()
            try:
                needs_import_list = json.loads(needs_file_content)
            except json.JSONDecodeError as e:
                # ToDo: Add exception handling
                raise e

        if version is None:
            try:
                version = needs_import_list["current_version"]
                if not isinstance(version, str):
                    raise KeyError
            except KeyError:
                raise CorruptedNeedsFile(f"Key 'current_version' missing or corrupted in {correct_need_import_path}")
        if version not in needs_import_list["versions"].keys():
            raise VersionNotFound(f"Version {version} not found in needs import file {correct_need_import_path}")

        needs_list = needs_import_list["versions"][version]["needs"]

        # Filter imported needs
        needs_list_filtered = {}
        for key, need in needs_list.items():
            if filter_string is None:
                needs_list_filtered[key] = need
            else:
                # filter_context = {key: value for key, value in need.items()}
                filter_context = dict(need)

                # Support both ways of addressing the description, as "description" is used in json file, but
                # "content" is the sphinx internal name for this kind of information
                filter_context["content"] = need["description"]
                try:
                    if filter_single_need(self.env.app, filter_context, filter_string):
                        needs_list_filtered[key] = need
                except Exception as e:
                    logger.warning(
                        "needimport: Filter {} not valid. Error: {}. {}{}".format(
                            filter_string, e, self.docname, self.lineno
                        )
                    )

        needs_list = needs_list_filtered

        # If we need to set an id prefix, we also need to manipulate all used ids in the imported data.
        if id_prefix:
            needs_ids = needs_list.keys()

            for need in needs_list.values():
                for id in needs_ids:
                    # Manipulate links in all link types
                    for extra_link in self.env.config.needs_extra_links:
                        if extra_link["option"] in need and id in need[extra_link["option"]]:
                            for n, link in enumerate(need[extra_link["option"]]):
                                if id == link:
                                    need[extra_link["option"]][n] = "".join([id_prefix, id])
                    # Manipulate descriptions
                    # ToDo: Use regex for better matches.
                    need["description"] = need["description"].replace(id, "".join([id_prefix, id]))

        # tags update
        for need in needs_list.values():
            need["tags"] = need["tags"] + tags

        need_nodes = []
        for need in needs_list.values():
            # Set some values based on given option or value from imported need.
            need["template"] = self.options.get("template", getattr(need, "template", None))
            need["pre_template"] = self.options.get("pre_template", getattr(need, "pre_template", None))
            need["post_template"] = self.options.get("post_template", getattr(need, "post_template", None))
            need["layout"] = self.options.get("layout", getattr(need, "layout", None))
            need["style"] = self.options.get("style", getattr(need, "style", None))
            need["style"] = self.options.get("style", getattr(need, "style", None))
            if "hide" in self.options:
                need["hide"] = True
            else:
                need["hide"] = getattr(need, "hide", None)
            need["collapse"] = self.options.get("collapse", getattr(need, "collapse", None))

            # The key needs to be different for add_need() api call.
            need["need_type"] = need["type"]

            # Replace id, to get unique ids
            need["id"] = id_prefix + need["id"]

            need["content"] = need["description"]
            # Remove unknown options, as they may be defined in source system, but not in this sphinx project
            extra_link_keys = [x["option"] for x in self.env.config.needs_extra_links]
            extra_option_keys = list(NEEDS_CONFIG.get("extra_options").keys())
            default_options = [
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
            ]
            delete_options = []
            for option in need.keys():
                if option not in default_options + extra_link_keys + extra_option_keys:
                    delete_options.append(option)

            for option in delete_options:
                del need[option]

            need["docname"] = self.docname
            need["lineno"] = self.lineno

            nodes = add_need(self.env.app, self.state, **need)
            need_nodes.extend(nodes)

        add_doc(self.env, self.env.docname)

        return need_nodes

    @property
    def env(self) -> BuildEnvironment:
        return cast(BuildEnvironment, self.state.document.settings.env)

    @property
    def docname(self) -> str:
        return self.env.docname


class VersionNotFound(BaseException):
    pass


class CorruptedNeedsFile(BaseException):
    pass


class NeedimportException(BaseException):
    pass
