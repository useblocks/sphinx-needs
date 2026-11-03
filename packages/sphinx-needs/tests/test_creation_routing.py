"""What each producer and each legacy door hands the creation path as its own arguments,
rather than as a field.

``add_need`` bound the names of its own keywords (``jinja_content``, ``external_css``, ...)
wherever they came from; the paths that reach the core with a mapping take them out of the
mapping by name. Each line doing so is pinned here: dropping it would turn the value into
an unknown field, and the need into a refusal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

EXT = '''\
"""A service with a Jinja datum, and an extension calling ``add_external_need``."""

import warnings

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_external_need
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class JinjaService(BaseService):
    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [
            {
                "id": "R_SVC",
                "title": "a service need",
                "type": "req",
                "content": "rendered {{ id }}",
                "jinja_content": True,
            }
        ]

    def debug(self, options):
        return {}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "jinja" not in services.services:
        services.register("jinja", JinjaService)


class ExternalCalls(SphinxDirective):
    def run(self):
        app = self.env.app
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            add_external_need(
                app, "req", "a deprecated key", id="R_XDEP",
                external_url="http://example.org/a.html", hide_tags=True,
            )
        self.env.external_warnings = [
            (w.category.__name__, str(w.message))
            for w in caught
            if not w.category.__name__.startswith("RemovedInSphinx")
        ]
        # ``jinja_content`` is ``add_need``'s keyword, not a field
        add_external_need(
            app, "req", "a Jinja need", id="R_XJIN",
            external_url="http://example.org/b.html",
            content="rendered {{ id }}", jinja_content=True,
        )
        return []


def setup(app):
    app.connect("env-before-read-docs", _register)
    app.add_directive("external-calls", ExternalCalls)
    return {"parallel_read_safe": False}
'''

CONF = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("creation_routing_ext", None)
extensions = ["sphinx_needs", "creation_routing_ext"]
needs_fields = {"hide_status": {"nullable": True}}
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "ext.json", "css_class": "ext_css"},
]
"""


def _needs_json(need_id: str) -> str:
    need = {"id": need_id, "type": "req", "title": f"record {need_id}"}
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: need}}}}
    )


INDEX = """\
Routing
=======

.. req:: A need setting a field named like a deprecated key
   :id: R_DIR
   :hide_status: kept

.. list2need::
   :types: req

   * (R_L2N) A list2need item ((jinja_content="true"))
     rendered {{ id }}

.. needservice:: jinja

.. needimport:: imp.json

.. external-calls::
"""


@pytest.fixture
def needs(test_app: SphinxTestApp):
    test_app.build()
    assert build_warnings(test_app) == []
    return SphinxNeedsData(test_app.env).get_needs_view()


PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), CONF),
        (Path("creation_routing_ext.py"), EXT),
        (Path("index.rst"), INDEX),
        (Path("imp.json"), _needs_json("R_IMP")),
        (Path("ext.json"), _needs_json("R_EXT")),
    ],
}


@pytest.mark.parametrize("test_app", [PROJECT], indirect=True)
def test_jinja_content_is_the_argument_on_every_path(needs):
    """A list2need item's inline ``jinja_content``, a service datum's, and
    ``add_external_need``'s keyword render the content."""
    assert {nid: needs[nid]["content"] for nid in ("R_L2N", "R_SVC", "R_XJIN")} == {
        "R_L2N": "rendered R_L2N",
        "R_SVC": "rendered R_SVC",
        "R_XJIN": "rendered R_XJIN",
    }


@pytest.mark.parametrize("test_app", [PROJECT], indirect=True)
def test_the_record_paths_external_css(needs):
    """An imported need takes the default css class, an external one its source's."""
    assert (needs["R_IMP"]["external_css"], needs["R_EXT"]["external_css"]) == (
        "external_link",
        "ext_css",
    )


@pytest.mark.parametrize("test_app", [PROJECT], indirect=True)
def test_add_external_need_still_warns_of_a_deprecated_key(test_app, needs):
    """One ``DeprecationWarning``, the key dropped, the need created."""
    assert test_app.env.external_warnings == [
        ("DeprecationWarning", "deprecated key found in kwargs")
    ]
    assert needs["R_XDEP"]["is_external"] is True


@pytest.mark.parametrize("test_app", [PROJECT], indirect=True)
def test_a_field_named_like_a_deprecated_key_is_a_field(needs):
    """``add_need`` drops its deprecated keys (``hide_status``, ...) with a warning; a
    field the project declares under such a name is a field through the producers."""
    assert needs["R_DIR"]["hide_status"] == "kept"


SERVICE_FULL_TITLE = """\
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class FullTitleService(BaseService):
    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [{"title": "short", "type": "req", "full_title": "A much longer title"}]

    def debug(self, options):
        return {}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "full" not in services.services:
        services.register("full", FullTitleService)


def setup(app):
    app.connect("env-before-read-docs", _register)
    return {"parallel_read_safe": True}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    "import sys\nfrom pathlib import Path\n\n"
                    "sys.path.insert(0, str(Path(__file__).parent))\n"
                    'sys.modules.pop("full_title_service", None)\n'
                    'extensions = ["sphinx_needs", "full_title_service"]\n'
                    'needs_fields = {"full_title": {"nullable": True}}\n',
                ),
                (Path("full_title_service.py"), SERVICE_FULL_TITLE),
                (Path("index.rst"), "Ids\n===\n\n.. needservice:: full\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_service_s_declared_full_title_keeps_its_generated_id(test_app):
    """A service datum's ``full_title`` that the project declares as a field is the
    field, and still the full title the generated id is derived from, as ``add_need``
    took it: the id is the one it had."""
    test_app.build()
    assert build_warnings(test_app) == []
    needs = SphinxNeedsData(test_app.env).get_needs_view()
    expected = "R_" + hashlib.sha1(b"A much longer title").hexdigest().upper()[:5]
    assert list(needs) == [expected]
    assert needs[expected]["full_title"] == "A much longer title"
