from docutils import nodes

import sphinx

from pkg_resources import parse_version

sphinx_version = sphinx.__version__

if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
log = logging.getLogger(__name__)


class NeedInline(nodes.Inline, nodes.Element):
    pass


def process_need_inline(app, doctree, fromdocname):
    pass
