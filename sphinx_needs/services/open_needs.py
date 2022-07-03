import json
import os
import re
from random import choices

import requests
from jinja2 import Template
from sphinx.application import Sphinx

from sphinx_needs.utils import dict_get, jinja_parse

from .base import BaseService
from .config.open_needs import (
    CONFIG_OPTIONS,
    DEFAULT_CONTENT,
    EXTRA_DATA_OPTIONS,
    EXTRA_LINK_OPTIONS,
    MAPPINGS_REPLACES_DEFAULT,
)


class OpenNeedsService(BaseService):
    options = CONFIG_OPTIONS + EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS

    def __init__(self, app: Sphinx, name: str, config, **kwargs) -> None:

        self.app = app
        self.name = name
        self.config = config

        self.url = self.config.get("url", "http://127.0.0.1:9595")
        # if not self.url.endswith("/"):
        #     self.url = f"{self.url}/"
        self.url_postfix = self.config.get("url_postfix", "/api/needs/")
        self.max_content_lines = self.config.get("max_content_lines", -1)

        self.id_prefix = self.config.get("id_prefix", "OPEN_NEEDS_")
        self.query = self.config.get("query", "")
        self.content = self.config.get("content", DEFAULT_CONTENT)
        self.mappings = self.config.get("mappings", {})
        self.mapping_replaces = self.config.get("mappings_replaces", MAPPINGS_REPLACES_DEFAULT)

        self.extra_data = self.config.get("extra_data", {})
        self.params = self.config.get("params", "skip=0,limit=100")

        self.username = self.config.get("user", None)
        self.password = self.config.get("password", None)

        if len(self.config) != 0 and not self.app.config.open_needs_test_env:
            auth = dict(username=self.username, password=self.password)
            login_postfix = "/auth/jwt/login"
            login_resp = requests.post(self.url + login_postfix, data=auth)
            if login_resp.status_code != 200:
                raise OpenNeedsServiceException(
                    "ONS service error during request.\n"
                    "Status code: {}\n"
                    "Error: {}\n".format(login_resp.status_code, login_resp.text)
                )
            oauth_credentials = dict(**login_resp.json())
            self.token_type = oauth_credentials.get("token_type")
            self.access_token = oauth_credentials.get("access_token")

        self.open_needs_json_file = self.app.config.open_needs_json_file

        super().__init__(**kwargs)

    def _prepare_request(self, options):
        if options is None:
            options = {}
        url = options.get("url", self.url)
        url = url + self.url_postfix

        headers = {"Authorization": "{} {}".format(self.token_type, self.access_token)}
        params = [param.strip() for param in re.split(r";|,", options.get("params", self.params))]
        params = "&".join(params)

        url = "{}?{}".format(url, params)

        request = {"url": url, "headers": headers}
        return request

    def _send_request(self, request):
        """
        Sends the final request.

        ``request`` must be a dictionary, which contains data valid to the requests-lib.
        This request-data gets mostly defined by using ``prepare_request``.

        :param request: dict
        :return: request answer
        """

        # params = {
        #     'queryString': query
        # }

        result = requests.request(**request)
        if result.status_code >= 300:
            raise OpenNeedsServiceException(f"Problem accessing {result.url}.\nReason: {result.text}")

        return result

    def _extract_data(self, data, options):
        """
        Extract data of a list/dictionary, which was retrieved via send_request.

        :param data: list or dict
        :param options: dict of set directive options
        :return: list of need-data
        """

        need_data = []
        if options is None:
            options = {}
        # How to know if a referenced link is a need object in the data we are retrieving from the Open Needs Server
        id_selector = self.mappings.get("id")
        ids_of_needs_data = []  # list of all IDs of need objects being retrieved from the Open Needs Server
        needs_id_validator = self.app.config.needs_id_regex
        for item in data:
            if isinstance(id_selector, str):
                value = jinja_parse(item, id_selector)
            else:
                value = str(dict_get(item, id_selector))
            # Validate the value for a need ID or generate a valid ID for the need
            need_id = (
                value
                if re.search(needs_id_validator, value) is not None
                else self.id_prefix + "".join(map(choices(range(0, 1000), k=3)))
            )
            ids_of_needs_data.append(need_id)

        for item in data:
            extra_data = {}
            for name, selector in self.extra_data.items():
                if not (isinstance(selector, tuple) or isinstance(selector, list) or isinstance(selector, str)):
                    raise InvalidConfigException(
                        f"Given selector for {name} of extra_data must be a list or tuple. "
                        f'Got {type(selector)} with value "{selector}"'
                    )
                if isinstance(selector, str):
                    # Set the "hard-coded" string or
                    # combine the "hard-coded" string and dynamic value
                    selector = jinja_parse(item, selector)
                    # Set the returned string as value
                    extra_data[name] = selector
                else:
                    extra_data[name] = dict_get(item, selector)

            content_template = Template(self.content, autoescape=True)
            context = {"data": item, "options": options}
            content = content_template.render(context)
            content += "\n\n| \n"  # Add enough space between content and extra_data

            # Add extra_data to content
            for key, value in extra_data.items():
                if value is not None:
                    content += f"\n| **{key}**: {value}"
            content += "\n"

            prefix = options.get("prefix") or options.get("id_prefix", self.id_prefix)

            need_values = {}
            for name, selector in self.mappings.items():
                if not (isinstance(selector, tuple) or isinstance(selector, list) or isinstance(selector, str)):
                    raise InvalidConfigException(
                        f"Given selector for {name} of mapping must be a list or tuple. "
                        f'Got {type(selector)} with value "{selector}"'
                    )
                if isinstance(selector, str):
                    # Set the "hard-coded" string or
                    # combine the "hard-coded" string and dynamic value
                    selector = jinja_parse(item, selector)
                    # Set the returned string as value
                    need_values[name] = selector
                else:
                    value = dict_get(item, selector)
                    if isinstance(value, tuple) or isinstance(value, list):
                        if name == "links":
                            # Add a prefix to the referenced link if it is an ID of a need object in
                            # the data retrieved from the Open Needs Server or don't add prefix
                            value = [(prefix + link if link in ids_of_needs_data else link) for link in value]
                        value = ";".join(value)
                    # Ensures mapping option with value == None is not implemented. E.g. the links option
                    # can't be == None since there will be nothing to link to and that will raise a warning
                    if value is not None:
                        need_values[name] = value

                for regex, new_str in self.mapping_replaces.items():
                    need_values[name] = re.sub(regex, new_str, need_values.get(name, ""))

                if name == "id":
                    need_values[name] = prefix + need_values.get(name, "")

            finale_data = {"content": content}
            finale_data.update(need_values)

            need_data.append(finale_data)
        return need_data

    def request(self, options=None):
        if options is None:
            options = {}
        self.log.info(f"Requesting data for service {self.name}")

        if len(self.config) != 0 and not self.app.config.open_needs_test_env:
            params = self._prepare_request(options)

            request_params = {
                "method": "GET",
                "url": params["url"],
                "headers": params["headers"],
            }
            answer = self._send_request(request_params)
            data = answer.json()
        else:
            # Absolute path starts with /, based on the conf.py directory. The / need to be striped
            correct_open_needs_json_path = os.path.join(self.app.confdir, self.open_needs_json_file.lstrip("/"))

            if not os.path.exists(correct_open_needs_json_path):
                raise OpenNeedsServiceException(f"Could not load Open Needs json file: {correct_open_needs_json_path}")

            with open(correct_open_needs_json_path) as needs_file:
                needs_file_content = needs_file.read()
            try:
                data = json.loads(needs_file_content)
            except json.JSONDecodeError as e:
                raise ReferenceError(
                    f'There was an error decoding the JSON data in file: "{correct_open_needs_json_path}". '
                    f"Error "
                    f"Message: {e}"
                )

        for datum in data:
            # Be sure "description" is set and valid
            if "description" not in datum or datum["description"] is None:
                datum["description"] = ""

        need_data = self._extract_data(data, options)

        return need_data

    def debug(self, options):
        if options is None:
            options = {}
        self.log.debug(f"Requesting data for service {self.name}")

        if not self.app.config.open_needs_test_env:
            params = self._prepare_request(options)

            request_params = {
                "method": "GET",
                "url": params["url"],
                "headers": params["headers"],
            }
            answer = self._send_request(request_params)
            debug_data = answer.json()
        else:
            # Absolute path starts with /, based on the conf.py directory. The / need to be striped
            correct_open_needs_json_path = os.path.join(self.app.confdir, self.open_needs_json_file.lstrip("/"))

            if not os.path.exists(correct_open_needs_json_path):
                raise OpenNeedsServiceException(f"Could not load Open Needs json file: {correct_open_needs_json_path}")

            with open(correct_open_needs_json_path) as needs_file:
                needs_file_content = needs_file.read()
            try:
                debug_data = json.loads(needs_file_content)
            except json.JSONDecodeError as e:
                raise ReferenceError(
                    f'There was an error decoding the JSON data in file: "{correct_open_needs_json_path}". '
                    f"Error "
                    f"Message: {e}"
                )

        return debug_data


class OpenNeedsServiceException(BaseException):
    pass


class InvalidConfigException(BaseException):
    pass
