import json
import os
import re

import six
from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinxcontrib.needs.api import add_need
from sphinxcontrib.needs.filter_common import filter_single_need
from sphinxcontrib.needs.utils import logger


class Needimport(nodes.General, nodes.Element):
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

    def run(self):
        needs_list = {}
        version = self.options.get("version", None)
        filter_string = self.options.get("filter", None)
        id_prefix = self.options.get("id_prefix", "")

        tags = self.options.get("tags", [])
        if len(tags) > 0:
            tags = [tag.strip() for tag in re.split(";|,", tags)]

        env = self.state.document.settings.env

        need_import_path = self.arguments[0]

        if not os.path.isabs(need_import_path):
            need_import_path = os.path.join(env.app.confdir, need_import_path)

        if not os.path.exists(need_import_path):
            raise ReferenceError("Could not load needs import file {0}".format(need_import_path))

        with open(need_import_path, "r") as needs_file:
            needs_file_content = needs_file.read()
        try:
            needs_import_list = json.loads(needs_file_content)
        except json.JSONDecodeError as e:
            # ToDo: Add exception handling
            raise e

        if version is None:
            try:
                version = needs_import_list["current_version"]
                if not isinstance(version, six.string_types):
                    raise KeyError
            except KeyError:
                raise CorruptedNeedsFile("Key 'current_version' missing or corrupted in {0}".format(need_import_path))
        if version not in needs_import_list["versions"].keys():
            raise VersionNotFound("Version {0} not found in needs import file {1}".format(version, need_import_path))

        needs_list = needs_import_list["versions"][version]["needs"]

        # Filter imported needs
        needs_list_filtered = {}
        for key, need in needs_list.items():
            if filter_string is None:
                needs_list_filtered[key] = need
            else:
                filter_context = {key: value for key, value in need.items()}

                # Support both ways of addressing the description, as "description" is used in json file, but
                # "content" is the sphinx internal name for this kind of information
                filter_context["content"] = need["description"]
                try:
                    if filter_single_need(filter_context, filter_string):
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

            for key, need in needs_list.items():
                for id in needs_ids:
                    # Manipulate links in all link types
                    for extra_link in env.config.needs_extra_links:
                        if extra_link["option"] in need.keys() and id in need[extra_link["option"]]:
                            for n, link in enumerate(need[extra_link["option"]]):
                                if id == link:
                                    need[extra_link["option"]][n] = "".join([id_prefix, id])
                    # Manipulate descriptions
                    # ToDo: Use regex for better matches.
                    need["description"] = need["description"].replace(id, "".join([id_prefix, id]))

        # tags update
        for key, need in needs_list.items():
            need["tags"] = need["tags"] + tags

        need_nodes = []
        for key, need in needs_list.items():
            # Set some values based on given option or value from imported need.
            need["template"] = self.options.get("template", getattr(need, "template", None))
            need["pre_template"] = self.options.get("pre_template", getattr(need, "pre_template", None))
            need["post_template"] = self.options.get("post_template", getattr(need, "post_template", None))
            need["layout"] = self.options.get("layout", getattr(need, "layout", None))
            need["style"] = self.options.get("style", getattr(need, "style", None))
            need["style"] = self.options.get("style", getattr(need, "style", None))
            if "hide" in self.options.keys():
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
            extra_link_keys = [x["option"] for x in env.config.needs_extra_links]
            extra_option_keys = list(env.config.needs_extra_options.keys())
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

            nodes = add_need(env.app, self.state, **need)
            need_nodes.extend(nodes)

        return need_nodes

    @property
    def docname(self):
        return self.state.document.settings.env.docname


class VersionNotFound(BaseException):
    pass


class CorruptedNeedsFile(BaseException):
    pass
