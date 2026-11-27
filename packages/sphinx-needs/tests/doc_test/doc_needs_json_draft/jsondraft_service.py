"""A local service, so that a generated need needs no network."""

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class ProbeService(BaseService):
    """One need, whatever it is asked."""

    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [{"id": "SVC_1", "title": "a generated need", "type": "req"}]

    def debug(self, options):
        return {}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "probe" not in services.services:
        services.register("probe", ProbeService)


def setup(app):
    app.connect("env-before-read-docs", _register)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
