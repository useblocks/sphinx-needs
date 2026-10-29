"""The service of the source hops project, registered as an extension registers one.

Registered from code rather than through ``needs_services``, whose class would make the
configuration unpickleable, and every incremental build a full one.
"""

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class SourceHopsService(BaseService):
    """Two needs, whatever it is asked."""

    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [
            {"id": "SVC_A", "title": "service need a", "type": "req"},
            {"id": "SVC_B", "title": "service need b", "type": "req"},
        ]

    def debug(self, options):
        return {}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "probe" not in services.services:
        services.register("probe", SourceHopsService)


def setup(app):
    app.connect("env-before-read-docs", _register)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
