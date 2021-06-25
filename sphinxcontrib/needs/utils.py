import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List

from docutils import nodes
from sphinx.application import Sphinx

from sphinxcontrib.needs.logging import get_logger

logger = get_logger(__name__)

NEEDS_FUNCTIONS = {}

# List of internal need option names. They should not be used by or presented to user.
INTERNALS = [
    "docname",
    "lineno",
    "target_node",
    "refid",
    "content",
    "pre_content",
    "post_content",
    "collapse",
    "parts",
    "id_parent",
    "id_complete",
    "title",
    "full_title",
    "is_part",
    "is_need",
    "type_prefix",
    "type_color",
    "type_style",
    "type",
    "type_name",
    "id",
    "hide",
    "hide_status",
    "hide_tags",
    "sections",
    "section_name",
    "content_node",
    # "parent_needs",
    "parent_need",
    # "child_needs",
    "is_external",
    "external_css",
    "is_modified",
    "modifications",
]


MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def row_col_maker(
    app: Sphinx, fromdocname, all_needs, need_info, need_key, make_ref=False, ref_lookup=False, prefix=""
):
    """
    Creates and returns a column.

    :param app: current sphinx app
    :param fromdocname: current document
    :param all_needs: Dictionary of all need objects
    :param need_info: need_info object, which stores all related need data
    :param need_key: The key to access the needed data from need_info
    :param make_ref: If true, creates a reference for the given data in need_key
    :param ref_lookup: If true, it uses the data to lookup for a related need and uses its data to create the reference
    :param prefix: string, which is used as prefix for the text output
    :return: column object (nodes.entry)
    """
    row_col = nodes.entry(classes=["needs_" + need_key])
    para_col = nodes.paragraph()

    if need_key in need_info and need_info[need_key] is not None:
        if isinstance(need_info[need_key], (list, set)):
            data = need_info[need_key]
        else:
            data = [need_info[need_key]]

        for index, datum in enumerate(data):
            link_id = datum
            link_part = None

            link_list = []
            for link_type in app.env.config.needs_extra_links:
                link_list.append(link_type["option"])
                link_list.append(link_type["option"] + "_back")

            if need_key in link_list:
                if "." in datum:
                    link_id = datum.split(".")[0]
                    link_part = datum.split(".")[1]

            datum_text = prefix + str(datum)
            text_col = nodes.Text(datum_text, datum_text)
            if make_ref or ref_lookup:
                try:
                    ref_col = nodes.reference("", "")
                    if make_ref:
                        if need_info["is_external"]:
                            # if need is external, just use the already calculated external_url
                            ref_col["refuri"] = need_info["external_url"]
                            ref_col["classes"].append(need_info["external_css"])
                            row_col["classes"].append(need_info["external_css"])
                        else:
                            ref_col["refuri"] = app.builder.get_relative_uri(fromdocname, need_info["docname"])
                            ref_col["refuri"] += "#" + datum
                    elif ref_lookup:
                        temp_need = all_needs[link_id]
                        if temp_need["is_external"]:
                            ref_col["refuri"] = temp_need["external_url"]
                            ref_col["classes"].append(temp_need["external_css"])
                            row_col["classes"].append(temp_need["external_css"])
                        else:
                            ref_col["refuri"] = app.builder.get_relative_uri(fromdocname, temp_need["docname"])
                            ref_col["refuri"] += "#" + temp_need["id"]
                            if link_part:
                                ref_col["refuri"] += "." + link_part

                except KeyError:
                    para_col += text_col
                else:
                    ref_col.append(text_col)
                    para_col += ref_col
            else:
                para_col += text_col

            if index + 1 < len(data):
                para_col += nodes.emphasis("; ", "; ")

    row_col += para_col

    return row_col


def rstjinja(app: Sphinx, docname: str, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != "html":
        return
    src = source[0]
    rendered = app.builder.templates.render_string(src, app.config.html_context)
    source[0] = rendered


def import_prefix_link_edit(needs: Dict[str, Any], id_prefix: str, needs_extra_links: List[Dict[str, Any]]):
    """
    Changes existing links to support given prefix.
    Only link-ids get touched, which are part of ``needs`` (so are linking them).
    Other links do not get the prefix, as there are treated as "external" links.

    :param needs: Dict of all needs
    :param id_prefix: Prefix as string
    :param needs_extra_links: config var of all supported extra links. Normally coming from env.config.needs_extra_links
    :return:
    """
    needs_ids = needs.keys()

    for need in needs.values():
        for id in needs_ids:
            # Manipulate links in all link types
            for extra_link in needs_extra_links:
                if extra_link["option"] in need.keys() and id in need[extra_link["option"]]:
                    for n, link in enumerate(need[extra_link["option"]]):
                        if id == link:
                            need[extra_link["option"]][n] = f"{id_prefix}{id}"
            # Manipulate descriptions
            # ToDo: Use regex for better matches.
            need["description"] = need["description"].replace(id, "".join([id_prefix, id]))


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
        self.log = get_logger(__name__)
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
        if version in self.needs_list["versions"].keys():
            del self.needs_list["versions"][version]

    def write_json(self, file=None):
        # We need to rewrite some data, because this kind of data gets overwritten during needs.json import.
        self.needs_list["created"] = datetime.now().isoformat()
        self.needs_list["current_version"] = self.current_version
        self.needs_list["project"] = self.project

        needs_json = json.dumps(self.needs_list, indent=4, sort_keys=True)
        file = os.path.join(self.outdir, "needs.json")

        # if file is None:
        #     file = getattr(self.config, "needs_file", "needs.json")
        with open(file, "w") as needs_file:
            needs_file.write(needs_json)

        doc_tree_folder = os.path.join(self.outdir, ".doctrees")
        if os.path.exists(doc_tree_folder):
            shutil.rmtree(doc_tree_folder)

    def load_json(self, file=None):
        if file is None:
            file = getattr(self.config, "needs_file", "needs.json")
        if not os.path.isabs(file):
            file = os.path.join(self.confdir, file)

        if not os.path.exists(file):
            self.log.warning("Could not load needs json file {0}".format(file))
        else:
            with open(file, "r") as needs_file:
                needs_file_content = needs_file.read()
            try:
                needs_list = json.loads(needs_file_content)
            except json.JSONDecodeError:
                self.log.warning("Could not decode json file {0}".format(file))
            else:
                self.needs_list = needs_list
