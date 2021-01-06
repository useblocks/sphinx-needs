import os
import requests
import textwrap

from urllib.parse import urlparse

from sphinxcontrib.needs.api import add_need_type
from sphinxcontrib.needs.api.exceptions import NeedsApiConfigException
from sphinxcontrib.needs.services.base import BaseService

# Additional needed options, which are not defined by default
EXTRA_DATA_OPTIONS = ['user', 'created_at', 'updated_at', 'closed_at', 'service']
EXTRA_LINK_OPTIONS = ['url']
EXTRA_IMAGE_OPTIONS = ['avatar']

# Additional options, which are used to configure the service and shall not be part of the later needs
CONFIG_OPTIONS = ['type', 'query', 'specific', 'max_amount', 'max_content_lines', 'id_prefix']

# All Github related data options
GITHUB_DATA = ['status', 'tags'] + EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS + EXTRA_IMAGE_OPTIONS

# Needed for layout. Example: "user","avatar",...
GITHUB_DATA_STR = '"' + '","'.join(EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS + EXTRA_IMAGE_OPTIONS) + '"'
CONFIG_DATA_STR = '"' + '","'.join(CONFIG_OPTIONS) + '"'

GITHUB_LAYOUT = {
    'grid': 'complex',
    'layout': {

        'head_left': [
            '<<meta_id()>>',
            '<<collapse_button("meta,footer", collapsed="icon:arrow-down-circle", '
            'visible="icon:arrow-right-circle", initial=True)>>'
        ],
        'head': ['**<<meta("title")>>** ('
                 + ", ".join(['<<link("{value}", text="{value}", is_dynamic=True)>>'.format(value=x)
                              for x in EXTRA_LINK_OPTIONS]) + ')'],
        'head_right': [
            '<<image("field:avatar", width="40px", align="middle")>>',
            '<<meta("user")>>'
        ],
        'meta_left': ['<<meta("{value}", prefix="{value}: ")>>'.format(value=x) for x in EXTRA_DATA_OPTIONS] +
                     [


                         '<<link("{value}", text="Link", prefix="{value}: ", is_dynamic=True)>>'.format(value=x)
                         for x in EXTRA_LINK_OPTIONS],
        'meta_right': [
            '<<meta("type_name", prefix="type: ")>>',
            '<<meta_all(no_links=True, exclude=["layout","style",{}, {}])>>'.format(GITHUB_DATA_STR, CONFIG_DATA_STR),
            '<<meta_links_all()>>'
        ],
        'footer_left': [
            'layout: <<meta("layout")>>',
        ],
        'footer': [
            'service:  <<meta("service")>>',
        ],
        'footer_right': [
            'style: <<meta("style")>>'
        ]
    }
}


class GithubService(BaseService):
    options = CONFIG_OPTIONS + EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS + EXTRA_IMAGE_OPTIONS

    def __init__(self, app, name, config, **kwargs):
        self.app = app
        self.name = name
        self.config = config

        self.url = self.config.get('url', 'https://api.github.com/')
        self.max_amount = self.config.get('max_amount', 5)
        self.max_content_lines = self.config.get('max_content_lines', -1)
        self.id_prefix = self.config.get('id_prefix', 'GITHUB_')
        self.layout = self.config.get('layout', 'github')
        self.download_avatars = self.config.get('download_avatars', True)
        self.download_folder = self.config.get('download_folder', 'github_images')

        self.username = self.config.get('username', None)
        self.token = self.config.get('token', None)

        if 'github' not in self.app.config.needs_layouts.keys():
            self.app.config.needs_layouts['github'] = GITHUB_LAYOUT

        self.gh_type_config = {
            'issue': {
                'url': 'search/issues',
                'query': 'is:issue',
                'need_type': 'issue'
            },
            'pr': {
                'url': 'search/issues',
                'query': 'is:pr',
                'need_type': 'pr'
            },
            'commit': {
                'url': 'search/commits',
                'query': '',
                'need_type': 'commit'
            },
        }

        try:
            add_need_type(self.app, 'issue', 'Issue', 'IS_', '#cccccc', 'card')
        except NeedsApiConfigException:
            pass  # Issue already exists, so we are fine

        try:
            add_need_type(self.app, 'pr', 'PullRequest', 'PR_', '#aaaaaa', 'card')
        except NeedsApiConfigException:
            pass  # PR already exists, so we are fine

        try:
            add_need_type(self.app, 'commit', 'Commit', 'C_', '#888888', 'card')
        except NeedsApiConfigException:
            pass  # Commit already exists, so we are fine

        if 'gh_type' in kwargs:
            self.gh_type = kwargs['gh_type']

        if self.gh_type not in self.gh_type_config.keys():
            raise KeyError('github type "{}" not supported. Use: {}'.format(
                self.gh_type, ", ".join(self.gh_type_config.keys())))

        # Set need_type to use by default
        self.need_type = self.config.get('need_type', self.gh_type_config[self.gh_type]['need_type'])

        super(GithubService, self).__init__()

    def _send(self, query, options, specific=False):
        if not specific:
            url = self.url + self.gh_type_config[self.gh_type]['url']
            query = '{} {}'.format(query, self.gh_type_config[self.gh_type]["query"])
            params = {
                'q': query,
                'per_page': options.get('max_amount', self.max_amount)
            }
        else:
            try:
                specific_elements = query.split('/')
                owner = specific_elements[0]
                repo = specific_elements[1]
                number = specific_elements[2]
                if self.gh_type == 'issue':
                    single_type = 'issues'
                elif self.gh_type == 'pr':
                    single_type = 'pulls'
                else:
                    single_type = 'commits'
                url = self.url + 'repos/{owner}/{repo}/{single_type}/{number}'.format(
                    owner=owner, repo=repo, single_type=single_type, number=number)
            except IndexError:
                raise NeedGithubServiceException('Single option ot valid, must follow "owner/repo/number"')

            params = {}

        self.log.info('Service {} requesting data for query: {}'.format(self.name, query))

        if self.username:
            auth = (self.username, self.token)
        else:
            auth = None
        resp = requests.get(url, params=params, auth=auth)

        if specific:
            return {'items': [resp.json()]}
        return resp.json()

    def request(self, options=None):
        if options is None:
            options = {}
        self.log.debug('Requesting data for service {}'.format(self.name))

        if 'query' not in options and 'specific' not in options:
            raise NeedGithubServiceException('"query" or "specific" missing as option for github service.')
        elif 'query' in options and 'specific' in options:
            raise NeedGithubServiceException('Only "query" or "specific" allowed for github service. Not both!')
        elif 'query' in options:
            query = options['query']
            specific = False
        else:
            query = options['specific']
            specific = True

        response = self._send(query, options, specific=specific)
        data = []

        if 'items' not in response.keys():
            if 'errors' in response.keys():
                raise NeedGithubServiceException('GitHub service query error: {}\n'
                                                 'Used query: {}'.format(response["errors"][0]["message"], query))
            else:
                raise NeedGithubServiceException('Github service: Unknown error. Status code: {}. '
                                                 'Content: {}'.format(response.status_code, response.text))
        for item in response['items']:
            # wraps content lines, if they are too long. Respects already existing newlines.
            content_lines = ['\n   '.join(textwrap.wrap(line, 60, break_long_words=True, replace_whitespace=False))
                             for line in item["body"].splitlines() if line.strip() != '']

            content = '\n\n   '.join(content_lines)
            # Reduce content length, if requested by config
            if self.max_content_lines > 0:
                max_lines = int(options.get('max_content_lines', self.max_content_lines))
                content_lines = content.splitlines()
                if len(content_lines) > max_lines:
                    content_lines = content_lines[0:max_lines]
                    content_lines.append('\n   [...]\n')  # Mark, if content got cut
                content = '\n'.join(content_lines)

            # Be sure the content gets not interpreted as rst or html code, so we put
            # everything in a safe code-block
            content = '.. code-block:: text\n\n   ' + content

            prefix = options.get('id_prefix', self.id_prefix)
            need_id = prefix + str(item["number"])
            given_tags = options.get('tags', False)
            github_tags = ",".join([x['name'] for x in item["labels"]])
            if given_tags:
                tags = str(given_tags) + ', ' + str(github_tags)
            else:
                tags = github_tags

            # Download and store avatar image
            avatar_url = item['user']['avatar_url']
            url_parsed = urlparse(avatar_url)
            filename = os.path.basename(url_parsed.path) + '.png'
            path = os.path.join(self.app.srcdir, self.download_folder)
            avatar_file_path = os.path.join(path, filename)

            # Placeholder avatar, if things go wrong or avatar download is deactivated
            default_avatar_file_path = os.path.join(os.path.dirname(__file__), '../images/avatar.png')
            if self.download_avatars:
                # Download only, if file not downloaded yet
                if not os.path.exists(avatar_file_path):
                    try:
                        os.mkdir(path)
                    except FileExistsError:
                        pass
                    if self.username and self.token:
                        auth = (self.username, self.token)
                    else:
                        auth = ()
                    response = requests.get(avatar_url, auth=auth, allow_redirects=False)
                    if response.status_code == 200:
                        with open(avatar_file_path, 'wb') as f:
                            f.write(response.content)
                    elif response.status_code == 302:
                        self.log.warning('GitHub service {} could not download avatar image '
                                         'from {}.\n'
                                         '    Status code: {}\n'
                                         '    Reason: Looks like the authentication provider tries to redirect you.'
                                         ' This is not supported and is a common problem, '
                                         'if you use GitHub Enterprise.'.format(self.name, avatar_url,
                                                                                response.status_code))
                        avatar_file_path = default_avatar_file_path
                    else:
                        self.log.warning('GitHub service {} could not download avatar image '
                                         'from {}.\n'
                                         '    Status code: {}'.format(self.name, avatar_url,
                                                                      response.status_code
                                                                      ))
                        avatar_file_path = default_avatar_file_path
            else:
                avatar_file_path = default_avatar_file_path

            element_data = {
                'service': self.name,
                'type': options.get('type', self.need_type),
                'layout': options.get('layout', self.layout),
                'id': need_id,
                'title': item["title"],
                'content': content,
                'status': item["state"],
                'tags': tags,
                'user': item["user"]['login'],
                'url': item['html_url'],
                # 'avatar': item['user']['avatar_url'],
                'avatar': avatar_file_path,
                'created_at': item['created_at'],
                'updated_at': item['updated_at'],
                'closed_at': item['closed_at']
            }

            # Add data from options, which was defined by user but is not set by this service
            for key, value in options.items():
                # Check if given option is not already handled and is not part of the service internal options
                if key not in element_data.keys() and key not in GITHUB_DATA:
                    element_data[key] = value

            data.append(element_data)

        return data


class NeedGithubServiceException(BaseException):
    pass
