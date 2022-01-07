import copy
import json
import os

import requests
from requests_file import FileAdapter

from sphinxcontrib.needs.api import add_external_need, del_need
from sphinxcontrib.needs.api.exceptions import NeedsDuplicatedId
from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.utils import import_prefix_link_edit

log = get_logger(__name__)


def load_external_needs(app, env, _docname):
    for source in app.config.needs_external_needs:
        if source["base_url"].endswith("/"):
            source["base_url"] = source["base_url"][:-1]

        if source.get("json_url", False) and source.get("json_path", False):
            raise NeedsExternalException(
                "json_path and json_url are both configured, but only one is allowed.\n"
                f"json_path: {source['json_path']}\n"
                f"json_url: {source['json_url']}."
            )
        elif not (source.get("json_url", False) or source.get("json_path", False)):
            raise NeedsExternalException("json_path or json_url must be configured to use external_needs.")

        if source.get("json_url", False):
            log.info(f'Loading external needs from url {source["json_url"]}')
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(source["json_url"])
                needs_json = response.json()  # The downloaded file MUST be json. Everything else we do not handle!
            except Exception as e:
                raise NeedsExternalException(f'Getting {source["json_url"]} didn\'t work. Reason: {e}')

        if source.get("json_path", False):
            if os.path.isabs(source["json_path"]):
                json_path = source["json_path"]
            else:
                json_path = os.path.join(app.confdir, source["json_path"])

            if not os.path.exists(json_path):
                raise NeedsExternalException(f"Given json_path {json_path} does not exist.")

            with open(json_path) as json_file:
                needs_json = json.load(json_file)

        version = source.get("version", needs_json.get("current_version", None))
        if not version:
            raise NeedsExternalException(
                'No version defined in "needs_external_needs" or by "current_version" from loaded json file'
            )

        try:
            needs = needs_json["versions"][version]["needs"]
        except KeyError:
            raise NeedsExternalException(f'Version {version} not found in json file from {source["json_url"]}')

        log.debug(f"Loading {len(needs)} needs.")

        prefix = source.get("id_prefix", "").upper()
        import_prefix_link_edit(needs, prefix, env.config.needs_extra_links)
        for need in needs.values():
            need_params = copy.deepcopy(need)

            extra_links = [x["option"] for x in app.config.needs_extra_links]
            for key in list(need_params.keys()):
                if (
                    key not in app.config.needs_extra_options
                    and key not in extra_links
                    and key not in ["title", "type", "id", "description", "tags", "docname", "status"]
                ):
                    del need_params[key]

            need_params["need_type"] = need["type"]
            need_params["id"] = f'{prefix}{need["id"]}'
            need_params["external_css"] = source.get("css_class", None)
            need_params["external_url"] = f'{source["base_url"]}/{need.get("docname", "__error__")}.html#{need["id"]}'
            need_params["content"] = need["description"]
            need_params["links"] = need.get("links", [])
            need_params["tags"] = ",".join(need.get("tags", []))
            need_params["status"] = need.get("status", None)

            del need_params["description"]

            # check if external needs already exist
            ext_need_id = need_params["id"]
            if ext_need_id in env.needs_all_needs:
                # check need_params for more detail
                if (
                    env.needs_all_needs[ext_need_id]["is_external"]
                    and source["base_url"] in env.needs_all_needs[ext_need_id]["external_url"]
                ):
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
