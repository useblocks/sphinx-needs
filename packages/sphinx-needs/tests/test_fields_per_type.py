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
from sphinx.util.parallel import parallel_available

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
# A need type declares a field anew in its ``needs_types`` entry (``fields``), and
# closes the fields it does not declare (``closed``), which ``create_schema`` resolves:
# the configuration is the one place a field is declared for a type, and the schema is
# complete, and frozen, once ``create_schema`` has built it.

#: the default need types but ``need``, ``spec`` declaring its fields anew
DECLARING_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {fields}
needs_types = {{
    "req": {{"title": "Requirement", "prefix": "R_"}},
    "spec": {{"title": "Specification", "prefix": "S_", "fields": {spec}}},
    "impl": {{"title": "Implementation", "prefix": "I_"}},
    "test": {{"title": "Test Case", "prefix": "T_"}},
}}
"""


def _declaring_project(fields: str, spec: str, index: str) -> dict[str, Any]:
    return _project(DECLARING_CONF.format(fields=fields, spec=spec), index)


#: the default need types but ``need``, ``spec`` closed: it declares no field
CLOSED_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {fields}
needs_links = {{"blocks": {{"incoming": "is blocked by", "outgoing": "blocks"}}}}
needs_types = {{
    "req": {{"title": "Requirement", "prefix": "R_"}},
    "spec": {{"title": "Specification", "prefix": "S_", "closed": True}},
    "impl": {{"title": "Implementation", "prefix": "I_"}},
    "test": {{"title": "Test Case", "prefix": "T_"}},
}}
{extra}
"""


def _closed_project(
    fields: str, index: str, extra: str = "", **files: str
) -> dict[str, Any]:
    project = _project(CLOSED_CONF.format(fields=fields, extra=extra), index)
    project["files"].extend((Path(name), text) for name, text in files.items())
    return project


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


def _undeclared(value: object, field: str = "x", what: str = "Field") -> str:
    return (
        f"{what} {field!r} is not declared on need type 'spec', which is closed, and "
        f"cannot be set in a need; the value {value!r} is ignored "
        "[needs.undeclared_for_type]"
    )


@pytest.mark.parametrize(
    "test_app",
    [_closed_project('{"x": {"nullable": True}}', ADMISSION_INDEX, SERVICE_CONF)],
    indirect=True,
)
def test_a_field_closed_on_one_type(test_app: Any) -> None:
    """A field a closed need type does not declare is refused on its needs, from a
    directive, ``list2need`` and ``needservice``, and set on the needs of every other
    type."""
    app = test_app
    app.build()
    # the service class in conf.py cannot be cached, which Sphinx reports in words
    # that differ between its versions
    warnings = [w for w in build_warnings(app) if "cannot cache unpick" not in w]
    assert warnings == [
        f"<srcdir>/index.rst:8: WARNING: {_undeclared('two')}",
        f"<srcdir>/index.rst:17: WARNING: {_undeclared('four')}",
        f"<srcdir>/index.rst:19: WARNING: {_undeclared('six')}",
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


IMPORTED = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_1": {
                    "id": "IMP_1",
                    "type": "spec",
                    "title": "Imported",
                    "x": "imported",
                    "blocks": ["REQ_1"],
                },
                "IMP_2": {"id": "IMP_2", "type": "req", "title": "Kept", "x": "kept"},
            }
        }
    },
}

EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "E_1": {"id": "E_1", "type": "spec", "title": "External", "x": "ext"},
                "E_2": {"id": "E_2", "type": "req", "title": "Kept", "x": "ext-kept"},
            }
        }
    },
}

EXTERNAL_CONF = """
import os

needs_external_needs = [
    {
        "base_url": "http://example.org",
        "json_path": os.path.join(os.path.dirname(__file__), "external.json"),
        "id_prefix": "EXT_",
    }
]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _closed_project(
            '{"x": {"nullable": True}}',
            ".. req:: A\n   :id: REQ_1\n\n.. needimport:: imported.json\n",
            EXTERNAL_CONF,
            **{
                "imported.json": json.dumps(IMPORTED),
                "external.json": json.dumps(EXTERNAL),
            },
        )
    ],
    indirect=True,
)
def test_a_field_closed_on_one_type_from_outside(test_app: Any) -> None:
    """A need from outside the project's sources -- imported, or external -- keeps
    only the fields its type declares: a value of a field or link type a closed type
    does not declare is dropped, one warning each."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        f"WARNING: {_undeclared('ext')}",
        f"<srcdir>/index.rst:7: WARNING: {_undeclared('imported')}",
        "<srcdir>/index.rst:7: WARNING: "
        + _undeclared(["REQ_1"], "blocks", "Link type"),
    ]
    # an external need is not written to needs.json
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {k: (v["x"], v["blocks"]) for k, v in needs.items()} == {
        "REQ_1": (None, []),
        "IMP_1": (None, []),
        "IMP_2": ("kept", []),
        "EXT_E_1": (None, []),
        "EXT_E_2": ("ext-kept", []),
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
        _declaring_project(
            '{"x": {"nullable": True, "default": "global"}}',
            '{"x": {"default": "spec"}, "status": {"default": "spec-open"}}',
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
        _declaring_project(
            '{"x": {"nullable": True}}',
            '{"x": {"nullable": False}}',
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

.. spec:: D
   :id: SPEC_3

.. spec:: B
   :id: SPEC_1

.. spec:: C
   :id: SPEC_2

.. needextend:: type in ["req", "spec"]
   :x: extended
   :status: done

.. needextend:: type == "spec"
   :-x:
"""


@pytest.mark.parametrize(
    "test_app",
    [_closed_project('{"x": {"nullable": True}}', EXTEND_INDEX)],
    indirect=True,
)
def test_a_field_one_type_does_not_extend(test_app: Any) -> None:
    """A needextend matching needs of two types sets a field on the needs of the
    type that declares it; on the needs of a closed type that does not, it warns once
    for the type, naming its needs, and leaves the field, and still applies its other
    options. Deleting the field is refused the same."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:17: WARNING: Option 'x' does not support extend operations "
        "on need type 'spec'; it does not extend 3 needs (SPEC_1, SPEC_2, SPEC_3). "
        "[needs.needextend]",
        "<srcdir>/index.rst:21: WARNING: Option '-x' does not support extend "
        "operations on need type 'spec'; it does not extend 3 needs (SPEC_1, SPEC_2, "
        "SPEC_3). [needs.needextend]",
    ]
    needs = _needs(app)
    assert {k: (v["x"], v["status"]) for k, v in needs.items()} == {
        "REQ_1": ("extended", "done"),
        "SPEC_3": (None, "done"),
        "SPEC_1": (None, "done"),
        "SPEC_2": (None, "done"),
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
        _declaring_project(
            '{"x": {"nullable": True,'
            ' "schema": {"type": "string", "enum": ["A", "B", "QM"]}}}',
            '{"x": {"schema": {"enum": ["A", "B"]}}}',
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
        _declaring_project(
            '{"x": {"nullable": True}, "y": {"nullable": True}}',
            '{"x": {"nullable": False, "default": "d"}}',
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
        _declaring_project(
            "{"
            '"ox": {"nullable": True, "schema": {"type": "string", "minLength": 1},'
            ' "derive_by_type": {"req": {"kind": "copy", "field": "title"}}},'
            ' "oy": {"schema": {"type": "string"}, "default": "D",'
            ' "derive_by_type": {"req": {"kind": "copy", "field": "title"}}},'
            ' "c1": {"nullable": True}, "c2": {"nullable": True}'
            "}",
            '{"ox": {"nullable": False}, "oy": {"default": "S"},'
            ' "c1": {"nullable": False, "default": "cd"},'
            ' "c2": {"nullable": False, "default": "cd"}}',
            DERIVED_INDEX,
        )
    ],
    indirect=True,
)
def test_derived_values_of_one_type(test_app: Any) -> None:
    """A field derived on another type holds, on the needs of a type, the value its
    type declares: its empty value where the type makes it not nullable (and so no
    schema violation: it holds no value yet); a type does not declare a default of a
    derived field, so its needs hold the field's; a call on a cycle leaves a field the
    type makes not nullable empty, not unset."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['spec'].fields['oy'] sets 'default', but 'oy' is derived "
        "(by need type): a need type declares only its description, schema and "
        "nullable; the entry is ignored [needs.type_conflict]",
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
        "SPEC_1": ("", "D", "", ""),
        "SPEC_2": ("", "D", "cd", "cd"),
    }


LATE_CONF = """\
from sphinx_needs.data import SphinxNeedsData

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"x": {"nullable": True}}


def _late(app, env, docnames):
    schema = SphinxNeedsData(env).get_schema()
    schema.add_type_overlay("spec", schema.global_declaration("x"))


def setup(app):
    app.connect("env-before-read-docs", _late, priority=600)
"""


@pytest.mark.parametrize(
    "test_app", [_project(LATE_CONF, ".. req:: A\n   :id: REQ_1\n")], indirect=True
)
def test_an_overlay_after_create_schema_fails_the_build(test_app: Any) -> None:
    """The schema is frozen once ``create_schema`` has built it: an overlay registered
    after that is refused and the build stops, naming why."""
    app = test_app
    with pytest.raises(ExtensionError) as exc_info:
        app.build()
    cause = exc_info.value.orig_exc
    assert isinstance(cause, TypeError)
    assert str(cause) == FREEZE


FREEZE = (
    "The fields schema cannot be changed once it is complete: create_schema freezes "
    "the schema it builds, and the first read through for_type freezes one built by "
    "hand. Declare fields, link types and need types in the configuration, before "
    "the schema is built."
)

PARALLEL_CONF = """\
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.needs_schema import FieldSchema

extensions = ["sphinx_needs"]


def _late(app, env):
    SphinxNeedsData(env).get_schema().add_extra_field(
        FieldSchema(name="late", schema={"type": "string"}, nullable=True)
    )


def setup(app):
    app.connect("env-updated", _late)
    return {"parallel_read_safe": True}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "parallel": 4,
            "files": [
                (Path("conf.py"), PARALLEL_CONF),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. toctree::\n\n"
                    + "".join(f"   d{i}\n" for i in range(1, 11)),
                ),
                *(
                    (
                        Path(f"d{i}.rst"),
                        f"D{i}\n===\n\n.. req:: need {i}\n   :id: REQ_{i:03}\n",
                    )
                    for i in range(1, 11)
                ),
            ],
        }
    ],
    indirect=True,
)
@pytest.mark.skipif(not parallel_available, reason="Parallel execution not supported")
def test_a_parallel_build_has_the_schema_frozen(test_app: Any) -> None:
    """The schema is frozen in every process once built: a change at
    ``env-updated`` stops the build."""
    app = test_app
    with pytest.raises(ExtensionError) as exc_info:
        app.build()
    cause = exc_info.value.orig_exc
    assert isinstance(cause, TypeError)
    assert str(cause) == FREEZE


@pytest.mark.parametrize(
    "test_app", [_project("extensions = ['sphinx_needs']\n", "")], indirect=True
)
def test_the_schema_knows_the_configured_need_types(test_app: Any) -> None:
    """``create_schema`` tells the schema every configured need type, a service's
    included, so an overlay names one of them."""
    app = test_app
    app.build()
    assert SphinxNeedsData(app.env).get_schema().need_types == frozenset(
        {"req", "spec", "impl", "test", "need", "issue", "pr", "commit"}
    )
