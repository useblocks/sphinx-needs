from __future__ import annotations

import os
import textwrap
import time
from collections.abc import Mapping
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse

import requests
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig, NeedType
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import log_warning
from sphinx_needs.services.base import BaseService, service_options
from sphinx_needs.services.config.github import (
    GITHUB_DATA,
    GITHUB_FIELDS,
    GITHUB_LAYOUT,
    GITHUB_OPTIONS,
    GITHUB_SERVICES,
)

LOGGER = getLogger(__name__)

#: The GitHub services' need types: each is added only when its service is configured
GITHUB_NEED_TYPES: tuple[NeedType, ...] = (
    {
        "directive": "issue",
        "title": "Issue",
        "prefix": "IS_",
        "color": "#cccccc",
        "style": "card",
    },
    {
        "directive": "pr",
        "title": "PullRequest",
        "prefix": "PR_",
        "color": "#aaaaaa",
        "style": "card",
    },
    {
        "directive": "commit",
        "title": "Commit",
        "prefix": "C_",
        "color": "#888888",
        "style": "card",
    },
)


def add_configured_github_services(app: Sphinx, config: Config) -> None:
    """Record the built-in GitHub services ``needs_services`` configures, and add the
    need type of each and the ``github`` layout to sphinx-needs' registry, as its
    lowest tier, never to the ``needs_types`` and ``needs_layouts`` values (#2265).

    A built-in is configured when ``needs_services`` names it with a mapping of options
    (``{}`` will do), in ``conf.py`` or a ``[needs.services.<name>]`` table of the
    ``needs_from_toml`` file; any other value is a ``needs.config`` warning, and the
    service is not registered. Each configured service adds its own need type alone
    (``github-issues`` adds ``issue``) and registers its directive, so a handler above
    12 finds both, and any of them adds the ``github`` layout; the
    services themselves, and their fields, are registered from the same record when
    the documents are about to be read.

    Connected to ``config-inited`` at priority 12, right after ``resolve_need_types``:
    after the ``needs_from_toml`` file is read (10), so the final value is the one
    read, and before the documented readers of the need types (above 12). Each type or
    layout is read after every configured or added one, and only where none of its
    name is configured or added -- whenever that happens: each gives way on its own.

    :param app: The Sphinx application.
    :param config: The Sphinx configuration.
    """
    from sphinx_needs.needs import _register_need_directive  # avoid circular import

    services = NeedsSphinxConfig(config).services
    if not isinstance(services, Mapping):
        return
    need_types = {need_type["directive"]: need_type for need_type in GITHUB_NEED_TYPES}
    configured = False
    for name, gh_type in GITHUB_SERVICES.items():
        if name not in services:
            continue
        value = services[name]
        if not isinstance(value, Mapping):
            log_warning(
                LOGGER,
                f"needs_services entry {name!r} is not registered: its configuration "
                "must be a mapping of options "
                f"(got a value of type {type(value).__name__!r})",
                "config",
                None,
            )
            continue
        _NEEDS_CONFIG.add_builtin_service(name)
        _NEEDS_CONFIG.add_builtin_need_type(need_types[gh_type])
        _register_need_directive(app, gh_type)
        configured = True
    if configured:
        _NEEDS_CONFIG.add_builtin_layout("github", GITHUB_LAYOUT)


class GithubService(BaseService):
    options = list(GITHUB_OPTIONS)
    fields = list(GITHUB_FIELDS)

    def __init__(
        self, app: Sphinx, name: str, config: dict[str, Any], **kwargs: Any
    ) -> None:
        self.app = app
        self.name = name
        self.config = config

        self.url = self.config.get("url", "https://api.github.com/")
        if not self.url.endswith("/"):
            self.url = f"{self.url}/"
        self.retry_delay = self.config.get("retry_delay", 61)
        self.max_amount = self.config.get("max_amount", -1)
        self.max_content_lines = self.config.get("max_content_lines", -1)
        self.id_prefix = self.config.get("id_prefix", "GITHUB_")
        self.layout = self.config.get("layout", "github")
        self.download_avatars = self.config.get("download_avatars", True)
        self.download_folder = self.config.get("download_folder", "github_images")

        self.username = self.config.get("username")
        self.token = self.config.get("token")

        self.gh_type_config = {
            "issue": {
                "url": "search/issues",
                "query": "is:issue",
                "need_type": "issue",
            },
            "pr": {"url": "search/issues", "query": "is:pr", "need_type": "pr"},
            "commit": {"url": "search/commits", "query": "", "need_type": "commit"},
        }

        if "gh_type" in kwargs:
            self.gh_type = kwargs["gh_type"]

        if self.gh_type not in self.gh_type_config:
            raise KeyError(
                'github type "{}" not supported. Use: {}'.format(
                    self.gh_type, ", ".join(self.gh_type_config.keys())
                )
            )

        # Set need_type to use by default
        self.need_type = self.config.get(
            "need_type", self.gh_type_config[self.gh_type]["need_type"]
        )

        super().__init__()

    def _send(
        self, query: str, options: dict[str, Any], specific: bool = False
    ) -> dict[str, Any]:
        headers = {}
        if self.gh_type == "commit":
            headers["Accept"] = "application/vnd.github.cloak-preview+json"

        if specific:
            try:
                specific_elements = query.split("/")
                owner = specific_elements[0]
                repo = specific_elements[1]
                number = specific_elements[2]
                if self.gh_type == "issue":
                    single_type = "issues"
                elif self.gh_type == "pr":
                    single_type = "pulls"
                else:
                    single_type = "commits"
                url = self.url + f"repos/{owner}/{repo}/{single_type}/{number}"
            except IndexError:
                raise _SendException(
                    'Single option ot valid, must follow "owner/repo/number"'
                )

            params = {}
        else:
            url = self.url + self.gh_type_config[self.gh_type]["url"]
            query = "{} {}".format(query, self.gh_type_config[self.gh_type]["query"])
            params = {
                "q": query,
                "per_page": options.get("max_amount", self.max_amount),
            }

        self.log.info(f"Service {self.name} requesting data for query: {query}")

        auth: tuple[str, str] | None
        # TODO token can be None
        auth = (self.username, self.token) if self.username else None  # ty: ignore[invalid-assignment]

        resp = requests.get(url, params=params, auth=auth, headers=headers)

        if resp.status_code > 299:
            extra_info = ""
            # Lets try to get information about the rate limit, as this is mostly the main problem.
            if "rate limit" in resp.json()["message"]:
                resp_limit = requests.get(self.url + "rate_limit", auth=auth)
                extra_info = resp_limit.json()
                self.log.info(
                    f"GitHub: API rate limit exceeded. trying again in {self.retry_delay} seconds..."
                )
                self.log.info(extra_info)
                time.sleep(self.retry_delay)
                resp = requests.get(url, params=params, auth=auth, headers=headers)
                if resp.status_code > 299:
                    if "rate limit" in resp.json()["message"]:
                        raise _SendException(
                            "GitHub: API rate limit exceeded (twice). Stop here."
                        )
                    else:
                        raise _SendException(
                            "Github service error during request.\n"
                            f"Status code: {resp.status_code}\n"
                            f"Error: {resp.text}\n"
                            f"{extra_info}"
                        )
            else:
                raise _SendException(
                    "Github service error during request.\n"
                    f"Status code: {resp.status_code}\n"
                    f"Error: {resp.text}\n"
                    f"{extra_info}"
                )

        if specific:
            return {"items": [resp.json()]}
        return resp.json()

    def request_from_directive(
        self, directive: SphinxDirective, /
    ) -> list[dict[str, Any]]:
        self.log.debug(f"Requesting data for service {self.name}")
        options = directive.options

        if "query" not in options and "specific" not in options:
            create_warning(
                directive,
                '"query" or "specific" missing as option for github service.',
            )
            return []

        if "query" in options and "specific" in options:
            create_warning(
                directive,
                'Only "query" or "specific" allowed for github service. Not both!',
            )
            return []

        if "query" in options:
            query = options["query"]
            specific = False
        else:
            query = options["specific"]
            specific = True

        try:
            response = self._send(query, options, specific=specific)
        except _SendException as e:
            create_warning(directive, str(e))
            return []
        if "items" not in response:
            if "errors" in response:
                create_warning(
                    directive,
                    "GitHub service query error: {}\nUsed query: {}".format(
                        response["errors"][0]["message"], query
                    ),
                )
                return []
            else:
                create_warning(directive, "Github service: Unknown error")
                return []

        if self.gh_type == "issue" or self.gh_type == "pr":
            data = self.prepare_issue_data(response["items"], directive)
        elif self.gh_type == "commit":
            data = self.prepare_commit_data(response["items"], directive)
        else:
            create_warning(directive, "Github service failed. Wrong gh_type...")
            return []

        return data

    def prepare_issue_data(
        self, items: list[dict[str, Any]], directive: SphinxDirective
    ) -> list[dict[str, Any]]:
        data = []
        for item in items:
            # ensure that "None" can not reach .splitlines()
            if item["body"] is None:
                item["body"] = ""

            # wraps content lines, if they are too long. Respects already existing newlines.
            content_lines = [
                "\n   ".join(
                    textwrap.wrap(
                        line, 60, break_long_words=True, replace_whitespace=False
                    )
                )
                for line in item["body"].splitlines()
                if line.strip()
            ]

            content = "\n\n   ".join(content_lines)
            # Reduce content length, if requested by config
            if (self.max_content_lines > 0) or (
                "max_content_lines" in directive.options
            ):
                max_lines = int(
                    directive.options.get("max_content_lines", self.max_content_lines)
                )
                content_lines = content.splitlines()
                if len(content_lines) > max_lines:
                    content_lines = content_lines[0:max_lines]
                    content_lines.append("\n   [...]\n")  # Mark, if content got cut
                content = "\n".join(content_lines)

            # Be sure the content gets not interpreted as rst or html code, so we put
            # everything in a safe code-block
            content = ".. code-block:: text\n\n   " + content

            prefix = directive.options.get("id_prefix", self.id_prefix)
            need_id = prefix + str(item["number"])
            given_tags = directive.options.get("tags", False)
            github_tags = ",".join([x["name"] for x in item["labels"]])
            if given_tags:
                tags = str(given_tags) + ", " + str(github_tags)
            else:
                tags = github_tags

            avatar_file_path = self._get_avatar(item["user"]["avatar_url"], directive)

            element_data = {
                "service": self.name,
                "type": directive.options.get("type", self.need_type),
                "layout": directive.options.get("layout", self.layout),
                "id": need_id,
                "title": item["title"],
                "content": content,
                "status": item["state"],
                "tags": tags,
                "user": item["user"]["login"],
                "url": item["html_url"],
                "avatar": avatar_file_path,
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "closed_at": item["closed_at"],
            }
            self._add_given_options(directive.options, element_data)
            data.append(element_data)

        return data

    def prepare_commit_data(
        self, items: list[dict[str, Any]], directive: SphinxDirective
    ) -> list[dict[str, Any]]:
        data = []

        for item in items:
            avatar_file_path = self._get_avatar(item["author"]["avatar_url"], directive)

            element_data = {
                "service": self.name,
                "type": directive.options.get("type", self.need_type),
                "layout": directive.options.get("layout", self.layout),
                "id": self.id_prefix + item["sha"][:6],
                "title": item["commit"]["message"].split("\n")[0][
                    :60
                ],  # 1. line, max length 60 chars
                "content": item["commit"]["message"],
                "user": item["author"]["login"],
                "url": item["html_url"],
                "avatar": avatar_file_path,
                "created_at": item["commit"]["author"]["date"],
            }
            self._add_given_options(directive.options, element_data)
            data.append(element_data)

        return data

    def _get_avatar(self, avatar_url: str, directive: SphinxDirective) -> str:
        """Download and store avatar image"""
        url_parsed = urlparse(avatar_url)
        filename = os.path.basename(url_parsed.path) + ".png"
        path = os.path.join(self.app.srcdir, self.download_folder)
        avatar_file_path = os.path.join(path, filename)

        # Placeholder avatar, if things go wrong or avatar download is deactivated
        default_avatar_file_path = os.path.join(
            os.path.dirname(__file__), "../images/avatar.png"
        )
        if self.download_avatars:
            # Download only, if file not downloaded yet
            if not os.path.exists(avatar_file_path):
                with suppress(FileExistsError):
                    os.mkdir(path)
                if self.username and self.token:
                    auth = (self.username, self.token)
                else:
                    auth = None
                response = requests.get(avatar_url, auth=auth, allow_redirects=False)
                if response.status_code == 200:
                    with open(avatar_file_path, "wb") as f:
                        f.write(response.content)
                elif response.status_code == 302:
                    create_warning(
                        directive,
                        f"GitHub service {self.name} could not download avatar image "
                        f"from {avatar_url}.\n"
                        f"    Status code: {response.status_code}\n"
                        "    Reason: Looks like the authentication provider tries to redirect you."
                        " This is not supported and is a common problem, "
                        "if you use GitHub Enterprise.",
                    )
                    avatar_file_path = default_avatar_file_path
                else:
                    create_warning(
                        directive,
                        f"GitHub service {self.name} could not download avatar image "
                        f"from {avatar_url}.\n"
                        f"    Status code: {response.status_code}",
                    )
                    avatar_file_path = default_avatar_file_path
        else:
            avatar_file_path = default_avatar_file_path

        return avatar_file_path

    def _add_given_options(
        self, options: dict[str, Any], element_data: dict[str, Any]
    ) -> None:
        """Add the directive's options the service did not set, such as a field of the
        project's own, to the data of a need: not the service's own data, and not its
        control options (``query``, ...), which are request parameters, not need fields.

        :param options: The options of the ``needservice`` directive.
        :param element_data: The data of a need, updated in place.
        """
        # the options the needservice accepted as the service's: those of the class
        # (or factory) it was registered with, which for one written for the old
        # meaning of ``options`` are none -- its options are need fields, and are
        # copied as they were
        control = (
            SphinxNeedsData(self.app.env)
            .get_or_create_services()
            .directive_options(self.name)
        )
        if control is None:  # not registered under its name
            control = service_options(type(self))
        for key, value in options.items():
            if (
                key not in element_data
                and key not in GITHUB_DATA
                and key not in control
            ):
                element_data[key] = value


class _SendException(Exception):
    pass


def create_warning(directive: SphinxDirective, message: str) -> None:
    log_warning(
        LOGGER,
        message,
        "github",
        location=directive.get_location(),
    )
