"""A field or link type declared on need types alone whose name is close to a declared
one is reported, "did you mean" (#2299).

A ``needs_types`` entry's ``fields`` or ``links`` naming nothing declared otherwise
declares a field of the types that declare it alone. A misspelt name (``asl`` for
``asil``) is therefore indistinguishable from a deliberate new field: the narrowing the
user meant never applies, and nothing was reported. Such a name, within
``difflib.get_close_matches(name, known, n=1, cutoff=0.8)`` of a core field an author
sets, a registered field (``needs_fields``, an extension's, a service's) or a global
link type, is now one ``needs.type_near_name`` warning; the field is declared all the
same, so a deliberate near-name keeps working, and the subtype can be suppressed alone.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.logging import WarningSubTypeDescription, WarningSubTypes
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
{extra}
needs_fields = {{
    "asil": {{"schema": {{"type": "string"}}, "nullable": True}},
}}
needs_links = {{"verifies": {{}}}}
needs_types = {{
    "req": {{
        "title": "Requirement",
        "prefix": "R_",
        "fields": {{
            # meant to narrow asil on req; the name is misspelt
            "asl": {{"schema": {{"type": "string", "enum": ["A", "B"]}}}},
            # a deliberate field of req alone, close to the core field tags
            "tag": {{"schema": {{"type": "string"}}}},
            # a field of req alone at the cutoff, 0.8 to the core field hide
            "hidden": {{"schema": {{"type": "boolean"}}}},
            # a field of req alone under the cutoff, 0.769 to the core field style
            "style_id": {{"schema": {{"type": "integer"}}}},
        }},
        "links": {{"verifes": {{}}}},
    }},
    "spec": {{
        "title": "Specification",
        "prefix": "S_",
        "fields": {{"asl": {{"schema": {{"type": "string"}}}}}},
    }},
}}
"""

INDEX = """\
Case
====

.. req:: A
   :id: R_001
   :asl: A
   :asil: not-an-asil
   :tag: one
   :hidden: true
   :style_id: 3
   :verifes: S_001

.. spec:: B
   :id: S_001
   :asl: free
"""


def _project(extra: str = "") -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), CONF.format(extra=extra)),
            (Path("index.rst"), textwrap.dedent(INDEX)),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def test_the_subtype_is_registered() -> None:
    """``needs.type_near_name`` is a subtype of its own, so that it can be suppressed
    without suppressing every ``needs.config`` warning."""
    assert "type_near_name" in WarningSubTypes.__args__
    assert WarningSubTypeDescription["type_near_name"] == (
        "A field or link type declared on need types alone has a name close to that of "
        "a declared field or link type; it is declared all the same"
    )


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_a_near_name_is_reported_and_still_declared(test_app: Any) -> None:
    """One warning per near name, naming the first declaring entry, every need type
    declaring it, and the close name: a misspelt field (``asl``, of two need types), a
    misspelt link type (``verifes``), a deliberate plural pair (``tag`` beside the
    core field ``tags``), which is the price of the check, and ``hidden``, whose ratio to
    ``hide`` is the cutoff itself. ``style_id``, at 0.769 to ``style``, is under it and
    not reported. Each is still declared, and holds its values."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['req'].fields['asl'] declares a field of need types "
        "'req', 'spec' alone; did you mean 'asil'? [needs.type_near_name]",
        "WARNING: needs_types['req'].fields['tag'] declares a field of need types "
        "'req' alone; did you mean 'tags'? [needs.type_near_name]",
        "WARNING: needs_types['req'].fields['hidden'] declares a field of need types "
        "'req' alone; did you mean 'hide'? [needs.type_near_name]",
        "WARNING: needs_types['req'].links['verifes'] declares a link type of need "
        "types 'req' alone; did you mean 'verifies'? [needs.type_near_name]",
    ]
    needs = _needs(app)
    req = needs["R_001"]
    assert (
        req["asl"],
        req["asil"],
        req["tag"],
        req["hidden"],
        req["style_id"],
        req["verifes"],
    ) == ("A", "not-an-asil", "one", True, 3, ["S_001"])
    assert needs["S_001"]["asl"] == "free"


@pytest.mark.parametrize(
    "test_app",
    [_project('suppress_warnings = ["needs.type_near_name"]')],
    indirect=True,
)
def test_a_near_name_warning_is_suppressed_alone(test_app: Any) -> None:
    """``suppress_warnings = ["needs.type_near_name"]`` silences the check, for a
    project whose near names are deliberate."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["R_001"]["tag"] == "one"
