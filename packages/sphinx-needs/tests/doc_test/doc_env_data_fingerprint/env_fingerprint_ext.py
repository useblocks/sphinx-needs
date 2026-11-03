"""The local extension of the environment fingerprint project: a service, registered
from code (a service class in the configuration would make it unpickleable), and two
directives that create their needs through the API."""

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import NeedItemSource, add_need, create_need
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class FingerprintService(BaseService):
    """One need, whatever it is asked."""

    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [{"id": "SVC_A", "title": "service need", "type": "req"}]

    def debug(self, options):
        return {}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "probe" not in services.services:
        services.register("probe", FingerprintService)


class AddNeed(SphinxDirective):
    """A need made through ``add_need``."""

    def run(self):
        return add_need(
            self.env.app,
            self.state,
            self.env.docname,
            self.lineno,
            need_type="spec",
            title="made through add_need",
            id="SPEC_ADD",
        )


class CreateNeed(SphinxDirective):
    """A need made through ``create_need``."""

    def run(self):
        _need, need_nodes = create_need(
            self.env.app,
            self.state,
            NeedItemSource.from_directive(self),
            "spec",
            "made through create_need",
            id="SPEC_CREATE",
            fields={"effort": 2},
            links={"links": ["REQ_1"]},
        )
        return need_nodes


def setup(app):
    app.connect("env-before-read-docs", _register)
    app.add_directive("add-need", AddNeed)
    app.add_directive("create-need", CreateNeed)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
