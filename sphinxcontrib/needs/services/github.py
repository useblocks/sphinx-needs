import requests
import sphinx
from pkg_resources import parse_version
import textwrap

from sphinxcontrib.needs.services.base import BaseService


class GithubService(BaseService):
    options = ['query']

    def __init__(self, app, name, config, **kwargs):
        self.app = app
        self.name = name
        self.config = config

        self.url = self.config.get('url', 'https://api.github.com/')
        self.max_amount = self.config.get('max_amount', 5)
        self.max_content_lines = self.config.get('max_content_lines', -1)

        self.type_config = {
            'issue': {
                'url': 'search/issues',
                'query': 'is:issue',
            },
            'pr': {
                'url': 'search/issues',
                'query': 'is:pr',
            },
            'commit': {
                'url': 'search/commits',
                'query': '',
            },
        }

        if 'type' in kwargs:
            self.type = kwargs['type']

        if self.type not in self.type_config.keys():
            raise KeyError(f'github type "{self.type}" not supported. Use: {", ".join(self.type_config.keys())}')

        super(GithubService, self).__init__()

    def _send(self, query):
        query = f'{query} {self.type_config[self.type]["query"]}'
        params = {
            'q': query,
            'per_page': self.max_amount
        }
        url = self.url + self.type_config[self.type]['url']

        self.log.info(f'Service {self.name} requesting data for query: {query}')
        resp = requests.get(url, params=params)
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
        data = []
        for item in response['items']:
            # wraps content lines, if they are too long. Respects already existing newlines.
            content_lines = ['\n   '.join(textwrap.wrap(line, 60, break_long_words=True, replace_whitespace=False))
                             for line in item["body"].splitlines() if line.strip() != '']

            # Reduce content length, if requested by config
            if self.max_content_lines > 0:
                content_lines = content_lines[0:self.max_content_lines]
            content = '\n\n   '.join(content_lines)

            # Be sure the content gets not interpreted as rst or html code, so we put
            # everything in a safe code-block
            content = '.. code-block:: text\n\n   ' + content

            data.append(
                {
                    'id': f'GITHUB_{item["number"]}',
                    'title': item["title"],
                    'content': content,
                    'status': item["state"],
                    'tags': ".".join([x['name'] for x in item["labels"]]),
                    'author': item["user"]['login'],
                }
            )
        return data


class NeedGithubServiceException(BaseException):
    pass
