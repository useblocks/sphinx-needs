"""The sites that read a field's declaration for one need, and so for its need type.

Each entry point that admits a key (a need directive, ``list2need``, ``add_need``), the
``needextend`` checks and the field validation read the declaration of a field. The
tests here pin what each of them does today, with one declaration per field name for
every need type: the warnings, their codes and their texts, and the number of
validators the field validation compiles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api.need import generate_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.schema import core as schema_core
from sphinx_needs_testkit import build_warnings

PLAIN_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"x": {"nullable": True}}
"""


def _project(conf: str, index: str) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _count_compiles(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the validators the schema module compiles from now on."""
    calls = [0]
    compile_validator = schema_core.compile_validator

    def counting(schema: Any) -> Any:
        calls[0] += 1
        return compile_validator(schema)

    monkeypatch.setattr(schema_core, "compile_validator", counting)
    return calls


UNKNOWN_KEYS_INDEX = """\
.. req:: A
   :id: REQ_1
   :bogus: y

.. list2need::
   :types: req

   * (LIST_1)B ((bogus_l="z"))

.. needextend:: REQ_1
   :template: other
"""


@pytest.mark.parametrize(
    "test_app", [_project(PLAIN_CONF, UNKNOWN_KEYS_INDEX)], indirect=True
)
def test_unknown_keys_and_extend_checks(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown directive option and an unknown ``list2need`` option each warn,
    and the need is still created; a ``needextend`` option of a field that does not
    allow extending warns at the directive, and is not applied. The field validation
    of a project compiles one validator."""
    compiles = _count_compiles(monkeypatch)
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Unknown option 'bogus' [needs.directive]",
        "<srcdir>/index.rst:11: WARNING: Unknown option 'bogus_l' [needs.directive]",
        "<srcdir>/index.rst:13: WARNING: Option 'template' does not support extend "
        "operations. [needs.needextend]",
    ]
    needs = _needs(app)
    assert sorted(needs) == ["LIST_1", "REQ_1"]
    assert "bogus" not in needs["REQ_1"]
    assert "bogus_l" not in needs["LIST_1"]
    assert needs["REQ_1"]["template"] is None
    assert compiles == [1]


@pytest.mark.parametrize("test_app", [_project(PLAIN_CONF, "")], indirect=True)
def test_an_unknown_keyword_is_refused(test_app: Any) -> None:
    """``add_need`` (through ``generate_need``) refuses a keyword that is no field and
    no link type."""
    app = test_app
    app.build()
    with pytest.raises(InvalidNeedException) as exc_info:
        generate_need(
            NeedsSphinxConfig(app.config),
            SphinxNeedsData(app.env).get_schema(),
            "req",
            "A",
            id="REQ_1",
            bogus="1",
        )
    assert exc_info.value.type == "invalid_kwargs"
    assert exc_info.value.message == (
        "{'bogus'} not in 'needs_fields' or 'needs_links'."
    )
