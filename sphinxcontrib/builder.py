from sphinxcontrib.utils import NeedsList
from sphinx.builders.text import TextBuilder
from sphinx.util import logging
# import logging


class NeedsBuilder(TextBuilder):
    name = 'needs'
    format = 'json'
    file_suffix = '.txt'
    links_suffix = None

    def init(self):
        pass

    def write_doc(self, docname, doctree):
        pass

    def finish(self):
        log = logging.getLogger(__name__)
        needs = self.env.need_all_needs
        config = self.env.config
        version = config.version
        needs_list = NeedsList(config)

        needs_list.load_json()

        for key, need in needs.items():
            needs_list.add_need(version, need["title"], need["id"], need["type"], need["type_name"],
                                need["content"], need["status"], need["tags"], need["links"])
        try:
            needs_list.write_json()
        except Exception as e:
            log.error("Error during writing json file: {0}".format(e))
        else:
            log.info("Needs successfully exported")


