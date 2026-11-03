"""The local extension of the source hops project.

- The service, registered as an extension registers one: from code rather than through
  ``needs_services``, whose class would make the configuration unpickleable, and every
  incremental build a full one.
- A ``source-read`` handler that renders a banner into more lines than it takes, so the
  parser's lines after it are not the file's, and expands a token inside a need's body
  and a list2need item, so their first lines hold and their last do not.
- docutils' ``tab_width`` 4 for every document (``env.settings``), so a tab expands to
  another width than Python's default.
- ``api-need``, a directive that creates its need through ``add_need``, as
  sphinx-test-reports' directives do (no source given: the API's default source).
"""

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need
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


def _banner(app, docname, source):
    if docname == "srcread":
        source[0] = source[0].replace("BANNER\n", "Line A\n\nLine B\n\nLine C\n")
    if docname in ("srcread2", "srcread3"):
        # inside a need's body and a list2need item: their first lines still hold
        source[0] = source[0].replace(
            "EXPAND_HERE\n", "expanded one\n   expanded two\n   expanded three\n"
        )


def _tab_width(app, env, docnames):
    # the probe's documents are read with docutils' ``tab_width`` 4, not 8
    env.settings["tab_width"] = 4


class ApiNeed(SphinxDirective):
    """A need made through the API."""

    def run(self):
        return add_need(
            self.env.app,
            self.state,
            self.env.docname,
            self.lineno,
            need_type="req",
            title="made through add_need",
            id="REQ_APIX",
        )


def setup(app):
    app.connect("env-before-read-docs", _register)
    app.connect("env-before-read-docs", _tab_width)
    app.connect("source-read", _banner)
    app.add_directive("api-need", ApiNeed)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
