"""needimport and a record's template names: provenance, never instructions.

A needs.json record's ``content`` is already its templates' output, and its ``template``,
``pre_template``, ``post_template`` and ``jinja_content`` name files of the PRODUCING
project. ``needimport`` used to apply them again from the importing project's template
folder: the content was wrapped twice, Jinja in it was rendered twice, and every
templated record was lost where the importer had no such template. The conformance
corpus pins what is imported (``import-*`` cases); this pins sphinx-needs' deprecation
window for a record's pre and post templates, which are still applied where the
importer has the template (with one ``needs.deprecated`` per directive and template,
naming the directive's own option as the replacement) until 10.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs_testkit import build_warnings

CONF = 'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'


def _needs_json(*records: dict[str, Any]) -> str:
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {"1.0": {"needs": {r["id"]: r for r in records}}},
        }
    )


def _record(need_id: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": need_id,
        "type": "spec",
        "title": need_id,
        "content": "Body.",
    } | fields


RECORDS = _needs_json(
    _record("A_1", pre_template="pre", pre_content="PRODUCER PRE"),
    _record("A_2", pre_template="pre", post_template="gone"),
    _record("A_3", template="wrap", content="PRODUCER WRAP Body."),
)

INDEX = """\
Index
=====

.. needimport:: a.json

.. needimport:: a.json
   :id_prefix: OWN_
   :pre_template: own
"""


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("a.json"), RECORDS),
                (Path("needs_templates", "pre.need"), "IMPORTER PRE {{ id }}\n"),
                (Path("needs_templates", "own.need"), "OWN PRE {{ id }}\n"),
                (Path("needs_templates", "wrap.need"), "IMPORTER WRAP {{ content }}\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_records_decoration_is_deprecated_where_it_is_still_applied(
    test_app: Any,
) -> None:
    app = test_app
    app.build()
    needs = _needs(app)
    # the record's pre template, which the importer has: applied, from the importer
    assert needs["A_1"]["pre_content"] == "IMPORTER PRE A_1"
    assert needs["A_2"]["pre_content"] == "IMPORTER PRE A_2"
    # its post template, which the importer has not: dropped, nothing reported
    assert needs["A_2"]["post_template"] is None
    assert needs["A_2"]["post_content"] is None
    # its content template: never applied again
    assert needs["A_3"]["content"] == "PRODUCER WRAP Body."
    assert needs["A_3"]["template"] is None
    # the directive's own option replaces the record's, with no deprecation
    assert needs["OWN_A_1"]["pre_content"] == "OWN PRE OWN_A_1"
    assert needs["OWN_A_3"]["pre_content"] == "OWN PRE OWN_A_3"
    warnings = build_warnings(app)
    deprecated = [w for w in warnings if "[needs.deprecated]" in w]
    # once for the directive and template, though two records name it
    assert len(deprecated) == 1, warnings
    assert "pre_template 'pre'" in deprecated[0]
    assert ":pre_template: pre" in deprecated[0]
    assert "10.0" in deprecated[0]
    assert deprecated[0].startswith("<srcdir>/index.rst:4:")
    assert not any("[needs.template_" in w for w in warnings), warnings
