import sphinx
from pkg_resources import parse_version

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

    logging.basicConfig()  # Only need to do this once

from sphinxcontrib.needs.services.base import BaseService


class GithubService(BaseService):
    options = ['query', 'sort']

    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config
        super(GithubService, self).__init__()

    def request(self, options=None):
        if options is None:
            options = {}
        self.log.debug(f'Requesting data for service {self.name}')

        data = [
            {
                'title': 'test1',
                'content': 'test1 content',
                'id': 'GIT_001',
                'author': 'MEEEEE'
            },
            {
                'title': 'test2',
                'content': 'test2 content',
                'id': 'GIT_002',
                'unknown': 'BLUBB',
                'unknown2': 'BLUBB2'
            },
        ]

        return data
