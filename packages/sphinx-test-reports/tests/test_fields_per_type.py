"""Each field is declared on the need types that carry it (#2372).

The extension registers its fields with ``add_field(..., types=[...])``: a field of a
test case on the test-case type alone, a counter on the test-file and test-suite types,
the report path and ``tr_extra_options`` on all three. A project's own need type that
sets one (a ``test`` need carrying ``case_name``, to join on it) names the field in its
``needs_types`` entry, which declares it there too; without the entry the value is
reported and ignored.
"""

import json
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

#: the need types declaring each field, by the default directive names
DECLARING = {
    "suites": {"testfile"},
    "cases": {"testfile", "testsuite"},
    "errors": {"testfile", "testsuite"},
    "suite": {"testsuite", "testcase"},
    "case": {"testcase"},
    "case_name": {"testcase"},
    "case_parameter": {"testcase"},
    "classname": {"testcase"},
    "time": {"testcase"},
    "result": {"testcase"},
    "result_text": {"testcase"},
    "remote_url": {"testcase"},
    "file": {"testfile", "testsuite", "testcase"},
    "case_file": {"testcase"},
    "case_line": {"testcase"},
    "owner": {"testfile", "testsuite", "testcase"},
}


def _needs(app):
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/fields_per_type"}],
    indirect=True,
)
def test_each_field_is_declared_on_the_types_that_carry_it(test_app):
    app = test_app
    app.build()
    schema = SphinxNeedsData(app.env).get_schema()
    assert {name: schema.declaring_types(name) for name in DECLARING} == DECLARING
    # the project's `test` does not declare `case_name`: its value is ignored
    assert [w for w in build_warnings(app) if "undeclared_for_type" in w] == [
        "<srcdir>/index.rst:4: WARNING: Field 'case_name' is not declared on need "
        "type 'test' and cannot be set in need 'T_00001'; the value 'test_pass' is "
        "ignored [needs.undeclared_for_type]"
    ]
    needs = _needs(app)
    assert needs["T_00001"]["case_name"] is None
    # the extension's own needs keep every value they set
    cases = [n for n in needs.values() if n["type"] == "testcase"]
    assert {n["case_file"] for n in cases} >= {"src/math_test.cc"}
    assert needs["FPT_TF_1"]["cases"] == 5


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/fields_per_type_entry"}],
    indirect=True,
)
def test_a_project_type_naming_the_field_declares_it_too(test_app):
    """``needs_types`` naming ``case_name`` on ``test``: the project's need keeps its
    value, and the type joins the declaring ones."""
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if "undeclared_for_type" in w] == []
    schema = SphinxNeedsData(app.env).get_schema()
    assert schema.declaring_types("case_name") == {"testcase", "test"}
    assert _needs(app)["T_00001"]["case_name"] == "test_pass"
