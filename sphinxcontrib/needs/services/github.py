import requests
import sphinx
from pkg_resources import parse_version

from m2r import convert

sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging

    logging.basicConfig()  # Only need to do this once

from sphinxcontrib.needs.services.base import BaseService


class GithubService(BaseService):
    options = ['query']

    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config

        super(GithubService, self).__init__()

    def _send(self, query):
        params = {
            'q': query
        }
        resp = requests.get('https://api.github.com/search/issues', params=params)
        return resp.json()

    def request(self, options=None):
        if options is None:
            options = {}
        self.log.debug(f'Requesting data for service {self.name}')

        if 'query' not in options:
            raise NeedGithubServiceException('"query" missing as option for github service.')
        else:
            query = options['query']

        response = self._send(query)
        # data = [
        #     {
        #         'title': 'test1',
        #         'content': 'test1 content',
        #         'id': 'GIT_001',
        #         'author': 'MEEEEE'
        #     },
        #     {
        #         'title': 'test2',
        #         'content': 'test2 content',
        #         'id': 'GIT_002',
        #         'unknown': 'BLUBB',
        #         'unknown2': 'BLUBB2'
        #     },
        # ]
        data = []
        for item in response['items']:
            data.append(
                {
                    'id': f'GITHUB_{item["number"]}',
                    'title': item["title"],
                    # 'content': convert(item["body"]),
                    'content': item["body"],
                    'status': item["state"],
                    'tags': ".".join([x['name'] for x in item["labels"]]),
                    'author': item["user"]['login'],
                    }
            )
        return data


class NeedGithubServiceException(BaseException):
    pass
