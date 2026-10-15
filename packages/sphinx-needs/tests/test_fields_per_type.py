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
from sphinx.errors import ExtensionError

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


# -- the declarations of one need type -------------------------------------------------
#
# Nothing in the configuration declares a field for one need type yet: each project
# below registers its overlays from ``conf.py``, after the fields schema is created.

OVERLAY_CONF = """\
from dataclasses import replace

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.needs_schema import FieldLiteralValue

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {fields}

#: (need type, field name, the changes to its declaration)
OVERLAYS = {overlays}
{extra}


def _overlays(app, env, docnames):
    schema = SphinxNeedsData(env).get_schema()
    for need_type, name, changes in OVERLAYS:
        schema.add_type_overlay(need_type, replace(schema.get_any_field(name), **changes))


def setup(app):
    app.connect("env-before-read-docs", _overlays, priority=600)
"""


def _overlay_project(
    fields: str, overlays: str, index: str, extra: str = ""
) -> dict[str, Any]:
    return _project(
        OVERLAY_CONF.format(fields=fields, overlays=overlays, extra=extra), index
    )


#: a service whose data are a need of each of two types, each setting ``x``
SERVICE_CONF = """
from sphinx_needs.services.base import BaseService


class TwoTypes(BaseService):
    options = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [
            {"type": "req", "id": "SRV_1", "title": "E", "x": "five"},
            {"type": "spec", "id": "SRV_2", "title": "F", "x": "six"},
        ]


needs_services = {"two": {"class": TwoTypes, "class_init": {}}}
"""


ADMISSION_INDEX = """\
.. req:: A
   :id: REQ_1
   :x: one

.. spec:: B
   :id: SPEC_1
   :x: two

.. list2need::
   :types: req, spec

   * (LIST_1)C ((x="three"))

     * (LIST_2)D ((x="four"))

.. needservice:: two
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True}}',
            '[("spec", "x", {"directive_option": False})]',
            ADMISSION_INDEX,
            SERVICE_CONF,
        )
    ],
    indirect=True,
)
def test_a_field_closed_on_one_type(test_app: Any) -> None:
    """A field a need type closes is refused on its needs, from a directive,
    ``list2need`` and ``needservice``, and set on the needs of every other type."""
    app = test_app
    app.build()
    # the service class in conf.py cannot be cached, which Sphinx reports in words
    # that differ between its versions
    warnings = [w for w in build_warnings(app) if "cannot cache unpick" not in w]
    # the text and code are today's for a field closed by ``directive_option=False``;
    # the slice that closes need types owns them
    assert warnings == [
        "<srcdir>/index.rst:8: WARNING: Field 'x' is derived and cannot be set in a "
        "need; the value 'two' is ignored [needs.derive_authored]",
        "<srcdir>/index.rst:17: WARNING: Field 'x' is derived and cannot be set in a "
        "need; the value 'four' is ignored [needs.derive_authored]",
        "<srcdir>/index.rst:19: WARNING: Field 'x' is derived and cannot be set in a "
        "need; the value 'six' is ignored [needs.derive_authored]",
    ]
    needs = _needs(app)
    assert {k: v["x"] for k, v in needs.items()} == {
        "REQ_1": "one",
        "SPEC_1": None,
        "LIST_1": "three",
        "LIST_2": None,
        "SRV_1": "five",
        "SRV_2": None,
    }


DEFAULTS_INDEX = """\
.. req:: A
   :id: REQ_1

.. spec:: B
   :id: SPEC_1

.. spec:: C
   :id: SPEC_2
   :x: given
   :status: given
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True, "default": "global"}}',
            '[("spec", "x", {"default": FieldLiteralValue("spec")}),'
            ' ("spec", "status", {"default": FieldLiteralValue("spec-open")})]',
            DEFAULTS_INDEX,
        )
    ],
    indirect=True,
)
def test_a_default_of_one_type(test_app: Any) -> None:
    """A need type's default of a field, or of a core field, is the value of its
    unset needs; the needs of every other type take the field's default."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert {k: (v["x"], v["status"]) for k, v in needs.items()} == {
        "REQ_1": ("global", None),
        "SPEC_1": ("spec", "spec-open"),
        "SPEC_2": ("given", "given"),
    }


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True}}',
            '[("spec", "x", {"nullable": False})]',
            ".. req:: A\n   :id: REQ_1\n\n.. spec:: B\n   :id: SPEC_1\n\n"
            ".. spec:: C\n   :id: SPEC_2\n   :x: given\n",
        )
    ],
    indirect=True,
)
def test_a_field_not_nullable_on_one_type(test_app: Any) -> None:
    """A field a need type makes not nullable, with no default, must be set on its
    needs; on the needs of every other type it may be unset."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:7: WARNING: Need could not be created: Field 'x' is not "
        "nullable, but no value or default was given. [needs.create_need]",
    ]
    needs = _needs(app)
    assert {k: v["x"] for k, v in needs.items()} == {
        "REQ_1": None,
        "SPEC_2": "given",
    }


EXTEND_INDEX = """\
.. req:: A
   :id: REQ_1
   :x: one

.. spec:: B
   :id: SPEC_1
   :x: two

.. needextend:: type in ["req", "spec"]
   :x: extended
   :status: done
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True}}',
            '[("spec", "x", {"allow_extend": False})]',
            EXTEND_INDEX,
        )
    ],
    indirect=True,
)
def test_a_field_one_type_does_not_extend(test_app: Any) -> None:
    """A needextend matching needs of two types sets a field on the needs of the
    type that allows it to be extended; on the needs of a type that does not, it
    warns once per need and leaves the field, and still applies its other options."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:12: WARNING: Option 'x' does not support extend operations "
        "on need type 'spec'; need 'SPEC_1' is not extended by it. [needs.needextend]",
    ]
    needs = _needs(app)
    assert {k: (v["x"], v["status"]) for k, v in needs.items()} == {
        "REQ_1": ("extended", "done"),
        "SPEC_1": ("two", "done"),
    }


VALIDATION_INDEX = """\
.. req:: A
   :id: REQ_1
   :x: QM

.. spec:: B
   :id: SPEC_1
   :x: QM

.. spec:: C
   :id: SPEC_2
   :x: A

.. impl:: D
   :id: IMPL_1
   :x: QM
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True,'
            ' "schema": {"type": "string", "enum": ["A", "B", "QM"]}}}',
            '[("spec", "x", {"schema": {"type": "string", "enum": ["A", "B"]}})]',
            VALIDATION_INDEX,
        )
    ],
    indirect=True,
)
def test_a_schema_one_type_narrows(
    test_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A schema a need type narrows validates its needs; the needs of every other
    type are validated against the field's schema. One validator is compiled for
    every type, and one for each type that declares fields anew."""
    compiles = _count_compiles(monkeypatch)
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "ERROR: Need 'SPEC_1' has schema violations:\n"
        "  Severity:       violation\n"
        "  Field:          x\n"
        "  Need path:      SPEC_1\n"
        "  Schema path:    fields > schema > properties > x > enum\n"
        '  Schema message: "QM" is not one of "A" or "B" '
        "[sn_schema_violation.field_fail]",
    ]
    # the union validator is reused by identity for every type without overlays, so a
    # cache keyed wrongly shows here, not in the plain project's count of one
    assert compiles == [2]


RESOLVE_INDEX = """\
.. req:: A
   :id: REQ_1
   :x: [[copy("y")]]

.. spec:: B
   :id: SPEC_1
   :x: [[copy("y")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            '{"x": {"nullable": True}, "y": {"nullable": True}}',
            '[("spec", "x", {"nullable": False, "default": FieldLiteralValue("d")})]',
            RESOLVE_INDEX,
        )
    ],
    indirect=True,
)
def test_a_computed_value_in_the_field_of_its_type(test_app: Any) -> None:
    """A dynamic function that computes nothing leaves a nullable field unset; in a
    field the need's type makes not nullable it is refused, and the field holds its
    empty value."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:8: WARNING: Error while resolving dynamic values for field "
        "'x', of need 'SPEC_1': dynamic function value <class 'NoneType'> is not of "
        "type 'string' [needs.dynamic_function]",
    ]
    needs = _needs(app)
    assert {k: v["x"] for k, v in needs.items()} == {
        "REQ_1": None,
        "SPEC_1": "",
    }


DERIVED_INDEX = """\
.. req:: A
   :id: REQ_1

.. spec:: B
   :id: SPEC_1
   :c1: [[copy("c2")]]
   :c2: [[copy("c1")]]

.. spec:: C
   :id: SPEC_2
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _overlay_project(
            "{"
            '"ox": {"nullable": True, "schema": {"type": "string", "minLength": 1},'
            ' "derive_by_type": {"req": {"kind": "copy", "field": "title"}}},'
            ' "oy": {"schema": {"type": "string"}, "default": "D",'
            ' "derive_by_type": {"req": {"kind": "copy", "field": "title"}}},'
            ' "c1": {"nullable": True}, "c2": {"nullable": True}'
            "}",
            '[("spec", "ox", {"nullable": False}),'
            ' ("spec", "oy", {"default": FieldLiteralValue("S")}),'
            ' ("spec", "c1", {"nullable": False, "default": FieldLiteralValue("cd")}),'
            ' ("spec", "c2", {"nullable": False, "default": FieldLiteralValue("cd")})]',
            DERIVED_INDEX,
        )
    ],
    indirect=True,
)
def test_derived_values_of_one_type(test_app: Any) -> None:
    """A field derived on another type holds, on the needs of a type, the value its
    type declares: its empty value where the type makes it not nullable (and so no
    schema violation: it holds no value yet), the type's default; a call on a cycle
    leaves a field the type makes not nullable empty, not unset."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:7: WARNING: dynamic function 'copy' for option 'c1' is on "
        "a cycle: 'c1' on need 'SPEC_1' and 'c2' on need 'SPEC_1'; the field is left "
        "empty [needs.derive_cycle]",
        "<srcdir>/index.rst:7: WARNING: dynamic function 'copy' for option 'c2' is on "
        "a cycle: 'c1' on need 'SPEC_1' and 'c2' on need 'SPEC_1'; the field is left "
        "empty [needs.derive_cycle]",
    ]
    needs = _needs(app)
    assert {k: (v["ox"], v["oy"], v["c1"], v["c2"]) for k, v in needs.items()} == {
        "REQ_1": ("A", "A", None, None),
        "SPEC_1": ("", "S", "", ""),
        "SPEC_2": ("", "S", "cd", "cd"),
    }


LATE_CONF = """\
from sphinx_needs.data import SphinxNeedsData

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"x": {"nullable": True}}


def _late(app, env, docnames):
    schema = SphinxNeedsData(env).get_schema()
    schema.for_type("req")
    schema.add_type_overlay("spec", schema.declaration("x"))


def setup(app):
    app.connect("env-before-read-docs", _late, priority=600)
"""


@pytest.mark.parametrize(
    "test_app", [_project(LATE_CONF, ".. req:: A\n   :id: REQ_1\n")], indirect=True
)
def test_an_overlay_after_the_first_read_fails_the_build(test_app: Any) -> None:
    """The schema freezes once it is read for a need type: an overlay registered
    after that is refused, and the build stops, naming why."""
    app = test_app
    with pytest.raises(ExtensionError) as exc_info:
        app.build()
    cause = exc_info.value.orig_exc
    assert isinstance(cause, TypeError)
    assert str(cause) == (
        "The fields schema cannot be changed: it has been read for a need type. "
        "Register fields and need type overlays before the first need is created: "
        "in create_schema, or in an env-before-read-docs handler that runs before "
        "any need is created."
    )
