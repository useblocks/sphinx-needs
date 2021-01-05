import sphinx
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

    logging.basicConfig()


class BaseService:

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(__name__)

    def request(self, *args, **kwargs):
        raise NotImplementedError('Must be implemented by the service!')
