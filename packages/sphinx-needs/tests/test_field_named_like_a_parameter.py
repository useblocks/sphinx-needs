"""A field named like a parameter of the creation path is an ordinary field (#2392).

``add_need`` takes a need's fields as ``**kwargs`` beside its own keyword parameters, so a
field named ``state``, ``app``, ``need_type``, ... reached it twice and ended the build with
``TypeError: ... got multiple values for keyword argument``, and a field named
``allow_type_coercion`` bound to the parameter and lost its value. Every producer of this
package creates its needs through a path that takes the fields as a mapping, so no field
name meets a parameter there.

The names are read from the signatures of the creation functions, so a parameter added to
any of them later is covered without anyone remembering this file. A name no field can
have (a core field, or the ``links`` link type) is left out.

The project declares one field per name, and each producer sets every one of them: a need
directive, a ``list2need`` item, a ``needservice`` datum, a ``needimport`` record and a
``needs_external_needs`` record.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import need as api_need
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs_testkit import build_warnings

#: the functions a need is created through, public and private; those this version does
#: not have are skipped, so the list may name a function before it exists
CREATION_FUNCTIONS = (
    "create_need",
    "_create_need",
    "_generate_need",
    "add_need",
    "generate_need",
    "ingest_need_record",
    "add_external_need",
)


def _parameter_names() -> list[str]:
    names: set[str] = set()
    for function_name in CREATION_FUNCTIONS:
        function = getattr(api_need, function_name, None)
        if function is None:
            continue
        for parameter in inspect.signature(function).parameters.values():
            if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
                continue
            names.add(parameter.name)
    # a core field cannot be declared, and ``links`` is a link type of every project
    return sorted(names - set(NeedsCoreFields) - {"links"})


NAMES = _parameter_names()

PRODUCERS = {
    "R_DIR": "dir",
    "R_L2N": "l2n",
    "R_SVC": "svc",
    "R_IMP": "imp",
    "R_EXT": "ext",
}
"""Each producer's need, by id, and the prefix of the values it sets."""


def _values(prefix: str) -> dict[str, str]:
    return {name: f"{prefix}-{name}" for name in NAMES}


CONF = f"""\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("named_like_a_parameter_ext", None)
extensions = ["sphinx_needs", "named_like_a_parameter_ext"]
needs_fields = {{name: {{"nullable": True}} for name in {NAMES!r}}}
needs_external_needs = [{{"base_url": "http://example.org", "json_path": "ext.json"}}]
"""

EXT = f'''\
"""A service that returns one need, setting every field named like a parameter."""

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.base import BaseService


class ProbeService(BaseService):
    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [{{"id": "R_SVC", "title": "a service need", "type": "req", **{_values("svc")!r}}}]

    def debug(self, options):
        return {{}}


def _register(app, env, docnames):
    services = SphinxNeedsData(env).get_or_create_services()
    if "probe" not in services.services:
        services.register("probe", ProbeService)


def setup(app):
    app.connect("env-before-read-docs", _register)
    return {{"parallel_read_safe": True}}
'''


def _record(need_id: str, prefix: str) -> str:
    need = {
        "id": need_id,
        "type": "req",
        "title": f"a {prefix} need",
        **_values(prefix),
    }
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: need}}}}
    )


INDEX = "\n".join(
    [
        "Fields named like a parameter",
        "=============================",
        "",
        ".. req:: A directive need",
        "   :id: R_DIR",
        *(f"   :{name}: {value}" for name, value in _values("dir").items()),
        "",
        ".. list2need::",
        "   :types: req",
        "",
        "   * (R_L2N) A list2need need (("
        + ", ".join(f'{name}="{value}"' for name, value in _values("l2n").items())
        + "))",
        "",
        ".. needservice:: probe",
        "",
        ".. needimport:: imp.json",
        "",
    ]
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("named_like_a_parameter_ext.py"), EXT),
                (Path("index.rst"), INDEX),
                (Path("imp.json"), _record("R_IMP", "imp")),
                (Path("ext.json"), _record("R_EXT", "ext")),
            ],
        }
    ],
    indirect=True,
)
def test_a_field_named_like_a_parameter_round_trips(test_app: SphinxTestApp):
    """Every producer creates its need, and every field holds what it set. A field named
    ``source`` (``create_need``'s parameter) switches the ``source.*`` filter facets off,
    which is the one warning."""
    app = test_app
    app.build()
    assert build_warnings(app) == (
        [
            "WARNING: A field named 'source' is declared, which switches the source.* "
            "filter facets off for the project: 'source' in a filter reads the field "
            "[needs.source_shadowed]"
        ]
        if "source" in NAMES
        else []
    )
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {
        need_id: {name: needs[need_id][name] for name in NAMES}
        for need_id in PRODUCERS
        if need_id in needs
    } == {need_id: _values(prefix) for need_id, prefix in PRODUCERS.items()}


def test_the_names_cover_the_parameters_issue_2392_names():
    """The control: the names #2392 found colliding are among those read."""
    assert {
        "state",
        "app",
        "need_type",
        "need_source",
        "full_title",
        "allow_type_coercion",
    } <= set(NAMES)


# --- #2403: an external need keeps a field named ``state`` ------------------------------

STATE_EXT = '''\
"""Creates external needs through ``add_external_need``, as an extension may."""

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_external_need


class ExternalProbe(SphinxDirective):
    def run(self):
        add_external_need(
            self.env.app,
            "req",
            "an external need of the API",
            id="R_API",
            external_url="http://example.org/api.html",
            state="api-state",
        )
        return []


def setup(app):
    app.add_directive("external-probe", ExternalProbe)
    return {"parallel_read_safe": False}
'''


def _state_project(declared: bool) -> dict:
    conf = (
        "import sys\nfrom pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n"
        'sys.modules.pop("external_state_ext", None)\n'
        'extensions = ["sphinx_needs", "external_state_ext"]\n'
        'needs_external_needs = [{"base_url": "http://example.org", "json_path": "ext.json"}]\n'
    )
    if declared:
        conf += 'needs_fields = {"state": {"nullable": True}}\n'
    record = {"id": "R_EXT", "type": "req", "title": "external", "state": "draft"}
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("external_state_ext.py"), STATE_EXT),
            (Path("index.rst"), "State\n=====\n\n.. external-probe::\n"),
            (
                Path("ext.json"),
                json.dumps(
                    {
                        "current_version": "1.0",
                        "versions": {"1.0": {"needs": {"R_EXT": record}}},
                    }
                ),
            ),
        ],
    }


@pytest.mark.parametrize("test_app", [_state_project(declared=True)], indirect=True)
def test_an_external_need_keeps_a_declared_field_named_state(test_app: SphinxTestApp):
    """#2403: the record's ``state`` was dropped by ``add_external_need``, as if it were
    ``add_need``'s parser state; an extension's ``state=`` the same way."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["R_EXT"]["state"] == "draft"
    assert needs["R_API"]["state"] == "api-state"


@pytest.mark.parametrize("test_app", [_state_project(declared=False)], indirect=True)
def test_an_undeclared_state_of_an_external_need_is_as_before(test_app: SphinxTestApp):
    """The control, and the STOP condition of the fix: with no field named ``state`` the
    record's key is an unknown key, reported once and dropped, and an extension's
    ``state=`` is dropped without a word, both as before."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Unknown keys in external need source 'ext.json': ['state'] "
        "[needs.unknown_external_keys]"
    ]
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert "state" not in needs["R_EXT"]
    assert "state" not in needs["R_API"]
    assert needs["R_API"]["is_external"] is True
