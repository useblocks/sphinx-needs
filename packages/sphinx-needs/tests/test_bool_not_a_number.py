"""A boolean is not an ``integer`` or a ``number`` (#2533).

``bool`` is a subclass of ``int`` in Python, but not in JSON or TOML: ``true`` in an
``integer`` or ``number`` field, or as an item of an array of either, is a value of the
wrong type on every route that gives a field a typed value, as a string that is not a
number is.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from sphinx_needs.api import add_need, create_need
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import InvalidNeedException
from sphinx_needs.need_item import NeedItemSourceExternal
from sphinx_needs_testkit import build_warnings

FIELDS = """\
needs_fields = {
    "effort": {"schema": {"type": "integer"}, "nullable": True%(extra)s},
    "ratio": {"schema": {"type": "number"}, "nullable": True%(extra)s},
    "sizes": {
        "schema": {"type": "array", "items": {"type": "integer"}},
        "nullable": True%(extra)s,
    },
}
"""

TOML_FIELDS = """\
[needs.fields.effort]
schema = { type = "integer" }
nullable = true
%(effort)s
[needs.fields.ratio]
schema = { type = "number" }
nullable = true
%(ratio)s
[needs.fields.sizes]
schema = { type = "array", items = { type = "integer" } }
nullable = true
%(sizes)s
"""

#: one wrong value per record, and a record of right values beside them: an integer is
#: still a number, and an array of integers still an array of integers
RECORDS = {
    "REQ_E": {"id": "REQ_E", "type": "req", "title": "E", "effort": True},
    "REQ_R": {"id": "REQ_R", "type": "req", "title": "R", "ratio": False},
    "REQ_S": {"id": "REQ_S", "type": "req", "title": "S", "sizes": [1, True]},
    "REQ_OK": {
        "id": "REQ_OK",
        "type": "req",
        "title": "OK",
        "effort": 3,
        "ratio": 1,
        "sizes": [1, 2],
    },
}


def _conf(extra: str = "", rest: str = "") -> str:
    return 'extensions = ["sphinx_needs"]\n' + FIELDS % {"extra": extra} + rest


def _write(tmp_path: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")


def _needs_warnings(app) -> list[str]:
    """The build's sphinx-needs warnings and errors, Sphinx's own left out."""
    return [
        w
        for w in build_warnings(app)
        if "[needs." in w or "[sn_schema" in w or "ERROR" in w
    ]


def _values(app) -> dict[str, dict[str, object]]:
    needs = SphinxNeedsData(app.env).get_needs_mutable()
    return {
        nid: {k: need[k] for k in ("effort", "ratio", "sizes")}
        for nid, need in sorted(needs.items())
    }


IMPORT_JSON = json.dumps(
    {"current_version": "1.0", "versions": {"1.0": {"needs": RECORDS}}}
)

OK_VALUES = {"effort": 3, "ratio": 1.0, "sizes": [1, 2]}


@pytest.mark.parametrize("coercion", [True, False], ids=["coercion", "no-coercion"])
def test_an_imported_record_holding_a_boolean_is_not_imported(
    make_app, tmp_path, coercion
):
    """``needimport``: refused like a record holding any other wrong-typed value."""
    option = "" if coercion else "   :allow_type_coercion: false\n"
    _write(
        tmp_path,
        {
            "conf.py": _conf(),
            "index.rst": f"Import\n======\n\n.. needimport:: imp.json\n{option}",
            "imp.json": IMPORT_JSON,
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert _needs_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Need 'REQ_E' could not be imported: Field "
        "'effort' is invalid: Invalid value for field 'effort': True "
        "[needs.import_need]",
        "<srcdir>/index.rst:4: WARNING: Need 'REQ_R' could not be imported: Field "
        "'ratio' is invalid: Invalid value for field 'ratio': False [needs.import_need]",
        "<srcdir>/index.rst:4: WARNING: Need 'REQ_S' could not be imported: Field "
        "'sizes' is invalid: Invalid value for field 'sizes': [1, True] "
        "[needs.import_need]",
    ]
    assert _values(app) == {"REQ_OK": OK_VALUES}


@pytest.mark.parametrize("coercion", [True, False], ids=["coercion", "no-coercion"])
def test_an_external_record_holding_a_boolean_is_not_added(
    make_app, tmp_path, coercion
):
    """``needs_external_needs``: refused with the source's own warning."""
    source = {
        "base_url": "http://example.org",
        "json_path": "imp.json",
        "allow_type_coercion": coercion,
    }
    _write(
        tmp_path,
        {
            "conf.py": _conf(rest=f"needs_external_needs = [{source!r}]\n"),
            "index.rst": "External\n========\n",
            "imp.json": IMPORT_JSON,
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert _needs_warnings(app) == [
        "WARNING: External need 'REQ_E' in 'imp.json' could not be added: Field "
        "'effort' is invalid: Invalid value for field 'effort': True "
        "[needs.load_external_need]",
        "WARNING: External need 'REQ_R' in 'imp.json' could not be added: Field "
        "'ratio' is invalid: Invalid value for field 'ratio': False "
        "[needs.load_external_need]",
        "WARNING: External need 'REQ_S' in 'imp.json' could not be added: Field "
        "'sizes' is invalid: Invalid value for field 'sizes': [1, True] "
        "[needs.load_external_need]",
    ]
    assert _values(app) == {"REQ_OK": OK_VALUES}


WRONG = [
    (
        "effort",
        True,
        "Field 'effort' is invalid: Invalid value for field 'effort': True",
    ),
    (
        "ratio",
        False,
        "Field 'ratio' is invalid: Invalid value for field 'ratio': False",
    ),
    (
        "sizes",
        [1, True],
        "Field 'sizes' is invalid: Invalid value for field 'sizes': [1, True]",
    ),
]


def _api_app(make_app, tmp_path, validation: bool):
    _write(
        tmp_path,
        {
            "conf.py": _conf(rest=f"needs_schema_validation_enabled = {validation}\n"),
            "index.rst": "API\n===\n",
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    return app


@pytest.mark.parametrize(
    "validation", [True, False], ids=["validation", "no-validation"]
)
@pytest.mark.parametrize("coercion", [True, False], ids=["coercion", "no-coercion"])
def test_create_need_refuses_a_boolean_and_records_nothing(
    make_app, tmp_path, validation, coercion
):
    """``create_need`` raises the ``InvalidNeedException`` it raises for any other
    wrong-typed value, before anything is recorded -- whether or not the schema
    validation would have reported the value later."""
    app = _api_app(make_app, tmp_path, validation)
    source = NeedItemSourceExternal(url="http://example.org/x.html")
    for name, value, message in WRONG:
        with pytest.raises(InvalidNeedException) as err:
            create_need(
                app,
                None,
                source,
                "req",
                "T",
                id="REQ_X",
                fields={name: value},
                allow_type_coercion=coercion,
            )
        assert (err.value.type, err.value.message) == ("invalid_field_value", message)
        assert "REQ_X" not in SphinxNeedsData(app.env).get_needs_mutable()
    need, _ = create_need(
        app,
        None,
        source,
        "req",
        "T",
        id="REQ_OK",
        fields={"effort": 3, "ratio": 1, "sizes": [1, 2]},
        allow_type_coercion=coercion,
    )
    assert {k: need[k] for k in OK_VALUES} == OK_VALUES


@pytest.mark.parametrize(
    "validation", [True, False], ids=["validation", "no-validation"]
)
@pytest.mark.parametrize("coercion", [True, False], ids=["coercion", "no-coercion"])
def test_add_need_refuses_a_boolean_and_records_nothing(
    make_app, tmp_path, validation, coercion
):
    """The deprecated ``add_need`` refuses alike: it is the same creation path."""
    app = _api_app(make_app, tmp_path, validation)
    for name, value, message in WRONG:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(InvalidNeedException) as err:
                add_need(
                    app,
                    None,
                    need_type="req",
                    title="T",
                    id="REQ_X",
                    is_external=True,
                    external_url="http://example.org/x.html",
                    allow_type_coercion=coercion,
                    **{name: value},
                )
        assert (err.value.type, err.value.message) == ("invalid_field_value", message)
        assert "REQ_X" not in SphinxNeedsData(app.env).get_needs_mutable()


ONE_NEED = "One\n===\n\n.. req:: One\n   :id: REQ_1\n"


@pytest.mark.parametrize(
    "files,config_name",
    [
        pytest.param(
            {
                "conf.py": _conf(
                    rest='needs_fields["effort"]["default"] = True\n'
                    'needs_fields["ratio"]["default"] = False\n'
                    'needs_fields["sizes"]["default"] = [1, True]\n'
                ),
            },
            "['default']",
            id="conf.py-default",
        ),
        pytest.param(
            {
                "conf.py": 'extensions = ["sphinx_needs"]\n'
                'needs_from_toml = "ubproject.toml"\n',
                "ubproject.toml": TOML_FIELDS
                % {
                    "effort": "predicates = [[\"id == 'REQ_1'\", true]]",
                    "ratio": "predicates = [[\"id == 'REQ_1'\", false]]",
                    "sizes": "predicates = [[\"id == 'REQ_1'\", [1, true]]]",
                },
            },
            "['predicates']",
            id="ubproject.toml-predicates",
        ),
    ],
)
def test_a_boolean_default_is_reported_and_ignored(
    make_app, tmp_path, files, config_name
):
    """A ``default`` or ``predicates`` value of the wrong type is a ``needs.config``
    warning, and the field keeps no default."""
    _write(tmp_path, {**files, "index.rst": ONE_NEED})
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert _needs_warnings(app) == [
        f"WARNING: needs_fields['effort']{config_name} value is incorrect: Invalid "
        "value for field 'effort': True [needs.config]",
        f"WARNING: needs_fields['ratio']{config_name} value is incorrect: Invalid "
        "value for field 'ratio': False [needs.config]",
        f"WARNING: needs_fields['sizes']{config_name} value is incorrect: Invalid "
        "value for field 'sizes': [1, True] [needs.config]",
    ]
    assert _values(app) == {"REQ_1": {"effort": None, "ratio": None, "sizes": None}}


def test_a_boolean_type_default_is_a_type_conflict(make_app, tmp_path):
    """A need type's ``default`` of the wrong type: the entry is ignored, reported as
    ``needs.type_conflict`` (as any other wrong-typed default of a type is)."""
    _write(
        tmp_path,
        {
            "conf.py": 'extensions = ["sphinx_needs"]\n'
            'needs_from_toml = "ubproject.toml"\n',
            "ubproject.toml": TOML_FIELDS
            % {"effort": "", "ratio": "", "sizes": ""}
            + '\n[needs.types.req]\ntitle = "Req"\nprefix = "R_"\n'
            "[needs.types.req.fields.effort]\ndefault = true\n"
            "[needs.types.req.fields.ratio]\ndefault = false\n"
            "[needs.types.req.fields.sizes]\ndefault = [1, true]\n",
            "index.rst": ONE_NEED,
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert _needs_warnings(app) == [
        "WARNING: needs_types['req'].fields['effort'] sets a 'default' that cannot be "
        "used: Invalid value for field 'effort': True; the entry is ignored "
        "[needs.type_conflict]",
        "WARNING: needs_types['req'].fields['ratio'] sets a 'default' that cannot be "
        "used: Invalid value for field 'ratio': False; the entry is ignored "
        "[needs.type_conflict]",
        "WARNING: needs_types['req'].fields['sizes'] sets a 'default' that cannot be "
        "used: Invalid value for field 'sizes': [1, True]; the entry is ignored "
        "[needs.type_conflict]",
    ]
    assert _values(app) == {"REQ_1": {"effort": None, "ratio": None, "sizes": None}}


DF_FUNCS = """
def ret_true(app, need, needs):
    return True

def ret_false(app, need, needs):
    return False

def ret_list(app, need, needs):
    return [1, True]

needs_functions = [ret_true, ret_false, ret_list]
"""

THREE_NEEDS = """\
Computed
========

.. req:: E
   :id: REQ_E
   :effort: %(effort)s

.. req:: R
   :id: REQ_R
   :ratio: %(ratio)s

.. req:: S
   :id: REQ_S
   :sizes: %(sizes)s
"""


def test_a_dynamic_function_returning_a_boolean_is_reported(make_app, tmp_path):
    """A ``[[…]]`` returning a boolean for such a field (or a list with a boolean for
    an array of integers): ``needs.dynamic_function``, and the field stays empty."""
    _write(
        tmp_path,
        {
            "conf.py": _conf(', "parse_dynamic_functions": True', DF_FUNCS),
            "index.rst": THREE_NEEDS
            % {
                "effort": "[[ret_true()]]",
                "ratio": "[[ret_false()]]",
                "sizes": "[[ret_list()]]",
            },
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert _needs_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
        "'effort', of need 'REQ_E': dynamic function value <class 'bool'> is not of "
        "type 'integer' [needs.dynamic_function]",
        "<srcdir>/index.rst:8: WARNING: Error while resolving dynamic values for field "
        "'ratio', of need 'REQ_R': dynamic function value <class 'bool'> is not of "
        "type 'number' [needs.dynamic_function]",
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field "
        "'sizes', of need 'REQ_S': dynamic function value <class 'list'> is not of "
        "type 'array' or item type 'integer' [needs.dynamic_function]",
    ]
    assert _values(app) == {
        "REQ_E": {"effort": None, "ratio": None, "sizes": None},
        "REQ_R": {"effort": None, "ratio": None, "sizes": None},
        "REQ_S": {"effort": None, "ratio": None, "sizes": None},
    }


def test_variant_data_holding_a_boolean_is_reported(make_app, tmp_path):
    """``<{ var.… }>`` naming a boolean, as the field's value or as one item of an
    array of integers: ``needs.dynamic_function``."""
    _write(
        tmp_path,
        {
            "conf.py": _conf(
                ', "parse_variants": True',
                'needs_variant_data = {"t": True, "f": False}\n',
            ),
            "index.rst": THREE_NEEDS
            % {
                "effort": "<{ var.t }>",
                "ratio": "<{ var.f }>",
                "sizes": "1, <{ var.t }>",
            },
        },
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert sorted(_needs_warnings(app)) == [
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field "
        "'sizes', of need 'REQ_S': variant data value <class 'bool'> is not of type "
        "'array' or item type 'integer' [needs.dynamic_function]",
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
        "'effort', of need 'REQ_E': variant data value <class 'bool'> is not of type "
        "'integer' [needs.dynamic_function]",
        "<srcdir>/index.rst:8: WARNING: Error while resolving dynamic values for field "
        "'ratio', of need 'REQ_R': variant data value <class 'bool'> is not of type "
        "'number' [needs.dynamic_function]",
    ]
    values = _values(app)
    assert values["REQ_E"]["effort"] is None
    assert values["REQ_R"]["ratio"] is None
    assert values["REQ_S"]["sizes"] == [1]
