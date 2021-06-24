"""


"""

from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinxcontrib.needs.filter_common import process_filters


class Needextend(nodes.General, nodes.Element):
    pass


class NeedextendDirective(Directive):
    """
    Directive to modify existing needs
    """
    has_content = False
    required_arguments = 1
    optional_arguments = 0

    option_spec = {
    }

    def run(self):
        print("NEEDEXTRACT-OUTPUT")
        for key,value in self.options.items():
            print(f"{key} : {value}")
        return []


def process_needextend(app, doctree, fromdocname):
    """
    Perform all modifications on needs
    """
    env = app.builder.env

    for node in doctree.traverse(Needextend):
        pass
