from __future__ import annotations

import json
import os
from functools import lru_cache

import requests
from jinja2 import Environment, Template
from requests_file import FileAdapter
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.api import add_external_need, del_need
from sphinx_needs.api.exceptions import NeedsDuplicatedId
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import clean_log, import_prefix_link_edit

log = get_logger(__name__)


@lru_cache(maxsize=20)
def get_target_template(target_url: str) -> Template:
    """
    Provides template for target_link style
    Can be cached, as the template is always the same for a given target_url
    """
    mem_template = Environment().from_string(target_url)
    return mem_template


def load_external_needs(app: Sphinx, env: BuildEnvironment, _docname: str) -> None:
    """Load needs from configured external sources."""
    needs_config = NeedsSphinxConfig(app.config)
    for source in needs_config.external_needs:
        if source["base_url"].endswith("/"):
            source["base_url"] = source["base_url"][:-1]

        target_url = source.get("target_url", "")

        if source.get("json_url", False) and source.get("json_path", False):
            raise NeedsExternalException(
                clean_log(
                    "json_path and json_url are both configured, but only one is allowed.\n"
                    f"json_path: {source['json_path']}\n"
                    f"json_url: {source['json_url']}."
                )
            )
        elif not (source.get("json_url", False) or source.get("json_path", False)):
            raise NeedsExternalException(
                "json_path or json_url must be configured to use external_needs."
            )

        if source.get("json_url", False):
            log.info(
                clean_log(f"Loading external needs from url {source['json_url']}.")
            )
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(source["json_url"])
                needs_json = (
                    response.json()
                )  # The downloaded file MUST be json. Everything else we do not handle!
            except Exception as e:
                raise NeedsExternalException(
                    clean_log(
                        "Getting {} didn't work. Reason: {}".format(
                            source["json_url"], e
                        )
                    )
                )

        if source.get("json_path", False):
            if os.path.isabs(source["json_path"]):
                json_path = source["json_path"]
            else:
                json_path = os.path.join(app.srcdir, source["json_path"])

            if not os.path.exists(json_path):
                raise NeedsExternalException(
                    f"Given json_path {json_path} does not exist."
                )

            with open(json_path) as json_file:
                needs_json = json.load(json_file)

        version = source.get("version", needs_json.get("current_version"))
        if not version:
            raise NeedsExternalException(
                'No version defined in "needs_external_needs" or by "current_version" from loaded json file'
            )

        try:
            needs = needs_json["versions"][version]["needs"]
        except KeyError:
            raise NeedsExternalException(
                clean_log(
                    f"Version {version} not found in json file from {source['json_url']}"
                )
            )

        log.debug(f"Loading {len(needs)} needs.")

        prefix = source.get("id_prefix", "").upper()
        import_prefix_link_edit(needs, prefix, needs_config.extra_links)
        for need in needs.values():
            need_params = {**need}

            extra_links = [x["option"] for x in needs_config.extra_links]
            for key in list(need_params.keys()):
                if (
                    key not in needs_config.extra_options
                    and key not in extra_links
                    and key
                    not in [
                        "title",
                        "type",
                        "id",
                        "description",
                        "tags",
                        "docname",
                        "status",
                    ]
                ):
                    del need_params[key]

            need_params["need_type"] = need["type"]
            need_params["id"] = f'{prefix}{need["id"]}'
            need_params["external_css"] = source.get("css_class")

            if target_url:
                # render jinja content
                mem_template = get_target_template(target_url)
                cal_target_url = mem_template.render(**{"need": need})
                need_params["external_url"] = f'{source["base_url"]}/{cal_target_url}'
            else:
                need_params["external_url"] = (
                    f'{source["base_url"]}/{need.get("docname", "__error__")}.html#{need["id"]}'
                )

            need_params["content"] = need["description"]
            need_params["links"] = need.get("links", [])
            need_params["tags"] = ",".join(need.get("tags", []))
            need_params["status"] = need.get("status")
            need_params["constraints"] = need.get("constraints", [])

            del need_params["description"]

            # check if external needs already exist
            ext_need_id = need_params["id"]

            need = SphinxNeedsData(env).get_or_create_needs().get(ext_need_id)

            if need is not None:
                # check need_params for more detail
                if need["is_external"] and source["base_url"] in need["external_url"]:
                    # delete the already existing external need from api need
                    del_need(app, ext_need_id)
                else:
                    raise NeedsDuplicatedId(
                        f'During external needs handling, an identical ID was detected: {ext_need_id} \
                            from needs_external_needs url: {source["base_url"]}'
                    )

            add_external_need(app, **need_params)


class NeedsExternalException(BaseException):
    pass
