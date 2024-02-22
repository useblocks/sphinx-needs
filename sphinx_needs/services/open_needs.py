from __future__ import annotations

import re
from random import choices
from typing import Any

import requests
from jinja2 import Template
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
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

    def __init__(
        self, app: Sphinx, name: str, config: dict[str, Any], **kwargs: Any
    ) -> None:
        self.app = app
        self.name = name
        self.config = config

        self.url: str = self.config.get("url", "http://127.0.0.1:9595")
        if self.url.endswith("/"):
            self.url = self.url.rstrip("/")
        self.url_postfix = self.config.get("url_postfix", "/api/needs/")
        if not self.url_postfix.startswith("/"):
            self.url_postfix = "/" + self.url_postfix
        self.max_content_lines = self.config.get("max_content_lines", -1)

        self.id_prefix = self.config.get("id_prefix", "OPEN_NEEDS_")
        self.query = self.config.get("query", "")
        self.content = self.config.get("content", DEFAULT_CONTENT)
        self.mappings: dict[str, Any] = self.config.get("mappings", {})
        self.mapping_replaces = self.config.get(
            "mappings_replaces", MAPPINGS_REPLACES_DEFAULT
        )

        self.extra_data: dict[str, Any] = self.config.get("extra_data", {})
        self.params = self.config.get("params", "skip=0,limit=100")

        super().__init__(**kwargs)

    def _oauthorization(self) -> None:
        username = self.config.get("user")
        password = self.config.get("password")
        if len(self.config) != 0:
            auth = {"username": username, "password": password}
            login_postfix = "/auth/jwt/login"
            url: str = self.url + login_postfix
            login_resp = requests.post(url, data=auth)
            if login_resp.status_code != 200:
                raise OpenNeedsServiceException(
                    "ONS service error during request.\n"
                    f"Status code: {login_resp.status_code}\n"
                    f"Error: {login_resp.text}\n"
                )
            oauth_credentials = dict(**login_resp.json())
            self.token_type = oauth_credentials.get("token_type")
            self.access_token = oauth_credentials.get("access_token")

    def _prepare_request(self, options: Any) -> Any:
        if options is None:
            options = {}
        url: str = options.get("url", self.url)
        url = url + str(self.url_postfix)

        headers: dict[str, str] = {
            "Authorization": f"{self.token_type} {self.access_token}"
        }
        params: list[str] = [
            param.strip()
            for param in re.split(r";|,", options.get("params", self.params))
        ]
        new_params: str = "&".join(params)

        url = f"{url}?{new_params}"

        request: Any = {"url": url, "headers": headers}
        return request

    @staticmethod
    def _send_request(request: Any) -> Any:
        """
        Sends the final request.
        ``request`` must be a dictionary, which contains data valid to the requests-lib.
        This request-data gets mostly defined by using ``prepare_request``.
        :param request: dict
        :return: request answer
        """

        result: Any = requests.get(**request)
        if result.status_code >= 300:
            raise OpenNeedsServiceException(
                f"Problem accessing {result.url}.\nReason: {result.text}"
            )
        return result

    def _extract_data(
        self, data: list[dict[str, Any]], options: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Extract data of a list/dictionary, which was retrieved via send_request.
        :param data: list or dict
        :param options: dict of set directive options
        :return: list of need-data
        """
        needs_config = NeedsSphinxConfig(self.app.config)
        need_data = []
        if options is None:
            options = {}
        # How to know if a referenced link is a need object in the data we are retrieving from the Open Needs Server
        id_selector = self.mappings.get("id")
        ids_of_needs_data = []  # list of all IDs of need objects being retrieved from the Open Needs Server
        needs_id_validator = needs_config.id_regex or "^[A-Z0-9_]{5,}"
        for item in data:
            if isinstance(id_selector, str):
                context = {**item, **needs_config.render_context}
                value = jinja_parse(context, id_selector)
            else:
                value = str(dict_get(item, id_selector))
            # Validate the value for a need ID or generate a valid ID for the need
            need_id = (
                value
                if re.search(needs_id_validator, value) is not None
                else self.id_prefix + "".join(map(str, choices(range(0, 1000), k=6)))
            )
            ids_of_needs_data.append(need_id)

        for item in data:
            extra_data = {}
            for name, selector in self.extra_data.items():
                if not isinstance(selector, (tuple, list, str)):
                    raise InvalidConfigException(
                        f"Given selector for {name} of extra_data must be a list or tuple. "
                        f'Got {type(selector)} with value "{selector}"'
                    )
                if isinstance(selector, str):
                    # Set the "hard-coded" string or
                    # combine the "hard-coded" string and dynamic value
                    context = {**item, **needs_config.render_context}
                    selector = jinja_parse(context, selector)
                    # Set the returned string as value
                    extra_data[name] = selector
                else:
                    extra_data[name] = dict_get(item, selector)

            content_template = Template(self.content, autoescape=True)
            context = {"data": item, "options": options, **needs_config.render_context}
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
                if not isinstance(selector, (tuple, list, str)):
                    raise InvalidConfigException(
                        f"Given selector for {name} of mapping must be a list or tuple. "
                        f'Got {type(selector)} with value "{selector}"'
                    )
                if isinstance(selector, str):
                    # Set the "hard-coded" string or
                    # combine the "hard-coded" string and dynamic value
                    context = {**item, **needs_config.render_context}
                    selector = jinja_parse(context, selector)
                    # Set the returned string as value
                    need_values[name] = selector
                else:
                    value = dict_get(item, selector)
                    if isinstance(value, (tuple, list)):
                        if name == "links":
                            # Add a prefix to the referenced link if it is an ID of a need object in
                            # the data retrieved from the Open Needs Server or don't add prefix
                            value = [
                                (prefix + link if link in ids_of_needs_data else link)
                                for link in value
                            ]
                        value = ";".join(value)
                    # Ensures mapping option with value == None is not implemented. E.g. the links option
                    # can't be == None since there will be nothing to link to and that will raise a warning
                    if value is not None:
                        need_values[name] = value

                for regex, new_str in self.mapping_replaces.items():
                    need_values[name] = re.sub(
                        regex, new_str, need_values.get(name, "")
                    )

                if name == "id":
                    need_values[name] = str(prefix) + str(need_values.get(name, ""))

            finale_data = {"content": content}
            finale_data.update(need_values)

            need_data.append(finale_data)
        return need_data

    def request_from_directive(
        self, directive: SphinxDirective, /
    ) -> list[dict[str, Any]]:
        self.log.info(f"Requesting data for service {self.name}")
        self._oauthorization()  # Get authorization token
        params = self._prepare_request(directive.options)

        request_params = {
            "url": params["url"],
            "headers": params["headers"],
        }
        answer = self._send_request(request_params)
        data = answer.json()

        for datum in data:
            # Be sure "description" is set and valid
            if "description" not in datum or datum["description"] is None:
                datum["description"] = ""

        need_data = self._extract_data(data, directive.options)

        return need_data

    def debug(self, *args: Any, **kwargs: Any) -> Any:
        self.log.debug(f"Requesting data for service {self.name}")
        self._oauthorization()  # Get authorization token
        params = self._prepare_request(*args)

        request_params = {
            "url": params["url"],
            "headers": params["headers"],
        }
        answer = self._send_request(request_params)
        debug_data = answer.json()

        return debug_data


class OpenNeedsServiceException(BaseException):
    pass


class InvalidConfigException(BaseException):
    pass
