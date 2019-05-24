from sphinx.builders import Builder
from sphinxcontrib.needs.utils import NeedsList
import sphinx
from pkg_resources import parse_version
sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging


class NeedsBuilder(Builder):
    name = 'needs'
    format = 'json'
    file_suffix = '.txt'
    links_suffix = None

    def write_doc(self, docname, doctree):
        pass

    def finish(self):
        log = logging.getLogger(__name__)
        needs = self.env.needs_all_needs
        filters = self.env.needs_all_filters
        config = self.env.config
        version = config.version
        needs_list = NeedsList(config, self.outdir, self.confdir)

        needs_list.load_json()

        # Clean needs_list from already stored needs of the current version.
        # This is needed as needs could have been removed from documentation and if this is the case,
        # removed needs would stay in needs_list, if list gets not cleaned.
        needs_list.wipe_version(version)

        for key, need in needs.items():
            needs_list.add_need(version, need)

        for key, need_filter in filters.items():
            if need_filter['export_id']:
                needs_list.add_filter(version, need_filter)

        try:
            needs_list.write_json()
        except Exception as e:
            log.error("Error during writing json file: {0}".format(e))
        else:
            log.info("Needs successfully exported")

    def get_outdated_docs(self):
        return ""

    def prepare_writing(self, docnames):
        pass

    def write_doc_serialized(self, docname, doctree):
        pass

    def cleanup(self):
        pass

    def get_target_uri(self, docname, typ=None):
        return ""
