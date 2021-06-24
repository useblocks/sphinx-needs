import copy

import requests
from requests_file import FileAdapter

from sphinxcontrib.needs.api import add_external_need
from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.utils import import_prefix_link_edit

log = get_logger(__name__)


def load_external_needs(app, env, _docname):
    for source in app.config.needs_external_needs:
        if source["base_url"].endswith("/"):
            source["base_url"] = source["base_url"][:-1]

        log.info(f'Loading external needs from {source["json_url"]}')

        s = requests.Session()
        s.mount("file://", FileAdapter())

        try:
            response = s.get(source["json_url"])
            needs_json = response.json()  # The downloaded file MUST be json. Everything else we do not handle!
        except Exception as e:
            raise NeedsExternalException(f'Getting {source["json_url"]} didn\'t work. Reason: {e}')

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
                    and key not in ["title", "type", "id", "description", "tags", "docname"]
                ):
                    del need_params[key]

            need_params["need_type"] = need["type"]
            need_params["id"] = f'{prefix}{need["id"]}'
            need_params["external_css"] = source.get("css_class", None)
            need_params["external_url"] = f'{source["base_url"]}/{need.get("docname", "__error__")}.html#{need["id"]}'
            need_params["content"] = need["description"]
            need_params["links"] = need.get("links", [])
            need_params["tags"] = ",".join(need.get("tags", []))

            del need_params["description"]

            add_external_need(app, **need_params)


class NeedsExternalException(BaseException):
    pass
