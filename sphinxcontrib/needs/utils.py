from docutils import nodes
import json
from datetime import datetime
import os
import shutil
import sphinx
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

logger = logging.getLogger(__name__)


def row_col_maker(app, fromdocname, all_needs, need_info, need_key, make_ref=False, ref_lookup=False, prefix=''):
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
    row_col = nodes.entry()
    para_col = nodes.paragraph()

    if need_key in need_info and need_info[need_key] is not None:
        if not isinstance(need_info[need_key], (list, set)):
            data = [need_info[need_key]]
        else:
            data = need_info[need_key]

        for index, datum in enumerate(data):
            link_id = datum
            link_part = None

            link_list = []
            for link_type in app.env.config.needs_extra_links:
                link_list.append(link_type["option"])
                link_list.append(link_type["option"] + '_back')

            if need_key in link_list:
                if '.' in datum:
                    link_id = datum.split('.')[0]
                    link_part = datum.split('.')[1]

            datum_text = prefix + datum
            text_col = nodes.Text(datum_text, datum_text)
            if make_ref or ref_lookup:
                try:
                    ref_col = nodes.reference("", "")
                    if not ref_lookup:
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, need_info['docname'])
                        ref_col['refuri'] += "#" + datum
                    else:
                        temp_need = all_needs[link_id]
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, temp_need['docname'])
                        ref_col['refuri'] += "#" + temp_need["id"]
                        if link_part is not None:
                            ref_col['refuri'] += '.' + link_part

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


def status_sorter(a):
    """
    Helper function to sort string elements, which can be None, too.
    :param a: element, which gets sorted
    :return:
    """
    if not a["status"]:
        return ""
    return a["status"]


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != 'html':
        return
    src = source[0]
    rendered = app.builder.templates.render_string(
        src, app.config.html_context
    )
    source[0] = rendered


def process_dynamic_values(app, doctree, fromdocname):
    env = app.builder.env
    if not hasattr(env, 'needs_all_needs'):
        return

    # all_needs = env.needs_all_needs


class NeedsList:
    JSON_KEY_EXCLUSIONS_NEEDS = {'links_back', 'type_color', 'hide_status',
                                 'target_node', 'hide', 'type_prefix', 'lineno',
                                 'collapse', 'type_style', 'hide_tags', 'content'}

    JSON_KEY_EXCLUSIONS_FILTERS = {'links_back', 'type_color', 'hide_status',
                                   'target_node', 'hide', 'type_prefix', 'lineno',
                                   'collapse', 'type_style', 'hide_tags', 'content'}

    def __init__(self, config, outdir, confdir):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.outdir = outdir
        self.confdir = confdir
        self.current_version = config.version
        self.project = config.project
        self.needs_list = {
            "project": self.project,
            "current_version": self.current_version,
            "created": "",
            "versions": {}}

    def update_or_add_version(self, version):
        if version not in self.needs_list["versions"].keys():
            self.needs_list["versions"][version] = {"created": "",
                                                    "needs_amount": 0,
                                                    "needs": {},
                                                    "filters_amount": 0,
                                                    "filters": {}}

        if "needs" not in self.needs_list["versions"][version].keys():
            self.needs_list["versions"][version]["needs"] = {}

        self.needs_list["versions"][version]["created"] = datetime.now().isoformat()

    def add_need(self, version, need_info):
        self.update_or_add_version(version)
        writable_needs = {key: need_info[key] for key in need_info
                          if key not in self.JSON_KEY_EXCLUSIONS_NEEDS}
        writable_needs['description'] = need_info['content']
        self.needs_list["versions"][version]["needs"][need_info["id"]] = writable_needs
        self.needs_list["versions"][version]["needs_amount"] = len(self.needs_list["versions"][version]["needs"])

    def add_filter(self, version, need_filter):
        self.update_or_add_version(version)
        writable_filters = {key: need_filter[key] for key in need_filter if key not in self.JSON_KEY_EXCLUSIONS_FILTERS}
        self.needs_list["versions"][version]["filters"][need_filter["export_id"].upper()] = writable_filters
        self.needs_list["versions"][version]["filters_amount"] = len(self.needs_list["versions"][version]["filters"])

    def wipe_version(self, version):
        if version in self.needs_list["versions"].keys():
            del (self.needs_list["versions"][version])

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


def merge_two_dicts(x, y):
    """
    Merges 2 dictionary.
    Overrides values from x with values from y, if key is the same.

    Needed for Python < 3.5

    See: https://stackoverflow.com/a/26853961

    :param x:
    :param y:
    :return:
    """
    z = x.copy()  # start with x's keys and values
    z.update(y)  # modifies z with y's keys and values & returns None
    return z
